import sys

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import re
import ast
import json
import time
import subprocess
import requests
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, START, END
from json_repair import repair_json

from backend.llm import llm
from backend.error_handler import handle_llm_exception
from agents.coding_agent import create_coding_agent
from agents.testing_agent import testing_agent
from agents.debug_agent import create_debug_agent
from agents.understand_agent import create_understand_agent
from tools.file_tools import write_file
from tools.git_tools import (
    create_branch,
    get_git_diff,
    commit_changes,
    push_to_github,
    create_pull_request,
    check_pr_ci_status,
    get_failed_ci_logs
)

class AgentState(TypedDict):
    repo_path: str                # Path to the cloned repository
    task: str                     # User requested task
    file: str                     # Primary file targeted for update
    code: str                     # Current code content of primary file
    analysis: str                 # Problem analysis from understand agent
    test_result: str              # Local pytest execution output
    attempts: int                 # Number of fix attempts executed
    debug_result: str             # Feedback from debug agent
    branch_name: str              # Working branch name
    repo_url: str                 # Cloned GitHub repository URL
    summary: str                  # Final execution summary
    pr_number: Optional[int]      # Pull Request number on GitHub
    ci_status: Optional[str]      # CI status: 'success', 'failure', 'pending', 'skipped'
    ci_logs: Optional[str]        # Failure logs from GitHub Actions CI
    repo_name : str               # Repository name
    repo_owner : str              # Repository owner/organization
    ci_attempts: int              # CI polling attempt count
    file_contents: dict[str, str] # Dictionary of file paths to their full content

# Fetch repository details from remote URL
def fetch_repo_details(state):
    repo_path = state["repo_path"]
    
    try:
        # Step 1: Run terminal git command to get the remote origin URL
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"], 
            cwd=repo_path, 
            capture_output=True, 
            text=True
        )
        git_url = result.stdout.strip()
        
        # Step 2: Parse owner and repo name from the URL
        if git_url:
            cleaned_url = git_url.strip().rstrip("/").removesuffix(".git")
            parts = cleaned_url.split("/")
            
            repo_owner = parts[-2]
            repo_name = parts[-1]
            
            state["repo_owner"] = repo_owner
            state["repo_name"] = repo_name
            state["repo_url"] = git_url
            
            print(f"✅ Successfully fetched -> Owner: {repo_owner} | Repo: {repo_name}")
        else:
            print("❌ Git remote origin URL not found. Was the repository cloned properly?")
            
    except Exception as e:
        print(f"❌ Error fetching repo details: {e}")
        
    return state

# Run local pytest suite
def testing_node(state):
    target_tests = []
    for path in state.get("file_contents", {}):
        norm = path.replace("\\", "/")
        base = norm.split("/")[-1]
        if base.endswith(".py") and (base.startswith("test_") or base.endswith("_test.py")):
            target_tests.append(norm)
    result = testing_agent(state["repo_path"], target_tests=target_tests or None)
    state["test_result"] = result
    return state

