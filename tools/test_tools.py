import subprocess
import os
import sys

def is_docker_available() -> bool:
    """Quick check whether Docker daemon is active and responsive."""
    try:
        res = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=3
        )
        return res.returncode == 0
    except Exception:
        return False


SANDBOX_IMAGE = "swe-agent-env"


def is_sandbox_image_built() -> bool:
    """Checks whether the sandbox Docker image has been built locally."""
    try:
        res = subprocess.run(
            ["docker", "image", "inspect", SANDBOX_IMAGE],
            capture_output=True,
            text=True,
            timeout=10
        )
        return res.returncode == 0
    except Exception:
        return False


def _count_test_files(repo_path: str) -> int:
    """Counts pytest test files in the repository to detect large suites."""
    count = 0
    ignored = {".git", "__pycache__", "venv", "node_modules"}
    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ignored]
        for fn in filenames:
            if fn.endswith(".py") and (fn.startswith("test_") or fn.endswith("_test.py")):
                count += 1
                if count > 25:
                    return count
    return count


def run_tests(repo_path: str, target_tests: list[str] | None = None) -> str:
    """
    Runs tests on the target repository.
    Installs repository dependencies when missing and executes pytest.
    For large repositories (> 25 test files), scopes execution to target_tests when available.
    Uses Docker container sandbox if Docker daemon is active.
    Falls back to host Python pytest environment if Docker is unavailable.
    """
    abs_repo_path = os.path.abspath(repo_path)

    scoped_targets = []
    if target_tests and _count_test_files(abs_repo_path) > 25:
        for t in target_tests:
            norm_t = t.replace("\\", "/")
            if os.path.isfile(os.path.join(abs_repo_path, norm_t)):
                scoped_targets.append(norm_t)
        if scoped_targets:
            print(f"🎯 Large repository detected — running scoped tests: {scoped_targets}")

    # 1. Use Docker sandbox if available
    docker_ready = is_docker_available()
    if docker_ready and not is_sandbox_image_built():
        print(f"⚠️ Docker image '{SANDBOX_IMAGE}' not found. Build it with: docker build -t {SANDBOX_IMAGE} .")
        docker_ready = False

    if docker_ready:
        container_name = f"swe_runner_{os.getpid()}"
        target_arg = " ".join(scoped_targets) if scoped_targets else ""
        test_script = (
            "if [ -f requirements.txt ]; then pip install --no-cache-dir -q -r requirements.txt; fi; "
            "if [ -f requirements-dev.txt ]; then pip install --no-cache-dir -q -r requirements-dev.txt; fi; "
            "if [ -f pyproject.toml ] && [ ! -f requirements.txt ]; then pip install --no-cache-dir -q -e .; fi; "
            f"python -m pytest -v -o cache_dir=/tmp/.pytest_cache {target_arg}".strip()
        )
        docker_cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--cpus=2.0",
            "--memory=1024m",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{abs_repo_path}:/app/workspace/repo",
            "-w", "/app/workspace/repo",
            SANDBOX_IMAGE,
            "sh", "-c", test_script
        ]

        try:
            result = subprocess.run(
                docker_cmd, 
                capture_output=True, 
                text=True, 
                timeout=180
            )
            output = result.stdout + "\n" + result.stderr

            if result.returncode == 0:
                return f"TESTS PASSED:\n{output}"
            else:
                return f"TESTS FAILED:\n{output}"

        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
            return "ERROR: Execution timed out (180s limit reached)."
        except Exception as e:
            return f"ERROR: Execution failed due to: {str(e)}"

    # 2. Safe fallback to local host Python pytest
    print("⚠️ Docker daemon not active. Running pytest in host Python environment...")
    try:
        req_file = os.path.join(abs_repo_path, "requirements.txt")
        req_dev_file = os.path.join(abs_repo_path, "requirements-dev.txt")

        test_env = os.environ.copy()
        src_path = os.path.join(abs_repo_path, "src")
        extra_paths = [abs_repo_path]
        if os.path.isdir(src_path):
            extra_paths.append(src_path)
        existing_pypath = test_env.get("PYTHONPATH", "")
        test_env["PYTHONPATH"] = os.pathsep.join(extra_paths) + (os.pathsep + existing_pypath if existing_pypath else "")
        # Keep __pycache__ / .pytest_cache out of the target repo so they don't end up in the commit
        test_env["PYTHONDONTWRITEBYTECODE"] = "1"

        if os.path.isdir(os.path.join(abs_repo_path, "src", "_pytest")):
            test_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
            version_file = os.path.join(abs_repo_path, "src", "_pytest", "_version.py")
            if not os.path.isfile(version_file):
                scm_env = test_env.copy()
                scm_env["SETUPTOOLS_SCM_PRETEND_VERSION"] = "9.0.0"
                subprocess.run(
                    [sys.executable, "-m", "setuptools_scm", "--force-write-version-files"],
                    cwd=abs_repo_path,
                    env=scm_env,
                    capture_output=True,
                    text=True,
                    check=False,
                )

        django_runner = os.path.join(abs_repo_path, "tests", "runtests.py")
        if os.path.isfile(django_runner):
            django_labels = []
            for t in scoped_targets:
                norm = t.replace("\\", "/")
                if norm.startswith("tests/") and norm.endswith(".py"):
                    label = norm[len("tests/"):-3].replace("/", ".")
                    if label.endswith(".__init__"):
                        label = label[:-9]
                    django_labels.append(label)
            pytest_cmd = [sys.executable, "tests/runtests.py"] + django_labels
        else:
            pytest_cmd = [sys.executable, "-m", "pytest", "-v", "-p", "no:cacheprovider"] + scoped_targets
        result = subprocess.run(
            pytest_cmd,
            cwd=abs_repo_path,
            env=test_env,
            capture_output=True,
            text=True,
            timeout=180
        )
        output = result.stdout + "\n" + result.stderr

        # Only attempt pip install if pytest failed due to a missing module
        if result.returncode != 0 and ("ModuleNotFoundError" in output or "No module named" in output):
            if os.path.isfile(req_file):
                subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--only-binary=:all:", "-r", req_file], cwd=abs_repo_path, check=False)
            if os.path.isfile(req_dev_file):
                subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--only-binary=:all:", "-r", req_dev_file], cwd=abs_repo_path, check=False)
            result = subprocess.run(
                pytest_cmd,
                cwd=abs_repo_path,
                env=test_env,
                capture_output=True,
                text=True,
                timeout=180
            )
            output = result.stdout + "\n" + result.stderr

        if result.returncode == 0:
            return f"TESTS PASSED:\n{output}"
        else:
            return f"TESTS FAILED:\n{output}"

    except subprocess.TimeoutExpired:
        return "ERROR: Execution timed out (180s limit reached)."
    except Exception as e:
        return f"ERROR: Execution failed due to: {str(e)}"
