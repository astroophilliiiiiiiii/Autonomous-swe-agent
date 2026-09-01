from typing import TypedDict
from agents.coding_agent import create_coding_agent
from backend.llm import llm
from tools.file_tools import write_file
from agents.testing_agent import testing_agent
from langgraph.graph import StateGraph, START, END
from agents.debug_agent import create_debug_agent
from agents.understand_agent import create_understand_agent
from tools.git_tools import create_branch
from tools.git_tools import get_git_diff, commit_changes, push_to_github, create_pull_request , check_pr_ci_status, get_failed_ci_logs
import os 
import time
from typing import TypedDict, Optional
import subprocess

class AgentState(TypedDict):
    repo_path: str      # where is repo 
    task: str           # task of user 
    file: str           #which file to change
    code: str           #current code
    analysis: str       #understand agent's result 
    test_result: str    #pytest result 
    attempts: int       # how many times fix try hua 
    debug_result: str
    branch_name: str
    repo_url: str       # 👈 NAYI LINE: GitHub URL save karne ke liye
    summary: str        # 👈 NAYI LINE: Final report card save karne ke liye
    pr_number: Optional[int]      # PR banne ke baad yahan PR number save hoga
    ci_status: Optional[str]      # 'success', 'failure', ya 'pending'
    ci_logs: Optional[str]        # Fail hone par logs yahan save honge
    repo_name : str 
    repo_owner : str 

def fetch_repo_details(state):
    repo_path = state["repo_path"]  # "workspace/repo" jahan code rakha hai
    
    try:
        # Step 1: Terminal command chala kar GitHub ka link nikalo
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"], 
            cwd=repo_path, 
            capture_output=True, 
            text=True
        )
        git_url = result.stdout.strip() # Example: https://github.com/owner/repo_name.git
        
        # Step 2: Link ko cut karke Owner aur Repo Name nikalo
        if git_url:
            # ".git" hatao aur "/" se link ko tod do
            parts = git_url.replace(".git", "").split("/")
            
            repo_owner = parts[-2]  # Aakhiri se doosra (Owner)
            repo_name = parts[-1]   # Sabse aakhiri (Repo)
            
            # Step 3: State mein update kar do!
            state["repo_owner"] = repo_owner
            state["repo_name"] = repo_name
            
            print(f"✅ Successfully fetched -> Owner: {repo_owner} | Repo: {repo_name}")
        else:
            print("❌ Git URL nahi mila. Kya yeh repo clone hui thi?")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        
    return state

def coding_node(state):

    coding_agent = create_coding_agent(llm)

    result = coding_agent.invoke({
        "task": state["task"],
        "analysis": state["analysis"],
        "file_contents": state["code"] , 
        "error_feedback": state["debug_result"]  # 👈 takes the debugged error ( not the original itnaa badaa sa error )
    })

    new_code = result.content

    # path , code !! 
    file_path = os.path.join(state["repo_path"], state["file"])
    write_file(file_path, new_code)

    state["code"] = new_code
    state["attempts"] += 1

    return state


def testing_node(state):
    result = testing_agent(state["repo_path"])
    state["test_result"] = result # saved the test_result -- incase again needed toh 
    return state

def summary_node(state):
    repo = state["repo_path"]
    branch = state["branch_name"]
    task = state["task"]
    
    # 1. 🔍 Diff Check
    diff_changes = get_git_diff(repo)
    
    # 2. 💾 Commit
    commit_msg = f"Auto-fix: {task}"
    commit_result = commit_changes(repo, commit_msg)
    if not commit_result:
        raise Exception("❌ Commit failed")

    
    # 3. 🚀 Push
    push_result = push_to_github(repo, branch)
    if not push_result:
        raise Exception("❌ Push failed")
    
    # 4. 🔗 Pull Request (Yahan apna username aur repo name daal dena!)
    pr_link = create_pull_request(
        repo_owner=state["repo_owner"],  
        repo_name=state["repo_name"],
        branch_name=branch,
        title=commit_msg,
        description=f"Fixed issue automatically.\n\nChanges:\n{diff_changes}"
    )
    if not pr_link:
        raise Exception("❌ Pull Request creation failed")

    # 👈 NEW LOGIC: URL se PR number nikal kar state mein save karo
    # Example pr_link: "https://github.com/owner/repo/pull/12" -> "12"
    try:
        pr_number = int(pr_link.split("/")[-1])
        state["pr_number"] = pr_number
    except:
        print("Warning: PR Number extract nahi ho paya URL se.")
    
    
    # 5. 📝 Final Summary (Report Card)
    final_summary = f"""
    ✅ Task Completed Successfully!

    🌿 Branch: {branch}
    💾 Commit: {commit_msg}
    🧪 Tests: PASS
    🔗 PR Link: {pr_link if pr_link else 'Failed to create PR'}
    """
    
    # State mein save kar do
    state["summary"] = final_summary
    print(final_summary) # Screen par bhi dikha do
    
    return state

def branch_node(state):
    state = fetch_repo_details(state)
    # Branch banayega aur state mein update karega
    branch = create_branch(state["repo_path"], "swe-agent/task-fix")
    state["branch_name"] = branch
    return state


