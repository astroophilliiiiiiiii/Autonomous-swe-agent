import subprocess # to run command from terminal 
import sys # Function ko cloned repository ka path milega.
import os # Current computer ke environment variables ki copy bana lo.

#Python mein usko list ke form mein dete hain: ["pytest"] 
# Agar command hoti: ( python test.py ) toh: ["python", "test.py"]

#🎉🎉🎉--Pehle tum direct pytest naam ke tool ko bulane ki koshish kar rahi thi, jo Windows ko nahi mil raha tha.
#Naye code mein tumne pehle Python ko bulaya, aur Python ko bola ki "bhai, apne andar se pytest naam ka module chalana shuru kar". Kyunki Python wahi hai, usne bina kisi error ke usko chala diya.
def run_tests(repo_path): # input -- repository path 
    env = os.environ.copy() # Jo current system variables mere paas hain, un sabhi ki ek duplicate copy bana kar env naam ke dictionary variable mein rakh lo
    # jo usme predefined PYTHONPATH ko ni change krna isliye copy made !! 
    
    full_src_path = os.path.abspath(os.path.join(repo_path, "src")) # isko full absolute path bnado --C:\Users\Kriti\...\workspace\repo\src
    env["PYTHONPATH"] = full_src_path #Python jab bhi koi file import karne jata hai, 
    #toh woh ek khas list dekhta hai jise PYTHONPATH bolte hain -- isme original code jo hai 
    
    # python -m pytest ( jis Python se tumhara current program chal raha hai, us Python ka exact path. )
    result = subprocess.run([sys.executable, "-m", "pytest"],  #🎉🎉🎉🎉🎉🎉
            cwd=repo_path,       # isko kahan run krna h -- jahanpe cloned repo h vahin run it
            capture_output=True, # Standard output aur error ko terminal par direct print karne ki jagah memory me hold karke result.stdout aur result.stderr me store kar leta hai.
            text=True ,    # Output raw binary bytes (b'...') me na mile, balki simple string formatted text me mile.
            env = env # original code h isme 
            )          

    return result

# You actually have two Zomato apps (two Python environments) on your computer right now:
# Your main computer's Python (Python314).
# Your project's Virtual Environment (venv).
# You likely installed pytest on one of them, but your script is accidentally trying to open the other one!
# To fix this permanently, we need to tell your script: "Don't just guess where Python is. Use the exact same Python that is running this script right now!
#sys.executable is a magic trick in Python that ensures it always uses the current active environment.


# Ab env mein same variables hain, but ye separate copy hai.
# Phir hum is copy mein apni setting add/change kar sakte hain:
# env["PYTHONPATH"] = full_src_path
# without directly changing the original os.environ.
