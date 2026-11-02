
from langgraph.graph import END
from backend.graph import route_after_ci


def test_ci_success_stops():
    assert route_after_ci({
        "ci_status": "success",
        "ci_attempts": 0,
    }) == END


def test_ci_timeout_stops_without_debugging():
    assert route_after_ci({
        "ci_status": "timeout",
        "ci_attempts": 1,
    }) == END


def test_api_error_stops():
    assert route_after_ci({
        "ci_status": "error",
        "ci_attempts": 0,
    }) == END


def test_real_ci_failure_goes_to_debug():
    assert route_after_ci({
        "ci_status": "failure",
        "ci_attempts": 1,
        "ci_logs": "AssertionError: expected 5, got 4",
    }) == "debug"


def test_ci_log_fetch_error_stops():
    assert route_after_ci({
        "ci_status": "failure",
        "ci_attempts": 1,
        "ci_logs": "ERROR: Could not fetch CI logs",
    }) == END
