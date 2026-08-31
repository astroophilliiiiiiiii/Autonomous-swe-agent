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

    # Mujhe is repository mein PR create karna hai
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"  # /pulls -- pr ke related kaam - ispe request -- pr creates 
    
    headers = {  # request is authorised , its response jis format mein chahiyeee 
        "Authorization": f"Bearer {token}", #Ye request authorized user ki hai, ye raha uska token.” 🔐
        "Accept": "application/vnd.github.v3+json" # RESPONSE kis format mein chahiye? 📦
    }

    # 🔍 Target repo ki default branch dynamically check karna (main/master)
    repo_info_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"  #👉 Target repository ka API URL bana rahe ho.
    repo_res = requests.get(repo_info_url, headers=headers)                   #"Is repo ki information do."
    default_branch = "main"
    if repo_res.status_code == 200:         # agr sahi se aaya hai response from the repo of user 
        default_branch = repo_res.json().get("default_branch", "main")   #GitHub ke response se actual default branch nikaalo.
    
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



def check_pr_ci_status(repo_owner: str, repo_name: str, pr_number: int ) -> str:
    """
    Checks the CI/CD status of a Pull Request on GitHub.
    Returns 'pending', 'success', or 'failure'.
    """

    token = os.getenv("GITHUB_TOKEN")  # for identifying that a authorised github user is creating a PR 
    if not token:
            print("❌ Error: GITHUB_TOKEN environment variable mein nahi mila!")
            return ""

    headers = {
        "Authorization": f"token {token}", #Ye request authorized user ki hai, ye raha uska token.” 🔐
        "Accept": "application/vnd.github.v3+json"   # RESPONSE kis format mein chahiye -- JSON 📦
    }
    
    # 1. PR ki details API se fetch karke uska latest commit SHA nikalo
    pr_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}"   # apui url of commit 
    pr_response = requests.get(pr_url, headers=headers) # uspe get request lgaake data fetched 
    
    if pr_response.status_code != 200:
        return f"Error API Call 1: {pr_response.status_code} - {pr_response.text}"

    # us data mein se latest commit kaa id( SHA ) fetch 
    # github ka reponse json meni -- pr ka head info ( meri changes vaali branch ) -- us branch ke latest commit ki unique id 
    commit_sha = pr_response.json().get("head", {}).get("sha")
    if not commit_sha:
        return "Error: Commit SHA nahi mila."  

    # 2. Us commit par chalne wale saare 'Check Runs' (GitHub Actions) ka status check karo
    checks_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{commit_sha}/check-runs"
    checks_response = requests.get(checks_url, headers=headers)
    
    if checks_response.status_code != 200:
        return f"Error API Call 2: {checks_response.status_code} - {checks_response.text}"
        
    check_runs = checks_response.json().get("check_runs", []) #.get("check_runs", []) → us response se saare check runs nikaalo , agr ni hai toh [] dedo 
    
    # Agar abhi tak koi test trigger hi nahi hua
    if not check_runs:
        return "pending" 
        
    # 3. Status logic: Pass, Fail, ya Pending
    for run in check_runs:
        if run["status"] != "completed":
            return "pending"  # Test abhi chal raha hai
        
        # Agar complete hua hai par fail ho gaya
        if run["conclusion"] in ["failure", "timed_out", "action_required", "cancelled"]:
            return "failure"  # ❌ Fail ho gaya!
            
    # Agar saare tests complete ho gaye aur fail nahi hue
    return "success"      # ✅ Pass ho gaya!



def get_failed_ci_logs(repo_owner: str, repo_name: str, pr_number: int ) -> str:
    """
    Fetches the raw error logs from a failed GitHub Action job for a specific PR.
    Returns the last 150 lines of the log so the LLM doesn't get overwhelmed.
    """

    token = os.getenv("GITHUB_TOKEN")  # for identifying that a authorised github user is creating a PR 
    if not token:
        print("❌ Error: GITHUB_TOKEN environment variable mein nahi mila!")
        return ""
    

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 1. PR se latest commit SHA nikalo
    pr_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}"
    pr_response = requests.get(pr_url, headers=headers)
    
    if pr_response.status_code != 200:
        return "Error: Cannot fetch PR details."
        
    commit_sha = pr_response.json().get("head", {}).get("sha")  # us pr ka latest commit nikaal liyyaa 

    # 2. Check Runs API se pata karo kaunsi job fail hui hai
    checks_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{commit_sha}/check-runs" # uske ci checks nikaalo
    checks_response = requests.get(checks_url, headers=headers)   # Is commit par jo Ci checks chale, unka result mujhe do
    check_runs = checks_response.json().get("check_runs", [])     # usme se check_runs nikaal specifically
    
    failed_job_id = None
    for run in check_runs:
        if run["conclusion"] in ["failure", "timed_out", "action_required"]:
            failed_job_id = run["id"]
            break  # Pehli failed job milte hi loop rok do
            
    if not failed_job_id:
        return "No failed jobs found. Everything seems fine."

    # 3. Failed job ke raw logs download karo
    logs_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/jobs/{failed_job_id}/logs" # url bnao for the failed job
    logs_response = requests.get(logs_url, headers=headers)     # uskaa response nikaaloo 
    
    if logs_response.status_code == 200:
        full_logs = logs_response.text
        # LLM token limit bachaane ke liye sirf aakhiri 150 lines return karenge
        # Kyunki pytest ke actual errors hamesha end mein aate hain!
        log_lines = full_logs.splitlines()
        tail_logs = "\n".join(log_lines[-150:])
        
        return f"--- FAILED CI LOGS ---\n{tail_logs}"
    else:
        return f"Error fetching logs: {logs_response.status_code} - {logs_response.text}"