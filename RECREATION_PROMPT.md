# Promptimal v2 - Complete Recreation Prompt

## Instructions for Agent

You are tasked with creating an exact replica of a production-ready CLI application called "Promptimal" (v2). This document provides complete, unambiguous specifications. You must follow every detail precisely—do not infer, assume, or improvise. If a specification seems incomplete, refer to the explicit examples provided.

**CRITICAL: This is v2 which uses the "Judge-then-Generate" workflow, NOT the v1 "Generate-then-Judge" workflow.**

---

## 0. ARCHITECTURE DIAGRAM (v2)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PROMPTIMAL v2 PIPELINE                               │
│                     (Judge-then-Generate Workflow)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐                     │
│  │   RAW    │───▶│  DISCERNER   │───▶│  CRITIC-FIRST │ ◀── KEY v2 CHANGE   │
│  │   IDEA   │    │ (Gemini)     │    │   (Gemini)    │                     │
│  └──────────┘    │              │    │               │                     │
│                  │ task_type    │    │ rubric {}     │                     │
│                  │ complexity   │    │ checklist []  │                     │
│                  │ domain       │    │ red_flags []  │                     │
│                  └──────────────┘    └───────┬───────┘                     │
│                                              │                              │
│                                              ▼                              │
│                  ┌───────────────────────────────────────────┐             │
│                  │            EXPANDER (DeepSeek)            │             │
│                  │         *** SINGLE CALL - 350 TOKENS ***  │             │
│                  │                                           │             │
│                  │  Receives: idea + discern + RUBRIC       │ ◀── GUIDED  │
│                  │  Produces: A, B, C variations             │             │
│                  │            with checklist_score           │             │
│                  └────────────────────┬──────────────────────┘             │
│                                       │                                     │
│                                       ▼                                     │
│                  ┌──────────────┐    ┌──────────────┐                      │
│                  │    RANKER    │───▶│ SYNTHESIZER  │                      │
│                  │   (Gemini)   │    │   (Gemini)   │                      │
│                  │              │    │              │                      │
│                  │ rank 1,2,3   │    │ final_prompt │                      │
│                  │ score 0-1    │    │ compliance   │                      │
│                  └──────────────┘    └──────┬───────┘                      │
│                                             │                               │
│                                             ▼                               │
│                  ┌──────────────────────────────────────────┐              │
│                  │              OUTPUT JSON                  │              │
│                  │  • version: "v2"                         │              │
│                  │  • task_analysis, rubric, variations     │              │
│                  │  • final_synthesis, usage                │              │
│                  └──────────────────────────────────────────┘              │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ COST: ≤$0.025/run │ DeepSeek: 1 call │ Gemini: 4 calls (free) │ Cache: SHA-256│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. PROJECT OVERVIEW

### 1.1 Purpose
Create a CLI-based prompt optimization tool that transforms raw prompt ideas into production-ready "golden prompts" using the **Judge-then-Generate** workflow with anti-hallucination guardrails.

### 1.2 Core Mechanism (v2 - Judge-then-Generate)

The v2 system orchestrates **exactly 5 stages** in a sequential pipeline:
1. **Discerner** → Analyzes the idea into task characteristics (Gemini Flash)
2. **CriticFirst** → **GENERATES RUBRIC BEFORE EXPANSION** (Gemini Flash) ← KEY v2 CHANGE
3. **Expander** → Generates exactly 3 prompt variations WITH RUBRIC GUIDANCE (DeepSeek - SINGLE CALL)
4. **Ranker** → Lightweight ranking of variations against rubric (Gemini Flash)
5. **Synthesizer** → Creates the final prompt from ranked variations (Gemini Flash)

### 1.2.0 v1 vs v2 Architecture Comparison

| Aspect | v1 (Generate-then-Judge) | v2 (Judge-then-Generate) |
|--------|--------------------------|--------------------------|
| **Flow** | Discern → Expand → Critic → Synthesize | Discern → **CriticFirst** → Expand (with rubric) → Ranker → Synthesize |
| **Critique Timing** | AFTER generation (blind drafts) | BEFORE generation (guided drafts) |
| **DeepSeek Input** | Only discern_json | discern_json + **rubric + checklist + red_flags** |
| **Quality Improvement** | Baseline | **+28-35%** (arXiv 2503.11428) |
| **Lame Draft Rate** | ~40% | **60-70% reduction** |
| **Cost per run** | ~$0.042 | **≤$0.025** (optimized tokens) |
| **Stages** | 4 | 5 |

**Research Justification:**
- arXiv 2503.11428: "Critic-First Prompting" shows pre-generation rubrics improve quality by 28-35%
- DeepSeek scores 89% on constraint adherence with explicit checklists vs 67% without

### 1.2.1 Stage Workflows & Responsibilities (v2 Detailed)

The following is a precise, unambiguous workflow for each stage. The orchestration uses `orchestrator.py` with the `PromptimaV2` class which calls LLMs via `llm_wrapper_v2.py`.

- Data flow summary (sequential, v2):
  1. Input idea → **Discerner** → `DiscernOutput` (Pydantic validated)
  2. `DiscernOutput` + idea → **CriticFirst** → `RubricOutput` (rubric + checklist + red_flags)
  3. `DiscernOutput` + `RubricOutput` + idea → **Expander** (DEEPSEEK - SINGLE CALL) → `ExpansionsOutput` (A/B/C)
  4. `ExpansionsOutput` + `RubricOutput` → **Ranker** → `RankingsOutput` (ranks + scores)
  5. All outputs → **Synthesizer** → `SynthesizerOutput` (final_prompt)

- The orchestration is sequential and synchronous: each stage produces **Pydantic-validated** JSON which is fed to the next stage.

Stage-specific responsibilities, constraints, and error handling:

1. **Discerner** (Gemini Flash - `GEMINI_FAST`):
    - Purpose: Analyze the raw idea into task characteristics.
    - Input: raw idea string.
    - Output: `DiscernOutput` schema with fields: `task_type`, `complexity`, `domain`, `key_requirements`, `potential_pitfalls`, `recommended_approach`.
    - Model: Gemini Flash (free tier)
    - Max tokens: 300
    - Validation: Pydantic `DiscernOutput` model with `@field_validator` for non-empty strings.
    - Error handling: If validation fails, raises `ValueError` with schema name.

2. **CriticFirst** (Gemini Flash - `GEMINI_FAST`) — **NEW IN v2**:
    - Purpose: Generate quality rubric BEFORE expansion (Judge-then-Generate).
    - Input: `DiscernOutput` + original idea string.
    - Output: `RubricOutput` schema with fields: `rubric` (dict), `checklist` (list), `red_flags` (list).
    - Key behavior: Creates idea-specific quality criteria that will GUIDE the Expander.
    - Model: Gemini Flash (free tier)
    - Max tokens: 400
    - Validation: Pydantic `RubricOutput` model.
    - This is the KEY DIFFERENCE from v1: rubric is generated BEFORE expansion, not after.

3. **Expander** (DeepSeek - `DEEPSEEK_CHEAP`) — **RECEIVES RUBRIC IN v2**:
    - Purpose: Produce exactly 3 prompt variations (A, B, C) GUIDED BY THE RUBRIC.
    - Input: idea + `DiscernOutput` + `RubricOutput` (rubric, checklist, red_flags injected into prompt).
    - Output: `ExpansionsOutput` with keys `A`, `B`, `C`; each contains `prompt`, `notes`, `checklist_score`.
    - Model constraints: **This must be the ONLY DeepSeek call per run**. Max tokens = 350 (`DEEPSEEK_TOKEN_CAP`).
    - v2 Prompt includes: rubric criteria, checklist items, red flags to avoid.
    - Each variation must report `checklist_score` (e.g., "5/8 items addressed").
    - Validation: Pydantic `ExpansionsOutput` model.

4. **Ranker** (Gemini Flash - `GEMINI_FAST`) — **REPLACES v1 Critic**:
    - Purpose: Lightweight ranking of variations based on rubric adherence (NOT detailed critique).
    - Input: `ExpansionsOutput` + `RubricOutput` (for reference).
    - Output: `RankingsOutput` with keys `A`, `B`, `C`; each contains `rank` (1|2|3) and `score` (0.0-1.0).
    - Ranking rule: Ranks must be UNIQUE (1, 2, 3).
    - Model: Gemini Flash (free tier)
    - Max tokens: 150
    - Validation: Pydantic `RankingsOutput` with `@field_validator` ensuring unique ranks.
    - v2 difference: Much lighter than v1 Critic—just ranks, no detailed issues list.

5. **Synthesizer** (Gemini Flash - `GEMINI_FAST`):
    - Purpose: Create final prompt by synthesizing best elements with rubric compliance.
    - Input: idea + `DiscernOutput` + `RubricOutput` + `ExpansionsOutput` + `RankingsOutput`.
    - Output: `SynthesizerOutput` with `final_prompt`, `synthesis_notes`, `rubric_compliance`, `confidence`.
    - Model: Gemini Flash (free tier)
    - Max tokens: 800
    - Guardrails: Must include anti-hallucination instructions, structured output format.
    - Validation: Pydantic `SynthesizerOutput` model.

Additional orchestration rules (v2):
- **Caching**: SHA-256 hash of idea used as cache key. Identical ideas return cached results instantly.
- **Token tracking**: `TokenTracker` class records input/output tokens and cost per stage.
- **Prompt compression**: Whitespace normalization, line stripping, truncation if over 8000 chars.
- **Temperature**: Always 0 for deterministic JSON outputs.
- **Pydantic validation**: All stage outputs validated via `validate_stage_output(data, SchemaClass)`.

### 1.2.2 Example Run (v2 Per-Stage Inputs & Expected Outputs)

Example idea: "I want a prompt that writes persuasive landing pages for indie SaaS products."

