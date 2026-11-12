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


def run_tests(repo_path: str) -> str:
    """
    Runs tests on the target repository.
    Installs repository dependencies (from requirements.txt / requirements-dev.txt)
    and executes pytest.
    Uses Docker container sandbox if Docker daemon is active.
    Falls back to host Python pytest environment if Docker is unavailable.
    """
    abs_repo_path = os.path.abspath(repo_path)

    # 1. Use Docker sandbox if available
    docker_ready = is_docker_available()
    if docker_ready and not is_sandbox_image_built():
        print(f"⚠️ Docker image '{SANDBOX_IMAGE}' not found. Build it with: docker build -t {SANDBOX_IMAGE} .")
        docker_ready = False

    if docker_ready:
        container_name = f"swe_runner_{os.getpid()}"
        test_script = (
            "if [ -f requirements.txt ]; then pip install --no-cache-dir -q -r requirements.txt; fi; "
            "if [ -f requirements-dev.txt ]; then pip install --no-cache-dir -q -r requirements-dev.txt; fi; "
            "if [ -f pyproject.toml ] && [ ! -f requirements.txt ]; then pip install --no-cache-dir -q -e .; fi; "
            "python -m pytest -v -o cache_dir=/tmp/.pytest_cache"
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
        setup_file = os.path.join(abs_repo_path, "setup.py")
        pyproject_file = os.path.join(abs_repo_path, "pyproject.toml")

        if os.path.isfile(req_file):
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", req_file], cwd=abs_repo_path, check=False)
        if os.path.isfile(req_dev_file):
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", req_dev_file], cwd=abs_repo_path, check=False)
        test_env = os.environ.copy()
        src_path = os.path.join(abs_repo_path, "src")
        extra_paths = [abs_repo_path]
        if os.path.isdir(src_path):
            extra_paths.append(src_path)
        existing_pypath = test_env.get("PYTHONPATH", "")
        test_env["PYTHONPATH"] = os.pathsep.join(extra_paths) + (os.pathsep + existing_pypath if existing_pypath else "")
        # Keep __pycache__ / .pytest_cache out of the target repo so they don't end up in the commit
        test_env["PYTHONDONTWRITEBYTECODE"] = "1"

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-v", "-p", "no:cacheprovider"],
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
