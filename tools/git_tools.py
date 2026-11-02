import os
import subprocess
import requests

def create_branch(repo_path: str, branch_name: str = "swe-agent/task-fix"):
    """
    Creates a new branch or switches to an existing branch.
    If the branch already exists, it checks out the existing branch cleanly.
    """
    try:
        # 1. Create and switch to new branch (git checkout -b <branch_name>)
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        print(f"🌿 Branch '{branch_name}' created successfully.")

    except subprocess.CalledProcessError:
        # 2. If branch already exists (checkout -b fails), switch directly to it
        subprocess.run(
            ["git", "checkout", branch_name],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        print(f"🔄 Switched to existing branch '{branch_name}'.")

    return branch_name


def get_git_diff(repo_path: str) -> str:
    """Returns the unstaged and staged git diff against HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            errors="replace"
        )
        return result.stdout.strip()

    except subprocess.CalledProcessError as e:
        print(f"❌ Error checking diff: {e.stderr}")
        return ""


def commit_changes(repo_path: str, commit_message: str = "Agent auto-fix"):
    """Stages tracked modifications and creates a git commit."""
    try:
        # Step 1: Stage all modified tracked files
        subprocess.run(
            ["git", "add", "-u"],
            cwd=repo_path,
            check=True,
            encoding="utf-8",
            errors="replace"
        )

        # Step 2: Also stage any new files that were created
        subprocess.run(
            ["git", "add", "."],
            cwd=repo_path,
            check=True,
            encoding="utf-8",
            errors="replace"
        )

        # Step 3: Create git commit with message
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        print(f"💾 Changes successfully committed: '{commit_message}'")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Error committing changes: {e.stderr}")
        return False


def push_to_github(repo_path: str, branch_name: str) -> bool:
    """Pushes the branch and its commits to remote GitHub repository."""
    try:
        token = os.getenv("GITHUB_TOKEN")
        remote_target = "origin"
        if token:
            res = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=repo_path, capture_output=True, text=True
            )
            raw_url = res.stdout.strip()
            if "github.com" in raw_url:
                clean = raw_url.split("@")[-1].replace("https://", "").replace("http://", "")
                remote_target = f"https://x-access-token:{token}@{clean}"

        subprocess.run(
            ["git", "push", "-u", remote_target, branch_name],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        print(f"🚀 Successfully pushed '{branch_name}' to GitHub!")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Error pushing to GitHub: {e.stderr}")
        return False


def create_pull_request(repo_owner: str, repo_name: str, branch_name: str, title: str, description: str) -> str:
    """Creates a Pull Request on GitHub for the specified branch."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN missing!")
        return ""

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"

    try:
        # Check repository's default branch
        repo_res = requests.get(base_url, headers=headers, timeout=30)
        repo_res.raise_for_status()
        default_branch = repo_res.json().get("default_branch", "main")

        # Check whether an open PR already exists for this branch
        response = requests.get(
            f"{base_url}/pulls",
            headers=headers,
            params={
                "head": f"{repo_owner}:{branch_name}",
                "base": default_branch,
                "state": "open"
            },
            timeout=30
        )
        response.raise_for_status()
        existing_prs = response.json()

        if existing_prs:
            pr_url = existing_prs[0]["html_url"]
            print(f"🔄 Existing PR found: {pr_url}")
            return pr_url

        # Create PR only if no open PR exists
        response = requests.post(
            f"{base_url}/pulls",
            headers=headers,
            json={
                "title": title,
                "body": description,
                "head": branch_name,
                "base": default_branch
            },
            timeout=30
        )

        response.raise_for_status()
        pr_url = response.json()["html_url"]
        print(f"✅ PR created: {pr_url}")
        return pr_url

    except requests.RequestException as e:
        print(f"❌ GitHub PR error: {e}")
        return ""


def check_pr_ci_status(repo_owner, repo_name, pr_number):
    """Checks the status of GitHub Actions check-runs on the PR commit."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN missing!")
        return "error"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        pr_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}"
        pr_response = requests.get(pr_url, headers=headers, timeout=10)

        if pr_response.status_code != 200:
            print(f"❌ GitHub PR API error: {pr_response.status_code}")
            return "error"

        commit_sha = pr_response.json().get("head", {}).get("sha")
        if not commit_sha:
            return "error"

        checks_url = (
            f"https://api.github.com/repos/{repo_owner}/{repo_name}"
            f"/commits/{commit_sha}/check-runs"
        )
        checks_response = requests.get(
            checks_url, headers=headers, timeout=10
        )

        if checks_response.status_code != 200:
            print(f"❌ GitHub Checks API error: {checks_response.status_code}")
            return "error"

        check_runs = checks_response.json().get("check_runs", [])

        if not check_runs:
            return "no_ci"

        for run in check_runs:
            if run["status"] != "completed":
                return "pending"
            if run.get("conclusion") in [
                "failure", "timed_out", "action_required", "cancelled"
            ]:
                return "failure"

        return "success"

    except requests.RequestException as e:
        print(f"❌ GitHub network error: {e}")
        return "error"


def get_failed_ci_logs(repo_owner: str, repo_name: str, pr_number: int) -> str:
    """Fetches log output from the first failed GitHub Actions check run."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "ERROR: GITHUB_TOKEN missing."

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"

    try:
        pr_response = requests.get(
            f"{base_url}/pulls/{pr_number}",
            headers=headers, timeout=10
        )
        pr_response.raise_for_status()

        commit_sha = pr_response.json().get("head", {}).get("sha")
        if not commit_sha:
            return "ERROR: PR commit SHA missing."

        checks_response = requests.get(
            f"{base_url}/commits/{commit_sha}/check-runs",
            headers=headers, timeout=10
        )
        checks_response.raise_for_status()

        check_runs = checks_response.json().get("check_runs", [])
        failed_job_id = next(
            (
                run["id"] for run in check_runs
                if run.get("status") == "completed"
                and run.get("conclusion") in [
                    "failure", "timed_out", "action_required"
                ]
            ),
            None
        )

        if not failed_job_id:
            return "No failed jobs found."

        logs_response = requests.get(
            f"{base_url}/actions/jobs/{failed_job_id}/logs",
            headers=headers, timeout=20
        )
        logs_response.raise_for_status()

        logs = "\n".join(logs_response.text.splitlines()[-50:])
        return f"--- FAILED CI LOGS ---\n{logs[-2500:]}"

    except (requests.RequestException, ValueError, KeyError) as e:
        return f"ERROR: Could not fetch CI logs: {e}"
