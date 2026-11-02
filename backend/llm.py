from dotenv import load_dotenv
from langchain_groq import ChatGroq

# Load environment variables from .env file
load_dotenv()

# Active model configured for Groq
llm = ChatGroq(model="openai/gpt-oss-120b")
