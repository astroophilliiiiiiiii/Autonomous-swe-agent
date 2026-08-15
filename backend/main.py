from tools.repo import clone_repo , list_directory
from tools.file_tools import read_file
#Python mein module ke andar defined functions/classes by default importable hote hain. _ se start => private

#python -m backend.main # no error in the import 
# __pycache makes .pyc files that makes import shorter and faster version of files -- easier for imports 

# input of the repo and the task to perform in the repo

#------------------------------------------input------------------------------------------------------------
repo = input("GitHub Repository: ")   #⏳TASK :-- validator -- repo is in the right format and validity check 
task = input("Task: ")

print("\nRepository:", repo)
print("Task:", task)

#------------------------------------------cloning the repo------------------------------------------------------------
repo_path = clone_repo(repo)
print("Local repository:", repo_path)

#------------------------------------------lisitng all the files in repo -----------------------------------------------
print("\nFiles in repository:")
list_directory(repo_path)

#------------------------------------------reading the file -----------------------------------------------------------
file_path = input("\nEnter file to read: ")

content = read_file(file_path)

print("\nFile content:\n")
print(content)