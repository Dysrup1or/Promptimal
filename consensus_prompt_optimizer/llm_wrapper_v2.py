"""
LLM Wrapper v2 for Promptly - Enhanced with caching, compression, JSON mode.

Key v2 enhancements:
- SHA-256 idea hash caching (avoid re-running identical ideas)
- Prompt compression for token efficiency
- JSON mode enforcement for structured outputs
- Temperature=0 for deterministic results
- Token tracking with sub-penny cost calculation
"""

import os
import json
import hashlib
import tiktoken
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from .config import DEEPSEEK_CHEAP, GEMINI_FAST, DEEPSEEK_TOKEN_CAP


# ============================================================================
# COST CONSTANTS (as of June 2025)
# ============================================================================
COST_PER_1M = {
    DEEPSEEK_CHEAP: {"input": 0.14, "output": 0.28},
    GEMINI_FAST: {"input": 0.0, "output": 0.0},  # Free tier
}

# Cache directory
CACHE_DIR = Path(__file__).parent.parent / ".prompt_cache"


# ============================================================================
# TOKEN COUNTING
# ============================================================================
def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count tokens using tiktoken.
    
    Note: tiktoken doesn't have Gemini/DeepSeek encodings, 
    so we use cl100k_base as a reasonable approximation.
    """
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Fallback: ~4 chars per token
        return len(text) // 4


def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate cost in dollars for a given model call."""
    if model not in COST_PER_1M:
        return 0.0
    
    costs = COST_PER_1M[model]
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return input_cost + output_cost


# ============================================================================
# PROMPT COMPRESSION
# ============================================================================
def compress_prompt(prompt: str, max_chars: int = 8000) -> str:
    """
    Compress prompt by removing excessive whitespace and truncating if needed.
    
    Techniques applied:
    1. Normalize whitespace (multiple spaces → single)
    2. Normalize newlines (multiple → single)
    3. Remove leading/trailing whitespace from lines
    4. Truncate with indicator if over max_chars
    """
    import re
    
    # Normalize whitespace
    compressed = re.sub(r' +', ' ', prompt)
    compressed = re.sub(r'\n{3,}', '\n\n', compressed)
    
    # Strip lines
    lines = [line.strip() for line in compressed.split('\n')]
    compressed = '\n'.join(lines)
    
    # Truncate if needed
    if len(compressed) > max_chars:
        compressed = compressed[:max_chars - 50] + "\n[TRUNCATED FOR TOKEN LIMIT]"
    
    return compressed


# ============================================================================
# SHA-256 CACHING
# ============================================================================
def get_idea_hash(idea: str) -> str:
    """Generate SHA-256 hash of idea for cache key."""
    return hashlib.sha256(idea.strip().lower().encode()).hexdigest()[:16]


def cache_path(idea_hash: str) -> Path:
    """Get cache file path for an idea hash."""
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{idea_hash}.json"


def load_from_cache(idea: str) -> Optional[Dict[str, Any]]:
    """Load cached result if it exists and is valid."""
    idea_hash = get_idea_hash(idea)
    path = cache_path(idea_hash)
    
    if not path.exists():
        return None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            cached = json.load(f)
        
        # Check cache version compatibility
        if cached.get("version") != "v2":
            return None
        
        return cached
    except Exception:
        return None


def save_to_cache(idea: str, result: Dict[str, Any]) -> None:
    """Save result to cache."""
    idea_hash = get_idea_hash(idea)
    path = cache_path(idea_hash)
    
    cached = {
        "version": "v2",
        "idea": idea,
        "timestamp": datetime.now().isoformat(),
        "result": result
    }
    
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cached, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save cache: {e}")


def clear_cache() -> int:
    """Clear all cached results. Returns count of files deleted."""
    if not CACHE_DIR.exists():
        return 0
    
    count = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
        count += 1
    return count


