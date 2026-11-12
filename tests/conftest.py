import os

# backend.llm creates the Groq client at import time, which requires an API key.
# Unit tests mock all LLM calls, so a placeholder key is enough.
os.environ.setdefault("GROQ_API_KEY", "test-key")
