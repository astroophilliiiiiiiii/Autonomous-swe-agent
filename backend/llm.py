from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv() # loads all dotenv variables 

llm = ChatGroq( model="openai/gpt-oss-120b") # model created llama-3.3-70b-versatile