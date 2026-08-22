from langchain_core.prompts import ChatPromptTemplate

def create_debug_agent(llm):
    prompt = ChatPromptTemplate.from_messages([
        ( "system",  """You are an expert Python Debugger. 
            Analyze the user's task, the current code, and the test error.
            Explain in simple, concise terms:
            1. Why did the test fail?
            2. What is the exact bug?
            3. How should the Coding Agent fix it?"""),
        ( "human",  """Task: {task} Current Code: {code} Test Error/Result:  {test_result}""" )
    ])

    return prompt | llm