from langchain.prompts import ChatPromptTemplate  # Fixed import for current LangChain versions

def create_coding_agent(llm):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a software engineer.
                Given a task, the problem analysis, the relevant file contents, and any 
                previous test failure feedback, modify the code to fix the problem. Return the complete updated 
                file content. Do not explain. Do not use markdown formatting (no code blocks or backticks).
                Only modify the provided files. Never create or invent files. 
                Return only the updated content of the provided file.""",),
        ("human", """Task: {task} Problem analysis: {analysis} File contents: {file_contents} Previous Test Error Feedback (if any):
        {error_feedback}""",),
    ])

    return prompt | llm