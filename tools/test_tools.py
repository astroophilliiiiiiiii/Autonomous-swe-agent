import subprocess  # to run command from terminal
import os

# Python mein usko list ke form mein dete hain: ["pytest"]
# Agar command hoti: ( python test.py ) toh: ["python", "test.py"]

def run_tests(repo_path: str) -> str:
    """
    Host machine ke repository code par Docker ke andar Pytest chalaata hai.
    """
    # Host machine ka absolute system path nikalna
    abs_repo_path = os.path.abspath(repo_path)
    
    # Har run ke liye unique container name (Process ID se)
    container_name = f"swe_runner_{os.getpid()}"

    # Docker command setup:
    # 1. --rm: Test complete hone par container auto-delete ho jayega (Incognito Tab ki tarah fresh state).
    # 2. -v ...:ro: Host repo ko read-only mode mein sync karta hai (Host file safe rehti hai).
    # 3. pytest -v: Container ke andar pytest verbose mode mein chalta hai.
    docker_cmd = [
        "docker", "run", "--rm",
        "--name", container_name,
        "--cpus=1.0",
        "--memory=512m",
        "--network", "none",
        "-v", f"{abs_repo_path}:/app/workspace/repo:ro",  # mount kiya
        "-w", "/app/workspace/repo", #python -m pytest -v seedha tumhare repo folder (/app/workspace/repo) ke andar chalegi
        "swe-agent-env", 
        "python", "-m", "pytest", "-v"  # python -m module execution use kar rahe hain for safety
    ]
#     Pehle Container banati hai (Host folder ko mount karke aur RAM/CPU limits laga kar).
#     Container ke andar jajate hi python -m pytest -v wali command chala deti hai.

    try:
        # result = subprocess.run(...)
        # capture_output=True: Standard output aur error ko terminal par direct print karne ki jagah memory me hold karke result.stdout aur result.stderr me store kar leta hai.
        # text=True: Output raw binary bytes (b'...') me na mile, balki simple string formatted text me mile.
        # timeout=10: 10 second timeout for infinite loop protection
        result = subprocess.run(
            docker_cmd, 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        output = result.stdout + "\n" + result.stderr
        
        if result.returncode == 0:
            return f"TESTS PASSED:\n{output}"
        else:
            return f"TESTS FAILED:\n{output}"

    except subprocess.TimeoutExpired:
        # Infinite loop ya hang hone par container ko force kill aur clean karna
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        return "TEST FAILED: Execution timed out (10s limit reached)."
    except Exception as e:
        return f"ERROR: Execution failed due to: {str(e)}"