from langchain_core.prompts import ChatPromptTemplate

def create_file_selector(llm):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a software engineer.
Given a user task and a list of repository files,
select only the files that are relevant to the task.

IMPORTANT:
- Return ONLY file paths.
- Return one file path per line.
- Do NOT write explanations.
- Do NOT write Python code.
- Do NOT use markdown.
- Do NOT use ``` . 
Example output:
backend/main.py
tools/file_tools.py
tests/test_login.py"""),
        ("human", """Task: {task} Repository files: {files}""")
    ])

    return prompt | llm