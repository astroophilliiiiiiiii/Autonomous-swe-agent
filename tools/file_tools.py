from pathlib import Path

# function to read a file ( by taking the address of the file in input )
def read_file(file_path: str):
    path = Path(file_path)    # converting file path --> path object 

    if not path.is_file():    # check if this file already exists or not 
        raise FileNotFoundError(f"File not found: {file_path}")

    # file ke andr kaa text returned 
    return path.read_text(encoding="utf-8")   # utf-8 to correctlly read the file 

