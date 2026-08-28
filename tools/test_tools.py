import subprocess # to run command from terminal 

#Python mein usko list ke form mein dete hain: ["pytest"] 
# Agar command hoti: ( python test.py ) toh: ["python", "test.py"]

#🎉🎉🎉--Pehle tum direct pytest naam ke tool ko bulane ki koshish kar rahi thi, jo Windows ko nahi mil raha tha.
#Naye code mein tumne pehle Python ko bulaya, aur Python ko bola ki "bhai, apne andar se pytest naam ka module chalana shuru kar". Kyunki Python wahi hai, usne bina kisi error ke usko chala diya.
def run_tests(repo_path): # input -- repository path 

    #Docker, swe-container ke andar jao, /app/workspace/repo ko current folder banao, 
    # aur wahan pytest se saare tests run karo
    result = subprocess.run(["docker","exec","-w","/app/workspace/repo","swe-container","pytest","-v"],  #🎉
            capture_output=True, # Standard output aur error ko terminal par direct print karne ki jagah memory me hold karke result.stdout aur result.stderr me store kar leta hai.
            text=True ,    # Output raw binary bytes (b'...') me na mile, balki simple string formatted text me mile.
            )          

    return result