# Commit, push, and create pull request workflow
def summary_node(state):
    if not state.get("test_result", "").startswith("TESTS PASSED:"):
        print("⚠️ Tests not marked as passed. Commit and push skipped.")
        return state

    repo = state["repo_path"]
    branch = state["branch_name"]
    task = state["task"]
    
    # 1. 🔍 Diff Check
    diff_changes = get_git_diff(repo)
    if not diff_changes:
        print("ℹ️ No changes detected to commit. Working tree is clean.")
        state["summary"] = f"""
    ✅ Task Completed: Review / Verification Successful!

    🌿 Branch: {branch}
    🧪 Local Tests: Passed
    ℹ️ Status: Working tree clean. All tests pass and no code changes are needed.
    """
        return state
    
    # 2. 💾 Commit
    # Use only the first line of the task so commit messages / PR titles stay short
    first_line = next((l.strip() for l in task.splitlines() if l.strip()), "Automated change")
    if len(first_line) > 72:
        first_line = first_line[:69].rstrip() + "..."
    commit_msg = f"Auto-fix: {first_line}"
    commit_result = commit_changes(repo, commit_msg)
    if not commit_result:
        print("⚠️ Commit failed or working tree clean.")
        return state
    
    # 3. 🚀 Push
    push_result = push_to_github(repo, branch)
    if not push_result:
        print("⚠️ Push to GitHub failed. PR creation skipped.")
        state["summary"] = f"✅ Code fixed and committed locally on branch {branch}.\n⚠️ Push failed (check network or token permissions)."
        return state
    
    # 4. 🔗 Pull Request
    if state.get("pr_number"):
        print(f"🔄 PR #{state['pr_number']} already exists. Updated with new commit!")
        pr_link = f"https://github.com/{state['repo_owner']}/{state['repo_name']}/pull/{state['pr_number']}"
    else:
        pr_link = create_pull_request(
            repo_owner=state["repo_owner"],  
            repo_name=state["repo_name"],
            branch_name=branch,
            title=commit_msg,
            description=f"Fixed issue automatically.\n\nTask:\n{task}\n\nChanges:\n{diff_changes}"
        )
        if not pr_link:
            print("⚠️ Pull Request creation failed. Continuing with local summary.")
            pr_link = ""
        else:
            try:
                pr_number = int(pr_link.split("/")[-1])
                state["pr_number"] = pr_number
            except ValueError:
                print("Warning: Could not extract PR number from URL.")
    
    # 5. 📝 Final Summary
    final_summary = f"""
    ✅ Task Completed Successfully!

    🌿 Branch: {branch}
    💾 Commit: {commit_msg}
    🧪 Local Tests: Passed
    💾 GitHub CI: Pending
    🔗 PR Link: {pr_link if pr_link else 'Failed to create PR'}
    """
    
    state["summary"] = final_summary
    print(final_summary)
    return state

