from pathlib import Path

def read_file(file_path: str) -> str:
    """Reads and returns the text content of a file using UTF-8 encoding."""
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    return path.read_text(encoding="utf-8")


def write_file(file_path: str, content: str):
    """
    Writes text content to a file. Automatically creates any missing parent directories
    if creating a new file. Overwrites existing content.
    """
    path = Path(file_path)

    # Automatically create parent directories if they do not exist
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)
