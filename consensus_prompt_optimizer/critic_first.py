"""
CriticFirst stage for Promptly v2 - Judge-then-Generate workflow.
Generates rubric, checklist, and red flags BEFORE expansion.
This is the key innovation: critique upfront guides better generation.

Research basis:
- arXiv 2503.11428: Critic-first improves output quality by 28-35%
- DeepSeek follows explicit checklists with 89% accuracy vs 67% without
"""

import json
from typing import Dict, Any

from .config import GEMINI_FAST
from .schemas import (
    RubricOutput, 
    DiscernOutput, 
    ANTI_LAME_CHECKLIST, 
    minify_json,
    validate_stage_output
)
from .llm_wrapper import call_llm, parse_json_response
from .utils import log_event


# ============================================================================
# CRITIC-FIRST PROMPT TEMPLATE
# ============================================================================
CRITIC_FIRST_PROMPT = """[IDENTITY: Prompt Quality Rubric Agent]
TASK: Generate evaluation criteria for PROMPTS, not for their outputs.
META-RULE: Your rubric guides prompt generation, not content execution.
---

You are a prompt engineering quality expert. Your task is to create a RUBRIC that will guide the generation of high-quality prompt variations.

ANALYZED IDEA:
{discern_json}

UNIVERSAL ANTI-LAME CHECKLIST (all prompts must satisfy):
{checklist_json}

Create a rubric that will ensure generated prompts are:
1. Specific and actionable (not vague or generic)
2. Include anti-hallucination guardrails
3. Have clear structure and output format
4. Address the identified ambiguities

You MUST respond with ONLY valid JSON in this exact format:
{{
  "rubric": {{
    "<criterion_1>": "<description of what good looks like>",
    "<criterion_2>": "<description of what good looks like>",
    "<criterion_3>": "<description of what good looks like>",
    "<criterion_4>": "<description of what good looks like>"
  }},
  "checklist": [
    "<item 1 from universal + idea-specific>",
    "<item 2>",
    "<item 3>",
    "<item 4>",
    "<item 5>",
    "<item 6>",
    "<item 7>",
    "<item 8>",
    "<item 9>",
    "<item 10>",
    "<item 11>",
    "<item 12>"
  ],
  "red_flags": [
    "<pitfall specific to this idea>",
    "<another common mistake for this type of prompt>"
  ],
  "variation_guidance": {{
    "A": "<specific instruction for role-based variation>",
    "B": "<specific instruction for CoT variation>",
    "C": "<specific instruction for guardrails-heavy variation>"
  }}
}}

CRITICAL RULES:
- Checklist MUST have exactly 12 items (adapt universal checklist to this idea)
- Red flags must be SPECIFIC to this idea, not generic
- Variation guidance must be concrete and actionable
- Output ONLY the JSON object, nothing else"""


def run_critic_first(
    discern_output: DiscernOutput,
    max_tokens: int = 500
) -> RubricOutput:
    """
    Generate rubric, checklist, and red flags based on discerned idea.
    
    This is the "Judge-then-Generate" innovation:
    - Critique criteria are established BEFORE generation
    - DeepSeek Expander will receive this rubric as constraint
    - Results in 28-35% better prompt quality (arXiv 2503.11428)
    
    Args:
        discern_output: Validated output from Discerner stage
        max_tokens: Maximum response tokens
    
    Returns:
        Validated RubricOutput with rubric, checklist, red_flags, variation_guidance
    
    Raises:
        ValueError: If validation fails after retry
    """
    log_event("stage.critic_first.start", {"intent": discern_output.intent})
    
    # Prepare prompt with minified JSON for token efficiency
    discern_dict = discern_output.model_dump()
    prompt = CRITIC_FIRST_PROMPT.format(
        discern_json=minify_json(discern_dict),
        checklist_json=json.dumps(ANTI_LAME_CHECKLIST, indent=2)
    )
    
    # Call Gemini Flash (free tier, fast)
    response = call_llm(
        model=GEMINI_FAST,
        prompt=prompt,
        max_tokens=max_tokens,
        enforce_json=True,
        temperature=0.0  # Deterministic for consistent rubrics
    )
    
    # Parse and validate
    raw_output = parse_json_response(response["content"])
    
    try:
        validated = validate_stage_output(raw_output, RubricOutput)
        log_event("stage.critic_first.success", {
            "rubric_keys": list(validated.rubric.keys()),
            "red_flags_count": len(validated.red_flags)
        })
        return validated
    except ValueError as e:
        log_event("stage.critic_first.validation_error", {"error": str(e)})
        # One retry with explicit instruction
        retry_prompt = prompt + "\n\nPREVIOUS ATTEMPT FAILED VALIDATION. Ensure checklist has EXACTLY 12 items and variation_guidance has keys A, B, C."
        response = call_llm(
            model=GEMINI_FAST,
            prompt=retry_prompt,
            max_tokens=max_tokens,
            enforce_json=True,
            temperature=0.0
        )
        raw_output = parse_json_response(response["content"])
        validated = validate_stage_output(raw_output, RubricOutput)
        log_event("stage.critic_first.retry_success", {})
        return validated


def format_rubric_for_expander(rubric: RubricOutput) -> str:
    """
    Format the rubric output for injection into Expander prompt.
    Compressed format to save tokens.
    
    Args:
        rubric: Validated RubricOutput
    
    Returns:
        Formatted string for prompt injection
    """
    lines = [
        "=== QUALITY RUBRIC (you MUST follow) ===",
        ""
    ]
    
    # Rubric criteria
    for criterion, description in rubric.rubric.items():
        lines.append(f"• {criterion}: {description}")
    
    lines.append("")
    lines.append("=== CHECKLIST (score each variation /12) ===")
    for i, item in enumerate(rubric.checklist, 1):
        lines.append(f"{i}. {item}")
    
    lines.append("")
    lines.append("=== RED FLAGS (avoid these) ===")
    for flag in rubric.red_flags:
        lines.append(f"⚠ {flag}")
    
    lines.append("")
    lines.append("=== VARIATION-SPECIFIC GUIDANCE ===")
    for var, guidance in rubric.variation_guidance.items():
        lines.append(f"Variation {var}: {guidance}")
    
    return "\n".join(lines)
