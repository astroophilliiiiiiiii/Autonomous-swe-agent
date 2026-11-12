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


def filter_candidate_files(files: list[str], task: str, max_files: int = 120) -> list[str]:
    """
    Pre-filters repository files for large codebases so the file-selector LLM prompt
    stays within token limits. Preserves exact path/filename matches and keyword hits.
    """
    if len(files) <= max_files:
        return files

    import re
    task_lower = task.lower()
    # Extract meaningful tokens (>= 3 chars) from the task
    tokens = set(re.findall(r"[a-zA-Z0-9_]{3,}", task_lower))
    stopwords = {"the", "and", "for", "with", "that", "this", "from", "into", "add", "fix", "all", "run", "test", "tests", "file", "files", "create", "commit", "push", "github", "pytest", "ensure", "pass"}
    keywords = [t for t in tokens if t not in stopwords]

    scored = []
    for f in files:
        norm = f.replace("\\", "/").lower()
        score = 0
        # Strong boost if exact relative path or basename is mentioned in task
        basename = norm.split("/")[-1]
        if norm in task_lower:
            score += 100
        elif basename in task_lower and basename not in ("__init__.py", "readme.md"):
            score += 50

        for kw in keywords:
            if kw in norm:
                score += 10

        # Prefer Python source/test files over docs/assets
        if norm.endswith(".py"):
            score += 2
        if score > 0 or norm.endswith(".py"):
            scored.append((score, f))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [f for _, f in scored[:max_files]]