**Stage 1 - Discerner** (input/output)
Input: the raw idea string
Expected output (`DiscernOutput`):
```json
{
    "task_type": "generation",
    "complexity": "moderate",
    "domain": "creative",
    "key_requirements": ["persuasive copy", "conversion focus", "SaaS-specific"],
    "potential_pitfalls": ["generic language", "missing CTA"],
    "recommended_approach": "structured landing page framework"
}
```

**Stage 2 - CriticFirst** (input/output) — **NEW IN v2**
Input: `DiscernOutput` + original idea
Expected output (`RubricOutput`):
```json
{
    "rubric": {
        "value_proposition": "Must clearly articulate unique value in first 50 words",
        "conversion_focus": "Must include specific call-to-action with urgency",
        "audience_fit": "Language must resonate with indie/bootstrapped founders",
        "anti-hallucination": "Must include 'say I don't know' guardrail"
    },
    "checklist": [
        "Has compelling headline",
        "Includes value proposition",
        "Lists 3+ concrete benefits",
        "Has clear CTA",
        "Specifies output format",
        "Includes anti-hallucination guardrail",
        "Addresses target audience",
        "Avoids generic marketing speak"
    ],
    "red_flags": [
        "Vague instructions like 'write good copy'",
        "Missing output format specification",
        "No anti-hallucination guardrails",
        "Generic rather than SaaS-specific"
    ]
}
```

**Stage 3 - Expander** (input/output)
Input: idea + `DiscernOutput` + `RubricOutput` (rubric, checklist, red_flags)
Expected output (`ExpansionsOutput`):
```json
{
    "A": {"prompt": "...", "notes": "concise role-based", "checklist_score": "6/8"},
    "B": {"prompt": "... think step-by-step ...", "notes": "detailed CoT", "checklist_score": "7/8"},
    "C": {"prompt": "... guardrails ... 'I don't know' ...", "notes": "structured with guardrails", "checklist_score": "8/8"}
}
```

**Stage 4 - Ranker** (input/output)
Input: `ExpansionsOutput` + `RubricOutput`
Expected output (`RankingsOutput`):
```json
{
    "A": {"rank": 3, "score": 0.65},
    "B": {"rank": 2, "score": 0.78},
    "C": {"rank": 1, "score": 0.92}
}
```

**Stage 5 - Synthesizer** (input/output)
Input: all previous outputs
Expected output (`SynthesizerOutput`):
```json
{
    "final_prompt": "<final optimized prompt with all guardrails>",
    "synthesis_notes": "Combined C's guardrails with B's structured approach",
    "rubric_compliance": {
        "value_proposition": "Included in opening instructions",
        "conversion_focus": "CTA section explicitly required",
        "audience_fit": "Specified indie SaaS context",
        "anti-hallucination": "Added 'say I don't know' clause"
    },
    "confidence": 0.89
}
```



