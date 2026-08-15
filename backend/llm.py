from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv() # loads all dotenv variables 

llm = ChatGroq( model="llama-3.1-8b-instant") # model created 