# ============================================================================
# LLM CALL WRAPPER (v2)
# ============================================================================
def call_llm_v2(
    model: str,
    prompt: str,
    max_tokens: int = 500,
    temperature: float = 0.0,
    enforce_json: bool = False,
    compress: bool = True
) -> Dict[str, Any]:
    """
    Enhanced LLM call with v2 features.
    
    Args:
        model: Model identifier (GEMINI_FAST or DEEPSEEK_CHEAP)
        prompt: The prompt to send
        max_tokens: Maximum response tokens
        temperature: Sampling temperature (default 0 for determinism)
        enforce_json: If True, add JSON mode instruction
        compress: If True, apply prompt compression
    
    Returns:
        Dict with keys: content, input_tokens, output_tokens, cost, model
    """
    import litellm
    
    # Apply compression if enabled
    if compress:
        prompt = compress_prompt(prompt)
    
    # Count input tokens
    input_tokens = count_tokens(prompt, model)
    
    # Enforce token cap for DeepSeek
    if model == DEEPSEEK_CHEAP and max_tokens > DEEPSEEK_TOKEN_CAP:
        max_tokens = DEEPSEEK_TOKEN_CAP
    
    # Build messages
    messages = [{"role": "user", "content": prompt}]
    
    # Add JSON mode hint if requested
    if enforce_json:
        messages[0]["content"] += "\n\n[IMPORTANT: Your response MUST be valid JSON only. No text before or after the JSON object. Start with { and end with }]"
    
    # Build API call kwargs
    api_kwargs = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    
    # Add response_format for JSON mode (supported by Gemini and newer models)
    if enforce_json:
        api_kwargs["response_format"] = {"type": "json_object"}
    
    # Make API call
    try:
        response = litellm.completion(**api_kwargs)
        
        content = response.choices[0].message.content
        output_tokens = count_tokens(content, model)
        cost = calculate_cost(input_tokens, output_tokens, model)
        
        return {
            "content": content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "model": model,
            "success": True
        }
        
    except Exception as e:
        return {
            "content": "",
            "input_tokens": input_tokens,
            "output_tokens": 0,
            "cost": 0.0,
            "model": model,
            "success": False,
            "error": str(e)
        }


def parse_json_response_v2(content: str) -> Dict[str, Any]:
    """
    Parse JSON from LLM response with enhanced error handling.
    
    Handles common issues:
    - Markdown code blocks (```json ... ```)
    - Leading/trailing whitespace
    - Single quotes instead of double quotes
    - Trailing commas
    - Text before/after JSON object
    """
    import re
    
    # Strip whitespace
    content = content.strip()
    
    # Remove markdown code blocks
    if content.startswith("```"):
        # Extract content between ``` markers
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if match:
            content = match.group(1).strip()
    
    # If content doesn't start with {, try to find JSON object in the text
    if not content.startswith("{"):
        # Look for JSON object anywhere in the response
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            content = match.group()
    
    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Try fixing common issues
    try:
        # Replace single quotes with double quotes (naive approach)
        fixed = content.replace("'", '"')
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    
    # Try removing trailing commas
    try:
        fixed = re.sub(r',\s*}', '}', content)
        fixed = re.sub(r',\s*]', ']', fixed)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    
    # Last resort: try to find any JSON object
    try:
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        pass
    
    # Check if response appears truncated (no closing brace)
    if content.count('{') > content.count('}'):
        raise ValueError(
            f"Response appears truncated (token limit may be too low). "
            f"Open braces: {content.count('{')}, Close braces: {content.count('}')}. "
            f"Consider increasing DEEPSEEK_TOKEN_CAP. Preview: {content[:150]}..."
        )
    
    # Failed to parse
    raise ValueError(f"Failed to parse JSON from response: {content[:200]}...")


# ============================================================================
# TOKEN TRACKER
# ============================================================================
class TokenTracker:
    """Track token usage and cost across a pipeline run."""
    
    def __init__(self):
        self.calls = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
    
    def record(self, result: Dict[str, Any], stage: str):
        """Record a call result."""
        self.calls.append({
            "stage": stage,
            "model": result.get("model"),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "cost": result.get("cost", 0.0)
        })
        self.total_input_tokens += result.get("input_tokens", 0)
        self.total_output_tokens += result.get("output_tokens", 0)
        self.total_cost += result.get("cost", 0.0)
    
    def summary(self) -> Dict[str, Any]:
        """Get usage summary."""
        return {
            "total_calls": len(self.calls),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost, 6),
            "by_stage": self.calls
        }
    
    def is_under_budget(self, budget: float = 0.025) -> bool:
        """Check if under budget."""
        return self.total_cost <= budget
