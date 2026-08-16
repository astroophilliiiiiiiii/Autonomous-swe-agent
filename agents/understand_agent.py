from langchain_core.prompts import ChatPromptTemplate

#tum software engineer ho. User ka task aur selected files ka code dekho aur batao problem kya h
def create_understand_agent(llm):

    # TASK -- apply pydantic basemodel class --> for the structured output taaki kabhi glti na ho 
    prompt = ChatPromptTemplate.from_messages([
        ( "system", """ You are a software engineer.
                        Analyze the user's task and the provided code.
                        Tell us:
                        1. What is the problem?
                        2. What changes are needed?
                        3. Which files should be modified? Be concise and practical.""" ),
        ( "human", """ Task: {task} Relevant files and their contents: {file_contents} """ )
    ])

    return prompt | llm

