import sys

def format_llm_error(error: Exception) -> str:
    """
    Parses Groq and LangChain API exceptions and returns a human-friendly,
    easy-to-read error banner with clear resolution steps.
    """
    err_str = str(error).lower()
    raw_msg = str(error)

    # 1. Rate Limit Error (TPM / RPM / RPD / 429)
    if "rate_limit" in err_str or "rate limit" in err_str or "429" in err_str or "tokens per minute" in err_str or "requests per minute" in err_str:
        return f"""
══════════════════════════════════════════════════════════════════════════════
🛑 GROQ API ERROR: RATE LIMIT REACHED (HTTP 429)
══════════════════════════════════════════════════════════════════════════════
What happened:
  You have temporarily exceeded your Groq account's rate limit:
  - Tokens Per Minute (TPM) or Requests Per Minute (RPM) threshold reached.

Details:
  {raw_msg}

How to fix:
  1. Wait 1 to 2 minutes for your quota window to refresh.
  2. Run the command again: python -m backend.main
  3. Check your real-time usage at: https://console.groq.com/settings/limits
══════════════════════════════════════════════════════════════════════════════"""

    # 2. Context Window / Token Limit Exceeded
    if "context_length_exceeded" in err_str or "maximum context length" in err_str or "context window" in err_str or "too large" in err_str or ("token" in err_str and "exceed" in err_str):
        return f"""
══════════════════════════════════════════════════════════════════════════════
🛑 GROQ API ERROR: CONTEXT / TOKEN LIMIT EXCEEDED
══════════════════════════════════════════════════════════════════════════════
What happened:
  The combined text of the prompt and selected code files exceeds the
  model's maximum context window (token limit).

Details:
  {raw_msg}

How to fix:
  1. The repository files being sent are too large.
  2. Narrow down your task to target fewer or smaller files.
  3. Or shorten your task description.
══════════════════════════════════════════════════════════════════════════════"""

    # 3. Authentication / Missing or Invalid API Key (401)
    if "invalid_api_key" in err_str or "authentication" in err_str or "401" in err_str or "api key" in err_str and "invalid" in err_str:
        return f"""
══════════════════════════════════════════════════════════════════════════════
🛑 GROQ API ERROR: INVALID OR MISSING API KEY (HTTP 401)
══════════════════════════════════════════════════════════════════════════════
What happened:
  Groq rejected the API key provided in your .env file.

Details:
  {raw_msg}

How to fix:
  1. Open the .env file in the project root.
  2. Ensure GROQ_API_KEY is set correctly.
  3. Verify or generate a new key at: https://console.groq.com/keys
══════════════════════════════════════════════════════════════════════════════"""

    # 4. Model Not Found or Inaccessible (404)
    if "model_not_found" in err_str or "does not exist" in err_str or "404" in err_str:
        return f"""
══════════════════════════════════════════════════════════════════════════════
🛑 GROQ API ERROR: MODEL NOT FOUND (HTTP 404)
══════════════════════════════════════════════════════════════════════════════
What happened:
  The configured LLM model does not exist or your account doesn't have access to it.

Details:
  {raw_msg}

How to fix:
  1. Open backend/llm.py
  2. Check the model name (default: openai/gpt-oss-120b).
  3. Check the full list of active models at: https://console.groq.com/docs/models
══════════════════════════════════════════════════════════════════════════════"""

    # 5. Service Temporarily Unavailable / Server Overload (503 / 500)
    if "503" in err_str or "overloaded" in err_str or "service unavailable" in err_str or "internal server error" in err_str:
        return f"""
══════════════════════════════════════════════════════════════════════════════
🛑 GROQ API ERROR: SERVICE TEMPORARILY OVERLOADED (HTTP 503)
══════════════════════════════════════════════════════════════════════════════
What happened:
  Groq API servers are currently experiencing high traffic or a temporary outage.

Details:
  {raw_msg}

How to fix:
  1. Wait 30-60 seconds and run the command again.
  2. Check the real-time status of Groq servers at: https://status.groq.com/
══════════════════════════════════════════════════════════════════════════════"""

    # 6. General fallback
    return f"""
══════════════════════════════════════════════════════════════════════════════
🛑 GROQ API ERROR
══════════════════════════════════════════════════════════════════════════════
Details:
  {raw_msg}

Suggestion:
  Please check your internet connection, API key, and Groq account status.
══════════════════════════════════════════════════════════════════════════════"""


def handle_llm_exception(error: Exception):
    """Prints formatted error and cleanly exits or re-raises."""
    banner = format_llm_error(error)
    print(banner, file=sys.stderr)

