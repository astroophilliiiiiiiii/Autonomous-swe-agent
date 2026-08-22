from typing import TypedDict
from agents.coding_agent import create_coding_agent
from backend.llm import llm
from tools.file_tools import write_file
from agents.testing_agent import testing_agent
from langgraph.graph import StateGraph, START, END
from agents.debug_agent import create_debug_agent
from agents.understand_agent import create_understand_agent

class AgentState(TypedDict):
    repo_path: str      # where is repo 
    task: str           # task of user 
    file: str           #which file to change
    code: str           #current code
    analysis: str       #understand agent's result 
    test_result: str    #pytest result 
    attempts: int       # how many times fix try hua 
    debug_result: str


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

    if "PASS" in state["test_result"]:
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

graph.add_edge(START, "understand")
graph.add_edge("understand", "coding")

graph.add_edge("coding", "testing")
graph.add_conditional_edges( "testing", check_result, {"fix": "debug", "done": END } )
graph.add_edge("debug", "coding")

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

