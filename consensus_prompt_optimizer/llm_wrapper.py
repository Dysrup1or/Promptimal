"""
LiteLLM wrapper with enforcement of single DeepSeek call policy.
"""

import json
from typing import Dict, Any, Optional
from litellm import completion
from config import DEEPSEEK_EXPAND, MAX_TOKENS_PER_CALL, EXPANDER_TOKEN_LIMIT
from utils import retry_with_backoff, log_event


# Global state to track DeepSeek usage
_deepseek_call_count = 0


class DeepSeekCallLimitExceeded(Exception):
    """Raised when attempting to make more than one DeepSeek call per run."""
    pass


def reset_deepseek_counter():
    """Reset the DeepSeek call counter. Call this at the start of each run."""
    global _deepseek_call_count
    _deepseek_call_count = 0


def get_deepseek_call_count() -> int:
    """Get the current DeepSeek call count."""
    return _deepseek_call_count


@retry_with_backoff(max_retries=3, initial_delay=1.0)
def call_llm(
    model: str,
    prompt: str,
    max_tokens: int = MAX_TOKENS_PER_CALL,
    enforce_json: bool = True,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """
    Call an LLM via LiteLLM with enforcement of single DeepSeek call policy.
    
    Args:
        model: LiteLLM model identifier (e.g., "gemini/gemini-1.5-flash")
        prompt: The prompt text to send
        max_tokens: Maximum tokens for the response
        enforce_json: Whether to enforce JSON output format
        temperature: Sampling temperature
    
    Returns:
        Dictionary containing 'content' (response text) and 'usage' (token counts)
    
    Raises:
        DeepSeekCallLimitExceeded: If attempting to make more than one DeepSeek call
    """
    global _deepseek_call_count
    
    # Enforce single DeepSeek call policy
    if DEEPSEEK_EXPAND in model:
        if _deepseek_call_count >= 1:
            raise DeepSeekCallLimitExceeded(
                "Only ONE DeepSeek call is allowed per run to maintain cost < $0.05"
            )
        _deepseek_call_count += 1
        # Enforce strict token limit for DeepSeek
        max_tokens = min(max_tokens, EXPANDER_TOKEN_LIMIT)
    
    # Prepare messages
    messages = [{"role": "user", "content": prompt}]
    
    # Log the call
    log_event("agent.call", {
        "model": model,
        "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt,
        "max_tokens": max_tokens,
    })
    
    # Make the API call
    try:
        response = completion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"} if enforce_json else None,
        )
        
        # Extract response content
        content = response.choices[0].message.content
        
        # Extract usage statistics
        usage = {
            "input_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') else 0,
            "output_tokens": response.usage.completion_tokens if hasattr(response, 'usage') else 0,
            "total_tokens": response.usage.total_tokens if hasattr(response, 'usage') else 0,
        }
        
        return {
            "content": content,
            "usage": usage,
        }
    
    except Exception as e:
        log_event("agent.error", {
            "model": model,
            "error": str(e),
        })
        raise


def parse_json_response(response: str) -> Dict[str, Any]:
    """
    Parse a JSON response string, handling common edge cases.
    
    Args:
        response: JSON string from LLM
    
    Returns:
        Parsed JSON dictionary
    
    Raises:
        json.JSONDecodeError: If the response is not valid JSON
    """
    # Strip markdown code blocks if present
    response = response.strip()
    if response.startswith("```json"):
        response = response[7:]
    if response.startswith("```"):
        response = response[3:]
    if response.endswith("```"):
        response = response[:-3]
    
    return json.loads(response.strip())
