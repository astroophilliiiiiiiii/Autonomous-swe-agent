from tools.repo import clone_repo , list_directory
from tools.file_tools import read_file
from agents.file_selector import create_file_selector
from backend.llm import llm
#Python mein module ke andar defined functions/classes by default importable hote hain. _ se start => private

# input of the repo and the task to perform in the repo
repo = input("GitHub Repository: ")   #⏳TASK :-- validator -- repo is in the right format and validity check 
task = input("Task: ")

repo_path = clone_repo(repo)                    # cloning the repo 
files = list_directory(repo_path)               # listing all the files 

file_selector = create_file_selector(llm)       #  chain returned -- need to invoke it 
result = file_selector.invoke({ "task" : task , "files" : files })

print("\nRelevant files:")
print(result.content)