# Create working branch or checkout target PR branch if specified in task
def branch_node(state):
    state = fetch_repo_details(state)
    task = state.get("task", "")
    
    # Check if task requests updating an existing PR (e.g. "PR #2", "PR 2", "pull request 2")
    pr_match = re.search(r'(?:PR|pull request)\s*#?\s*(\d+)', task, re.IGNORECASE)
    if pr_match and state.get("repo_owner") and state.get("repo_name"):
        pr_num = int(pr_match.group(1))
        token = os.getenv("GITHUB_TOKEN")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"} if token else {}
        base_url = f"https://api.github.com/repos/{state['repo_owner']}/{state['repo_name']}/pulls/{pr_num}"
        try:
            resp = requests.get(base_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                head_ref = resp.json().get("head", {}).get("ref")
                if head_ref:
                    print(f"🎯 Target existing PR #{pr_num} branch detected: '{head_ref}'")
                    # Fetch origin and switch cleanly to the existing PR branch
                    subprocess.run(["git", "fetch", "origin", head_ref], cwd=state["repo_path"], capture_output=True, text=True)
                    checkout_res = subprocess.run(["git", "checkout", head_ref], cwd=state["repo_path"], capture_output=True, text=True)
                    if checkout_res.returncode != 0:
                        subprocess.run(["git", "checkout", "-b", head_ref, f"origin/{head_ref}"], cwd=state["repo_path"], capture_output=True, text=True)
                    subprocess.run(["git", "pull", "origin", head_ref], cwd=state["repo_path"], capture_output=True, text=True)
                    print(f"🔄 Switched to target PR #{pr_num} branch '{head_ref}'.")
                    state["branch_name"] = head_ref
                    state["pr_number"] = pr_num
                    return state
        except Exception as e:
            print(f"Warning checking existing PR #{pr_num}: {e}")

    branch_name = f"swe-agent/task-fix-{int(time.time())}"
    branch = create_branch(state["repo_path"], branch_name)
    state["branch_name"] = branch
    return state


def _truncate_cleanly(content: str, max_chars: int) -> str:
    """Truncates large file content cleanly at newline boundaries, keeping head and tail."""
    if len(content) <= max_chars:
        return content
    half = max_chars // 2
    head = content[:half]
    last_nl = head.rfind("\n")
    if last_nl > half // 2:
        head = head[:last_nl]
    tail = content[-half:]
    first_nl = tail.find("\n")
    if 0 <= first_nl < half // 2:
        tail = tail[first_nl + 1:]
    omitted = len(content) - len(head) - len(tail)
    return f"{head}\n\n# ... [TRUNCATED {omitted} CHARS — use 'append' or 'edits' for large files] ...\n\n{tail}"


def _invoke_with_tpm_retry(agent, payload: dict, max_retries: int = 2):
    """Retries LLM invocation briefly when hitting Groq's per-minute (TPM) window."""
    for attempt in range(max_retries + 1):
        try:
            return agent.invoke(payload)
        except Exception as exc:
            msg = str(exc).lower()
            is_tpm = ("tokens per minute" in msg or "tpm" in msg) and "tokens per day" not in msg
            if is_tpm and attempt < max_retries:
                wait_match = re.search(r"try again in\s+(\d+(?:\.\d+)?)s", msg)
                wait_sec = float(wait_match.group(1)) + 1.5 if wait_match else 10.0
                wait_sec = min(max(wait_sec, 3.0), 25.0)
                print(f"⏳ Groq TPM limit hit. Waiting {wait_sec:.1f}s before retry ({attempt + 1}/{max_retries})...")
                time.sleep(wait_sec)
                continue
            raise


def understand_node(state):
    agent = create_understand_agent(llm)
    files = state.get("file_contents") or {
        state["file"]: state["code"]
    }

    truncated_files = {}
    total_chars = 0
    for path, content in files.items():
        if total_chars >= 9000:
            break
        snippet = _truncate_cleanly(content, 4500)
        truncated_files[path] = snippet
        total_chars += len(snippet)

    try:
        result = _invoke_with_tpm_retry(agent, {
            "task": state["task"],
            "file_contents": json.dumps(truncated_files, ensure_ascii=False)
        })
    except Exception as exc:
        handle_llm_exception(exc)
        raise exc

    state["analysis"] = result.content
    return state


def clean_extracted_content(content: str) -> str:
    """Cleans up escape characters in extracted file content."""
    if r'\n' in content:
        content = content.replace(r'\n', '\n')
    if r'\t' in content:
        content = content.replace(r'\t', '\t')
    if r'\r' in content:
        content = content.replace(r'\r', '')
    if r'\"' in content:
        content = content.replace(r'\"', '"')
    if r"\'" in content:
        content = content.replace(r"\'", "'")
    if r'\\' in content:
        content = content.replace(r'\\', '\\')
    return content


def extract_file_updates_robust(raw_response: str, json_candidate: str = None):
    """
    Extract file updates using multiple fallback strategies:
    1. Perfect json.loads if JSON is valid.
    2. Regex extraction from raw text (handles unescaped quotes in Python code strings).
    3. json_repair fallback with recursive dict inspection.
    """
    if json_candidate is None:
        json_candidate = raw_response

    # Strategy 1: Perfect json.loads
    try:
        obj = json.loads(json_candidate)
        entries = []
        if isinstance(obj, dict):
            # Check if agent explicitly specified 0 files changed
            for k in ("files", "file", "updated_files", "modified_files"):
                if k in obj and isinstance(obj[k], list) and len(obj[k]) == 0:
                    return []
            for k in ("files", "file", "updated_files", "modified_files", "changes", "solution"):
                val = obj.get(k)
                if isinstance(val, list):
                    entries = val
                    break
                elif isinstance(val, dict):
                    entries = [val]
                    break
            if not entries and any(k in obj for k in ("path", "filename", "name")) and any(k in obj for k in ("content", "code")):
                entries = [obj]
        elif isinstance(obj, list):
            entries = obj

        valid = [
            e for e in entries
            if isinstance(e, dict)
            and any(k in e for k in ("path", "filename", "file_path", "file", "name"))
            and any(k in e for k in ("content", "code", "new_content", "updated_content", "source", "append", "edits"))
        ]
        if valid:
            return valid
    except Exception:
        pass

    # Strategy 2: Regex extraction from raw text (robust against unescaped quotes in code)
    regex_entries = []
    # Pattern 1: {"path": "...", "content": "..."}
    p1 = re.compile(
        r'\{\s*["\'](?:path|filename|file_path|file|name)["\']\s*:\s*["\']([^"\']+)["\']\s*,\s*["\'](?:content|code|new_content|updated_content|source)["\']\s*:\s*"(.*?)"\s*\}\s*(?=,\s*\{|\s*\]|\s*\})',
        re.DOTALL
    )
    for path, content in p1.findall(raw_response):
        regex_entries.append({"path": path, "content": clean_extracted_content(content)})

    # Pattern 2: {"content": "...", "path": "..."}
    if not regex_entries:
        p2 = re.compile(
            r'\{\s*["\'](?:content|code|new_content|updated_content|source)["\']\s*:\s*"(.*?)"\s*,\s*["\'](?:path|filename|file_path|file|name)["\']\s*:\s*["\']([^"\']+)["\']\s*\}\s*(?=,\s*\{|\s*\]|\s*\})',
            re.DOTALL
        )
        for content, path in p2.findall(raw_response):
            regex_entries.append({"path": path, "content": clean_extracted_content(content)})

    if regex_entries:
        return regex_entries

    # Strategy 3: json_repair fallback with recursive dict inspection
    try:
        repaired = repair_json(json_candidate, return_objects=True)
        if not isinstance(repaired, (dict, list)):
            repaired = repair_json(raw_response, return_objects=True)

        def find_file_entries(o):
            res = []
            if isinstance(o, dict):
                p = next((o[k] for k in ("path", "filename", "file_path", "file", "name") if k in o and isinstance(o[k], str)), None)
                c = next((o[k] for k in ("content", "code", "new_content", "updated_content", "source") if k in o and isinstance(o[k], str)), None)
                if p and c is not None:
                    res.append({"path": p, "content": c})
                else:
                    for v in o.values():
                        res.extend(find_file_entries(v))
            elif isinstance(o, list):
                for it in o:
                    res.extend(find_file_entries(it))
            return res

        repaired_entries = find_file_entries(repaired)
        if repaired_entries:
            return repaired_entries
    except Exception:
        pass

    return None


def coding_node(state):
    agent = create_coding_agent(llm)

    files = state.get("file_contents") or {
        state["file"]: state["code"]
    }

    truncated_files = {}
    total_chars = 0
    for path, content in files.items():
        if total_chars >= 12000:
            break
        snippet = _truncate_cleanly(content, 5000)
        truncated_files[path] = snippet
        total_chars += len(snippet)

    analysis_text = state.get("analysis", "")
    if len(analysis_text) > 2000:
        analysis_text = analysis_text[:2000]

    feedback_text = state.get("debug_result", "")
    if len(feedback_text) > 2000:
        feedback_text = feedback_text[-2000:]

    approved = {
        path.replace("\\", "/"): path
        for path in files
    }
    root = os.path.abspath(state["repo_path"])
    validated = {}
    syntax_errors = {}

    for syntax_try in range(2):
        try:
            result = _invoke_with_tpm_retry(agent, {
                "task": state["task"],
                "analysis": analysis_text,
                "file_contents": json.dumps(truncated_files, ensure_ascii=False),
                "error_feedback": feedback_text
            })
        except Exception as exc:
            handle_llm_exception(exc)
            raise exc

        raw_response = result.content.strip()

        # Step 1: Check for markdown code fences
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_response, re.DOTALL)
        if fence_match:
            json_candidate = fence_match.group(1).strip()
        else:
            json_candidate = raw_response

        # Step 2: Extract between outermost brackets ({...} or [...])
        start_brace = json_candidate.find("{")
        start_bracket = json_candidate.find("[")
        starts = [pos for pos in (start_brace, start_bracket) if pos != -1]
        if starts:
            first_start = min(starts)
            if first_start == start_brace:
                end = json_candidate.rfind("}")
            else:
                end = json_candidate.rfind("]")
            if end > first_start:
                json_candidate = json_candidate[first_start:end+1].strip()

        # Step 3: Extract updates using multi-strategy robust extractor
        updates = extract_file_updates_robust(raw_response, json_candidate)

        if updates == []:
            print("ℹ️ Coding agent determined no file modifications are needed.")
            state["debug_result"] = ""
            state["attempts"] = state.get("attempts", 0) + 1
            return state

        if not updates:
            print("❌ Raw LLM response received:")
            print(raw_response[:2000])
            raise ValueError("Coding agent returned invalid JSON: response must contain file updates.")

        validated = {}
        # Validate ALL updates before writing ANY files
        for item in updates:
            if not isinstance(item, dict):
                print(f"⚠️ Skipping non-dict file entry: {repr(item)[:200]}")
                continue

            # Extract path safely
            path = None
            for k in ("path", "filename", "file_path", "file", "name"):
                if k in item and isinstance(item[k], str):
                    path = item[k]
                    break

            if not isinstance(path, str):
                print(f"⚠️ Skipping file entry with missing path. Keys: {list(item.keys())}")
                continue

            path = path.replace("\\", "/")

            # Safety checks (apply to both existing and new files)
            if path.startswith("/") or ".." in path.split("/"):
                raise ValueError(f"Unsafe file path: {path}")

            if path in validated:
                raise ValueError(f"Duplicate file update: {path}")

            full_path = os.path.abspath(os.path.join(root, path))

            if os.path.commonpath([root, full_path]) != root:
                raise ValueError(f"Path escapes repository: {path}")

            # Extract content or apply incremental append / edits on existing file
            content = None
            if isinstance(item.get("append"), str) and path in approved:
                base_text = files[approved[path]].rstrip()
                content = f"{base_text}\n\n\n{item['append'].lstrip()}\n"
            elif isinstance(item.get("edits"), list) and path in approved:
                base_text = files[approved[path]]
                for edit in item["edits"]:
                    if not isinstance(edit, dict):
                        continue
                    old_snip = edit.get("old", "")
                    new_snip = edit.get("new", "")
                    if not isinstance(old_snip, str) or not isinstance(new_snip, str):
                        continue
                    if old_snip == "":
                        base_text = f"{base_text.rstrip()}\n\n\n{new_snip.lstrip()}\n"
                    elif old_snip in base_text:
                        base_text = base_text.replace(old_snip, new_snip, 1)
                content = base_text
            else:
                for k in ("content", "code", "new_content", "updated_content", "source"):
                    if k in item and isinstance(item[k], str):
                        content = item[k]
                        break

            if not isinstance(content, str):
                print(f"⚠️ Skipping file entry with missing content/append/edits. Keys: {list(item.keys())}")
                continue

            validated[path] = content

        if not validated:
            print("❌ Raw LLM response (first 2000 chars):")
            print(raw_response[:2000])
            raise ValueError("Coding agent returned no valid file updates. Check LLM output above.")

        syntax_errors = {}
        for path, content in validated.items():
            if path in approved and len(files[approved[path]]) > 4000 and len(content) < len(files[approved[path]]) * 0.4:
                syntax_errors[path] = (
                    f"returned content shrank large existing file from {len(files[approved[path]])} "
                    f"to {len(content)} chars — use 'append' or 'edits' instead of rewriting the whole file"
                )
                continue
            if path.endswith(".py"):
                try:
                    ast.parse(content)
                except SyntaxError as syn_err:
                    syntax_errors[path] = f"line {syn_err.lineno}: {syn_err.msg}"

        if not syntax_errors:
            break

        if syntax_try == 0:
            err_summary = "; ".join(f"{p} ({msg})" for p, msg in syntax_errors.items())
            print(f"⚠️ Generated Python syntax error in {err_summary}. Retrying generation...")
            feedback_text = (
                f"SYNTAX ERROR in your previous output: {err_summary}. "
                "Output complete, valid JSON with syntactically valid Python code "
                "(do not truncate the file or use JS '+' string concatenation).\n\n"
                + feedback_text
            )[:2000]
            time.sleep(3)

    # Write files only after all validation succeeds
    for path, content in validated.items():
        full_path = os.path.abspath(os.path.join(root, path))
        if path not in approved:
            if os.path.isfile(full_path):
                print(f"📄 Updating existing repo file: {path}")
            else:
                print(f"📄 New file will be created: {path}")
        if path in approved:
            original_path = approved[path]
        else:
            original_path = path  # new file — use as-is
        write_file(os.path.join(root, original_path), content)
        # Do not overwrite cached file_contents with syntactically broken Python
        if path not in syntax_errors:
            files[original_path] = content

    state["file_contents"] = files

    if state["file"] in files:
        state["code"] = files[state["file"]]

    state["debug_result"] = ""
    state["attempts"] = state.get("attempts", 0) + 1

    print(f"Updated {len(validated)} file(s) successfully.")
    return state


