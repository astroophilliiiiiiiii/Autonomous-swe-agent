import subprocess # from python code to run a terminal command 
from pathlib import Path

# GITHUB REPO -- clone function of the github repo 
def clone_repo(repo_url: str, repo_path: str = "workspace/repo"): # input -- repo url , path where to clone
    path = Path(repo_path)     # string address -----> Python's proper path object

# If workspace/repo already exists means repo already cloned --- assuming we r dealing with only 1 type of repo
    #⏳TASK-- dealing with multiple repos ---- this one doesnt deals 
    if path.exists():
        print("Repository already exists.")
        return path

    # path.parent = workspace  --- mkdir => make it 
    # parents -- a/b/c/repo --makes the parent c but a/b also doesnt exist -- so parent true makes all a/b/c
    path.parent.mkdir(parents=True, exist_ok=True)  # exist_ok -- if already exists ok -- dont give error ❌

    subprocess.run(
        ["git", "clone", repo_url, str(path)], # git clone repo_url path -- becomes the exact command that we'll run in terminal -- we'll give string path obv
        check=True  #Agar git command successfully run nhi hui, toh Python error raise kare -- like url mein error -- or any other 
    )

    print("Repository cloned successfully.")
    return path  # now agent can use this location of the repo_url to do further work 


def list_directory(repo_path: str):
    path = Path(repo_path)

    ignored_dirs = {".git","__pycache__","venv","node_modules"}

    files = []

    for item in path.rglob("*"):            # rglob("*") = inside repo --- all files and folders search

        relative_path = item.relative_to(path)

        if any(part in ignored_dirs for part in relative_path.parts):
            continue

        if item.is_file():                  # only files r needed -- folders ignored 
            files.append(str(item.relative_to(path)))   # File ka repo ke clean relative path print 

    return files # list of files 
    # path = workspace/repo
    # item = workspace/repo/backend/app.py
    #relative_to(path) means: "path wala starting part hata do."

