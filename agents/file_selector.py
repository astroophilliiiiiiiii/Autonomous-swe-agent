from langchain_core.prompts import ChatPromptTemplate   # to create prompt template 

# input-- llm model 
def create_file_selector(llm):

    #instructions template
    prompt = ChatPromptTemplate.from_messages([
    # system message -- iske according work will happen 
    ( "system", """You are a software engineer.   

                Given a user task and a list of repository files,
                select only the files that are likely relevant to the task.

                Return only the file paths, one per line.
                Do not explain your answer."""),
    # human message  -- actual user query 
    ("human", """Task: {task} Repository files: {files}""" )
    ])

    return prompt | llm   # chain returned 


