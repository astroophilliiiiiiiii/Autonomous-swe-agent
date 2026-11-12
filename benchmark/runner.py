import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Windows UTF-8 encoding fix
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from tools.repo import clone_repo, list_directory, filter_candidate_files
from tools.file_tools import read_file
from agents.file_selector import create_file_selector
from backend.llm import llm
from backend.graph import app
from backend.error_handler import handle_llm_exception


def execute_single_task(task_def: dict, workspace_dir: str = "workspace/repo") -> dict:
    """
    Executes a single benchmark task through the SWE-Agent pipeline
    and returns granular telemetry metrics.
    """
    task_id = task_def["id"]
    repo_url = task_def["repo"]
    task_prompt = task_def["task"]
    name = task_def.get("name", task_id)
    category = task_def.get("category", "General")

    print(f"\n{'='*75}")
    print(f"🚀 Running Task: [{task_id}] - {name}")
    print(f"📁 Repository: {repo_url}")
    print(f"🏷️  Category: {category}")
    print(f"{'='*75}\n")

    start_time = time.time()
    error_msg = None
    result = {}
    test_passed = False
    pr_created = False
    ci_passed = False
    self_healed = False
    attempts = 0

    try:
        repo_path = clone_repo(repo_url, workspace_dir)
        files = list_directory(repo_path)
        candidate_files = filter_candidate_files(files, task_prompt)

        file_selector = create_file_selector(llm)
        selector_res = file_selector.invoke({"task": task_prompt, "files": candidate_files})

        # Match relevant files
        normalized_repo_files = {f.replace("\\", "/"): f for f in files}
        relevant_files = []
        for norm_path, orig_path in normalized_repo_files.items():
            if norm_path.lower() in selector_res.content.replace("\\", "/").lower():
                if orig_path not in relevant_files:
                    relevant_files.append(orig_path)

        if not relevant_files:
            for norm_path, orig_path in normalized_repo_files.items():
                base_name = norm_path.split("/")[-1]
                if base_name in task_prompt and base_name not in ("__init__.py", ".gitignore"):
                    if orig_path not in relevant_files:
                        relevant_files.append(orig_path)

        if not relevant_files:
            # Fallback to first non-init python file
            for f in files:
                if f.endswith(".py") and "__init__" not in f:
                    relevant_files.append(f)
                    break

        print(f"📂 Relevant files selected: {relevant_files}")

        file_contents = {}
        for f in relevant_files:
            try:
                file_contents[f] = read_file(str(repo_path / f))
            except Exception as e:
                print(f"Could not read {f}: {e}")

        initial_state = {
            "repo_path": str(repo_path),
            "repo_url": repo_url,
            "repo_owner": "",
            "repo_name": "",
            "task": task_prompt,
            "file": relevant_files[0] if relevant_files else "main.py",
            "code": file_contents.get(relevant_files[0], "") if relevant_files else "",
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

        result = app.invoke(initial_state)

        test_result_str = result.get("test_result", "")
        test_passed = test_result_str.startswith("TESTS PASSED:")
        attempts = result.get("attempts", 0)

        # Self-healing: if tests failed on first attempt, but debug loop fixed it
        self_healed = (attempts > 1 and test_passed)

        summary_text = result.get("summary", "")
        pr_number = result.get("pr_number")
        pr_created = bool(pr_number or ("PR Link: https://" in summary_text and "Failed" not in summary_text))

        ci_status = result.get("ci_status")
        ci_passed = (ci_status == "success")

    except Exception as exc:
        error_msg = str(exc)
        print(f"❌ Error during task {task_id}: {exc}")
        handle_llm_exception(exc)

    end_time = time.time()
    duration = round(end_time - start_time, 2)

    # Success definition: tests passed and branch/PR or clean verification was achieved
    task_success = test_passed and error_msg is None

    outcome = {
        "id": task_id,
        "name": name,
        "repo": repo_url,
        "category": category,
        "duration_seconds": duration,
        "test_passed": test_passed,
        "attempts": attempts,
        "self_healed": self_healed,
        "pr_created": pr_created,
        "pr_number": result.get("pr_number"),
        "ci_status": result.get("ci_status"),
        "ci_passed": ci_passed,
        "task_success": task_success,
        "error": error_msg,
        "summary": result.get("summary", "")[:300] if result else "",
        "timestamp": datetime.now().isoformat()
    }

    status_icon = "✅ SUCCESS" if task_success else "❌ FAILED"
    print(f"\n{status_icon} | Duration: {duration}s | Tests Passed: {test_passed} | PR Created: {pr_created} | Self-Healed: {self_healed} | Attempts: {attempts}")
    return outcome


def run_benchmark(task_ids=None, repo_filter=None, limit=None, tasks_file=None):
    tasks_path = Path(tasks_file) if tasks_file else ROOT_DIR / "benchmark" / "tasks.json"
    if not tasks_path.exists():
        print(f"❌ Tasks file not found at {tasks_path}")
        return

    with open(tasks_path, "r", encoding="utf-8") as f:
        all_tasks = json.load(f)

    selected_tasks = all_tasks

    if task_ids:
        selected_tasks = [t for t in selected_tasks if t["id"] in task_ids]

    if repo_filter:
        selected_tasks = [t for t in selected_tasks if repo_filter.lower() in t["repo"].lower()]

    if limit and limit > 0:
        selected_tasks = selected_tasks[:limit]

    print(f"\n📊 Benchmark Suite Initialized: {len(selected_tasks)} task(s) queued.")

    results_dir = ROOT_DIR / "benchmark" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    suite_start = time.time()
    outcomes = []

    for idx, t in enumerate(selected_tasks, 1):
        print(f"\n[{idx}/{len(selected_tasks)}] Processing: {t['id']}")
        try:
            outcome = execute_single_task(t)
            outcomes.append(outcome)
        except KeyboardInterrupt:
            print("\n⚠️ Benchmark interrupted by user.")
            break
        except Exception as e:
            print(f"⚠️ Unexpected runner error on task {t['id']}: {e}")

    total_duration = round(time.time() - suite_start, 2)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = results_dir / f"evaluation_{timestamp_str}.json"
    latest_file = results_dir / "latest.json"

    benchmark_summary = {
        "timestamp": datetime.now().isoformat(),
        "total_tasks": len(outcomes),
        "total_duration_seconds": total_duration,
        "results": outcomes
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_summary, f, indent=2, ensure_ascii=False)

    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_summary, f, indent=2, ensure_ascii=False)

    print(f"\n📁 Raw experiment results saved to: {out_file}")
    print(f"📁 Updated {latest_file}")

    # Automatically generate markdown report
    from benchmark.report import generate_metrics_report
    report_text = generate_metrics_report(benchmark_summary)
    print("\n" + report_text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous SWE-Agent Benchmarking & Evaluation Suite")
    parser.add_argument("--task", "-t", nargs="+", help="Specific task ID(s) to run")
    parser.add_argument("--repo", "-r", help="Filter tasks by repo URL or substring")
    parser.add_argument("--limit", "-l", type=int, help="Limit number of tasks to execute")
    parser.add_argument("--tasks-file", help="Path to custom tasks.json file")

    args = parser.parse_args()
    run_benchmark(
        task_ids=args.task,
        repo_filter=args.repo,
        limit=args.limit,
        tasks_file=args.tasks_file
    )

