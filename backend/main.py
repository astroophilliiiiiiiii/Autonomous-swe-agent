import sys

# Windows terminal UTF-8 encoding fix (prevents UnicodeEncodeError on emojis)
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from tools.repo import clone_repo, list_directory
from tools.file_tools import read_file
from agents.file_selector import create_file_selector
from backend.llm import llm
from backend.graph import app
from backend.error_handler import handle_llm_exception

# ------------------------------- Input repo and task ---------------------------------
repo = input("GitHub Repository: ")

print("Task (Paste your multi-line task below. When done, type 'END' on a new line and press Enter):")
task_lines = []
while True:
    try:
        line = input()
        if line.strip() == "END":
            break
        task_lines.append(line)
    except EOFError:
        break

task = "\n".join(task_lines).strip()


repo_path = clone_repo(repo)
files = list_directory(repo_path)

file_selector = create_file_selector(llm)
try:
    result = file_selector.invoke({"task": task, "files": files})
except Exception as e:
    handle_llm_exception(e)
    sys.exit(1)

# Normalize file list from repository
normalized_repo_files = {f.replace("\\", "/"): f for f in files}

# Robust parsing of file selector response
relevant_files = []

# Strategy 1: Check each repo file against LLM output content
for norm_path, orig_path in normalized_repo_files.items():
    if norm_path.lower() in result.content.replace("\\", "/").lower():
        if orig_path not in relevant_files:
            relevant_files.append(orig_path)

# Strategy 2: Parse line-by-line in case of whitespace/bullets
if not relevant_files:
    for line in result.content.splitlines():
        cleaned = line.strip().strip("`'\"*-•0123456789. ").replace("\\", "/")
        for norm_path, orig_path in normalized_repo_files.items():
            if cleaned and (cleaned == norm_path or cleaned.endswith("/" + norm_path)):
                if orig_path not in relevant_files:
                    relevant_files.append(orig_path)

# Strategy 3: Fallback if LLM failed to select files - inspect task for mentioned file names
if not relevant_files:
    for norm_path, orig_path in normalized_repo_files.items():
        base_name = norm_path.split("/")[-1]
        if base_name in task and base_name not in ("__init__.py", ".gitignore"):
            if orig_path not in relevant_files:
                relevant_files.append(orig_path)

print(f"📂 Relevant files selected: {relevant_files}")

if not relevant_files:
    print("No relevant files found.")
    exit()

file_contents = {}
for file in relevant_files:
    full_path = repo_path / file
    try:
        file_contents[file] = read_file(str(full_path))
    except Exception as e:
        print(f"Could not read {file}: {e}")

# ---------------------------------------------- GRAPH -----------------------------------------------------
initial_state = {
    "repo_path": str(repo_path),
    "repo_url": repo,
    "repo_owner": "",
    "repo_name": "",
    "task": task,
    "file": relevant_files[0],
    "code": file_contents[relevant_files[0]],
    "file_contents": file_contents,
    "analysis": "",
    "test_result": "",
    "attempts": 0,
    "debug_result": "",
    "branch_name": "",  
    "summary": "",
    "pr_number": None,
    "ci_status": None,
    "ci_logs": None,
    "ci_attempts": 0,  
}

try:
    result = app.invoke(initial_state)
except Exception as e:
    # If the error was caused by an LLM call inside the graph nodes, format it clearly
    err_str = str(e).lower()
    if any(keyword in err_str for keyword in ("groq", "rate_limit", "rate limit", "context_length", "token", "429", "401", "404", "503")):
        handle_llm_exception(e)
        sys.exit(1)
    raise e

# ----------------------------------------------- FINAL SUMMARY --------------------------------------
print("\n--- Final AI Summary ---")

if result.get("ci_status") == "success":
    print("✅ Task Completed & Verified via GitHub Actions CI!")
    print(result.get("summary", ""))
elif result.get("test_result", "").startswith("TESTS PASSED:"):
    print("✅ Task Completed Successfully! Local tests passed.")
    print(result.get("summary", ""))
else:
    print("⚠️ Task NOT verified successfully.")
    print(f"Test Status: {result.get('test_result', 'No results')[:200]}")
    print(f"GitHub CI Status: {result.get('ci_status', 'unknown')}")
