"""
Pydantic schemas for Catalyze - Judge-then-Generate workflow.
Provides strict validation for all stage outputs.

Schemas are designed to work with the orchestrator's prompt templates.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional
import hashlib
import json


# ============================================================================
# STAGE 1: DISCERNER OUTPUT
# ============================================================================
class DiscernOutput(BaseModel):
    """Output schema for the Discerner stage - task analysis."""
    task_type: str = Field(description="Task classification: classification|generation|analysis|transformation|other")
    complexity: str = Field(description="Complexity level: simple|moderate|complex")
    domain: str = Field(description="Domain: general|technical|creative|analytical")
    key_requirements: List[str] = Field(default_factory=list, description="Key requirements for the task")
    potential_pitfalls: List[str] = Field(default_factory=list, description="Potential pitfalls to avoid")
    recommended_approach: str = Field(default="", description="Recommended approach strategy")

    @field_validator('task_type', 'complexity', 'domain')
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


# ============================================================================
# STAGE 2: CRITIC-FIRST (RUBRIC) OUTPUT
# ============================================================================
class RubricOutput(BaseModel):
    """Output schema for the CriticFirst rubric generation stage."""
    rubric: Dict[str, str] = Field(
        description="Key quality criteria with descriptions"
    )
    checklist: List[str] = Field(
        description="Checklist items (universal + idea-specific)"
    )
    red_flags: List[str] = Field(
        default_factory=list,
        description="Idea-specific pitfalls to avoid"
    )
    variation_guidance: Dict[str, str] = Field(
        default_factory=dict,
        description="A/B/C specific instructions for each variation"
    )


# ============================================================================
# STAGE 3: EXPANDER OUTPUT
# ============================================================================
class ExpansionVariant(BaseModel):
    """Detail for a single prompt variation."""
    prompt: str = Field(description="The actual prompt text")
    notes: str = Field(description="Brief notes on the approach")
    checklist_score: str = Field(description="Items satisfied, e.g. '4/6'")


class ExpansionsOutput(BaseModel):
    """Output schema for the Expander stage."""
    A: ExpansionVariant
    B: ExpansionVariant
    C: ExpansionVariant


# ============================================================================
# STAGE 4: RANKER OUTPUT
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
        # Access other fields via info.data
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
    rubric_compliance: Dict[str, str] = Field(
        default_factory=dict,
        description="How each rubric criterion was addressed"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")


# ============================================================================
# SUCCESS SPEC - INTENT PRESERVATION (The Tribunal Integration)
# ============================================================================
class SuccessSpec(BaseModel):
    """
    Success Specification for Intent Preservation.
    This artifact is passed to The Tribunal for verification.
    
    Generated alongside the optimized prompt to ensure the original
    intent is preserved and can be validated downstream.
    """
    intent_summary: str = Field(
        description="Concise summary of the user's original intent (1-2 sentences)"
    )
    key_constraints: List[str] = Field(
        default_factory=list,
        description="Critical constraints that must be satisfied by any output"
    )
    expected_behavior: str = Field(
        description="Description of what successful prompt execution looks like"
    )
    
    @field_validator('intent_summary', 'expected_behavior')
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


# ============================================================================
# COMPLETE RUN METADATA (Optional, for full run tracking)
# ============================================================================
class MetaInfo(BaseModel):
    """Metadata about the run (optional, for telemetry)."""
    duration_s: float = Field(default=0.0)
    models_used: List[str] = Field(default_factory=list)
    deepseek_calls: int = Field(default=1, le=1, description="Must be exactly 1")
    total_cost_usd: float = Field(default=0.0)
    cache_hit: bool = Field(default=False)
    version: str = Field(default="v2")


# ============================================================================
# CACHING UTILITIES
# ============================================================================
def compute_idea_hash(idea: str) -> str:
    """Compute SHA-256 hash of an idea for caching."""
    return hashlib.sha256(idea.strip().lower().encode()).hexdigest()[:16]


def minify_json(obj: Any) -> str:
    """Minify JSON for prompt compression (15% token savings)."""
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=False)


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


# ============================================================================
# VALIDATION HELPERS
# ============================================================================
def validate_stage_output(data: Dict[str, Any], schema_class: type) -> BaseModel:
    """
    Validate stage output against its Pydantic schema.
    
    Args:
        data: Raw dictionary from LLM
        schema_class: Pydantic model class
    
    Returns:
        Validated Pydantic model instance
    
    Raises:
        ValueError: If validation fails
    """
    try:
        return schema_class.model_validate(data)
    except Exception as e:
        raise ValueError(f"Schema validation failed for {schema_class.__name__}: {e}")
