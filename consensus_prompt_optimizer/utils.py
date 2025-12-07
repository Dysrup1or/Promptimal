"""
Utility functions for the Consensus Prompt Optimizer.
Includes token estimation, cost calculation, retry logic, and telemetry hooks.
"""

import time
import json
from typing import Any, Callable, Dict
from functools import wraps
from .config import PRICES_USD


# ============================================================================
# TOKEN ESTIMATION
# ============================================================================
def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a given text.
    Uses a simple heuristic: ~4 characters per token.
    
    For production, consider using tiktoken for accurate counts.
    """
    return max(1, len(text) // 4)


# ============================================================================
# COST ESTIMATION
# ============================================================================
def estimate_cost_usd(model_name: str, input_tokens: int, output_tokens: int = 0) -> float:
    """
    Estimate the cost in USD for a given model and token count.
    
    Args:
        model_name: LiteLLM model identifier (e.g., "gemini/gemini-1.5-flash")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens (default: 0)
    
    Returns:
        Estimated cost in USD
    """
    if model_name not in PRICES_USD:
        # Unknown model, return conservative estimate
        return (input_tokens + output_tokens) * 0.0000001
    
    pricing = PRICES_USD[model_name]
    input_cost = input_tokens * pricing["input"]
    output_cost = output_tokens * pricing["output"]
    
    return input_cost + output_cost


# ============================================================================
# RETRY LOGIC
# ============================================================================
def retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0):
    """
    Decorator to retry a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        print(f"All {max_retries} retries exhausted.")
            
            raise last_exception
        
        return wrapper
    return decorator


# ============================================================================
# TELEMETRY HOOKS (Placeholder for Langfuse integration)
# ============================================================================
def log_event(event_type: str, data: Dict[str, Any]) -> None:
    """
    Log an event for telemetry tracking.
    
    This is a placeholder function. In production, integrate with Langfuse:
    - run.start: Log the beginning of a run with metadata
    - agent.call: Log each agent invocation with input/output
    - run.end: Log the completion of a run with results
    
    Args:
        event_type: Type of event (e.g., "run.start", "agent.call", "run.end")
        data: Event data dictionary
    """
    # TODO: Integrate with Langfuse or similar telemetry service
    # from langfuse import Langfuse
    # langfuse = Langfuse()
    # langfuse.log(event_type, data)
    
    # For now, just print to stdout (development only)
    print(f"[TELEMETRY] {event_type}: {json.dumps(data, indent=2)}")


# ============================================================================
# JSON VALIDATION
# ============================================================================
def validate_json_schema(data: Dict[str, Any], required_keys: list) -> bool:
    """
    Validate that a JSON object contains all required keys.
    
    Args:
        data: JSON object to validate
        required_keys: List of required key names
    
    Returns:
        True if all keys are present, False otherwise
    """
    return all(key in data for key in required_keys)


# ============================================================================
# SEED MANAGEMENT
# ============================================================================
def set_seed(seed: int) -> None:
    """
    Set random seed for reproducibility.
    
    Args:
        seed: Random seed value
    """
    import random
    random.seed(seed)
    # Note: LLM calls may still have non-deterministic behavior
    # depending on the provider's implementation
