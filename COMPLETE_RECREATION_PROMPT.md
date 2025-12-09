# PROMPTLY 3.0 - COMPLETE CODEBASE RECREATION PROMPT

## Mission Statement

You are tasked with recreating the **Promptly 3.0** application from scratch. This is a production-grade AI-powered prompt engineering platform with authentication, usage tracking, and a sophisticated 5-stage prompt optimization pipeline. The codebase must be implemented **exactly** as specified below, with no ambiguity or deviation.

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Directory Structure](#2-directory-structure)
3. [Configuration & Environment](#3-configuration--environment)
4. [Core Pipeline Module](#4-core-pipeline-module)
5. [Authentication System](#5-authentication-system)
6. [Web UI (Streamlit)](#6-web-ui-streamlit)
7. [Admin CLI](#7-admin-cli)
8. [Deployment Configuration](#8-deployment-configuration)
9. [Testing Suite](#9-testing-suite)
10. [Implementation Checklist](#10-implementation-checklist)

---

## 1. System Architecture Overview

### 1.1 Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Runtime | Python | 3.11.9 |
| Web Framework | Streamlit | ≥1.28.0 |
| LLM Integration | LiteLLM | ≥1.0.0 |
| Schema Validation | Pydantic | ≥2.0.0 |
| Password Hashing | bcrypt | ≥4.0.0 |
| Database (local) | SQLite | Built-in |
| Database (production) | PostgreSQL | Via psycopg2-binary ≥2.9.0 |
| Logging | Loguru | ≥0.7.0 |
| Token Counting | tiktoken | ≥0.5.0 |
| Environment | python-dotenv | ≥1.0.0 |
| Testing | pytest | ≥7.4.0 |

### 1.2 LLM Models Used

| Model | LiteLLM Identifier | Purpose | Cost |
|-------|-------------------|---------|------|
| Gemini 2.0 Flash | `gemini/gemini-2.0-flash` | Discerner, CriticFirst, Ranker, Synthesizer | Free |
| DeepSeek Chat | `deepseek/deepseek-chat` | Expander (variation generation) | $0.14/1M input, $0.28/1M output |

### 1.3 Pipeline Architecture (Judge-then-Generate)

The core innovation is the **Judge-then-Generate** workflow:

```
User Idea → Discerner → CriticFirst (Rubric) → Expander → Ranker → Synthesizer → Final Prompt
             (Gemini)     (Gemini)              (DeepSeek)  (Gemini)   (Gemini)
```

**Key Constraints:**
- DeepSeek is called **exactly ONCE** per run (in Expander stage)
- Total cost per run ≤ $0.025
- All stage outputs are validated with Pydantic schemas
- Temperature = 0 for deterministic results
- JSON mode enforced for structured outputs

---

## 2. Directory Structure

```
Promptly/
├── .env                          # Environment variables (NEVER commit)
├── .env.example                  # Example environment file
├── .gitignore                    # Git ignore rules
├── Procfile                      # Railway/Heroku deployment
├── railway.json                  # Railway config-as-code
├── runtime.txt                   # Python version specification
├── requirements.txt              # Python dependencies
├── app.py                        # Main Streamlit web application
├── admin_cli.py                  # Admin command-line tool
│
├── consensus_prompt_optimizer/   # Core pipeline module
│   ├── __init__.py              # Module exports
│   ├── config.py                # Configuration & constants
│   ├── schemas.py               # Pydantic schemas for all stages
│   ├── llm_wrapper_v2.py        # LLM API wrapper with caching
│   ├── orchestrator.py          # Main pipeline orchestrator
│   ├── utils.py                 # Utility functions
│   ├── critic_first.py          # (Optional) Stage-specific logic
│   ├── expander.py              # (Optional) Stage-specific logic
│   ├── ranker.py                # (Optional) Stage-specific logic
│   └── synthesizer.py           # (Optional) Stage-specific logic
│
├── auth/                         # Authentication module
│   ├── __init__.py              # Module exports
│   ├── database.py              # SQLite/PostgreSQL abstraction
│   ├── models.py                # User, Session, Usage dataclasses
│   ├── auth_service.py          # Authentication operations
│   ├── usage_service.py         # Usage tracking operations
│   └── logger.py                # Structured logging (Loguru)
│
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_v2.py               # Unit tests for v2 pipeline
│   └── test_integration.py      # Integration tests (requires API keys)
│
├── data/                         # Local data storage
│   └── promptly.db              # SQLite database (auto-created)
│
├── logs/                         # Log files (auto-created)
│   ├── promptly_YYYY-MM-DD.log
│   └── errors_YYYY-MM-DD.log
│
└── .prompt_cache/               # LLM response cache (auto-created)
    └── <sha256_hash>.json
```

---

## 3. Configuration & Environment

### 3.1 `.env.example` (Template)

```env
# ==============================================
# PROMPTLY 3.0 - ENVIRONMENT CONFIGURATION
# ==============================================

# LLM API Keys (Required)
GEMINI_API_KEY=your_gemini_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Optional: OpenAI (for fallback/testing)
OPENAI_API_KEY=

# Database (Railway sets this automatically)
# DATABASE_URL=postgresql://user:pass@host:port/db

# Logging
LOG_LEVEL=INFO

# Optional: Langfuse Telemetry
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

### 3.2 `requirements.txt` (Exact)

```
# ==============================================
# PROMPTLY 3.0 - DEPENDENCIES
# ==============================================
# Core dependencies for production deployment
# ==============================================

# LLM Integration
litellm>=1.0.0

# Environment & Config
python-dotenv>=1.0.0

# Token Counting
tiktoken>=0.5.0

# Schema Validation
pydantic>=2.0.0

# Web UI
streamlit>=1.28.0

# Authentication
bcrypt>=4.0.0

# Database (PostgreSQL support for Railway)
psycopg2-binary>=2.9.0

# Logging
loguru>=0.7.0

# Development/Testing (optional - can be removed for production)
pytest>=7.4.0
```

### 3.3 `consensus_prompt_optimizer/config.py` (Complete)

```python
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
GEMINI_FAST = "gemini/gemini-2.0-flash"  # Free tier
DEEPSEEK_CHEAP = "deepseek/deepseek-chat"

# ============================================================================
# PRICING (USD per token)
# ============================================================================
PRICES_USD = {
    "gemini/gemini-2.0-flash": {
        "input": 0.00000000,  # Free tier
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
MAX_TOKENS_PER_CALL = 4000  # Hard cap per LLM call
DEEPSEEK_TOKEN_CAP = 4000   # DeepSeek output limit

# ============================================================================
# RATE LIMITING & COST CONTROLS
# ============================================================================
FREE_TIER_MONTHLY_LIMIT = 100   # Max requests per user per month
PRO_TIER_MONTHLY_LIMIT = 500    # Pro users get 500/month
ENTERPRISE_TIER_LIMIT = None    # Unlimited for enterprise

# ============================================================================
# API KEYS
# ============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

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
```

---

## 4. Core Pipeline Module

### 4.1 Pydantic Schemas (`consensus_prompt_optimizer/schemas.py`)

**Required schemas with exact field definitions:**

#### DiscernOutput (Stage 1)
```python
class DiscernOutput(BaseModel):
    task_type: str  # classification|generation|analysis|transformation|other
    complexity: str  # simple|moderate|complex
    domain: str  # general|technical|creative|analytical
    key_requirements: List[str]
    potential_pitfalls: List[str]
    recommended_approach: str
```

#### RubricOutput (Stage 2 - CriticFirst)
```python
class RubricOutput(BaseModel):
    rubric: Dict[str, str]  # Key criteria with descriptions
    checklist: List[str]  # 6-10 checkable items
    red_flags: List[str]  # 3-5 anti-patterns to avoid
    variation_guidance: Dict[str, str] = {}  # Optional A/B/C specific instructions
```

#### ExpansionsOutput (Stage 3)
```python
class ExpansionVariant(BaseModel):
    prompt: str  # The actual prompt text
    notes: str  # Brief approach notes
    checklist_score: str  # e.g., "4/6 items addressed"

class ExpansionsOutput(BaseModel):
    A: ExpansionVariant
    B: ExpansionVariant
    C: ExpansionVariant
```

#### RankingsOutput (Stage 4)
```python
class RankerVariant(BaseModel):
    rank: int  # 1=best, 2=middle, 3=worst (must be unique)
    score: float  # 0.0-1.0 quality score

class RankingsOutput(BaseModel):
    A: RankerVariant
    B: RankerVariant
    C: RankerVariant
    # Validator: ranks must be unique (1, 2, 3 each used exactly once)
```

#### SynthesizerOutput (Stage 5)
```python
class SynthesizerOutput(BaseModel):
    final_prompt: str  # The final optimized prompt
    synthesis_notes: str  # Explanation of synthesis decisions
    rubric_compliance: Dict[str, str]  # How each criterion was addressed
    confidence: float  # 0.0-1.0 confidence score
```

#### Anti-Lame Checklist (Universal)
```python
ANTI_LAME_CHECKLIST = [
    "Specifies exact output format (JSON schema or structured template)",
    "Includes explicit role/persona for the assistant",
    "Contains step-by-step reasoning instructions (CoT)",
    "Has anti-hallucination guardrail: 'say I don't know if uncertain'",
    "Requires sources/citations for factual claims",
    "Defines success criteria or evaluation rubric",
    "Addresses identified ambiguities from discern stage",
    "Includes concrete examples or few-shot demonstrations",
    "Sets appropriate scope boundaries (what NOT to do)",
    "Uses action verbs (analyze, generate, compare, NOT 'help with')",
    "Specifies target audience context",
    "Has fallback instructions for edge cases",
]
```

### 4.2 LLM Wrapper (`consensus_prompt_optimizer/llm_wrapper_v2.py`)

**Required functions:**

| Function | Purpose | Key Details |
|----------|---------|-------------|
| `count_tokens(text, model)` | Count tokens using tiktoken | Uses cl100k_base encoding |
| `calculate_cost(input_tokens, output_tokens, model)` | Calculate USD cost | Returns float |
| `compress_prompt(prompt, max_chars=8000)` | Compress prompt for efficiency | Normalizes whitespace, truncates if needed |
| `get_idea_hash(idea)` | SHA-256 hash for caching | Returns first 16 chars of hex digest |
| `load_from_cache(idea)` | Load cached result | Returns None if not found |
| `save_to_cache(idea, result)` | Save result to cache | Creates .prompt_cache/ directory |
| `call_llm_v2(model, prompt, max_tokens, temperature, enforce_json, compress)` | Main API call | Returns dict with content, tokens, cost, success |
| `parse_json_response_v2(content)` | Parse JSON from LLM | Handles markdown blocks, trailing commas, etc. |

**TokenTracker class:**
```python
class TokenTracker:
    def __init__(self): ...
    def record(self, result: Dict, stage: str): ...
    def summary(self) -> Dict: ...  # Returns total_calls, tokens, cost, by_stage
    def is_under_budget(self, budget=0.025) -> bool: ...
```

### 4.3 Orchestrator (`consensus_prompt_optimizer/orchestrator.py`)

**PromptimaV2 class with exact stage flow:**

```python
class PromptimaV2:
    def __init__(self, use_cache: bool = True, dry_run: bool = False):
        self.use_cache = use_cache
        self.dry_run = dry_run
        self.tracker = TokenTracker()
    
    def run(self, idea: str) -> Dict[str, Any]:
        # 1. Check cache
        # 2. Stage 1: Discerner (Gemini)
        # 3. Stage 2: CriticFirst (Gemini) - Rubric BEFORE expansion
        # 4. Stage 3: Expander (DeepSeek - SINGLE CALL)
        # 5. Stage 4: Ranker (Gemini)
        # 6. Stage 5: Synthesizer (Gemini)
        # 7. Build and return output
```

**Stage prompts must include:**
- DISCERNER_PROMPT: Analyze task type, complexity, domain, requirements, pitfalls
- CRITIC_FIRST_PROMPT: Generate rubric criteria, checklist, red flags
- EXPANDER_PROMPT: Generate 3 variations with rubric guidance
- RANKER_PROMPT: Rank variations 1-3 with scores
- SYNTHESIZER_PROMPT: Synthesize final prompt from ranked variations

**Output JSON structure:**
```json
{
  "version": "v2",
  "timestamp": "ISO8601",
  "original_idea": "...",
  "task_analysis": { /* DiscernOutput */ },
  "rubric": {
    "criteria": { /* key: description */ },
    "checklist": ["..."],
    "red_flags": ["..."]
  },
  "variations": {
    "A": { "prompt": "...", "notes": "...", "checklist_score": "...", "rank": 1, "score": 0.9 },
    "B": { /* ... */ },
    "C": { /* ... */ }
  },
  "final_synthesis": {
    "prompt": "...",
    "notes": "...",
    "rubric_compliance": { /* criterion: how addressed */ },
    "confidence": 0.85
  },
  "usage": {
    "total_calls": 5,
    "total_input_tokens": 1234,
    "total_output_tokens": 5678,
    "total_cost_usd": 0.0012,
    "by_stage": [ /* per-stage breakdown */ ]
  }
}
```

---

## 5. Authentication System

### 5.1 Database Schema

**6 tables with exact schema:**

#### users
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- SERIAL for PostgreSQL
    email TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    tier TEXT DEFAULT 'free',  -- 'free', 'pro', 'enterprise'
    email_verified INTEGER DEFAULT 0,  -- BOOLEAN for PostgreSQL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### sessions
```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    session_token TEXT UNIQUE NOT NULL,  -- SHA-256 hash of actual token
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);
```

#### usage
```sql
CREATE TABLE usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, month, year)
);
```

#### waitlist
```sql
CREATE TABLE waitlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### password_reset_tokens
```sql
CREATE TABLE password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    token TEXT UNIQUE NOT NULL,  -- SHA-256 hash
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used INTEGER DEFAULT 0  -- BOOLEAN for PostgreSQL
);
```

#### email_verification_tokens
```sql
CREATE TABLE email_verification_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    token TEXT UNIQUE NOT NULL,  -- SHA-256 hash
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used INTEGER DEFAULT 0  -- BOOLEAN for PostgreSQL
);
```

### 5.2 Database Abstraction (`auth/database.py`)

**Dual database support:**
- If `DATABASE_URL` environment variable is set → Use PostgreSQL
- Otherwise → Use SQLite at `data/promptly.db`

**Required features:**
- Connection pooling for PostgreSQL (SimpleConnectionPool, 1-10 connections)
- PostgresCursor wrapper to translate `?` → `%s` placeholders
- PostgresRowWrapper to make psycopg2 results behave like sqlite3.Row
- Auto-migration for adding email_verified column to existing databases
- `reset_database()` function for testing (drops all tables)

### 5.3 Data Models (`auth/models.py`)

**User dataclass:**
```python
@dataclass
class User:
    id: int
    email: str
    first_name: str
    last_name: str
    password_hash: str
    tier: str = "free"
    email_verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def full_name(self) -> str: ...
    @property
    def is_pro(self) -> bool: ...  # tier in ("pro", "enterprise")
    @property
    def is_enterprise(self) -> bool: ...
    @classmethod
    def from_row(cls, row) -> "User": ...
```

**Session dataclass:**
```python
@dataclass
class Session:
    id: int
    user_id: int
    session_token: str
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    @property
    def is_expired(self) -> bool: ...
    @classmethod
    def from_row(cls, row) -> "Session": ...
```

**Usage dataclass:**
```python
@dataclass
class Usage:
    id: int
    user_id: int
    month: int
    year: int
    count: int = 0
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row) -> "Usage": ...
```

### 5.4 AuthService (`auth/auth_service.py`)

**Constants:**
- SESSION_DURATION_DAYS = 30
- PASSWORD_RESET_DURATION_HOURS = 1
- EMAIL_VERIFICATION_DURATION_HOURS = 24
- MIN_PASSWORD_LENGTH = 8
- MAX_NAME_LENGTH = 50

**Required methods:**

| Method | Purpose | Returns |
|--------|---------|---------|
| `validate_email(email)` | Validate email format | (bool, str) |
| `validate_password(password)` | Validate password requirements | (bool, str) |
| `validate_name(name, field)` | Validate name field | (bool, str) |
| `hash_password(password)` | Hash with bcrypt (12 rounds) | str |
| `verify_password(password, hash)` | Verify password | bool |
| `generate_session_token()` | Generate UUID4 token | str |
| `hash_token(token)` | SHA-256 hash | str |
| `create_session(user_id)` | Create session, return raw token | str |
| `validate_session(token)` | Validate and return User | Optional[User] |
| `delete_session(token)` | Delete session (logout) | None |
| `get_user_by_email(email)` | Get user by email | Optional[User] |
| `get_user_by_id(user_id)` | Get user by ID | Optional[User] |
| `email_exists(email)` | Check if email exists | bool |
| `register(email, first_name, last_name, password, confirm)` | Register new user | (User, token, error) |
| `login(email, password)` | Login user | (User, token, error) |
| `logout(token)` | Logout user | None |
| `add_to_waitlist(email)` | Add to waitlist | (bool, str) |
| `request_password_reset(email)` | Request password reset | (bool, message, token) |
| `reset_password(token, new_password, confirm)` | Reset password | (bool, message) |
| `create_verification_token(user_id)` | Create verification token | Optional[str] |
| `verify_email(token)` | Verify email | (bool, message) |
| `resend_verification_email(user_id)` | Resend verification | (bool, message, token) |
| `is_email_verified(user_id)` | Check verification status | bool |

**Security requirements:**
- Never reveal whether email exists (password reset always returns success message)
- Invalidate all sessions on password reset
- Hash tokens before storing in database
- Use secrets.token_urlsafe(32) for reset/verification tokens

### 5.5 UsageService (`auth/usage_service.py`)

**Tier limits:**
```python
TIER_LIMITS = {
    "free": 100,      # 100 requests/month
    "pro": 500,       # 500 requests/month
    "enterprise": None  # Unlimited
}
```

**Required methods:**

| Method | Purpose | Returns |
|--------|---------|---------|
| `get_limit_for_tier(tier)` | Get monthly limit | Optional[int] |
| `get_usage(user_id, month, year)` | Get/create usage record | Usage |
| `increment_usage(user_id, month, year)` | Increment count | Usage |
| `check_limit(user_id, tier, month, year)` | Check if within limit | (bool, count, limit) |
| `get_remaining(user_id, tier, month, year)` | Get remaining requests | Optional[int] |
| `get_usage_percentage(user_id, tier, month, year)` | Get usage as percentage | float |
| `reset_usage(user_id, month, year)` | Reset count (admin) | None |

### 5.6 Structured Logging (`auth/logger.py`)

**Configuration:**
- Console output with color coding (disabled in production)
- Rotating file logs: 10MB rotation, 7 day retention, zip compression
- Separate error log: 30 day retention
- Production detection: `RAILWAY_ENVIRONMENT` or `DATABASE_URL` set

**Helper functions:**
```python
def log_auth_event(event, email=None, user_id=None, success=True, **kwargs): ...
def log_usage_event(user_id, action, tokens=0, **kwargs): ...
def log_llm_call(model, prompt_tokens, completion_tokens, duration_ms, success=True, error=None): ...
def log_db_operation(operation, table, duration_ms=None, success=True, error=None, **kwargs): ...
def log_request(endpoint, method="GET", user_id=None, duration_ms=None, status=200): ...
def mask_email(email) -> str: ...  # j***@example.com
def mask_sensitive(value, show_chars=4) -> str: ...
```

---

## 6. Web UI (Streamlit)

### 6.1 Page Configuration

```python
st.set_page_config(
    page_title="Promptly - AI Prompt Engineering",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)
```

### 6.2 Authentication Flow

1. **Session initialization:**
   - Check for `session_token` in `st.session_state`
   - If exists, validate with `auth_service.validate_session()`
   - If valid, set `current_user`; if invalid, clear token

2. **Auth gate:**
   - If no `current_user`, show login/register page and call `st.stop()`
   - Auth page has tabs: Login, Register
   - Login has "Forgot password?" link → forgot_password view
   - Register collects: email, first_name, last_name, password, confirm_password

3. **Password reset flow:**
   - forgot_password → enter email → receive token (shown in dev mode)
   - reset_password → enter new password + confirm → success → redirect to login

### 6.3 Sidebar Components

1. **User Profile:**
   - Full name, email, tier badge (FREE/PRO/ENTERPRISE)
   - Email verification status (✓ verified / ⚠ not verified + resend button)
   - Logout button

2. **Configuration (collapsible):**
   - Use cache checkbox
   - Dry run mode checkbox
   - Show stage details checkbox

3. **API Keys (collapsible):**
   - Connection status badge (Connected/Disconnected)
   - Gemini API key input (if not set)
   - DeepSeek API key input (if not set)

4. **Usage:**
   - Progress bar showing usage/limit
   - Remaining requests count
   - Upgrade button if at limit (free tier)

5. **Options (collapsible):**
   - Model preference dropdown (Balanced/Speed/Quality)
   - Creativity slider (0.0-1.0)

6. **History (collapsible):**
   - Last 5 optimizations

7. **About (collapsible):**
   - Pipeline explanation, cost info

### 6.4 Main Content Area

1. **Header:**
   - "⚡ Promptly" gradient header
   - "Transform your ideas into bulletproof prompts" subtitle

2. **Tabs: Input / Examples / History**

3. **Input Tab:**
   - Context tags multiselect (variables like {user_name}, {company}, etc.)
   - Text area for prompt idea
   - "🔧 Optimize Prompt" button

4. **Examples Tab:**
   - 5 example ideas with click-to-use buttons

5. **History Tab:**
   - Last 10 optimizations with expandable details

### 6.5 Results Display

1. **Output Card:**
   - Styled container with dark theme
   - Final prompt text in monospace font
   - Copy, Save, Regenerate buttons

2. **Metrics Panel:**
   - Token count, estimated cost, latency, prompt score

3. **Detailed Analysis (collapsible):**
   - Variations tab: Show all 3 variations with ranks
   - Rubric tab: Show criteria and checklist
   - Raw JSON tab: Full JSON output with download button

4. **Upgrade Dialog (@st.dialog):**
   - Pro tier benefits
   - Waitlist signup form (Stripe integration placeholder)

### 6.6 CSS Styling

**Color scheme:**
- Background: #0d1117 (main), #161b22 (sidebar)
- Borders: #30363d
- Text: #f0f6fc (primary), #c9d1d9 (secondary), #8b949e (muted)
- Accent gradient: #667eea → #764ba2 → #f093fb
- Success: #3fb950
- Warning: #d29922
- Error: #f85149
- Info: #58a6ff

**Key CSS classes to implement:**
- `.main-header` - Gradient text header
- `.output-card` - Dark card with gradient background
- `.prompt-output` - Monospace code display
- `.metric-card` - Metrics display cards
- `.tier-badge` - Tier label badges (free/pro/enterprise)
- `.status-badge` - Connection status badges
- `.footer` - Footer styling

---

## 7. Admin CLI

### 7.1 Commands

| Command | Arguments | Description |
|---------|-----------|-------------|
| `list-users` | `--tier`, `--limit` | List all users |
| `user-info` | `email` | Get detailed user info |
| `change-tier` | `email`, `tier` | Change user tier |
| `verify-user` | `email` | Manually verify email |
| `delete-user` | `email`, `--force` | Delete user account |
| `usage-stats` | `--month`, `--year` | Show usage statistics |
| `reset-password` | `email` | Generate password reset token |

### 7.2 Output Format

**list-users:**
```
ID     Email                               Name                      Tier         Verified   Created
========================================================================================================
1      john@example.com                    John Doe                  free         ✓          2025-12-01 10:30:00

Total: 1 users
```

**usage-stats:**
```
==================================================
Usage Statistics - 12/2025
==================================================

--- User Counts ---
Total Users:     100
Verified:        85 (85.0%)

By Tier:
  FREE         80
  PRO          18
  ENTERPRISE   2

--- Monthly Usage (12/2025) ---
Total Optimizations:  1234
Active Users:         45
Avg per User:         27.4

--- Top 10 Users ---
  1. power.user@example.com               89 optimizations
  ...

==================================================
```

---

## 8. Deployment Configuration

### 8.1 Procfile

```
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true
```

### 8.2 railway.json

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### 8.3 runtime.txt

```
python-3.11.9
```

### 8.4 .gitignore

```
# Environment
.env
.venv/
venv/
env/

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# Data
data/
logs/
.prompt_cache/

# IDE
.vscode/
.idea/

# Testing
.pytest_cache/
.coverage
htmlcov/

# Build
*.egg-info/
dist/
build/
```

---

## 9. Testing Suite

### 9.1 Test Categories

1. **Schema Validation Tests:**
   - Test each Pydantic schema with valid data
   - Test validation failures with invalid data
   - Test unique ranks validation for RankingsOutput

2. **LLM Wrapper Tests:**
   - Token counting accuracy
   - Cost calculation
   - Prompt compression
   - JSON parsing (clean, markdown-wrapped, trailing commas)
   - Idea hashing consistency

3. **Pipeline Tests (Dry Run):**
   - Full pipeline dry run
   - Output structure validation
   - Cache hit/miss behavior

4. **Token Tracker Tests:**
   - Recording multiple calls
   - Summary calculation
   - Budget checking

### 9.2 Test Fixtures

```python
VALID_DISCERN_DATA = {
    "task_type": "generation",
    "complexity": "moderate",
    "domain": "general",
    "key_requirements": ["clarity", "specificity"],
    "potential_pitfalls": ["ambiguity"],
    "recommended_approach": "structured approach"
}

VALID_RUBRIC_DATA = {
    "rubric": {"clarity": "prompt should be clear and unambiguous"},
    "checklist": ["includes examples", "specifies format"],
    "red_flags": ["vague instructions", "missing constraints"]
}
```

### 9.3 Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_v2.py -v

# Run with coverage
python -m pytest tests/ --cov=consensus_prompt_optimizer --cov-report=html
```

---

## 10. Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Create directory structure
- [ ] Create requirements.txt
- [ ] Create config.py with all constants
- [ ] Create .env.example

### Phase 2: Pipeline Module
- [ ] Implement schemas.py with all Pydantic models
- [ ] Implement llm_wrapper_v2.py with all functions
- [ ] Implement orchestrator.py with PromptimaV2 class
- [ ] Implement utils.py with log_event function
- [ ] Create __init__.py with exports

### Phase 3: Authentication System
- [ ] Implement database.py with dual SQLite/PostgreSQL support
- [ ] Implement models.py with User, Session, Usage dataclasses
- [ ] Implement auth_service.py with all authentication methods
- [ ] Implement usage_service.py with usage tracking
- [ ] Implement logger.py with Loguru configuration
- [ ] Create __init__.py with exports

### Phase 4: Web UI
- [ ] Implement app.py with complete Streamlit UI
- [ ] Add all CSS styling
- [ ] Implement authentication flow
- [ ] Implement optimization flow
- [ ] Implement results display
- [ ] Implement upgrade dialog

### Phase 5: Admin & Deployment
- [ ] Implement admin_cli.py with all commands
- [ ] Create Procfile
- [ ] Create railway.json
- [ ] Create runtime.txt
- [ ] Update .gitignore

### Phase 6: Testing
- [ ] Implement test_v2.py with all unit tests
- [ ] Implement test_integration.py with integration tests
- [ ] Verify all 27+ tests pass

### Phase 7: Final Verification
- [ ] Run `python -m pytest tests/ -v` - all tests pass
- [ ] Run `python admin_cli.py --help` - shows all commands
- [ ] Run `streamlit run app.py` - UI loads without errors
- [ ] Test full registration → login → optimization → logout flow
- [ ] Test password reset flow
- [ ] Test rate limiting (100 requests for free tier)

---

## Critical Implementation Notes

1. **DeepSeek Single Call:** The Expander stage is the ONLY place DeepSeek is called. This is a hard requirement for cost control.

2. **Token Hashing:** Session tokens and reset/verification tokens are NEVER stored raw. Always use SHA-256 hash.

3. **Password Hashing:** Use bcrypt with 12 rounds. Never store plaintext passwords.

4. **Database Compatibility:** All SQL must work with both SQLite and PostgreSQL. Use `?` placeholders (translated to `%s` for PostgreSQL).

5. **Email Enumeration Prevention:** Password reset always returns success message, regardless of whether email exists.

6. **Session Invalidation:** On password reset, ALL user sessions must be deleted (security measure).

7. **Cache Versioning:** Cache includes version field. Only load cache if version matches "v2".

8. **JSON Mode:** All LLM calls use `enforce_json=True` with response_format hint.

9. **Environment Detection:** Production is detected by presence of `RAILWAY_ENVIRONMENT` or `DATABASE_URL`.

10. **Log Privacy:** Emails are masked in logs (j***@example.com format).

---

## Execution Instructions

1. Read this entire document before starting implementation
2. Implement each phase in order
3. Test each component before moving to the next phase
4. Do not deviate from the specified schemas, function signatures, or behaviors
5. If any requirement is ambiguous, refer to this document as the source of truth
6. All 27+ tests must pass before considering implementation complete

---

*This prompt was generated on December 8, 2025 from a comprehensive analysis of the Promptly 3.0 codebase.*
