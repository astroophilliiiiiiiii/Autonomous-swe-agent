from benchmark.report import calculate_metrics, generate_metrics_report

def test_calculate_metrics_empty():
    data = {"results": []}
    metrics = calculate_metrics(data)
    assert metrics["total_repos"] == 0
    assert metrics["total_tasks"] == 0
    assert metrics["task_success_rate"] == 0.0


def test_calculate_metrics_with_data():
    sample_data = {
        "timestamp": "2026-11-02T16:00:00",
        "results": [
            {
                "id": "t1",
                "repo": "https://github.com/a/r1",
                "task_success": True,
                "test_passed": True,
                "pr_created": True,
                "ci_status": "success",
                "ci_passed": True,
                "attempts": 1,
                "self_healed": False,
                "duration_seconds": 30.0,
            },
            {
                "id": "t2",
                "repo": "https://github.com/b/r2",
                "task_success": True,
                "test_passed": True,
                "pr_created": True,
                "ci_status": "skipped",
                "ci_passed": False,
                "attempts": 2,
                "self_healed": True,
                "duration_seconds": 50.0,
            },
        ],
    }

    metrics = calculate_metrics(sample_data)
    assert metrics["total_repos"] == 2
    assert metrics["total_tasks"] == 2
    assert metrics["task_success_rate"] == 100.0
    assert metrics["test_pass_rate"] == 100.0
    assert metrics["self_healing_rate"] == 100.0
    assert metrics["avg_execution_time"] == 40.0

    report = generate_metrics_report(sample_data)
    assert "Autonomous SWE-Agent Benchmark" in report
    assert "## 📝 Summary" in report

