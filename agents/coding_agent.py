from langchain_core.prompts import ChatPromptTemplate


def create_coding_agent(llm):

    prompt = ChatPromptTemplate.from_messages([
        ( "system", """You are a software engineer.
                       Given a task, the problem analysis, and the relevant file contents,
                       modify the code to fix the problem.
                       Return the complete updated file content.
                       Do not explain.
                       Do not use markdown.
                       Only modify the provided files. Never create or invent files. Return only the updated content of the provided file.
        """),
        ("human", """Task: {task} Problem analysis: {analysis} File contents: {file_contents}""" )
    ])

    return prompt | llm