def understand_node(state):
    understand_agent = create_understand_agent(llm)
    
    # Agent ko task aur file ka code do
    result = understand_agent.invoke({
        "task": state["task"],
        "file_contents": state["code"]
    })
    
    # Uske banaye hue plan ko 'analysis' mein save kar do
    state["analysis"] = result.content
    return state

def debug_node(state):
    # 1. Debug Agent banaya
    debug_agent = create_debug_agent(llm)

    # 👈 NEW LOGIC: Check karo ki konsa error agent ko dena hai
    if state.get("ci_logs"):  # ✅ As pehle to ci_logs naam ki koi state mein value hi ni hogi -- so to avoid the error 
        error_to_fix = state["ci_logs"]  # Agar cloud par fail hua
    else:
        error_to_fix = state["test_result"]  # Agar local system par fail hua
    
    # 2. Agent ko task, code, aur red error diya
    result = debug_agent.invoke({
        "task": state["task"],
        "code": state["code"],
        "test_result": error_to_fix
    })
    
    # 3. Agent ki asaan bhasha wali advice state mein save kar li
    state["debug_result"] = result.content
    
    return state

# conditional decision -- pass -- end    fail -- coding agent 
def check_result(state):

    if state["test_result"].startswith("TESTS PASSED"):
        return "done"

    if state["attempts"] >= 3:
        return "done"

    return "fix"

# after every 30 secs ask the github ki ci workflow huaa puraa ?? yaml file ke tests hue run ?
def ci_cd_node(state: AgentState):
    print("\n--- ⏳ CI/CD NODE: Waiting for GitHub Actions ---")

    
    repo_owner=state["repo_owner"]  
    repo_name=state["repo_name"]
    pr_number = state["pr_number"]
    github_token = os.environ.get("GITHUB_TOKEN")
    
    if not pr_number:
        return {"ci_status": "error", "ci_logs": "No PR number found in state."}

    max_attempts = 10  # Maximum 10 baar check karega
    wait_time = 30     # Har check ke beech 30 seconds ka wait

    status = "pending"
    
    # Polling Loop: Cloud tests khatam hone ka wait kar rahe hain
    for attempt in range(max_attempts):
        status = check_pr_ci_status(repo_owner, repo_name, pr_number)
        
        if status != "pending":
            break # Status success ya failure aa gaya, loop se bahar niklo
            
        print(f"[{attempt+1}/{max_attempts}] CI is still running... waiting 30 seconds.")
        time.sleep(wait_time)
        
    # Wait khatam hone ke baad final decision
    if status == "success":
        print("✅ CI Passed Successfully!")
        return {"ci_status": "success", "ci_logs": None} # instead of returning whole state only return chnged values 
        
    elif status == "failure":
        print("❌ CI Failed! Fetching error logs...")
        logs = get_failed_ci_logs(repo_owner, repo_name, pr_number )
        return {"ci_status": "failure", "ci_logs": logs} # isme logs daaldiyyee 
        
    else:
        return {"ci_status": "timeout", "ci_logs": "CI took too long or crashed."}


def route_after_ci(state: AgentState):
    """
    Decides the next step based on CI/CD status.
    """
    status = state["ci_status"]
    
    if status == "success":
        print("🚥 ROUTER: CI Passed! Ending the workflow.")
        return END
    else:
        print("🚥 ROUTER: CI Failed! Sending logs back to Debug Agent.")
        return "debug"


#------------------------------------------GRAPH-----------------------------------------------------------
graph = StateGraph(AgentState)

# 1. Register all nodes
graph.add_node("coding", coding_node)
graph.add_node("testing", testing_node)
graph.add_node("debug", debug_node)
graph.add_node("understand", understand_node)
graph.add_node("branch", branch_node)
graph.add_node("summary", summary_node) 
graph.add_node("ci_cd", ci_cd_node) # Naam simple "ci_cd" rakha hai

# 2. Main workflow edges
graph.add_edge(START, "branch")
graph.add_edge("branch", "understand")
graph.add_edge("understand", "coding")
graph.add_edge("coding", "testing")

# 3. Local testing checks
graph.add_conditional_edges("testing", check_result, {"fix": "debug", "done": "summary"})
graph.add_edge("debug", "coding")

# 4. CI/CD flow edges --after creating the pr 
graph.add_edge("summary", "ci_cd") # Summary ke baad seedha CI/CD par jao

graph.add_conditional_edges(
    "ci_cd",             # Router yahan se start hoga
    route_after_ci,      # Yeh function chalega
    {
        END: END,        # Success -> Graph finish
        "debug": "debug" # Fail -> Wapas debug node par
    }
)

app = graph.compile()


# #-------------------------------------------RUN-------------------------------------------------------
# initial_state = {
#     "repo_path": "workspace/repo",
#     "task": "Fix the bug",
#     "file": "src/example.py",
#     "code": "...current code...",
#     "analysis": "...problem analysis...",
#     "test_result": "",
#     "attempts": 0
# }

# result = app.invoke(initial_state)

# print(result["test_result"])

