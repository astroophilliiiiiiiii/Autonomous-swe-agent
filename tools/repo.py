import os
import stat
import shutil
import subprocess
from pathlib import Path


def _remove_dir_safely(path: Path):
    """Safely removes a directory even if it contains read-only git files on Windows."""
    if not path.exists():
        return
    def _handle_remove_readonly(func, p, excinfo):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    shutil.rmtree(str(path), onerror=_handle_remove_readonly)


def clone_repo(repo_url: str, repo_path: str = "workspace/repo") -> Path:
    """
    Clones the specified GitHub repository to repo_path.
    If the repository already exists locally with the same remote URL, it resets and pulls the latest.
    If it points to a different repository, it removes the old directory and clones the new one.
    """
    repo_url = repo_url.strip()
    path = Path(repo_path)

    target_url = repo_url.rstrip("/").removesuffix(".git")

    if path.exists():
        current_url = ""
        try:
            res = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=str(path),
                capture_output=True,
                text=True
            )
            current_url = res.stdout.strip().rstrip("/").removesuffix(".git")
        except Exception:
            pass

        if current_url and current_url.lower() == target_url.lower():
            print("Repository already exists. Cleaning working tree and pulling latest...")
            try:
                subprocess.run(["git", "checkout", "master"], cwd=str(path), capture_output=True, text=True)
                subprocess.run(["git", "checkout", "main"], cwd=str(path), capture_output=True, text=True)
                subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=str(path), capture_output=True, text=True)
                subprocess.run(["git", "clean", "-fd"], cwd=str(path), capture_output=True, text=True)
                subprocess.run(["git", "pull"], cwd=str(path), capture_output=True, text=True)
                print("Repository updated and cleaned successfully.")
                return path
            except Exception as e:
                print(f"Warning during repository clean: {e}")
                return path
        else:
            print(f"Switching target repository to '{repo_url}'. Clearing existing workspace...")
            _remove_dir_safely(path)

    path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["git", "clone", repo_url, str(path)],
        check=True
    )

    print("Repository cloned successfully.")
    return path


def list_directory(repo_path: str) -> list[str]:
    """
    Recursively scans the repository directory and returns a list of relative file paths,
    excluding cache, version control, and virtual environment directories.
    """
    path = Path(repo_path)

    ignored_dirs = {".git", "__pycache__", "venv", "node_modules"}

    files = []

    for item in path.rglob("*"):
        relative_path = item.relative_to(path)
        if any(part in ignored_dirs for part in relative_path.parts):
            continue

        if item.is_file():
            files.append(str(item.relative_to(path)))

    return files