def _load_referenced_repo_files(
    repo_path: str,
    files: dict[str, str],
    *texts: str,
    max_added: int = 3,
) -> dict[str, str]:
    """Load existing repo files mentioned in error logs or debug analysis if not already loaded."""
    if not repo_path:
        return files

    root = os.path.abspath(repo_path)
    known = {p.replace("\\", "/").lstrip("./") for p in files}
    pattern = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:py|js|ts|tsx|jsx|json|yml|yaml|toml)")
    added = 0

    for text in texts:
        if not text or added >= max_added:
            break
        for match in pattern.findall(text):
            rel = match.replace("\\", "/").lstrip("./")
            if not rel or rel in known or rel.startswith("/") or ".." in rel.split("/"):
                continue
            full_path = os.path.abspath(os.path.join(root, rel))
            if os.path.commonpath([root, full_path]) != root or not os.path.isfile(full_path):
                continue
            try:
                files[rel] = read_file(full_path)
                known.add(rel)
                added += 1
                print(f"📥 Loaded referenced repo file for fix loop: {rel}")
                if added >= max_added:
                    break
            except Exception:
                continue

    return files


def debug_node(state):
    agent = create_debug_agent(llm)
    files = dict(state.get("file_contents") or {
        state["file"]: state["code"]
    })

    truncated_files = {}
    total_chars = 0
    for path, content in files.items():
        if total_chars >= 10000:
            break
        snippet = _truncate_cleanly(content, 4500)
        truncated_files[path] = snippet
        total_chars += len(snippet)

    error = state.get("ci_logs") or state.get("test_result", "")
    if len(error) > 3000:
        error = error[-3000:]
    time.sleep(3)

    try:
        result = _invoke_with_tpm_retry(agent, {
            "task": state["task"],
            "code": json.dumps(truncated_files, ensure_ascii=False),
            "test_result": error
        })
    except Exception as exc:
        handle_llm_exception(exc)
        raise exc

    state["file_contents"] = _load_referenced_repo_files(
        state.get("repo_path", ""),
        files,
        error,
        result.content,
    )
    state["debug_result"] = result.content
    print(f"\n🐛 Debug Analysis:\n{result.content[:500]}...\n")
    return state


