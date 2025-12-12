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

# Groq-hosted Llama for Expander (FAST: 280 TPS, replaces DeepSeek)
GROQ_EXPAND = "groq/llama-3.3-70b-versatile"

# Legacy: DeepSeek (removed - was too slow at 50 TPS)
# Use GROQ_EXPAND for all expansion tasks

# ============================================================================
# PRICING (USD per token)
# ============================================================================
# These are approximate costs; update based on current provider pricing
PRICES_USD = {
    "gemini/gemini-2.0-flash": {
        "input": 0.00000000,  # Gemini Flash is free tier for now
        "output": 0.00000000,
    },
    # Groq Llama 3.3 70B - Primary Expander model
    "groq/llama-3.3-70b-versatile": {
        "input": 0.00000059,   # $0.59 per 1M input tokens
        "output": 0.00000079,  # $0.79 per 1M output tokens
    },
    # Groq Llama 3.1 8B - Faster alternative (if needed)
    "groq/llama-3.1-8b-instant": {
        "input": 0.00000005,   # $0.05 per 1M input tokens
        "output": 0.00000008,  # $0.08 per 1M output tokens
    },
    # DeepSeek (legacy, kept for fallback)
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

# Groq token cap for Expander (Llama 3.3 70B has 32K output limit)
GROQ_TOKEN_CAP = 4000       # Output limit for Expander stage

# ============================================================================
# RATE LIMITING & TIERS (Sustainable SaaS Model)
# ============================================================================
# Flow (Free) tier - 40 Catalyze Credits (CCs) per month
FLOW_TIER_MONTHLY_LIMIT = 40       # Free tier: 40 CCs/month
FREE_TIER_MONTHLY_LIMIT = 40       # Alias for backward compatibility

# Synapse (Pro) tier - $19.99/month, 300 CCs
SYNAPSE_TIER_MONTHLY_LIMIT = 300   # Pro tier: 300 CCs/month
PRO_TIER_MONTHLY_LIMIT = 300       # Alias for backward compatibility

# Enterprise tier - unlimited
ENTERPRISE_TIER_LIMIT = None       # Unlimited for enterprise

# Cost metrics
COST_PER_REQUEST_AVG = 0.01375     # Average COGS per CC (~$0.01375)
OVERAGE_PRICE_PER_CC = 0.08        # Pay-as-you-go overage rate ($0.08/CC)

# ============================================================================
# API KEYS
# ============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # Primary for Expander
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
