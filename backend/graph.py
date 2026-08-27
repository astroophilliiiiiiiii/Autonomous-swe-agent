from typing import TypedDict
from agents.coding_agent import create_coding_agent
from backend.llm import llm
from tools.file_tools import write_file
from agents.testing_agent import testing_agent
from langgraph.graph import StateGraph, START, END
from agents.debug_agent import create_debug_agent
from agents.understand_agent import create_understand_agent
from tools.git_tools import create_branch
from tools.git_tools import get_git_diff, commit_changes, push_to_github, create_pull_request

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
    summary: str        # 👈 NAYI LINE: Final report card save karne ke liye


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
    write_file(  state["repo_path"] + "/" + state["file"], new_code )

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
    commit_result = commit_msg = f"Auto-fix: {task}"
    commit_changes(repo, commit_msg)
    if not commit_result:
        raise Exception("❌ Commit failed")

    
    # 3. 🚀 Push
    push_result = push_to_github(repo, branch)
    if not push_result:
        raise Exception("❌ Push failed")
    
    # 4. 🔗 Pull Request (Yahan apna username aur repo name daal dena!)
    pr_link = create_pull_request(
        repo_owner="astroophilliiiiiiii",  # abhi hum apne hi project m theek krree toh destination apna hi project dediyaa 
        repo_name="Autonomous-swe-agent",  # abhi hum apne hi project m theek krree toh destination apna hi project dediyaa 
        branch_name=branch,
        title=commit_msg,
        description=f"Fixed issue automatically.\n\nChanges:\n{diff_changes}"
    )
    if not pr_link:
        raise Exception("❌ Pull Request creation failed")
    
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
    
    # 2. Agent ko task, code, aur red error diya
    result = debug_agent.invoke({
        "task": state["task"],
        "code": state["code"],
        "test_result": state["test_result"]
    })
    
    # 3. Agent ki asaan bhasha wali advice state mein save kar li
    state["debug_result"] = result.content
    
    return state

# conditional decision -- pass -- end    fail -- coding agent 
def check_result(state):

    if state["test_result"].startswith("PASS"):
        return "done"

    if state["attempts"] >= 3:
        return "done"

    return "fix"


#------------------------------------------GRAPH-----------------------------------------------------------
graph = StateGraph(AgentState)

graph.add_node("coding", coding_node)
graph.add_node("testing", testing_node)
graph.add_node("debug" , debug_node )
graph.add_node("understand", understand_node)
graph.add_node("branch", branch_node)
graph.add_node("summary", summary_node) # 👈 MISSING: Node register karo


graph.add_edge(START, "branch")
graph.add_edge("branch", "understand")
graph.add_edge("understand", "coding")

graph.add_edge("coding", "testing")
graph.add_conditional_edges( "testing", check_result, {"fix": "debug", "done": "summary"} )
graph.add_edge("debug", "coding")
graph.add_edge("summary", END) 

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

