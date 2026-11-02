from langchain_core.prompts import ChatPromptTemplate

def create_understand_agent(llm):
    """
    Creates the understand agent that analyzes the task description alongside
    the relevant file contents to identify what needs to be changed.
    """
    prompt = ChatPromptTemplate.from_messages([
        ( "system", """You are a software engineer.
Analyze the user's task and the provided code.
Tell us:
1. What is the problem?
2. What changes are needed?
3. Which files should be modified? Be concise and practical.""" ),
        ( "human", """Task: {task} Relevant files and their contents: {file_contents}""" )
    ])

    return prompt | llm
