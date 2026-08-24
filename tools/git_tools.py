import subprocess

def create_branch(repo_path: str, branch_name: str = "swe-agent/task-fix"):

    """Creates a new git branch so we don't change the main branch directly."""

    try:
        # Terminal command: git checkout -b swe-agent/task-fix  -- create new branch and move to it 
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_path,          # Yeh command repo_path folder ke andar chalegi
            check=True,      # Command ka output/error screen pe print nhi, memory mein save karega--result.stdout
            capture_output=True,   # 📦 Store output/error instead of printing
            text=True              # 📝 Output as normal string, not bytes
        )
        print(f"🌿 Branch '{branch_name}' created successfully.")
        return branch_name
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error creating branch: {e.stderr}")
        return None


def get_git_diff(repo_path: str) -> str:
    """Dekhta hai ki code mein exactly kya-kya add ya remove hua hai."""
    try:
        # Terminal command: git diff
        result = subprocess.run(
            ["git", "diff"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip() # Terminal se nikle hue raw text output ko clean karke ek normal readable string banana! 🧹
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error checking diff: {e.stderr}")
        return ""


def commit_changes(repo_path: str, commit_message: str = "Agent auto-fix"):
    """Saare changes ko Git mein add aur commit karta hai."""
    try:
        # Step 1: git add . (Saare changes select karo)
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True) # koi error aaya toh save krlena
        
        # Step 2: git commit (Message ke saath save karo)
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"💾 Changes successfully committed: '{commit_message}'")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error committing changes: {e.stderr}")
        return False


def push_to_github(repo_path: str, branch_name: str) -> bool:
    """Nayi branch aur uske changes ko GitHub par upload karta hai."""
    try:
        # Terminal command: git push origin branch_name
        subprocess.run(
            ["git", "push", "origin", branch_name], # origin -- repo name , branch_name-- new branch created 
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"🚀 Successfully pushed '{branch_name}' to GitHub!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error pushing to GitHub: {e.stderr}")
        return False

import requests
import os




def create_pull_request(repo_owner: str, repo_name: str, branch_name: str, title: str, description: str) -> str:
    """GitHub API se automatic Pull Request (PR) banata hai."""
    
    # GitHub ko pata hona chahiye: "Ye request kis authorized user ki hai?"
    # identification + authentication/authorization
    token = os.getenv("GITHUB_TOKEN")  # for identifying that a authorised github user is creating a PR 
    if not token:
        print("❌ Error: GITHUB_TOKEN environment variable mein nahi mila!")
        return ""
        
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls" #KIS REPO mein PR banana hai?
    
    headers = {
        "Authorization": f"token {token}", #Ye request authorized user ki hai, ye raha uska token.” 🔐
        "Accept": "application/vnd.github.v3+json" #  RESPONSE kis format mein chahiye? 📦
    }
    
    # PR ki details
    data = {
        "title": title,       # PR ka naam/title kya hoga.
        "body": description,  #PR mein explanation/description kya hogi.
        "head": branch_name,  # Kis branch se changes aa rahe hain
        "base": "main"        # Kis branch mein changes bhejne hain
    }
    
    try:
        # GitHub, meri feature branch se main ke liye PR bana do
        response = requests.post(url, headers=headers, json=data) #Ye GitHub API ko POST request bhej raha hai.
        if response.status_code == 201: # 201 matlab "Created"
            pr_url = response.json().get("html_url") # PR ka actual GitHub link.
            print(f"🔗 Pull Request Created Successfully: {pr_url}")
            return pr_url
        else:
            print(f"❌ Failed to create PR: {response.text}")
            return ""
            
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        return ""


    