def check_result(state):
    result = state.get("test_result", "")

    if result.startswith("TESTS PASSED:"):
        return "done"

    if result.startswith("ERROR:"):
        print(f"❌ Infrastructure / Docker error detected: {result[:200]}")
        return "failed"

    if state.get("attempts", 0) >= 3:
        print("❌ Maximum fix attempts reached.")
        return "failed"

    print("⚠️ Tests failed. Sending to debug.")
    return "fix"


def ci_cd_node(state: AgentState):
    print("\n--- ⏳ CI/CD NODE: Waiting for GitHub Actions ---")
    
    repo_owner = state.get("repo_owner")  
    repo_name = state.get("repo_name")
    pr_number = state.get("pr_number")
    
    if not pr_number:
        return {"ci_status": "skipped", "ci_logs": "No PR number found in state."}

    max_attempts = 12
    wait_time = 10
    no_ci_count = 0

    status = "pending"
    
    for attempt in range(max_attempts):
        status = check_pr_ci_status(repo_owner, repo_name, pr_number)

        if status == "error":
            return {
                "ci_status": "error",
                "ci_logs": "GitHub API/network error. Do not attempt code debugging."
            }
        
        if status == "no_ci":
            no_ci_count += 1
            if no_ci_count >= 2:
                print("ℹ️ No GitHub Actions CI workflow configured on this repo. Skipping CI wait.")
                status = "skipped"
                break
            time.sleep(5)
            continue

        if status != "pending":
            break
            
        print(f"[{attempt+1}/{max_attempts}] CI is still running... waiting {wait_time} seconds.")
        time.sleep(wait_time)

    if status == "success":
        print("✅ CI Passed Successfully!")
        updated_summary = state.get("summary", "").replace("💾 GitHub CI: Pending", "💾 GitHub CI: Passed ✅")
        return {
            "ci_status": "success", 
            "ci_logs": None,
            "summary": updated_summary
        }
    elif status == "skipped":
        updated_summary = state.get("summary", "").replace("💾 GitHub CI: Pending", "💾 GitHub CI: Not Configured (Skipped)")
        return {
            "ci_status": "skipped",
            "ci_logs": None,
            "summary": updated_summary
        }
    elif status == "failure":
        print("❌ CI Failed! Fetching error logs...")
        logs = get_failed_ci_logs(repo_owner, repo_name, pr_number)
        updated_summary = state.get("summary", "").replace("💾 GitHub CI: Pending", "💾 GitHub CI: Failed ❌")
        return {
            "ci_status": "failure",
            "ci_logs": logs,
            "ci_attempts": state.get("ci_attempts", 0) + 1,
            "summary": updated_summary
        }
    else:
        return {
            "ci_status": "timeout",
            "ci_logs": "CI took too long or crashed.",
            "ci_attempts": state.get("ci_attempts", 0) + 1
        }


