# 📊 SWE-Agent Benchmarking & Evaluation Suite

This framework enables empirical, quantitative evaluation of the Autonomous SWE Agent across multiple repositories and tasks to generate verified, resume-ready metrics.

---

## 🎯 Target Metrics Collected

| Metric | What is Measured | Formula |
| :--- | :--- | :--- |
| **Repositories Tested** | Number of distinct codebases evaluated | `len(unique(repos))` |
| **Tasks Executed** | Total end-to-end coding tasks run | Total task count |
| **Task Success Rate** | Tasks where code was fixed and verified | `(successful_tasks / total) * 100` |
| **Test Pass Rate** | Tasks where pytest passed in Docker sandbox | `(passed_tests / total) * 100` |
| **PR Creation Rate** | Tasks where Git branch pushed & PR created/updated | `(prs_created / total) * 100` |
| **CI Success Rate** | GitHub Actions CI workflow pass rate on remote PRs | `(ci_passed / ci_runs) * 100` |
| **Self-Healing Rate** | Failures automatically resolved via reflection loop | `(self_healed / multi_attempt) * 100` |
| **Execution Time** | Average turnaround time per task | `mean(duration_seconds)` |

---

## 🚀 How to Run the Benchmark

### 1. Run all queued tasks:
```bash
python -m benchmark.runner
```

### 2. Run a specific task by ID:
```bash
python -m benchmark.runner --task calc-01-factorial
```

### 3. Run tasks for a specific repository:
```bash
python -m benchmark.runner --repo simple_calculator
```

### 4. Limit the number of tasks:
```bash
python -m benchmark.runner --limit 5
```

---

## 📋 Generating Resume Reports

After running the benchmark, generate your updated report and resume bullet points anytime with:
```bash
python -m benchmark.report
```

Raw experimental data is saved to `benchmark/results/evaluation_<timestamp>.json` and summarized in `benchmark/results/summary.md`.

---

## ➕ Adding New Repositories and Tasks

Edit `benchmark/tasks.json` to add new test tasks:
```json
{
  "id": "my-task-01",
  "repo": "https://github.com/your-username/your-repo.git",
  "name": "Task Title",
  "category": "Bug Fix / Feature Addition / Refactoring",
  "task": "Multi-line instructions here..."
}
```