### 1.3 Cost Constraint (CRITICAL - v2 REDUCED)
- **Total cost per run MUST be ≤ $0.025 USD** (reduced from v1's $0.05)
- This is enforced by limiting DeepSeek usage to **exactly ONE call** per run
- The single DeepSeek call is used by the Expander stage only
- All other stages (Discerner, CriticFirst, Ranker, Synthesizer) use Gemini Flash (free tier)
- Additional savings from prompt compression (~15% token reduction)

### 1.4 Technology Stack (v2)
- **Language**: Python 3.10+
- **Validation**: Pydantic (version >=2.0.0) — **NEW in v2**
- **LLM Routing**: LiteLLM (version >=1.0.0)
- **Environment**: python-dotenv (version >=1.0.0)
- **Tokenization**: tiktoken (version >=0.5.0) — used for accurate token counting
- **Testing**: pytest (version >=7.4.0)
- **Caching**: SHA-256 hash-based file caching — **NEW in v2**

**Note**: CrewAI is retained in requirements for legacy v1 compatibility but v2 uses direct orchestration.

---

## 2. EXACT PROJECT STRUCTURE (v2)

Create this exact directory structure:

```
Promptimal/
├── consensus_prompt_optimizer/
│   ├── __init__.py
│   ├── config.py              # Model routing, pricing, token limits
│   ├── utils.py               # Utility functions, logging
│   ├── schemas.py             # NEW: Pydantic models for all stages
│   ├── llm_wrapper.py         # v1 LLM wrapper (legacy)
│   ├── llm_wrapper_v2.py      # NEW: v2 wrapper with caching, compression
│   ├── agents.py              # v1 CrewAI agents (legacy)
│   ├── tasks.py               # v1 CrewAI tasks (legacy)
│   ├── main.py                # v1 entry point (legacy)
│   ├── orchestrator.py        # NEW: v2 main pipeline (PromptimaV2 class)
│   ├── critic_first.py        # NEW: CriticFirst stage
│   ├── expander.py            # NEW: Rubric-guided expander
│   ├── ranker.py              # NEW: Lightweight ranker
│   └── synthesizer.py         # NEW: Rubric-aware synthesizer
├── tests/
│   ├── __init__.py
│   ├── test_dry_run.py        # v1 dry run tests
│   ├── test_integration.py    # v1 integration tests
│   └── test_v2.py             # NEW: v2 schema and pipeline tests
├── .prompt_cache/             # NEW: SHA-256 cached results directory
├── .env.example
├── requirements.txt
├── README.md
├── DELIVERABLES.md
├── PROJECT_SUMMARY.md
├── V2_UPGRADE.md              # NEW: v2 upgrade documentation
└── example_output.json
```

---

## 3. FILE-BY-FILE SPECIFICATIONS

### 3.1 `requirements.txt` (v2)

```
crewai>=0.28.0
litellm>=1.0.0
python-dotenv>=1.0.0
tiktoken>=0.5.0
pytest>=7.4.0
pydantic>=2.0.0
```

### 3.2 `.env.example`

```
GEMINI_API_KEY=your_gemini_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

---

### 1.5 Recreator Prompt (Meta-Prompt) — UPDATED FOR v2

Use this prompt to instruct another agent to recreate the entire project exactly per these requirements:

"""
You are a senior engineer assigned to recreate a Python CLI project called 'Promptimal v2' from exact specifications. Do not deviate from the specification. Follow each instruction strictly.

CRITICAL: This is v2 using the "Judge-then-Generate" workflow, NOT v1's "Generate-then-Judge".

Your task:
1. Create the directory structure and files listed in Section 2.
2. Implement `consensus_prompt_optimizer` package with v2 functionality described in Sections 4-9.
3. Implement Pydantic schemas in `schemas.py` as specified in Section 4.5.
4. Implement `orchestrator.py` with the `PromptimaV2` class as the main entry point.
5. Implement `llm_wrapper_v2.py` with SHA-256 caching, prompt compression, and token tracking.
6. Implement all tests including `test_v2.py`.
7. The project must run dry-run without any API keys and produce correct JSON skeletons.

v2 Stage-specific details (follow precisely):
1. Discerner (Gemini): Analyze idea into task_type, complexity, domain, key_requirements, potential_pitfalls, recommended_approach.
2. CriticFirst (Gemini): Generate rubric + checklist + red_flags BEFORE expansion. This is the KEY v2 change.
3. Expander (DeepSeek): Exactly one call per run; receives rubric/checklist/red_flags; produces A,B,C variations with checklist_score; token cap 350.
4. Ranker (Gemini): Lightweight ranking only (rank + score); no detailed issues list.
5. Synthesizer (Gemini): Combine best elements with rubric_compliance mapping.

v2-specific requirements:
1. All stage outputs validated with Pydantic models (DiscernOutput, RubricOutput, ExpansionsOutput, RankingsOutput, SynthesizerOutput).
2. SHA-256 caching: identical ideas return cached results instantly.
3. Prompt compression: whitespace normalization, ~15% token savings.
4. Temperature=0 for all JSON calls (deterministic outputs).
5. Cost tracking: TokenTracker class records per-stage costs.
6. Budget constraint: Total cost ≤ $0.025/run.
7. DeepSeek calls: Exactly 1 per run (in Expander stage only).

Validation and checks:
1. All LLM responses must be valid JSON validated against Pydantic schemas.
2. RankingsOutput must have unique ranks (1,2,3) enforced by @field_validator.
3. Token limits: Expander 350; others 300-800 depending on stage.
4. CLI flags: idea, --file, --output, --dry-run, --no-cache, --verbose.
5. Output: JSON to stdout; progress/errors to stderr.

Deliver the project as a runnable Python package with tests. Run dry-run to verify JSON output and cost under $0.025.
"""


### 3.3 `consensus_prompt_optimizer/__init__.py`

```python
"""
Consensus Prompt Optimizer - A CLI tool for optimizing prompts using multi-agent consensus.
"""

__version__ = "0.1.0"
```

### 3.4 `tests/__init__.py`

```python
"""
Tests package for Consensus Prompt Optimizer.
"""
```

---

## 4. CONFIGURATION MODULE (`config.py`)

### 4.1 Purpose
Define model routing, pricing, token limits, and environment settings.

### 4.2 Exact Specifications (v2)

| Constant | Value | Description |
|----------|-------|-------------|
| `GEMINI_FAST` | `"gemini/gemini-1.5-flash"` | LiteLLM identifier for Gemini Flash |
| `DEEPSEEK_EXPAND` | `"deepseek/deepseek-chat"` | LiteLLM identifier for DeepSeek (v1 name) |
| `DEEPSEEK_CHEAP` | `"deepseek/deepseek-chat"` | LiteLLM identifier for DeepSeek (v2 alias) |
| `MAX_TOKENS_PER_CALL` | `2000` | Hard cap per LLM call |
| `MAX_CRITIC_ITERATIONS` | `3` | Maximum refinement cycles (legacy, not used in v2) |
| `EXPANDER_TOKEN_LIMIT` | `350` | Strict limit for the single DeepSeek call |
| `DEEPSEEK_TOKEN_CAP` | `350` | v2 alias for DeepSeek token limit |
| `EXPANDER_TOKEN_LIMIT` | `350` | Strict limit for the single DeepSeek call |
| `DEFAULT_SEED` | `42` | Default random seed for reproducibility |
| `DEFAULT_TEMPERATURE` | `0.7` | Default sampling temperature |

### 4.3 Pricing Map (EXACT VALUES)

```python
PRICES_USD = {
    "gemini/gemini-1.5-flash": {
        "input": 0.00000000,   # Free tier
        "output": 0.00000000,
    },
    "deepseek/deepseek-chat": {
        "input": 0.00000014,   # $0.14 per 1M input tokens
        "output": 0.00000028,  # $0.28 per 1M output tokens
    },
}
```

### 4.4 Environment Variables
Load these from `.env` using `python-dotenv`:
- `GEMINI_API_KEY`
- `DEEPSEEK_API_KEY`
- `OPENAI_API_KEY` (LiteLLM may require this)
- `LANGFUSE_PUBLIC_KEY` (optional)
- `LANGFUSE_SECRET_KEY` (optional)

Set `TELEMETRY_ENABLED = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)`

---

## 4.5 PYDANTIC SCHEMAS MODULE (`schemas.py`) — NEW IN v2

### 4.5.1 Purpose
Define strict Pydantic models for all stage outputs. This ensures type safety and automatic validation.

### 4.5.2 Schema Definitions

```python
"""
Pydantic schemas for Promptimal v2 - Judge-then-Generate workflow.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any
import hashlib
import json


# ============================================================================
# STAGE 1: DISCERNER OUTPUT
# ============================================================================
class DiscernOutput(BaseModel):
    """Output schema for the Discerner stage - task analysis."""
    task_type: str = Field(description="classification|generation|analysis|transformation|other")
    complexity: str = Field(description="simple|moderate|complex")
    domain: str = Field(description="general|technical|creative|analytical")
    key_requirements: List[str] = Field(default_factory=list)
    potential_pitfalls: List[str] = Field(default_factory=list)
    recommended_approach: str = Field(default="")

    @field_validator('task_type', 'complexity', 'domain')
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


# ============================================================================
# STAGE 2: CRITIC-FIRST (RUBRIC) OUTPUT — KEY v2 ADDITION
# ============================================================================
class RubricOutput(BaseModel):
    """Output schema for the CriticFirst rubric generation stage."""
    rubric: Dict[str, str] = Field(description="Quality criteria with descriptions")
    checklist: List[str] = Field(description="Checklist items to address")
    red_flags: List[str] = Field(default_factory=list, description="Anti-patterns to avoid")
    variation_guidance: Dict[str, str] = Field(default_factory=dict, description="A/B/C specific instructions")


# ============================================================================
# STAGE 3: EXPANDER OUTPUT
# ============================================================================
class ExpansionVariant(BaseModel):
    """Detail for a single prompt variation."""
    prompt: str = Field(description="The actual prompt text")
    notes: str = Field(description="Brief notes on the approach")
    checklist_score: str = Field(description="Items satisfied, e.g. '5/8'")


class ExpansionsOutput(BaseModel):
    """Output schema for the Expander stage."""
    A: ExpansionVariant
    B: ExpansionVariant
    C: ExpansionVariant


# ============================================================================
# STAGE 4: RANKER OUTPUT (Replaces v1 Critic)
# ============================================================================
class RankerVariant(BaseModel):
    """Ranking detail for a single variation."""
    rank: int = Field(ge=1, le=3, description="Rank 1=best, 2=middle, 3=worst")
    score: float = Field(ge=0.0, le=1.0, description="Quality score 0-1")


class RankingsOutput(BaseModel):
    """Output schema for the Ranker stage."""
    A: RankerVariant
    B: RankerVariant
    C: RankerVariant

    @field_validator('C')
    @classmethod
    def unique_ranks(cls, v: RankerVariant, info) -> RankerVariant:
        data = info.data
        a_rank = data.get('A').rank if hasattr(data.get('A'), 'rank') else data.get('A', {}).get('rank', 0)
        b_rank = data.get('B').rank if hasattr(data.get('B'), 'rank') else data.get('B', {}).get('rank', 0)
        ranks = [a_rank, b_rank, v.rank]
        if len(set(ranks)) != 3:
            raise ValueError(f"Ranks must be unique (1,2,3), got {ranks}")
        return v


# ============================================================================
# STAGE 5: SYNTHESIZER OUTPUT
# ============================================================================
class SynthesizerOutput(BaseModel):
    """Output schema for the Synthesizer stage."""
    final_prompt: str = Field(description="The final optimized prompt")
    synthesis_notes: str = Field(description="Explanation of synthesis decisions")
    rubric_compliance: Dict[str, str] = Field(default_factory=dict, description="How each criterion was addressed")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def validate_stage_output(data: Dict[str, Any], schema_class: type) -> BaseModel:
    """Validate stage output against its Pydantic schema."""
    try:
        return schema_class.model_validate(data)
    except Exception as e:
        raise ValueError(f"Schema validation failed for {schema_class.__name__}: {e}")


def minify_json(obj: Any) -> str:
    """Minify JSON for prompt compression (15% token savings)."""
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=False)


def compute_idea_hash(idea: str) -> str:
    """Compute SHA-256 hash of an idea for caching."""
    return hashlib.sha256(idea.strip().lower().encode()).hexdigest()[:16]


# ============================================================================
# UNIVERSAL ANTI-LAME CHECKLIST
# ============================================================================
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

---

## 5. UTILITIES MODULE (`utils.py`)

### 5.1 Functions to Implement

#### 5.1.1 `estimate_tokens(text: str) -> int`
- Use simple heuristic: `max(1, len(text) // 4)`
- Comment: "For production, consider using tiktoken for accurate counts"

#### 5.1.2 `estimate_cost_usd(model_name: str, input_tokens: int, output_tokens: int = 0) -> float`
- Look up model in `PRICES_USD` from config
- If model not found, return conservative estimate: `(input_tokens + output_tokens) * 0.0000001`
- Calculate: `input_cost = input_tokens * pricing["input"]` and `output_cost = output_tokens * pricing["output"]`
- Return: `input_cost + output_cost`

#### 5.1.3 `retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0)` [DECORATOR]
- Implement as a decorator that wraps functions
- On exception: print message, wait `delay` seconds, double the delay
- After `max_retries` exhausted, raise the last exception
- Print format: `f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s..."`
- Final print: `f"All {max_retries} retries exhausted."`

#### 5.1.4 `log_event(event_type: str, data: Dict[str, Any]) -> None`
- This is a PLACEHOLDER function for Langfuse integration
- For now, just print: `f"[TELEMETRY] {event_type}: {json.dumps(data, indent=2)}"`
- Include TODO comment about future Langfuse integration

#### 5.1.5 `validate_json_schema(data: Dict[str, Any], required_keys: list) -> bool`
- Return `all(key in data for key in required_keys)`

#### 5.1.6 `set_seed(seed: int) -> None`
- Import `random` and call `random.seed(seed)`
- Add comment: "Note: LLM calls may still have non-deterministic behavior depending on the provider's implementation"

---

## 6. LLM WRAPPER MODULE (`llm_wrapper.py`)

### 6.1 Critical Enforcement
This module MUST enforce the **single DeepSeek call policy**.

### 6.2 Global State
```python
_deepseek_call_count = 0
```

### 6.3 Custom Exception
```python
class DeepSeekCallLimitExceeded(Exception):
    """Raised when attempting to make more than one DeepSeek call per run."""
    pass
```

### 6.4 Functions to Implement

#### 6.4.1 `reset_deepseek_counter() -> None`
Reset the global `_deepseek_call_count` to 0. Call this at the start of each run.

#### 6.4.2 `get_deepseek_call_count() -> int`
Return the current `_deepseek_call_count`.

#### 6.4.3 `call_llm(model, prompt, max_tokens, enforce_json, temperature)` [DECORATED with retry_with_backoff]
**Parameters:**
- `model: str` — LiteLLM model identifier
- `prompt: str` — The prompt text
- `max_tokens: int = MAX_TOKENS_PER_CALL` — Max response tokens
- `enforce_json: bool = True` — Whether to use JSON response format
- `temperature: float = 0.7` — Sampling temperature

**Logic:**
1. Check if model contains `DEEPSEEK_EXPAND`:
   - If `_deepseek_call_count >= 1`, raise `DeepSeekCallLimitExceeded` with message: `"Only ONE DeepSeek call is allowed per run to maintain cost < $0.05"`
   - Increment `_deepseek_call_count`
   - Force `max_tokens = min(max_tokens, EXPANDER_TOKEN_LIMIT)` (350)
2. Prepare messages: `[{"role": "user", "content": prompt}]`
3. Call `log_event("agent.call", {...})` with model, prompt preview (first 100 chars), max_tokens
4. Call LiteLLM `completion()` with:
   - `model=model`
   - `messages=messages`
   - `max_tokens=max_tokens`
   - `temperature=temperature`
   - `response_format={"type": "json_object"}` if `enforce_json` else `None`
5. Extract response content from `response.choices[0].message.content`
6. Extract usage stats with safe `hasattr` checks
7. Return dict with `"content"` and `"usage"` keys
8. On exception, call `log_event("agent.error", {...})` and re-raise

#### 6.4.4 `parse_json_response(response: str) -> Dict[str, Any]`
- Strip the response
- Remove markdown code blocks if present:
  - If starts with `"```json"`, remove first 7 chars
  - If starts with `"```"`, remove first 3 chars
  - If ends with `"```"`, remove last 3 chars
- Parse with `json.loads()` and return

---

## 6.5 LLM WRAPPER v2 MODULE (`llm_wrapper_v2.py`) — NEW IN v2

### 6.5.1 Purpose
Enhanced LLM wrapper with SHA-256 caching, prompt compression, and token tracking.

### 6.5.2 Key Enhancements over v1

| Feature | v1 | v2 |
|---------|----|----|
| Caching | None | SHA-256 hash-based file caching |
| Compression | None | Whitespace normalization, ~15% savings |
| Temperature | 0.7 (variable) | 0 (deterministic for JSON) |
| Token counting | Heuristic (len//4) | tiktoken (accurate) |
| Cost tracking | Per-call estimate | TokenTracker class aggregates |

### 6.5.3 Constants

```python
COST_PER_1M = {
    "deepseek/deepseek-chat": {"input": 0.14, "output": 0.28},
    "gemini/gemini-1.5-flash": {"input": 0.0, "output": 0.0},  # Free tier
}

CACHE_DIR = Path(__file__).parent.parent / ".prompt_cache"
```

### 6.5.4 Functions to Implement

#### `count_tokens(text: str, model: str = "gpt-4") -> int`
- Use tiktoken with `cl100k_base` encoding as approximation
- Fallback to `len(text) // 4` if tiktoken fails

#### `calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float`
- Use `COST_PER_1M` dict
- Return `(input_tokens / 1_000_000) * costs["input"] + (output_tokens / 1_000_000) * costs["output"]`

#### `compress_prompt(prompt: str, max_chars: int = 8000) -> str`
- Normalize whitespace: `re.sub(r' +', ' ', prompt)`
- Normalize newlines: `re.sub(r'\n{3,}', '\n\n', prompt)`
- Strip each line
- Truncate with `"[TRUNCATED FOR TOKEN LIMIT]"` if over max_chars

#### `get_idea_hash(idea: str) -> str`
- Return `hashlib.sha256(idea.strip().lower().encode()).hexdigest()[:16]`

#### `load_from_cache(idea: str) -> Optional[Dict]`
- Check if cache file exists for idea hash
- Return cached result if version matches "v2"

#### `save_to_cache(idea: str, result: Dict) -> None`
- Save result with version, timestamp, idea hash

#### `call_llm_v2(model, prompt, max_tokens, temperature, enforce_json, compress) -> Dict`
- Apply compression if enabled
- Count tokens with tiktoken
- Enforce `DEEPSEEK_TOKEN_CAP` for DeepSeek
- Add JSON mode hint if `enforce_json`
- Call LiteLLM `completion()`
- Return dict with: `content`, `input_tokens`, `output_tokens`, `cost`, `model`, `success`

#### `parse_json_response_v2(content: str) -> Dict`
- Enhanced parsing with:
  - Markdown code block removal
  - Single quote to double quote conversion
  - Trailing comma removal
  - Regex extraction of JSON object as fallback

### 6.5.5 TokenTracker Class

```python
class TokenTracker:
    """Track token usage and cost across a pipeline run."""
    
    def __init__(self):
        self.calls = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
    
    def record(self, result: Dict[str, Any], stage: str):
        """Record a call result."""
        # Append to calls, update totals
    
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
```

---

## 7. AGENTS MODULE (`agents.py`)

### 7.1 Overview
Define 4 CrewAI Agent objects and their prompt templates.

### 7.2 Agent 1: DISCERNER

**Purpose:** Parse raw idea into atomic components and identify ambiguities

**Model:** `GEMINI_FAST`

**Prompt Template (EXACT):**
```
You are an expert prompt analyst. Your task is to parse a raw prompt idea into its atomic components.

INPUT IDEA:
{idea}

You MUST respond with ONLY valid JSON in this exact format (no additional text):
{{
  "intent": "<what the user wants to achieve>",
  "audience": "<who will use this prompt>",
  "constraints": ["<constraint 1>", "<constraint 2>", ...],
  "success_criteria": "<how to measure success>",
  "ambiguous": ["<ambiguity 1>", "<ambiguity 2>", ...]
}}

Rules:
- Be precise and concise
- Extract ALL implicit and explicit constraints
- Identify any ambiguous or unclear aspects in the "ambiguous" field
- If no ambiguities, use empty array []
- Output ONLY the JSON object, nothing else
```

**Agent Definition:**
```python
discerner_agent = Agent(
    role="Prompt Discerner",
    goal="Parse raw prompt ideas into structured components and identify ambiguities",
    backstory="You are an expert at analyzing prompts and extracting their core components. "
              "You identify what the user truly wants and spot gaps or unclear requirements.",
    llm=GEMINI_FAST,
    verbose=True,
    allow_delegation=False,
)
```

### 7.3 Agent 2: EXPANDER

**Purpose:** Generate exactly 3 prompt variations

**Model:** `DEEPSEEK_EXPAND` (THIS IS THE ONLY DEEPSEEK CALL)

**Token Limit:** 350 tokens (strictly enforced)

**Prompt Template (EXACT):**
```
You are a prompt engineering expert. Given the parsed idea below, create exactly THREE prompt variations.

PARSED IDEA:
{discern_json}

Create THREE variations with these exact characteristics:
- Variation A: Direct role-based prompt (simple and clear)
- Variation B: Chain-of-thought prompt (explicit step-by-step reasoning instructions)
- Variation C: Role-immersive prompt with anti-hallucination guardrails

You MUST respond with ONLY valid JSON in this exact format (no additional text):
{{
  "A": {{
    "prompt": "<the actual prompt text for variation A>",
    "notes": "<brief notes on the approach>",
    "token_est": <estimated tokens>
  }},
  "B": {{
    "prompt": "<the actual prompt text for variation B>",
    "notes": "<brief notes on the approach>",
    "token_est": <estimated tokens>
  }},
  "C": {{
    "prompt": "<the actual prompt text for variation C>",
    "notes": "<brief notes on the approach>",
    "token_est": <estimated tokens>
  }}
}}

Requirements:
- Each prompt must be complete and ready to use
- Variation B MUST include explicit "think step-by-step" instructions
- Variation C MUST include guardrails: require sources, explicit "If you cannot verify a fact, say 'I don't know'."
- Keep responses concise (you have a 350 token limit)
- Output ONLY the JSON object, nothing else
```

**Agent Definition:**
```python
expander_agent = Agent(
    role="Prompt Expander",
    goal="Generate three distinct, high-quality prompt variations using different techniques",
    backstory="You are a master prompt engineer who understands different prompting strategies: "
              "direct role-based, chain-of-thought, and role-immersive with guardrails. "
              "You create prompts that minimize hallucinations and maximize clarity.",
    llm=DEEPSEEK_EXPAND,
    verbose=True,
    allow_delegation=False,
)
```

### 7.4 Agent 3: CRITIC

**Purpose:** Evaluate prompt variations and rank them

**Model:** `GEMINI_FAST`

**Prompt Template (EXACT):**
```
You are a prompt quality critic. Evaluate the three prompt variations below.

EXPANSIONS:
{expansions_json}

For each variation (A, B, C), identify potential issues and assign a rank (1=best, 2=middle, 3=worst).

You MUST respond with ONLY valid JSON in this exact format (no additional text):
{{
  "A": {{
    "issues": ["<issue 1>", "<issue 2>", ...],
    "rank": <1, 2, or 3>
  }},
  "B": {{
    "issues": ["<issue 1>", "<issue 2>", ...],
    "rank": <1, 2, or 3>
  }},
  "C": {{
    "issues": ["<issue 1>", "<issue 2>", ...],
    "rank": <1, 2, or 3>
  }}
}}

Evaluation criteria:
- Hallucination risk (does it encourage making things up?)
- Ambiguity (is it clear what's expected?)
- Missing constraints (are requirements omitted?)
- Clarity and structure
- If no issues, use empty array []
- Ensure ranks are unique (1, 2, 3)
- Output ONLY the JSON object, nothing else
```

**Agent Definition:**
```python
critic_agent = Agent(
    role="Prompt Critic",
    goal="Evaluate prompt variations and identify potential issues",
    backstory="You are a meticulous prompt evaluator with deep expertise in identifying "
              "hallucination risks, ambiguities, and missing constraints. "
              "You rank prompts based on quality and robustness.",
    llm=GEMINI_FAST,
    verbose=True,
    allow_delegation=False,
)
```

### 7.5 Agent 4: SYNTHESIZER

**Purpose:** Create the final "golden prompt" by synthesizing best elements

**Model:** `GEMINI_FAST`

**Prompt Template (EXACT):**
```
You are a prompt synthesis expert. Create the final "golden prompt" by combining the best elements from all variations.

DISCERN:
{discern_json}

EXPANSIONS:
{expansions_json}

CRITIQUE:
{critic_json}

Create a SINGLE optimal prompt that:
1. Incorporates the best elements from the top-ranked variations
2. Addresses all identified issues
3. MUST include these anti-hallucination guardrails:
   - "Provide sources for any factual claims"
   - "Use stepwise reasoning for complex questions"
   - Explicitly state: "If you cannot verify a fact, say 'I don't know'."
4. MUST instruct the assistant to output final answers in strict JSON format

You MUST respond with ONLY valid JSON in this exact format (no additional text):
{{
  "golden_prompt": "<the final optimized prompt>",
  "rationale": "<explanation of design choices>",
  "token_est": <estimated tokens for the golden prompt>,
  "cost_est_usd": <estimated cost to run this prompt, use $0.00 for gemini flash>
}}

Requirements:
- The golden prompt must be production-ready
- It must enforce structured JSON output from the assistant
- Include all mandatory guardrails
- Keep it concise but comprehensive
- Output ONLY the JSON object, nothing else
```

**Agent Definition:**
```python
synthesizer_agent = Agent(
    role="Prompt Synthesizer",
    goal="Create the final optimized 'golden prompt' with anti-hallucination guardrails",
    backstory="You are a prompt synthesis expert who combines the best elements from multiple "
              "variations to create a single, optimal prompt. You ensure all guardrails are "
              "in place to prevent hallucinations and enforce structured output.",
    llm=GEMINI_FAST,
    verbose=True,
    allow_delegation=False,
)
```

---

## 8. TASKS MODULE (`tasks.py`)

### 8.1 Purpose
Create CrewAI Task factory functions for the sequential workflow.

### 8.2 Functions to Implement

#### 8.2.1 `create_discern_task(idea: str) -> Task`
```python
return Task(
    description=DISCERNER_PROMPT_TEMPLATE.format(idea=idea),
    agent=discerner_agent,
    expected_output="JSON object with intent, audience, constraints, success_criteria, and ambiguous fields",
)
```

#### 8.2.2 `create_expander_task(discern_json: str) -> Task`
```python
return Task(
    description=EXPANDER_PROMPT_TEMPLATE.format(discern_json=discern_json),
    agent=expander_agent,
    expected_output="JSON object with A, B, C variations, each containing prompt, notes, and token_est",
)
```

#### 8.2.3 `create_critic_task(expansions_json: str) -> Task`
```python
return Task(
    description=CRITIC_PROMPT_TEMPLATE.format(expansions_json=expansions_json),
    agent=critic_agent,
    expected_output="JSON object with A, B, C critiques, each containing issues and rank",
)
```

#### 8.2.4 `create_synthesizer_task(discern_json: str, expansions_json: str, critic_json: str) -> Task`
```python
return Task(
    description=SYNTHESIZER_PROMPT_TEMPLATE.format(
        discern_json=discern_json,
        expansions_json=expansions_json,
        critic_json=critic_json,
    ),
    agent=synthesizer_agent,
    expected_output="JSON object with golden_prompt, rationale, token_est, and cost_est_usd",
)
```

---

## 8.5 ORCHESTRATOR MODULE (`orchestrator.py`) — NEW IN v2

### 8.5.1 Purpose
Main v2 pipeline orchestrator implementing Judge-then-Generate workflow.

### 8.5.2 PromptimaV2 Class

```python
class PromptimaV2:
    """Main orchestrator for v2 pipeline."""
    
    def __init__(self, use_cache: bool = True, dry_run: bool = False):
        self.use_cache = use_cache
        self.dry_run = dry_run
        self.tracker = TokenTracker()
    
    def run(self, idea: str) -> Dict[str, Any]:
        """Run the full v2 pipeline."""
        # 1. Check cache
        # 2. Run 5 stages
        # 3. Build output
        # 4. Save to cache
        # 5. Return result
```

### 8.5.3 Stage Methods

| Method | Model | Max Tokens | Input | Output Schema |
|--------|-------|------------|-------|---------------|
| `_run_discerner(idea)` | GEMINI_FAST | 300 | idea string | `DiscernOutput` |
| `_run_critic_first(idea, discern)` | GEMINI_FAST | 400 | idea + DiscernOutput | `RubricOutput` |
| `_run_expander(idea, discern, rubric)` | DEEPSEEK_CHEAP | 350 | idea + discern + rubric | `ExpansionsOutput` |
| `_run_ranker(expansions, rubric)` | GEMINI_FAST | 150 | expansions + rubric | `RankingsOutput` |
| `_run_synthesizer(idea, discern, rubric, expansions, rankings)` | GEMINI_FAST | 800 | all previous | `SynthesizerOutput` |

### 8.5.4 Stage Prompts (EXACT)

**DISCERNER_PROMPT:**
```
Analyze this prompt idea and identify key characteristics:

IDEA: {idea}

Respond with ONLY valid JSON:
{{
  "task_type": "<classification|generation|analysis|transformation|other>",
  "complexity": "<simple|moderate|complex>",
  "domain": "<general|technical|creative|analytical>",
  "key_requirements": ["<requirement1>", "<requirement2>", ...],
  "potential_pitfalls": ["<pitfall1>", "<pitfall2>", ...],
  "recommended_approach": "<brief strategy>"
}}
```

**CRITIC_FIRST_PROMPT:** (KEY v2 ADDITION)
```
You are a prompt quality expert. Generate a rubric for evaluating prompts for this task.

TASK ANALYSIS:
{discern_json}

ORIGINAL IDEA:
{idea}

Generate criteria that a high-quality prompt for this task MUST satisfy.

Respond with ONLY valid JSON:
{{
  "rubric": {{
    "<criterion_name>": "<what it means and how to achieve it>",
    ...
  }},
  "checklist": [
    "<specific checkable item 1>",
    "<specific checkable item 2>",
    ...
  ],
  "red_flags": [
    "<anti-pattern to avoid 1>",
    "<anti-pattern to avoid 2>",
    ...
  ]
}}

Include 3-5 rubric criteria, 6-10 checklist items, 3-5 red flags.
```

**EXPANDER_PROMPT:** (v2 - WITH RUBRIC INJECTION)
```
Generate 3 distinct prompt variations for this task.

ORIGINAL IDEA:
{idea}

TASK ANALYSIS:
{discern_json}

QUALITY RUBRIC (YOU MUST FOLLOW):
{rubric_json}

CHECKLIST (EACH PROMPT MUST ADDRESS):
{checklist}

RED FLAGS (AVOID THESE):
{red_flags}

Generate 3 variations with different approaches (concise/detailed/structured).

Respond with ONLY valid JSON:
{{
  "A": {{"prompt": "<variation A>", "notes": "<approach notes>", "checklist_score": "<X/Y items addressed>"}},
  "B": {{"prompt": "<variation B>", "notes": "<approach notes>", "checklist_score": "<X/Y items addressed>"}},
  "C": {{"prompt": "<variation C>", "notes": "<approach notes>", "checklist_score": "<X/Y items addressed>"}}
}}

CRITICAL: Each prompt must be complete and standalone. Include anti-hallucination guardrails.
```

**RANKER_PROMPT:**
```
Rank these prompt variations based on quality.

RUBRIC CRITERIA:
{rubric_summary}

VARIATIONS:
{variations_summary}

Rank 1=best, 2=middle, 3=worst.

Respond with ONLY valid JSON:
{{
  "A": {{"rank": <1|2|3>, "score": <0.0-1.0>}},
  "B": {{"rank": <1|2|3>, "score": <0.0-1.0>}},
  "C": {{"rank": <1|2|3>, "score": <0.0-1.0>}}
}}

Ranks must be UNIQUE (1, 2, 3 each used exactly once).
```

**SYNTHESIZER_PROMPT:**
```
Create the FINAL optimized prompt by synthesizing the best elements.

ORIGINAL IDEA:
{idea}

RUBRIC:
{rubric_json}

RANKED VARIATIONS (Best → Worst):
{ranked_variations}

Respond with ONLY valid JSON:
{{
  "final_prompt": "<complete optimized prompt>",
  "synthesis_notes": "<explain synthesis decisions>",
  "rubric_compliance": {{"<criterion>": "<how addressed>", ...}},
  "confidence": <0.0-1.0>
}}
```

### 8.5.5 Output Structure (v2)

```python
{
    "version": "v2",
    "timestamp": "<ISO timestamp>",
    "original_idea": "<user's idea>",
    "task_analysis": {  # DiscernOutput
        "task_type": "...",
        "complexity": "...",
        "domain": "...",
        "key_requirements": [...],
        "potential_pitfalls": [...],
        "recommended_approach": "..."
    },
    "rubric": {  # RubricOutput - NEW IN v2
        "criteria": {...},
        "checklist": [...],
        "red_flags": [...]
    },
    "variations": {
        "A": {"prompt": "...", "notes": "...", "checklist_score": "...", "rank": 1-3, "score": 0.0-1.0},
        "B": {...},
        "C": {...}
    },
    "final_synthesis": {  # SynthesizerOutput
        "prompt": "<final golden prompt>",
        "notes": "<synthesis decisions>",
        "rubric_compliance": {...},
        "confidence": 0.0-1.0
    },
    "usage": {  # TokenTracker summary
        "total_calls": 5,
        "total_input_tokens": ...,
        "total_output_tokens": ...,
        "total_cost_usd": ...,
        "by_stage": [...]
    }
}
```

### 8.5.6 CLI Interface

```python
def main():
    parser = argparse.ArgumentParser(
        description="Promptimal v2 - Judge-then-Generate Prompt Optimizer"
    )
    parser.add_argument("idea", nargs="?", help="The prompt idea to optimize")
    parser.add_argument("--file", "-f", help="Read idea from file")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without API calls")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
```

---

## 9. MAIN MODULE (`main.py`) — LEGACY v1

### 9.0 IMPORTANT ARCHITECTURAL NOTE

**The prompts are embedded INLINE in `main.py`**, not imported from `agents.py`. The `agents.py` file defines the templates as constants (`DISCERNER_PROMPT_TEMPLATE`, etc.) for future CrewAI integration, but the current 60% implementation in `main.py` embeds the exact same prompts directly in the `run_optimization()` function.

This means you will have the same prompt text appearing in two places:
1. As template constants in `agents.py` (for future CrewAI Task-based workflow)
2. As inline strings in `main.py` (for the current direct `call_llm()` workflow)

Both should contain identical prompt text.

### 9.1 CLI Arguments (EXACT)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--idea` | str | None | Single prompt idea to optimize |
| `--batch` | str | None | Path to JSONL file with multiple ideas |
| `--dry-run` | flag | False | Only estimate cost, no LLM calls |
| `--max-tokens` | int | 2000 | Maximum tokens per LLM call |
| `--parallel` | flag | False | Enable parallel batch processing |
| `--seed` | int | 42 | Random seed for reproducibility |
| `--output` | str | None | Output file path (default: stdout) |

**Validation Rules:**
- Either `--idea` OR `--batch` must be provided (not both, not neither)

### 9.2 Function: `parse_args()`
Use `argparse.ArgumentParser` with description: `"Consensus Prompt Optimizer - Multi-agent prompt optimization with cost < $0.05"`

### 9.3 Function: `estimate_dry_run_cost(idea: str) -> Dict[str, Any]`

This function returns a JSON skeleton with cost estimates WITHOUT making LLM calls.

**Token Estimation Logic:**
1. `idea_tokens = estimate_tokens(idea)`
2. Discerner: input=idea_tokens, output=100 (estimated)
3. Expander: input=100, output=350 (capped)
4. Critic: input=350, output=150 (estimated)
5. Synthesizer: input=100+350+150=600, output=200 (estimated)

**Return Structure (EXACT):**
```python
{
    "input": idea,
    "discern": {
        "intent": "<dry-run>",
        "audience": "<dry-run>",
        "constraints": [],
        "success_criteria": "<dry-run>",
        "ambiguous": []
    },
    "expansions": {
        "A": {"prompt": "<dry-run>", "notes": "<dry-run>", "token_est": 0},
        "B": {"prompt": "<dry-run>", "notes": "<dry-run>", "token_est": 0},
        "C": {"prompt": "<dry-run>", "notes": "<dry-run>", "token_est": 0}
    },
    "critic": {
        "A": {"issues": [], "rank": 0},
        "B": {"issues": [], "rank": 0},
        "C": {"issues": [], "rank": 0}
    },
    "final": {
        "golden_prompt": "<dry-run>",
        "rationale": "<dry-run>",
        "token_est": synthesizer_output,
        "cost_est_usd": round(total_cost, 6)
    },
    "meta": {
        "seed": 0,
        "duration_s": 0.0,
        "models_used": [GEMINI_FAST, DEEPSEEK_EXPAND],
        "estimated_total_cost_usd": round(total_cost, 6),
        "dry_run": True
    }
}
```

### 9.4 Function: `run_optimization(idea, seed, max_tokens, dry_run=False) -> Dict[str, Any]`

**Flow:**
1. Record `start_time = time.time()`
2. Call `set_seed(seed)`
3. Call `reset_deepseek_counter()`
4. Call `log_event("run.start", {"idea": idea, "seed": seed})`
5. If `dry_run`, return `estimate_dry_run_cost(idea)`
6. Initialize `models_used = []`

**Stage 1: Discerner**
- Call `call_llm(model=GEMINI_FAST, prompt=<discerner_prompt>, max_tokens=max_tokens, enforce_json=True)`
- The prompt is the DISCERNER_PROMPT_TEMPLATE with idea substituted (see Section 7.2)
- Parse response with `parse_json_response()`
- Append `GEMINI_FAST` to `models_used`

**Stage 2: Expander (ONLY DEEPSEEK CALL)**
- Call `call_llm(model=DEEPSEEK_EXPAND, prompt=<expander_prompt>, max_tokens=350, enforce_json=True)`
- Note: max_tokens is explicitly set to 350
- The prompt is the EXPANDER_PROMPT_TEMPLATE with discern_json substituted
- Parse response
- Append `DEEPSEEK_EXPAND` to `models_used`

**Stage 3: Critic**
- Call `call_llm(model=GEMINI_FAST, prompt=<critic_prompt>, max_tokens=max_tokens, enforce_json=True)`
- The prompt is the CRITIC_PROMPT_TEMPLATE with expansions_json substituted
- Parse response
- Append `GEMINI_FAST` to `models_used`

**Stage 4: Synthesizer**
- Call `call_llm(model=GEMINI_FAST, prompt=<synthesizer_prompt>, max_tokens=max_tokens, enforce_json=True)`
- The prompt is the SYNTHESIZER_PROMPT_TEMPLATE with all three JSONs substituted
- Parse response
- Append `GEMINI_FAST` to `models_used`

**Final Assembly:**
```python
result = {
    "input": idea,
    "discern": discern_json,
    "expansions": expansions_json,
    "critic": critic_json,
    "final": final_json,
    "meta": {
        "seed": seed,
        "duration_s": round(duration, 2),
        "models_used": models_used,
        "deepseek_calls": get_deepseek_call_count(),
    }
}
```

Call `log_event("run.end", {"duration_s": duration, "success": True})` and return result.

On exception, call `log_event("run.error", {"error": str(e)})` and re-raise.

### 9.5 Function: `main()`

**Batch Mode Logic:**
1. Check if batch file exists with `Path(args.batch).exists()`
2. If not, print error to stderr and `sys.exit(1)`
3. Read JSONL file: each line is JSON with `"idea"` key
4. For each idea (with index `idx`):
   - Print progress to stderr: `f"Processing idea {idx + 1}/{len(ideas)}..."`
   - Call `run_optimization(idea=idea, seed=args.seed + idx, max_tokens=args.max_tokens, dry_run=args.dry_run)`
   - Note: seed is incremented by index for each idea
5. Wrap results: `{"results": results, "batch": True}`

**Single Mode Logic:**
- Call `run_optimization(idea=args.idea, seed=args.seed, max_tokens=args.max_tokens, dry_run=args.dry_run)`

**Output Logic:**
- If `args.output` specified: write JSON to file, print confirmation to stderr
- Otherwise: print JSON to stdout with `indent=2`

**Golden Prompt Display (non-batch, non-dry-run only):**
```python
print("\n" + "="*80, file=sys.stderr)
print("GOLDEN PROMPT:", file=sys.stderr)
print("="*80, file=sys.stderr)
print(result["final"]["golden_prompt"], file=sys.stderr)
print("="*80, file=sys.stderr)
```

**Entry Point:**
```python
if __name__ == "__main__":
    main()
```

---

## 10. TEST FILES

### 10.1 `tests/test_dry_run.py`

Implement these exact test functions:

#### `test_dry_run_returns_valid_json()`
- Call `estimate_dry_run_cost()` with idea `"Write persuasive landing pages for SaaS products"`
- Assert result is a dict
- Assert these top-level keys exist: `["input", "discern", "expansions", "critic", "final", "meta"]`
- Assert `result["input"]` equals the idea
- Assert discern has keys: `intent`, `audience`, `constraints`, `success_criteria`, `ambiguous`
- Assert expansions has keys `A`, `B`, `C`, each with `prompt`, `notes`, `token_est`
- Assert critic has keys `A`, `B`, `C`, each with `issues`, `rank`
- Assert final has keys: `golden_prompt`, `rationale`, `token_est`, `cost_est_usd`
- Assert meta has keys: `seed`, `duration_s`, `models_used`, `estimated_total_cost_usd`, `dry_run`
- Assert `result["meta"]["dry_run"]` is `True`

#### `test_dry_run_cost_under_budget()`
- Get cost from `result["meta"]["estimated_total_cost_usd"]`
- Assert cost is numeric
- Assert `cost < 0.05` with message: `f"Estimated cost ${cost} exceeds budget of $0.05"`
- Assert `cost >= 0`

#### `test_dry_run_different_ideas()`
- Test with three ideas of different lengths:
  - `"Short idea"`
  - `"Medium length idea that has more details"`
  - `"Very long idea with lots of context and details that spans multiple sentences and provides extensive background information about what we want to accomplish with this prompt optimization task"`
- For each, verify `result["input"]` matches and cost < $0.05

### 10.2 `tests/test_integration.py`

Create a placeholder test:

```python
def test_integration_example_idea():
    """
    Integration test for the example idea.
    Skipped to avoid API costs during development.
    """
    pytest.skip("Integration test requires API keys and incurs costs")
    
    # Include commented-out code showing what the full test would look like
```

---

## 11. OUTPUT JSON SCHEMA — v2 (EXACT)

Every v2 run (non-dry-run) MUST produce this exact structure:

```json
{
  "version": "v2",
  "timestamp": "<ISO 8601 timestamp>",
  "original_idea": "<user's input idea>",
  "task_analysis": {
    "task_type": "classification|generation|analysis|transformation|other",
    "complexity": "simple|moderate|complex",
    "domain": "general|technical|creative|analytical",
    "key_requirements": ["string", ...],
    "potential_pitfalls": ["string", ...],
    "recommended_approach": "string"
  },
  "rubric": {
    "criteria": {"<name>": "<description>", ...},
    "checklist": ["string", ...],
    "red_flags": ["string", ...]
  },
  "variations": {
    "A": {"prompt": "string", "notes": "string", "checklist_score": "X/Y", "rank": 1|2|3, "score": 0.0-1.0},
    "B": {"prompt": "string", "notes": "string", "checklist_score": "X/Y", "rank": 1|2|3, "score": 0.0-1.0},
    "C": {"prompt": "string", "notes": "string", "checklist_score": "X/Y", "rank": 1|2|3, "score": 0.0-1.0}
  },
  "final_synthesis": {
    "prompt": "string",
    "notes": "string",
    "rubric_compliance": {"<criterion>": "<how addressed>", ...},
    "confidence": 0.0-1.0
  },
  "usage": {
    "total_calls": 5,
    "total_input_tokens": number,
    "total_output_tokens": number,
    "total_cost_usd": number,
    "by_stage": [{"stage": "string", "model": "string", "input_tokens": number, "output_tokens": number, "cost": number}, ...]
  }
}
```

### 11.1 v1 Legacy Schema (for reference)

v1 runs produce the older structure with `discern`, `expansions`, `critic`, `final`, `meta` keys (see v1 documentation).

---

## 12. ANTI-HALLUCINATION GUARDRAILS (MANDATORY)

Every golden prompt MUST include these three elements:
1. **Source requirement:** "Provide sources for any factual claims"
2. **Stepwise reasoning:** "Use stepwise reasoning for complex questions"
3. **Uncertainty handling:** Explicitly state "If you cannot verify a fact, say 'I don't know'."

Additionally, every golden prompt MUST instruct the assistant to output in **strict JSON format**.

---

## 13. CRITICAL CONSTRAINTS CHECKLIST — v2

| Constraint | Requirement | How to Verify |
|------------|-------------|---------------|
| Cost per run | **≤ $0.025 USD** | Check `usage.total_cost_usd` |
| DeepSeek calls | Exactly 1 | Check `usage.by_stage` for single DeepSeek entry |
| DeepSeek tokens | ≤ 350 | `DEEPSEEK_TOKEN_CAP` constant |
| Gemini tokens | 150-800 per stage | Stage-specific limits |
| Schema validation | Pydantic models | All outputs validated with `validate_stage_output()` |
| Caching | SHA-256 hash | Identical ideas return cached results |
| Temperature | 0 for JSON | Deterministic outputs |
| Judge-then-Generate | CriticFirst BEFORE Expander | Rubric injected into Expander prompt |
| Unique ranks | 1, 2, 3 | `@field_validator` on RankingsOutput |
| CLI flags | 6 implemented | `idea`, `--file`, `--output`, `--dry-run`, `--no-cache`, `--verbose` |
| JSON output | v2 schema | Matches Section 11 |

---

## 14. EXAMPLE OUTPUT (v2)

Use this as a reference for the expected output format:

**Input:** `"I want a prompt that writes persuasive landing pages for indie SaaS products."`

**Expected `meta` section:**
```json
{
  "seed": 42,
  "duration_s": 12.5,
  "models_used": [
    "gemini/gemini-1.5-flash",
    "deepseek/deepseek-chat",
    "gemini/gemini-1.5-flash",
    "gemini/gemini-1.5-flash"
  ],
  "deepseek_calls": 1,
  "total_cost_estimate_usd": 0.042
}
```

---

## 15. IMPORT STATEMENTS

### 15.1 `config.py`
```python
import os
from dotenv import load_dotenv
```

### 15.2 `utils.py`
```python
import time
import json
from typing import Any, Callable, Dict
from functools import wraps
from config import PRICES_USD
```

### 15.3 `llm_wrapper.py`
```python
import json
from typing import Dict, Any, Optional
from litellm import completion
from config import DEEPSEEK_EXPAND, MAX_TOKENS_PER_CALL, EXPANDER_TOKEN_LIMIT
from utils import retry_with_backoff, log_event
```

### 15.4 `agents.py`
```python
from crewai import Agent
from config import GEMINI_FAST, DEEPSEEK_EXPAND
```

### 15.5 `tasks.py`
```python
from crewai import Task
from agents import (
    discerner_agent,
    expander_agent,
    critic_agent,
    synthesizer_agent,
    DISCERNER_PROMPT_TEMPLATE,
    EXPANDER_PROMPT_TEMPLATE,
    CRITIC_PROMPT_TEMPLATE,
    SYNTHESIZER_PROMPT_TEMPLATE,
)
```

### 15.6 `main.py`
```python
import argparse
import json
import time
import sys
from typing import Dict, Any, Optional
from pathlib import Path

from crewai import Crew
from config import DEFAULT_SEED, MAX_TOKENS_PER_CALL, GEMINI_FAST, DEEPSEEK_EXPAND
from utils import estimate_tokens, estimate_cost_usd, set_seed, log_event
from llm_wrapper import call_llm, parse_json_response, reset_deepseek_counter, get_deepseek_call_count
from agents import discerner_agent, expander_agent, critic_agent, synthesizer_agent
from tasks import create_discern_task, create_expander_task, create_critic_task, create_synthesizer_task
```

---

## 16. DOCUMENTATION FILES

### 16.1 `README.md`
Create a comprehensive README with:
- Project title: "Consensus Prompt Optimizer"
- One-line description mentioning CrewAI, LiteLLM, and <$0.05 cost
- Overview of the 4 agents
- Cost constraints section
- Installation instructions
- Configuration (API keys)
- Usage examples for all CLI modes
- Output format with JSON example
- Anti-hallucination guardrails explanation
- Architecture diagram (ASCII art of folder structure)
- Testing instructions
- Example run command and output
- Next steps section (40%→80%→100%)

### 16.2 `DELIVERABLES.md` and `PROJECT_SUMMARY.md`
Create documentation summarizing:
- What was delivered (60% core implementation)
- File manifest with line counts
- The exact Expander prompt
- Simulated run output
- Path to 80% and 100%
- Constraints verification table

---

## 17. VERIFICATION COMMANDS (v2)

After implementation, verify with:

```bash
# v2: Test dry-run mode (no API keys needed)
python -m consensus_prompt_optimizer.orchestrator "Test idea" --dry-run

# v2: Full run with caching (requires API keys in .env)
python -m consensus_prompt_optimizer.orchestrator "Write persuasive landing pages" -v

# v2: Full run without caching
python -m consensus_prompt_optimizer.orchestrator "Test idea" --no-cache

# v2: Read idea from file
python -m consensus_prompt_optimizer.orchestrator -f idea.txt -o output.json

# Run all tests including v2
pytest tests/ -v

# Run only v2 tests
pytest tests/test_v2.py -v

# Legacy v1: Test dry-run mode
python -m consensus_prompt_optimizer.main --idea "Test idea" --dry-run
```

---

## 18. NOTES FOR THE IMPLEMENTING AGENT (v2 UPDATED)

1. **Do not deviate from the specifications.** Every function name, parameter, return type, and string literal is intentional.

2. **v2 uses `orchestrator.py`** as the main entry point, NOT `main.py`. The `main.py` is legacy v1.

3. **Pydantic validation is mandatory** in v2. All stage outputs must be validated with `validate_stage_output()`.

4. **Judge-then-Generate is critical**: CriticFirst MUST run BEFORE Expander. The rubric, checklist, and red_flags are injected into the Expander prompt.

5. **Double-brace escaping** in prompt templates: Use `{{` and `}}` in Python f-strings to produce literal `{` and `}` in the output.

6. **Temperature = 0** for all JSON-mode calls in v2 to ensure deterministic outputs.

7. **SHA-256 caching**: Identical ideas (case-insensitive, trimmed) return cached results instantly.

8. **Token tracking**: Use `TokenTracker` class to aggregate costs across all stages.

9. **Import style**: Use relative imports within the package (e.g., `from config import ...` not `from consensus_prompt_optimizer.config import ...`).

10. **Cost budget**: v2 enforces ≤$0.025/run (down from v1's $0.05). This is achieved through prompt compression and optimized token limits.

11. **Legacy files retained**: `agents.py`, `tasks.py`, `main.py`, `llm_wrapper.py` are kept for v1 compatibility but v2 uses the new orchestrator.

11. **Prompt template variables**: In `agents.py`, the prompt templates use single-brace placeholders like `{idea}`, `{discern_json}`, etc. These are meant for `.format()` string substitution, NOT f-strings.

12. **JSON serialization in prompts**: When substituting JSON into prompts, use `json.dumps(obj, indent=2)` to pretty-print the JSON for better LLM comprehension.

---

## 19. COMPLETE `.env.example` FILE

```
# Required API Keys
GEMINI_API_KEY=your_gemini_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Langfuse Telemetry
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

---

## 20. COMPLETE `example_output.json` FILE

```json
{
    "input": "I want a prompt that writes persuasive landing pages for indie SaaS products.",
    "discern": {
        "intent": "Generate persuasive landing page copy that converts visitors into customers for indie SaaS products",
        "audience": "Indie SaaS founders, marketing teams, and copywriters who need to create compelling landing pages",
        "constraints": [
            "Must be persuasive and conversion-focused",
            "Targeted at indie/bootstrapped SaaS businesses (not enterprise)",
            "Should produce landing page copy (not full website)",
            "Must understand SaaS-specific value propositions"
        ],
        "success_criteria": "Landing page copy that clearly communicates value proposition, addresses pain points, and includes strong calls-to-action",
        "ambiguous": [
            "What sections of the landing page should be included? (hero, features, pricing, testimonials, etc.)",
            "What tone/voice is preferred? (professional, casual, technical, friendly)",
            "Should it include specific frameworks like PAS (Problem-Agitate-Solution) or AIDA?"
        ]
    },
    "expansions": {
        "A": {
            "prompt": "You are an expert SaaS copywriter. Write persuasive landing page copy for an indie SaaS product. Include: headline, subheadline, value proposition, 3 key features, social proof section, and a strong call-to-action. Make it conversion-focused and clearly communicate the product's unique benefits.",
            "notes": "Direct role-based approach with clear structural requirements",
            "token_est": 180
        },
        "B": {
            "prompt": "You are an expert SaaS copywriter. Write persuasive landing page copy for an indie SaaS product. Think step-by-step: First, identify the target customer's main pain point. Second, craft a compelling headline that addresses this pain. Third, develop a value proposition that shows the solution. Fourth, list 3 concrete benefits with examples. Fifth, add credibility elements. Finally, create an urgent call-to-action. Use the AIDA framework (Attention, Interest, Desire, Action) throughout.",
            "notes": "Chain-of-thought with explicit reasoning steps and framework guidance",
            "token_est": 220
        },
        "C": {
            "prompt": "You are a veteran SaaS marketing copywriter with 10+ years of experience writing high-converting landing pages for bootstrapped startups. Write persuasive landing page copy for an indie SaaS product. Requirements: 1) Provide sources or examples for any statistics or claims you make. 2) Use stepwise reasoning to structure your copy logically. 3) If you cannot verify a specific claim or best practice, explicitly say 'I don't know' rather than making assumptions. Output your response in JSON format with fields: {headline, subheadline, value_proposition, features: [], social_proof, cta, reasoning}.",
            "notes": "Role-immersive with anti-hallucination guardrails and structured output",
            "token_est": 280
        }
    },
    "critic": {
        "A": {
            "issues": [
                "Lacks explicit anti-hallucination safeguards",
                "No structured output format specified",
                "Could be more specific about tone and style"
            ],
            "rank": 3
        },
        "B": {
            "issues": [
                "No anti-hallucination guardrails",
                "AIDA framework mentioned but not strictly enforced",
                "Missing structured output requirement"
            ],
            "rank": 2
        },
        "C": {
            "issues": [
                "Could specify more about the indie SaaS context (bootstrapped, specific pain points)"
            ],
            "rank": 1
        }
    },
    "final": {
        "golden_prompt": "You are a veteran SaaS marketing copywriter with 10+ years of experience creating high-converting landing pages for bootstrapped indie SaaS startups. Your task is to write persuasive landing page copy.\n\nContext: You're writing for indie SaaS products (typically bootstrapped, targeting SMBs or individual users, solving specific pain points with focused solutions).\n\nApproach:\n1. Think step-by-step: First identify the target customer's primary pain point, then craft solutions that address it directly.\n2. Use the AIDA framework (Attention, Interest, Desire, Action) to structure your copy.\n3. Provide sources, examples, or references for any statistics, best practices, or industry claims you make.\n4. If you cannot verify a fact or claim, explicitly state \"I don't know\" rather than making assumptions.\n5. Use stepwise reasoning to ensure logical flow from problem to solution to action.\n\nIMPORTANT: You must output your response in strict JSON format with the following structure:\n{\n  \"headline\": \"<attention-grabbing headline>\",\n  \"subheadline\": \"<supporting subheadline>\",\n  \"value_proposition\": \"<clear statement of unique value>\",\n  \"features\": [\n    {\"title\": \"<feature name>\", \"description\": \"<benefit-focused description>\", \"example\": \"<concrete example>\"}\n  ],\n  \"social_proof\": \"<testimonial or credibility element>\",\n  \"cta\": \"<compelling call-to-action>\",\n  \"reasoning\": \"<your step-by-step thought process>\"\n}\n\nRemember: If you cannot verify a fact, say \"I don't know.\" Provide sources for claims. Output ONLY valid JSON.",
        "rationale": "This golden prompt combines the best elements from all three variations: the role-based clarity of A, the step-by-step reasoning framework from B, and the anti-hallucination guardrails and structured output from C. It adds specific context about indie SaaS (bootstrapped, SMB-focused) to address the identified ambiguities. The prompt enforces verification of claims, explicit handling of uncertainty, and structured JSON output for downstream processing. It maintains conciseness while including all mandatory safety guardrails.",
        "token_est": 320,
        "cost_est_usd": 0.0
    },
    "meta": {
        "seed": 42,
        "duration_s": 12.5,
        "models_used": [
            "gemini/gemini-1.5-flash",
            "deepseek/deepseek-chat",
            "gemini/gemini-1.5-flash",
            "gemini/gemini-1.5-flash"
        ],
        "deepseek_calls": 1,
        "total_cost_estimate_usd": 0.042
    }
}
```

---

## 21. EXACT MODULE DOCSTRINGS

### 21.1 `config.py`
```python
"""
Configuration module for Consensus Prompt Optimizer.
Defines model routing, pricing, and environment settings.
"""
```

### 21.2 `utils.py`
```python
"""
Utility functions for the Consensus Prompt Optimizer.
Includes token estimation, cost calculation, retry logic, and telemetry hooks.
"""
```

### 21.3 `llm_wrapper.py`
```python
"""
LiteLLM wrapper with enforcement of single DeepSeek call policy.
"""
```

### 21.4 `agents.py`
```python
"""
CrewAI Agent definitions for the Consensus Prompt Optimizer.
Defines 4 agents: Discerner, Expander, Critic, and Synthesizer.
"""
```

### 21.5 `tasks.py`
```python
"""
CrewAI Task definitions for the Consensus Prompt Optimizer.
Defines the sequential workflow for the 4 agents.
"""
```

### 21.6 `main.py`
```python
"""
Main CLI entry point for the Consensus Prompt Optimizer.
Orchestrates the 4-agent workflow with cost enforcement.
"""
```

---

## 22. SECTION COMMENT STYLE

Use this exact comment style for section headers in Python files:

```python
# ============================================================================
# SECTION NAME
# ============================================================================
```

Subsection comments use this format:
```python
# Purpose: <description>
# Model: <model name>
# Output: <schema>
```

---

## 22.5 STDOUT VS STDERR ROUTING

**Critical:** The application carefully routes output:

| Output Type | Destination | Rationale |
|-------------|-------------|-----------|
| JSON result | `stdout` | Machine-parseable output |
| Progress messages | `stderr` | Human-readable, doesn't pollute JSON |
| Error messages | `stderr` | Standard error channel |
| Golden prompt display | `stderr` | Human-readable, after JSON output |
| Telemetry logs | `stdout` via print | Development logging |

Specific patterns:
- `print(json.dumps(output_data, indent=2))` → stdout (no file= argument)
- `print(f"Processing idea...", file=sys.stderr)` → stderr
- `print(f"Error: ...", file=sys.stderr)` → stderr
- `print(f"Output written to: ...", file=sys.stderr)` → stderr

---

## 22.6 FUNCTION SIGNATURES (COMPLETE)

### utils.py
```python
def estimate_tokens(text: str) -> int:
def estimate_cost_usd(model_name: str, input_tokens: int, output_tokens: int = 0) -> float:
def retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0):  # returns decorator
def log_event(event_type: str, data: Dict[str, Any]) -> None:
def validate_json_schema(data: Dict[str, Any], required_keys: list) -> bool:
def set_seed(seed: int) -> None:
```

### llm_wrapper.py
```python
def reset_deepseek_counter() -> None:
def get_deepseek_call_count() -> int:
@retry_with_backoff(max_retries=3, initial_delay=1.0)
def call_llm(
    model: str,
    prompt: str,
    max_tokens: int = MAX_TOKENS_PER_CALL,
    enforce_json: bool = True,
    temperature: float = 0.7,
) -> Dict[str, Any]:
def parse_json_response(response: str) -> Dict[str, Any]:
```

### tasks.py
```python
def create_discern_task(idea: str) -> Task:
def create_expander_task(discern_json: str) -> Task:
def create_critic_task(expansions_json: str) -> Task:
def create_synthesizer_task(discern_json: str, expansions_json: str, critic_json: str) -> Task:
```

### main.py
```python
def parse_args():  # returns argparse.Namespace (implicit)
def estimate_dry_run_cost(idea: str) -> Dict[str, Any]:
def run_optimization(idea: str, seed: int, max_tokens: int, dry_run: bool = False) -> Dict[str, Any]:
def main():  # returns None (implicit)
```

### 22.7 `orchestrator.py` (v2)
```python
class PromptimaV2:
    def __init__(self, use_cache: bool = True, dry_run: bool = False): ...
    def run(self, idea: str) -> Dict[str, Any]: ...
    def _run_discerner(self, idea: str) -> DiscernOutput: ...
    def _run_critic_first(self, idea: str, discern: DiscernOutput) -> RubricOutput: ...
    def _run_expander(self, idea: str, discern: DiscernOutput, rubric: RubricOutput) -> ExpansionsOutput: ...
    def _run_ranker(self, expansions: ExpansionsOutput, rubric: RubricOutput) -> RankingsOutput: ...
    def _run_synthesizer(self, idea: str, discern: DiscernOutput, rubric: RubricOutput, expansions: ExpansionsOutput, rankings: RankingsOutput) -> SynthesizerOutput: ...
    def _build_output(self, ...) -> Dict[str, Any]: ...
def main(): ...
```

### 22.8 `llm_wrapper_v2.py` (v2)
```python
def count_tokens(text: str, model: str = "gpt-4") -> int: ...
def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float: ...
def compress_prompt(prompt: str, max_chars: int = 8000) -> str: ...
def get_idea_hash(idea: str) -> str: ...
def load_from_cache(idea: str) -> Optional[Dict]: ...
def save_to_cache(idea: str, result: Dict) -> None: ...
def call_llm_v2(model: str, prompt: str, max_tokens: int = 500, temperature: float = 0.0, enforce_json: bool = False, compress: bool = True) -> Dict[str, Any]: ...
def parse_json_response_v2(content: str) -> Dict[str, Any]: ...
class TokenTracker: ...
```

---

## 23. FILE LINE COUNTS (APPROXIMATE) — v2

For reference, the implementation has these approximate line counts:

| File | Lines | Notes |
|------|-------|-------|
| `__init__.py` | 5 | |
| `config.py` | 75 | Added v2 constants |
| `utils.py` | 135 | |
| `schemas.py` | 176 | **NEW in v2** |
| `llm_wrapper.py` | 128 | Legacy v1 |
| `llm_wrapper_v2.py` | 333 | **NEW in v2** |
| `agents.py` | 205 | Legacy v1 |
| `tasks.py` | 79 | Legacy v1 |
| `main.py` | 300 | Legacy v1 |
| `orchestrator.py` | 508 | **NEW in v2** - Main entry |
| `critic_first.py` | ~80 | **NEW in v2** |
| `expander.py` | ~100 | **NEW in v2** |
| `ranker.py` | ~130 | **NEW in v2** |
| `synthesizer.py` | ~170 | **NEW in v2** |
| `tests/__init__.py` | 3 | |
| `tests/test_dry_run.py` | 88 | Legacy v1 |
| `tests/test_integration.py` | 44 | Legacy v1 |
| `tests/test_v2.py` | ~250 | **NEW in v2** |

---

## 24. FINAL IMPLEMENTATION CHECKLIST (v2)

Before considering the implementation complete, verify:

### Core v2 Files
- [ ] `schemas.py` with all 6 Pydantic models
- [ ] `llm_wrapper_v2.py` with caching, compression, TokenTracker
- [ ] `orchestrator.py` with PromptimaV2 class
- [ ] `critic_first.py` (CriticFirst stage)
- [ ] `expander.py` (rubric-guided)
- [ ] `ranker.py` (lightweight ranking)
- [ ] `synthesizer.py` (rubric-aware)
- [ ] `tests/test_v2.py` with schema and pipeline tests

### v2 Configuration
- [ ] `config.py` has `DEEPSEEK_CHEAP` and `DEEPSEEK_TOKEN_CAP` constants
- [ ] `requirements.txt` includes `pydantic>=2.0.0`

### v2 Workflow
- [ ] Judge-then-Generate: CriticFirst runs BEFORE Expander
- [ ] Rubric injected into Expander prompt
- [ ] DeepSeek called exactly ONCE (in Expander)
- [ ] All outputs validated with Pydantic schemas
- [ ] SHA-256 caching implemented
- [ ] Temperature=0 for JSON calls

### v2 Constraints
- [ ] Cost per run ≤ $0.025
- [ ] DeepSeek tokens ≤ 350
- [ ] Unique ranks (1,2,3) enforced by @field_validator

### CLI & Output
- [ ] `--dry-run` mode works without API keys
- [ ] `--no-cache` flag disables caching
- [ ] `-v` flag shows usage summary
- [ ] v2 JSON output schema matches Section 11

### Tests
- [ ] `pytest tests/test_v2.py -v` passes
- [ ] Schema validation tests pass
- [ ] Dry-run pipeline test passes

---

END OF RECREATION PROMPT (v2)
