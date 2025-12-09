"""
Configuration module for Consensus Prompt Optimizer.
Defines model routing, pricing, and environment settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# MODEL NAMES (LiteLLM format)
# ============================================================================
GEMINI_FAST = "gemini/gemini-2.0-flash"  # Updated to 2.0 (1.5 deprecated)
DEEPSEEK_EXPAND = "deepseek/deepseek-chat"
DEEPSEEK_CHEAP = "deepseek/deepseek-chat"  # Alias for v2 compatibility

# ============================================================================
# PRICING (USD per token)
# ============================================================================
# These are approximate costs; update based on current provider pricing
PRICES_USD = {
    "gemini/gemini-2.0-flash": {
        "input": 0.00000000,  # Gemini Flash is free tier for now
        "output": 0.00000000,
    },
    "deepseek/deepseek-chat": {
        "input": 0.00000014,   # $0.14 per 1M input tokens
        "output": 0.00000028,  # $0.28 per 1M output tokens
    },
}

# ============================================================================
# TOKEN & ITERATION LIMITS
# ============================================================================
# NOTE: These are generous limits for personal testing.
# Reduce for production/multi-user to control costs.
MAX_TOKENS_PER_CALL = 4000  # Hard cap per LLM call (increased for testing)
MAX_CRITIC_ITERATIONS = 3   # Maximum refinement cycles
EXPANDER_TOKEN_LIMIT = 350  # Legacy v1 limit (not used in v2)
DEEPSEEK_TOKEN_CAP = 4000   # v2: DeepSeek output limit (~$0.0011 max)

# ============================================================================
# RATE LIMITING & COST CONTROLS (Production Safety)
# ============================================================================
# Free tier limits - adjust for paid tiers
FREE_TIER_MONTHLY_LIMIT = 100   # Max requests per user per month
COST_PER_REQUEST_AVG = 0.0012   # Average cost per optimization (~$0.0012)
MAX_MONTHLY_COST_FREE_USER = FREE_TIER_MONTHLY_LIMIT * COST_PER_REQUEST_AVG  # ~$0.12

# Paid tier limits (for future implementation)
PRO_TIER_MONTHLY_LIMIT = 500    # Pro users get 500/month
ENTERPRISE_TIER_LIMIT = None    # Unlimited for enterprise

# ============================================================================
# API KEYS
# ============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # LiteLLM may need this set

# ============================================================================
# TELEMETRY (Optional)
# ============================================================================
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
TELEMETRY_ENABLED = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)

# ============================================================================
# DEFAULT SETTINGS
# ============================================================================
DEFAULT_SEED = 42
DEFAULT_TEMPERATURE = 0.7