def route_after_ci(state: AgentState):
    status = state.get("ci_status")
    attempts = state.get("ci_attempts", 0)
    logs = state.get("ci_logs") or ""

    if status == "success":
        print("✅ ROUTER: CI Passed! Workflow complete.")
        return END

    if status in ("skipped", "error", "timeout"):
        print(f"⚠️ CI status: {status}. Stopping safely.")
        return END

    if status == "failure" and logs.startswith("ERROR:"):
        print("⚠️ CI logs could not be fetched. Stopping safely.")
        return END

    if status == "failure":
        if attempts >= 3:
            print("❌ CI retry limit reached. Stopping workflow.")
            return END

        print(f"⚠️ CI failed. Sending logs to debug (attempt {attempts}/3).")
        return "debug"

    print(f"❌ Unexpected CI status: {status}. Stopping safely.")
    return END


#------------------------------------------GRAPH-----------------------------------------------------------
graph = StateGraph(AgentState)

# 1. Register all nodes
graph.add_node("coding", coding_node)
graph.add_node("testing", testing_node)
graph.add_node("debug", debug_node)
graph.add_node("understand", understand_node)
graph.add_node("branch", branch_node)
graph.add_node("summary", summary_node) 
graph.add_node("ci_cd", ci_cd_node)

# 2. Main workflow edges
graph.add_edge(START, "branch")
graph.add_edge("branch", "understand")
graph.add_edge("understand", "coding")
graph.add_edge("coding", "testing")

# 3. Local testing checks
graph.add_conditional_edges("testing", check_result, { "fix": "debug", "done": "summary", "failed": END } )
graph.add_edge("debug", "coding")

# 4. CI/CD flow edges --after creating the pr 
graph.add_edge("summary", "ci_cd")

graph.add_conditional_edges(
    "ci_cd",
    route_after_ci,
    {
        END: END,
        "debug": "debug"
    }
)

app = graph.compile()
