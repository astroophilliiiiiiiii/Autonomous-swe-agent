from pathlib import Path

# function to read a file ( by taking the address of the file in input )
def read_file(file_path: str):
    path = Path(file_path)    # converting file path --> path object 

    if not path.is_file():    # check if this file already exists or not 
        raise FileNotFoundError(f"File not found: {file_path}")

    # file ke andr kaa text returned 
    return path.read_text(encoding="utf-8")   # utf-8 to correctlly read the file 

def write_file(file_path: str, content: str): # file to change , content 
    path = Path(file_path)

# If the file already exists, Python wipes it clean and overwrites it with the new text.
# If the file does not exist, Python automatically creates a brand-new file for you (as long as the parent folder exists).
# Because it creates files automatically, a standard write_file function usually skips the is_file() check.
    # 🛑 AI Guardrail: Do not allow the agent to create new files
    if not path.is_file():
        raise FileNotFoundError(f"Agent Error: You are not allowed to create files. '{file_path}' does not exist.")

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)