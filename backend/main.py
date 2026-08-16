from tools.repo import clone_repo , list_directory
from tools.file_tools import read_file
from agents.file_selector import create_file_selector
from backend.llm import llm
from agents.understand_agent import create_understand_agent
from agents.coding_agent import create_coding_agent
from tools.file_tools import write_file
#Python mein module ke andar defined functions/classes by default importable hote hain. _ se start => private

# input of the repo and the task to perform in the repo
repo = input("GitHub Repository: ")   #⏳TASK :-- validator -- repo is in the right format and validity check 
task = input("Task: ")

repo_path = clone_repo(repo)                    # cloning the repo 
files = list_directory(repo_path)               # listing all the files 

file_selector = create_file_selector(llm)       #  chain returned -- need to invoke it 
result = file_selector.invoke({ "task" : task , "files" : files })  # files by llm 

#dont trusts llm blindly -- check if these files actually exists or not 
relevant_files = [] 
for file in result.content.splitlines():   # string -- list of items -- can easily iterate
    if file in [f.replace("\\", "/") for f in files]:
        relevant_files.append(file)


file_contents = {}    # dictionary -- relevant files 

for file in relevant_files:
    full_path = repo_path / file  # making the full path of the file 

    try:
        file_contents[file] = read_file(str(full_path))  # file name : file content
    except Exception as e:
        print(f"Could not read {file}: {e}")  # error in reading 

understand_agent = create_understand_agent(llm)
result1 = understand_agent.invoke({"task":task , "file_contents": file_contents}) # takes dictionary in input 

if not relevant_files:
    print("No relevant files found.")
    exit()

coding_agent = create_coding_agent(llm)
result2 = coding_agent.invoke({
    "task": task,
    "analysis": result1.content,
    "file_contents": file_contents[ relevant_files[0] ] # is 0th file kaa content aajegaa isme 
})

# writing to the file 
write_file( str(repo_path / relevant_files[0]), result2.content )

