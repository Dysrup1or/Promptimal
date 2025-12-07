"""
Ranker stage for Promptimal v2 - Lightweight ranking of variations.
Replaces the heavier Critic stage from v1.

Key differences from v1 Critic:
- Focuses ONLY on ranking (no detailed issues list)
- Faster, fewer tokens
- Rubric was already applied upfront by CriticFirst
- Simply evaluates which variation best followed the rubric
"""

import json
from typing import Dict, Any

from .config import GEMINI_FAST
from .schemas import (
    RankingsOutput,
    ExpansionsOutput,
    RubricOutput,
    minify_json,
    validate_stage_output
)
from .llm_wrapper import call_llm, parse_json_response
from .utils import log_event


# ============================================================================
# RANKER PROMPT TEMPLATE (Lightweight)
# ============================================================================
RANKER_PROMPT = """You are a prompt quality ranker. Evaluate which variation best follows the rubric.

RUBRIC CRITERIA:
{rubric_json}

VARIATIONS TO RANK:
{expansions_json}

Rank the variations 1=best, 2=middle, 3=worst based on:
1. Rubric adherence (does it follow all criteria?)
2. Checklist score (reported by expander)
3. Anti-hallucination guardrails (are they present and clear?)
4. Clarity and completeness

You MUST respond with ONLY valid JSON:
{{
  "A": {{"rank": <1|2|3>, "score": <0.0-1.0>}},
  "B": {{"rank": <1|2|3>, "score": <0.0-1.0>}},
  "C": {{"rank": <1|2|3>, "score": <0.0-1.0>}}
}}

CRITICAL: Ranks must be UNIQUE (1, 2, 3 each used exactly once).
Score is your confidence in the variation's quality (0.0-1.0).
Output ONLY JSON."""


def run_ranker(
    expansions_output: ExpansionsOutput,
    rubric_output: RubricOutput,
    max_tokens: int = 150
) -> RankingsOutput:
    """
    Rank the 3 variations based on rubric adherence.
    
    This is a lightweight stage - detailed critique was done upfront
    in CriticFirst. Here we just rank which variation best followed
    the rubric guidance.
    
    Args:
        expansions_output: Validated output from Expander
        rubric_output: Validated output from CriticFirst (for reference)
        max_tokens: Maximum response tokens (default 150)
    
    Returns:
        Validated RankingsOutput with unique ranks 1, 2, 3
    
    Raises:
        ValueError: If ranks are not unique after retry
    """
    log_event("stage.ranker.start", {})
    
    # Format inputs (minified for efficiency)
    rubric_summary = {
        "criteria": list(rubric_output.rubric.keys()),
        "red_flags": rubric_output.red_flags
    }
    
    expansions_summary = {
        "A": {
            "notes": expansions_output.A.notes,
            "checklist_score": expansions_output.A.checklist_score,
            "preview": expansions_output.A.prompt[:200] + "..."
        },
        "B": {
            "notes": expansions_output.B.notes,
            "checklist_score": expansions_output.B.checklist_score,
            "preview": expansions_output.B.prompt[:200] + "..."
        },
        "C": {
            "notes": expansions_output.C.notes,
            "checklist_score": expansions_output.C.checklist_score,
            "preview": expansions_output.C.prompt[:200] + "..."
        }
    }
    
    prompt = RANKER_PROMPT.format(
        rubric_json=minify_json(rubric_summary),
        expansions_json=minify_json(expansions_summary)
    )
    
    # Call Gemini Flash
    response = call_llm(
        model=GEMINI_FAST,
        prompt=prompt,
        max_tokens=max_tokens,
        enforce_json=True,
        temperature=0.0
    )
    
    raw_output = parse_json_response(response["content"])
    
    # Validate unique ranks
    try:
        validated = validate_stage_output(raw_output, RankingsOutput)
        log_event("stage.ranker.success", {
            "rankings": {k: v.rank for k, v in validated.model_dump().items()}
        })
        return validated
    except ValueError as e:
        log_event("stage.ranker.validation_error", {"error": str(e)})
        # One retry with explicit instruction
        retry_prompt = prompt + "\n\nCRITICAL: Previous attempt had duplicate ranks. Use UNIQUE values 1, 2, 3."
        response = call_llm(
            model=GEMINI_FAST,
            prompt=retry_prompt,
            max_tokens=max_tokens,
            enforce_json=True,
            temperature=0.0
        )
        raw_output = parse_json_response(response["content"])
        validated = validate_stage_output(raw_output, RankingsOutput)
        log_event("stage.ranker.retry_success", {})
        return validated


def get_ranking_order(rankings: RankingsOutput) -> list:
    """
    Get variations in ranked order (best to worst).
    
    Args:
        rankings: Validated rankings
    
    Returns:
        List of variation keys ['C', 'A', 'B'] in rank order
    """
    items = [
        ('A', rankings.A.rank),
        ('B', rankings.B.rank),
        ('C', rankings.C.rank)
    ]
    return [k for k, _ in sorted(items, key=lambda x: x[1])]
