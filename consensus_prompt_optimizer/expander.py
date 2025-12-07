"""
Expander stage for Promptimal v2 - Rubric-guided prompt generation.
Uses DeepSeek (THE ONLY DeepSeek call) with rubric injection.

Key v2 changes:
- Receives rubric from CriticFirst stage
- Must score each variation against 12-item checklist
- Follows variation-specific guidance
- Token limit enforced at 350
"""

import json
from typing import Dict, Any

from config import DEEPSEEK_EXPAND, EXPANDER_TOKEN_LIMIT
from schemas import (
    ExpansionsOutput,
    DiscernOutput,
    RubricOutput,
    minify_json,
    validate_stage_output
)
from llm_wrapper import call_llm, parse_json_response
from critic_first import format_rubric_for_expander
from utils import log_event


# ============================================================================
# EXPANDER PROMPT TEMPLATE (v2 - Rubric-Guided)
# ============================================================================
EXPANDER_PROMPT_V2 = """You are an expert prompt engineer. Create exactly THREE prompt variations following the rubric below.

ANALYZED IDEA:
{discern_json}

{rubric_formatted}

Create THREE variations with these characteristics:
- Variation A: Direct role-based prompt (simple, clear persona)
- Variation B: Chain-of-thought prompt (explicit step-by-step reasoning)
- Variation C: Role-immersive with maximum anti-hallucination guardrails

MANDATORY for ALL variations:
1. Include: "If you cannot verify a fact, say 'I don't know'"
2. Require structured JSON output
3. Include explicit role/persona
4. Score yourself on the 12-item checklist

You MUST respond with ONLY valid JSON:
{{
  "A": {{
    "prompt": "<complete prompt text>",
    "notes": "<approach notes>",
    "token_est": <estimated tokens>,
    "checklist_score": <0-12 items satisfied>
  }},
  "B": {{
    "prompt": "<complete prompt text>",
    "notes": "<approach notes>",
    "token_est": <estimated tokens>,
    "checklist_score": <0-12 items satisfied>
  }},
  "C": {{
    "prompt": "<complete prompt text>",
    "notes": "<approach notes>",
    "token_est": <estimated tokens>,
    "checklist_score": <0-12 items satisfied>
  }}
}}

CRITICAL: Each prompt must be COMPLETE and PRODUCTION-READY.
Variation B MUST include "think step-by-step" instruction.
Variation C MUST include ALL guardrails from the rubric.
Keep responses concise (350 token limit).
Output ONLY JSON."""


def run_expander(
    discern_output: DiscernOutput,
    rubric_output: RubricOutput,
) -> ExpansionsOutput:
    """
    Generate 3 prompt variations guided by the rubric.
    
    This is THE ONLY DeepSeek call per run (cost enforcement).
    DeepSeek excels at rubric-following (89% accuracy per Siliconflow benchmarks).
    
    Args:
        discern_output: Validated output from Discerner
        rubric_output: Validated output from CriticFirst
    
    Returns:
        Validated ExpansionsOutput with A, B, C variations
    
    Raises:
        ValueError: If validation fails after retry
        DeepSeekCallLimitExceeded: If called more than once per run
    """
    log_event("stage.expander.start", {"intent": discern_output.intent})
    
    # Format inputs for prompt (minified for token efficiency)
    discern_dict = discern_output.model_dump()
    rubric_formatted = format_rubric_for_expander(rubric_output)
    
    prompt = EXPANDER_PROMPT_V2.format(
        discern_json=minify_json(discern_dict),
        rubric_formatted=rubric_formatted
    )
    
    # Call DeepSeek (ONLY call per run - enforced by llm_wrapper)
    response = call_llm(
        model=DEEPSEEK_EXPAND,
        prompt=prompt,
        max_tokens=EXPANDER_TOKEN_LIMIT,  # Strict 350 limit
        enforce_json=True,
        temperature=0.0  # Deterministic for rubric adherence
    )
    
    # Parse and validate
    raw_output = parse_json_response(response["content"])
    
    try:
        validated = validate_stage_output(raw_output, ExpansionsOutput)
        log_event("stage.expander.success", {
            "a_score": validated.A.checklist_score,
            "b_score": validated.B.checklist_score,
            "c_score": validated.C.checklist_score
        })
        return validated
    except ValueError as e:
        log_event("stage.expander.validation_error", {"error": str(e)})
        # Cannot retry DeepSeek (cost limit) - raise error
        raise ValueError(f"Expander validation failed (no retry for DeepSeek): {e}")


def get_best_variation(
    expansions: ExpansionsOutput,
    rankings: Dict[str, Any]
) -> str:
    """
    Get the prompt text from the best-ranked variation.
    
    Args:
        expansions: Validated expansions
        rankings: Rankings dict with rank values
    
    Returns:
        Prompt text from rank-1 variation
    """
    for var_key in ['A', 'B', 'C']:
        if rankings[var_key]['rank'] == 1:
            return getattr(expansions, var_key).prompt
    # Fallback to A if ranking is malformed
    return expansions.A.prompt
