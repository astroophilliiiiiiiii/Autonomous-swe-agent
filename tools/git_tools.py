import os
import subprocess
import requests

# Is code me sabse badi dikkat ye thi ki jab swe-agent/task-fix branch pehle se exist karti thi, 
# toh checkout -b command error de kar except block me chali jaati thi aur return None kar deti thi. 
# Phir summary_node ko branch name None milta tha, jiski wajah se git push command crash ho jaati thi.
# Sahi tarika ye hai ki agar branch pehle se bani hui hai, toh hum error throw karne ke bajaye 
# simply us existing branch par switch (git checkout branch_name) kar lein.

def create_branch(repo_path: str, branch_name: str = "swe-agent/task-fix"):
    try:
        # 1. Nayi branch make and switch to it  (git checkout -b <branch_name>)
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_path,         # Command repo_path folder ke andar chalegi
            check=True,            # Error aane par CalledProcessError raise karega
            capture_output=True,   # Output/error ko print karne ki jagah memory mein capture karega
            text=True,             # Output ko string format mein rakhega (bytes mein nahi)
            encoding="utf-8",
            errors="replace"
        )
        print(f"🌿 Branch '{branch_name}' created successfully.")

    except subprocess.CalledProcessError:
        # 2. if branch exists pehle se (checkout -b fail hua), toh directly switch karo
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

    # 3. Always branch_name return ( None return kabhi nahi hoga!)
    return branch_name


def get_git_diff(repo_path: str) -> str:
    """Dekhta hai ki code mein exactly kya-kya add ya remove hua hai."""
    try:
        # Terminal command: git diff
        result = subprocess.run(
            ["git", "diff"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            errors="replace"
        )
        if result and result.stdout:
            return result.stdout.strip() # Terminal se nikle hue raw text output ko clean karke ek normal readable string banana! 🧹
        return ""
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error checking diff: {e.stderr}")
        return ""


def commit_changes(repo_path: str, commit_message: str = "Agent auto-fix"):
    """Saare changes ko Git mein add aur commit karta hai."""
    try:
        # Step 1: git add . (Saare changes select karo)
        subprocess.run(
            ["git", "add", "."], 
            cwd=repo_path, 
            check=True,
            encoding="utf-8",
            errors="replace"
        ) # koi error aaya toh save krlena
        
        # Step 2: git commit (Message ke saath save karo)
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
    """Nayi branch aur uske changes ko GitHub par upload karta hai."""
    try:
        # Terminal command: git push origin branch_name
        subprocess.run(
            ["git", "push", "origin", branch_name,"--force-with-lease"], # origin -- repo name , branch_name-- new branch created 
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
    """GitHub API se automatic Pull Request (PR) banata hai."""
    
    # GitHub ko pata hona chahiye: "Ye request kis authorized user ki hai?"
    # identification + authentication/authorization
    token = os.getenv("GITHUB_TOKEN")  # for identifying that a authorised github user is creating a PR 
    if not token:
        print("❌ Error: GITHUB_TOKEN environment variable mein nahi mila!")
        return ""
        
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls" #KIS REPO mein PR banana hai?
    
    headers = {
        "Authorization": f"Bearer {token}", #Ye request authorized user ki hai, ye raha uska token.” 🔐
        "Accept": "application/vnd.github.v3+json" # RESPONSE kis format mein chahiye? 📦
    }

    # 🔍 Target repo ki default branch dynamically check karna (main/master)
    repo_info_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    repo_res = requests.get(repo_info_url, headers=headers)
    default_branch = "main"
    if repo_res.status_code == 200:
        default_branch = repo_res.json().get("default_branch", "main")
    
    # PR ki details
    data = {
        "title": title,       # PR ka naam/title kya hoga.
        "body": description,  #PR mein explanation/description kya hogi.
        "head": branch_name,  # Kis branch se changes aa rahe hain
        "base": default_branch        # Kis branch mein changes bhejne hain
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