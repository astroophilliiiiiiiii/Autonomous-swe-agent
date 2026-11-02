import pytest
from backend.error_handler import format_llm_error

def test_rate_limit_error_formatting():
    err = Exception("Rate limit reached for model openai/gpt-oss-120b in organization org: tokens per minute (TPM)")
    banner = format_llm_error(err)
    assert "RATE LIMIT REACHED" in banner
    assert "Wait 1 to 2 minutes" in banner
    assert "https://console.groq.com/settings/limits" in banner

def test_context_window_error_formatting():
    err = Exception("context_length_exceeded: maximum context length is 131072 tokens")
    banner = format_llm_error(err)
    assert "CONTEXT / TOKEN LIMIT EXCEEDED" in banner
    assert "maximum context window" in banner

def test_invalid_api_key_error_formatting():
    err = Exception("invalid_api_key: Invalid API Key provided (HTTP 401)")
    banner = format_llm_error(err)
    assert "INVALID OR MISSING API KEY" in banner
    assert ".env" in banner

def test_model_not_found_error_formatting():
    err = Exception("model_not_found: The model `llama-3.3-70b-versatile` does not exist (HTTP 404)")
    banner = format_llm_error(err)
    assert "MODEL NOT FOUND" in banner
    assert "backend/llm.py" in banner

