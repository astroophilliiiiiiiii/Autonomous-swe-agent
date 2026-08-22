from tools.repo import clone_repo , list_directory
from tools.file_tools import read_file
from agents.file_selector import create_file_selector
from backend.llm import llm
from agents.understand_agent import create_understand_agent
from backend.graph import app
#Python mein module ke andar defined functions/classes by default importable hote hain. _ se start => private

#-------------------------------input of the repo,task to perform---------------------------------
repo = input("GitHub Repository: ")   #⏳TASK :-- validator -- repo is in the right format and validity check 
task = input("Task: ")

repo_path = clone_repo(repo)                    # cloning the repo 
files = list_directory(repo_path)               # listing all the files 

file_selector = create_file_selector(llm)       #  chain returned -- need to invoke it 
result = file_selector.invoke({ "task" : task , "files" : files })  # files by llm 


#🎉🎉🎉 dont trusts llm blindly -- check if these files actually exists or not 
relevant_files = [] 
for file in result.content.splitlines():   # string -- list of items -- can easily iterate
    if file.replace("\\", "/") in [f.replace("\\", "/") for f in files]:
        relevant_files.append(file)

if not relevant_files:
    print("No relevant files found.")
    exit()


file_contents = {}    # dictionary -- relevant files 

for file in relevant_files:
    full_path = repo_path / file  # making the full path of the file 

    try:
        file_contents[file] = read_file(str(full_path))  # file name : file content
    except Exception as e:
        print(f"Could not read {file}: {e}")  # error in reading 

understand_agent = create_understand_agent(llm)
result1 = understand_agent.invoke({"task":task , "file_contents": file_contents}) # takes dictionary in input 


#----------------------------------------------GRAPH-----------------------------------------------------
initial_state = {
    "repo_path": str(repo_path),
    "task": task,
    "file": relevant_files[0],
    "code": file_contents[relevant_files[0]], # !! -- only one file content abhi ke liye !!
    "analysis": result1.content, # by the understand agent -- like problem , error 
    "test_result": "",
    "attempts": 0,
    "debug_result": ""
}
result = app.invoke(initial_state)
print(result["test_result"])


#-----------------------------------------------FINAL NEAT RESULT--------------------------------------
print("\n--- Final Summary ---")

print("Task:", task)

print("\nChanged:")
for file in relevant_files:
    print("-", file)

print("\nTests:")
print(result["test_result"])

print("\nResult:")
if "PASS" in result["test_result"]:
    print("Task completed successfully. ✅")
else:
    print("Task could not be completed successfully. ❌")
