from tools.test_tools import run_tests

def testing_agent(repo_path: str, target_tests: list[str] | None = None) -> str:
    """Executes the test suite on the specified repository path."""
    return run_tests(repo_path, target_tests=target_tests)
