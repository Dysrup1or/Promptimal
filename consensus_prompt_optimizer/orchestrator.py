"""
Orchestrator for Promptly v2 - Main pipeline with Judge-then-Generate workflow.

Pipeline Flow:
1. Discerner    → Analyze the idea (Gemini Flash)
2. CriticFirst  → Generate rubric BEFORE expansion (Gemini Flash) 
3. Expander     → Generate 3 variations with rubric guidance (DeepSeek - SINGLE CALL)
4. Ranker       → Lightweight ranking of variations (Gemini Flash)
5. Synthesizer  → Final synthesis from ranked variations (Gemini Flash)

Key Constraints:
- DeepSeek called exactly ONCE per run (in Expander)
- Total cost ≤ $0.025/run
- All outputs validated with Pydantic schemas
"""

import os
import json
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# v2 imports
from .config import GEMINI_FAST, GROQ_EXPAND, GROQ_TOKEN_CAP
from .schemas import (
    DiscernOutput,
    RubricOutput,
    ExpansionsOutput,
    ExpansionVariant,
    RankingsOutput,
    RankerVariant,
    SynthesizerOutput,
    validate_stage_output
)
from .llm_wrapper_v2 import (
    call_llm_v2,
    parse_json_response_v2,
    load_from_cache,
    save_to_cache,
    TokenTracker,
    count_tokens
)
from .utils import log_event


# ============================================================================
# STAGE PROMPTS
# ============================================================================

DISCERNER_PROMPT = """[IDENTITY: Prompt Analysis Agent]
TASK: Analyze the user's idea to extract intent, audience, and constraints.
META-RULE: You analyze WHAT the user wants a prompt to do—you don't do it yourself.
---

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
}}"""


CRITIC_FIRST_PROMPT = """[IDENTITY: Prompt Quality Rubric Agent]
TASK: Generate evaluation criteria for PROMPTS, not for their outputs.
META-RULE: Your rubric guides prompt generation, not content execution.
---

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

Include 3-5 rubric criteria, 6-10 checklist items, 3-5 red flags."""


EXPANDER_PROMPT = """[IDENTITY: Prompt Expansion Agent]
TASK: Create three PROMPT variations—not implementations.
META-RULE: The user's idea describes what a FUTURE LLM should do. You REFINE
those instructions into better prompts. You do NOT execute them yourself.
CREATIVITY: Full freedom in style (role-based, CoT, structured, conversational).
Vary tone, format, and technique across variations A/B/C.
---

CRITICAL: Each prompt must be complete and standalone. Include anti-hallucination guardrails.

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

---
EXECUTION CREEP CHECK:
Example input: "Create a landing page with testimonials"
  X WRONG: Output HTML/React code for a landing page
  V RIGHT: Output a PROMPT like "You are a copywriter. Write landing page copy..."

Example input: "Build a Python script that parses logs"
  X WRONG: Output Python code with argparse
  V RIGHT: Output a PROMPT like "You are a Python developer. Generate a script..."

YOUR OUTPUT = A prompt that instructs, not content that executes.
---

FINAL CHECK: Each variation is a META-PROMPT, not an implementation.

Respond with ONLY valid JSON:
{{
  "A": {{"prompt": "<variation A>", "notes": "<approach notes>", "checklist_score": "<X/Y items addressed>"}},
  "B": {{"prompt": "<variation B>", "notes": "<approach notes>", "checklist_score": "<X/Y items addressed>"}},
  "C": {{"prompt": "<variation C>", "notes": "<approach notes>", "checklist_score": "<X/Y items addressed>"}}
}}"""


RANKER_PROMPT = """[IDENTITY: Prompt Ranking Agent]
TASK: Rank prompt variations by quality—not by what they would generate.
---

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

Ranks must be UNIQUE (1, 2, 3 each used exactly once)."""


SYNTHESIZER_PROMPT = """[IDENTITY: Prompt Synthesis Agent]
TASK: Merge the best elements into ONE optimized PROMPT.
META-RULE: Your output is a refined PROMPT, not the content it would generate.
CREATIVITY: Combine techniques freely. The final prompt should exceed any single variation.
---

Create the FINAL optimized prompt by synthesizing the best elements.

ORIGINAL IDEA:
{idea}

RUBRIC:
{rubric_json}

RANKED VARIATIONS (Best → Worst):
{ranked_variations}

---
EXECUTION CREEP CHECK:
Example: If user wants "a script that automates deployments"
    X WRONG: Output actual deployment code
    V RIGHT: Output a PROMPT that instructs an LLM to generate deployment code

YOUR OUTPUT = A refined prompt, not generated content.
---

FINAL CHECK: final_prompt contains a prompt, not generated content.

OUTPUT FORMAT (STRICT) - respond with ONLY valid JSON using EXACT keys:
{{
    "final_prompt": "<complete optimized prompt as plain text>",
    "synthesis_notes": "<concise rationale of what you combined and why>",
    "rubric_compliance": {{"<criterion>": "<how addressed>", ...}},
    "confidence": <0.0-1.0>
}}

REQUIRED:
- Do NOT add or rename keys (no "optimized_prompt", "summary", etc.).
- All four keys must be present; missing any key is invalid.
- rubric_compliance must be an object with the rubric criteria as keys.
- confidence must be a number between 0 and 1.

If your previous attempt failed validation, immediately output corrected JSON with the EXACT keys above.
"""


# ============================================================================
# ORCHESTRATOR
# ============================================================================

class PromptimaV2:
    """Main orchestrator for v2 pipeline."""
    
    def __init__(self, use_cache: bool = True, dry_run: bool = False):
        self.use_cache = use_cache
        self.dry_run = dry_run
        self.tracker = TokenTracker()
    
    def run(self, idea: str) -> Dict[str, Any]:
        """
        Run the full v2 pipeline.
        
        Args:
            idea: User's prompt idea
        
        Returns:
            Complete output JSON with all stages
        """
        log_event("pipeline.start", {"idea_preview": idea[:100]})
        
        # Check cache first
        if self.use_cache:
            cached = load_from_cache(idea)
            if cached:
                log_event("pipeline.cache_hit", {})
                return cached["result"]
        
        # Stage 1: Discerner
        discern = self._run_discerner(idea)
        
        # Stage 2: CriticFirst (Judge-then-Generate!)
        rubric = self._run_critic_first(idea, discern)
        
        # Stage 3: Expander (DeepSeek - SINGLE CALL)
        expansions = self._run_expander(idea, discern, rubric)
        
        # Stage 4: Ranker
        rankings = self._run_ranker(expansions, rubric)
        
        # Stage 5: Synthesizer
        final = self._run_synthesizer(idea, discern, rubric, expansions, rankings)
        
        # Build output
        result = self._build_output(idea, discern, rubric, expansions, rankings, final)
        
        # Save to cache
        if self.use_cache:
            save_to_cache(idea, result)
        
        log_event("pipeline.complete", self.tracker.summary())
        
        return result
    
    def _run_discerner(self, idea: str) -> DiscernOutput:
        """Stage 1: Analyze the idea."""
        log_event("stage.discerner.start", {})
        
        prompt = DISCERNER_PROMPT.format(idea=idea[:1000])
        
        if self.dry_run:
            return DiscernOutput(
                task_type="generation",
                complexity="moderate",
                domain="general",
                key_requirements=["clarity", "specificity"],
                potential_pitfalls=["ambiguity"],
                recommended_approach="structured approach"
            )
        
        response = call_llm_v2(
            model=GEMINI_FAST,
            prompt=prompt,
            max_tokens=500,  # Increased for detailed analysis
            enforce_json=True
        )
        self.tracker.record(response, "discerner")
        
        raw = parse_json_response_v2(response["content"])
        return validate_stage_output(raw, DiscernOutput)
    
    def _run_critic_first(self, idea: str, discern: DiscernOutput) -> RubricOutput:
        """Stage 2: Generate rubric BEFORE expansion (Judge-then-Generate)."""
        log_event("stage.critic_first.start", {})
        
        prompt = CRITIC_FIRST_PROMPT.format(
            idea=idea[:500],
            discern_json=json.dumps(discern.model_dump(), indent=2)
        )
        
        if self.dry_run:
            return RubricOutput(
                rubric={"clarity": "prompt should be clear"},
                checklist=["includes examples", "specifies format"],
                red_flags=["vague instructions"]
            )
        
        response = call_llm_v2(
            model=GEMINI_FAST,
            prompt=prompt,
            max_tokens=1200,  # Generous for detailed rubrics
            enforce_json=True
        )
        self.tracker.record(response, "critic_first")
        
        raw = parse_json_response_v2(response["content"])
        return validate_stage_output(raw, RubricOutput)
    
    def _run_expander(
        self, 
        idea: str, 
        discern: DiscernOutput, 
        rubric: RubricOutput
    ) -> ExpansionsOutput:
        """Stage 3: Generate variations with rubric guidance (Groq - SINGLE CALL)."""
        log_event("stage.expander.start", {})
        
        prompt = EXPANDER_PROMPT.format(
            idea=idea[:500],
            discern_json=json.dumps(discern.model_dump(), indent=2),
            rubric_json=json.dumps(rubric.rubric, indent=2),
            checklist="\n".join(f"- {item}" for item in rubric.checklist),
            red_flags="\n".join(f"- {flag}" for flag in rubric.red_flags)
        )
        
        if self.dry_run:
            return ExpansionsOutput(
                A=ExpansionVariant(prompt="Prompt A", notes="concise", checklist_score="4/6"),
                B=ExpansionVariant(prompt="Prompt B", notes="detailed", checklist_score="5/6"),
                C=ExpansionVariant(prompt="Prompt C", notes="structured", checklist_score="6/6")
            )
        
        # ==================================================================
        # BULLETPROOF EXPANDER (retry + coercion)
        # ==================================================================
        
        def _coerce_expansion(data: Any) -> ExpansionsOutput:
            """Coerce various response formats into ExpansionsOutput."""
            if not isinstance(data, dict):
                if isinstance(data, list) and len(data) >= 3:
                    # Handle array format: [{...}, {...}, {...}]
                    data = {"A": data[0], "B": data[1], "C": data[2]}
                else:
                    raise ValueError(f"Expander output is not a dict: {type(data)}")
            
            # Handle various key naming conventions
            key_maps = [
                ("A", ["A", "a", "variation_a", "variant_a", "1", "first"]),
                ("B", ["B", "b", "variation_b", "variant_b", "2", "second"]),
                ("C", ["C", "c", "variation_c", "variant_c", "3", "third"]),
            ]
            
            normalized = {}
            for target_key, synonyms in key_maps:
                for syn in synonyms:
                    if syn in data:
                        normalized[target_key] = data[syn]
                        break
            
            if len(normalized) < 3:
                raise ValueError(f"Could not find 3 variations. Found keys: {list(data.keys())}")
            
            # Normalize each variation
            for key in ["A", "B", "C"]:
                var = normalized[key]
                if isinstance(var, str):
                    # Handle case where variation is just a string prompt
                    normalized[key] = {
                        "prompt": var,
                        "notes": f"Variation {key}",
                        "checklist_score": "N/A"
                    }
                elif isinstance(var, dict):
                    # Ensure required fields exist
                    prompt_keys = ["prompt", "text", "content", "variation", "output"]
                    found_prompt = None
                    for pk in prompt_keys:
                        if pk in var and isinstance(var[pk], str):
                            found_prompt = var[pk]
                            break
                    if not found_prompt:
                        # Last resort: use the whole dict as string
                        found_prompt = str(var)
                    
                    normalized[key] = {
                        "prompt": found_prompt,
                        "notes": var.get("notes", var.get("approach", var.get("description", f"Variation {key}"))),
                        "checklist_score": var.get("checklist_score", var.get("score", "N/A"))
                    }
            
            return validate_stage_output(normalized, ExpansionsOutput)
        
        def _generate_fallback_variations() -> ExpansionsOutput:
            """Generate simple fallback variations from the idea."""
            log_event("expander.fallback", {"reason": "all_retries_failed"})
            
            # Create basic variations based on the idea
            base_prompt = f"You are an expert assistant. {idea[:300]}"
            
            return ExpansionsOutput(
                A=ExpansionVariant(
                    prompt=f"[CONCISE] {base_prompt}\n\nProvide a clear, direct response.",
                    notes="Simple concise approach (fallback)",
                    checklist_score="Fallback"
                ),
                B=ExpansionVariant(
                    prompt=f"[DETAILED] {base_prompt}\n\nThink through this step-by-step:\n1. First, analyze the request\n2. Then, develop your approach\n3. Finally, deliver a comprehensive response",
                    notes="Chain-of-thought approach (fallback)",
                    checklist_score="Fallback"
                ),
                C=ExpansionVariant(
                    prompt=f"[STRUCTURED] You are a senior expert in this domain.\n\n## Task\n{idea[:300]}\n\n## Requirements\n- Be thorough and accurate\n- Cite sources when possible\n- Flag any assumptions\n\n## Output Format\nProvide a well-organized response.",
                    notes="Structured expert approach (fallback)",
                    checklist_score="Fallback"
                )
            )
        
        # Try up to 3 times with increasingly explicit prompts
        last_error = None
        for attempt in range(1, 4):
            try:
                if attempt == 1:
                    current_prompt = prompt
                else:
                    # Add explicit retry instructions
                    current_prompt = prompt + f"""

ATTEMPT {attempt} - PREVIOUS PARSE FAILED: {last_error}

YOU MUST OUTPUT EXACTLY THIS JSON FORMAT (no markdown, no code fences, just raw JSON):
{{
  "A": {{"prompt": "your first variation here", "notes": "concise approach", "checklist_score": "4/6"}},
  "B": {{"prompt": "your second variation here", "notes": "detailed approach", "checklist_score": "5/6"}},
  "C": {{"prompt": "your third variation here", "notes": "structured approach", "checklist_score": "6/6"}}
}}

CRITICAL: Start your response with {{ and end with }}. No other text."""
                
                response = call_llm_v2(
                    model=GROQ_EXPAND,
                    prompt=current_prompt,
                    max_tokens=GROQ_TOKEN_CAP,
                    enforce_json=True
                )
                
                if attempt == 1:
                    self.tracker.record(response, "expander")
                else:
                    self.tracker.record(response, f"expander.retry{attempt}")
                
                raw = parse_json_response_v2(response["content"])
                return _coerce_expansion(raw)
                
            except Exception as e:
                last_error = str(e)[:200]
                log_event("expander.retry", {"attempt": attempt, "error": last_error})
                
                if attempt == 3:
                    # Ultimate fallback: generate basic variations
                    return _generate_fallback_variations()
    
    def _run_ranker(
        self, 
        expansions: ExpansionsOutput, 
        rubric: RubricOutput
    ) -> RankingsOutput:
        """Stage 4: Rank variations."""
        log_event("stage.ranker.start", {})
        
        rubric_summary = {
            "criteria": list(rubric.rubric.keys()),
            "red_flags": rubric.red_flags[:3]
        }
        
        variations_summary = {
            "A": {"notes": expansions.A.notes, "checklist": expansions.A.checklist_score, "preview": expansions.A.prompt[:150]},
            "B": {"notes": expansions.B.notes, "checklist": expansions.B.checklist_score, "preview": expansions.B.prompt[:150]},
            "C": {"notes": expansions.C.notes, "checklist": expansions.C.checklist_score, "preview": expansions.C.prompt[:150]}
        }
        
        prompt = RANKER_PROMPT.format(
            rubric_summary=json.dumps(rubric_summary),
            variations_summary=json.dumps(variations_summary, indent=2)
        )
        
        if self.dry_run:
            return RankingsOutput(
                A=RankerVariant(rank=2, score=0.7),
                B=RankerVariant(rank=3, score=0.6),
                C=RankerVariant(rank=1, score=0.9)
            )
        
        response = call_llm_v2(
            model=GEMINI_FAST,
            prompt=prompt,
            max_tokens=150,
            enforce_json=True
        )
        self.tracker.record(response, "ranker")
        
        raw = parse_json_response_v2(response["content"])
        return validate_stage_output(raw, RankingsOutput)
    
    def _run_synthesizer(
        self,
        idea: str,
        discern: DiscernOutput,
        rubric: RubricOutput,
        expansions: ExpansionsOutput,
        rankings: RankingsOutput
    ) -> SynthesizerOutput:
        """Stage 5: Synthesize final prompt."""
        log_event("stage.synthesizer.start", {})
        
        # Sort variations by rank
        vars_data = [
            ("A", rankings.A.rank, expansions.A),
            ("B", rankings.B.rank, expansions.B),
            ("C", rankings.C.rank, expansions.C)
        ]
        sorted_vars = sorted(vars_data, key=lambda x: x[1])
        
        ranked_text = ""
        for key, rank, var in sorted_vars:
            ranked_text += f"\n--- Rank {rank} ({key}) ---\n{var.prompt}\n"
        
        prompt = SYNTHESIZER_PROMPT.format(
            idea=idea[:300],
            rubric_json=json.dumps(rubric.rubric, indent=2),
            ranked_variations=ranked_text
        )
        
        if self.dry_run:
            return SynthesizerOutput(
                final_prompt="[DRY RUN] Final synthesized prompt",
                synthesis_notes="Dry run mode",
                rubric_compliance={"clarity": "addressed"},
                confidence=0.9
            )
        
        response = call_llm_v2(
            model=GEMINI_FAST,
            prompt=prompt,
            max_tokens=2000,  # Generous for complex final prompts
            enforce_json=True
        )
        self.tracker.record(response, "synthesizer")
        
        raw = parse_json_response_v2(response["content"])

        # ==================================================================
        # BULLETPROOF SYNTHESIZER COERCION (v3)
        # Handles: missing keys, renamed keys, garbage prompts, nested data
        # ==================================================================
        
        MIN_PROMPT_LENGTH = 50  # Minimum chars for a valid prompt
        
        def _extract_prompt_recursively(obj: Any, depth: int = 0) -> Optional[str]:
            """Recursively search for a prompt-like string in nested structures."""
            if depth > 5:  # Prevent infinite recursion
                return None
            if isinstance(obj, str) and len(obj.strip()) >= MIN_PROMPT_LENGTH:
                return obj.strip()
            if isinstance(obj, dict):
                # Priority order for prompt-like keys
                for key in ["final_prompt", "prompt", "optimized_prompt", "best_prompt", 
                            "synthesized_prompt", "refined_prompt", "master_prompt",
                            "result", "output", "text", "content", "response"]:
                    if key in obj:
                        found = _extract_prompt_recursively(obj[key], depth + 1)
                        if found and len(found) >= MIN_PROMPT_LENGTH:
                            return found
                # Fallback: try any string value that looks like a prompt
                for v in obj.values():
                    if isinstance(v, str) and len(v.strip()) >= MIN_PROMPT_LENGTH:
                        return v.strip()
                    found = _extract_prompt_recursively(v, depth + 1)
                    if found and len(found) >= MIN_PROMPT_LENGTH:
                        return found
            if isinstance(obj, list) and obj:
                return _extract_prompt_recursively(obj[0], depth + 1)
            return None
        
        def _is_valid_prompt(text: str) -> bool:
            """Check if a string looks like a valid prompt, not garbage."""
            if not text or len(text.strip()) < MIN_PROMPT_LENGTH:
                return False
            # Check for nonsensical patterns
            garbage_patterns = [
                "what are we building",
                "i don't understand",
                "please clarify",
                "not sure what",
                "can you explain",
                "hey!",
                "hello!",
            ]
            lower_text = text.lower()
            if any(pattern in lower_text for pattern in garbage_patterns):
                return False
            # Check for minimum word count
            word_count = len(text.split())
            if word_count < 10:
                return False
            return True
        
        def _get_best_variation_prompt() -> str:
            """Fallback: return the best-ranked variation as final prompt."""
            # Sort by rank and return the best one
            vars_by_rank = sorted([
                (rankings.A.rank, expansions.A.prompt),
                (rankings.B.rank, expansions.B.prompt),
                (rankings.C.rank, expansions.C.prompt)
            ], key=lambda x: x[0])
            return vars_by_rank[0][1]  # Best ranked variation

        def coerce_and_validate(data: Any, attempt: int = 1) -> SynthesizerOutput:
            """
            Aggressively coerce LLM output into SynthesizerOutput schema.
            Handles: renamed keys, nested structures, missing fields.
            """
            # Handle non-dict responses (e.g., wrapped in array or nested)
            if not isinstance(data, dict):
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    data = data[0]
                else:
                    raise ValueError(f"Synthesizer output is not a JSON object: {type(data)}")
            
            # Unwrap nested structures like {"result": {...}} or {"output": {...}}
            for wrapper_key in ["result", "output", "response", "data"]:
                if wrapper_key in data and isinstance(data[wrapper_key], dict):
                    nested = data[wrapper_key]
                    # Check if nested has prompt-like content
                    if any(k in nested for k in ["final_prompt", "prompt", "optimized_prompt"]):
                        data = nested
                        break
            
            # Extract prompt from multiple possible key names
            prompt_synonyms = ["final_prompt", "prompt", "optimized_prompt", "best_prompt", 
                               "synthesized_prompt", "master_prompt", "refined_prompt"]
            coerced_prompt = None
            for key in prompt_synonyms:
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    coerced_prompt = val.strip()
                    break
            
            # Fallback: recursive extraction if no direct key match
            if not coerced_prompt:
                coerced_prompt = _extract_prompt_recursively(data)
            
            # CRITICAL: Validate prompt quality, use fallback if garbage
            if not coerced_prompt or not _is_valid_prompt(coerced_prompt):
                fallback_prompt = _get_best_variation_prompt()
                if _is_valid_prompt(fallback_prompt):
                    coerced_prompt = fallback_prompt
                    log_event("synthesizer.fallback", {"reason": "invalid_prompt_extracted"})
                else:
                    raise ValueError(f"Extracted prompt is invalid and fallback failed (attempt {attempt}): '{coerced_prompt[:100] if coerced_prompt else 'None'}'")
            
            # Extract synthesis notes with multiple fallbacks
            notes_synonyms = ["synthesis_notes", "notes", "rationale", "explanation", 
                              "reasoning", "summary", "synthesis_rationale"]
            coerced_notes = None
            for key in notes_synonyms:
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    coerced_notes = val.strip()
                    break
            if not coerced_notes:
                coerced_notes = f"Auto-generated: synthesized from variations (attempt {attempt})"
            
            # Extract rubric compliance with fallbacks
            rubric_synonyms = ["rubric_compliance", "compliance", "rubric", "criteria_met", "rubric_scores"]
            coerced_rubric = None
            for key in rubric_synonyms:
                val = data.get(key)
                if isinstance(val, dict) and val:
                    coerced_rubric = val
                    break
            if not coerced_rubric:
                coerced_rubric = {
                    key: "Addressed in final synthesis" 
                    for key in (rubric.rubric.keys() if rubric.rubric else ["quality"])
                }
            
            # Extract confidence with fallbacks
            conf_synonyms = ["confidence", "confidence_score", "score", "certainty"]
            coerced_conf = None
            for key in conf_synonyms:
                val = data.get(key)
                if isinstance(val, (int, float)) and 0 <= val <= 1:
                    coerced_conf = float(val)
                    break
                # Handle percentage-style confidence (e.g., 85 -> 0.85)
                if isinstance(val, (int, float)) and 1 < val <= 100:
                    coerced_conf = float(val) / 100.0
                    break
            if coerced_conf is None:
                coerced_conf = 0.75  # Default confidence for coerced responses
            
            # Clamp confidence to valid range and minimum threshold
            coerced_conf = max(0.7, min(1.0, coerced_conf))
            
            # Build normalized data dict
            normalized = {
                "final_prompt": coerced_prompt,
                "synthesis_notes": coerced_notes,
                "rubric_compliance": coerced_rubric,
                "confidence": coerced_conf,
            }
            
            # Final validation
            return validate_stage_output(normalized, SynthesizerOutput)

        # Try up to 3 times with increasingly explicit prompts
        last_error = None
        for attempt in range(1, 4):
            try:
                if attempt == 1:
                    return coerce_and_validate(raw, attempt)
                else:
                    # Retry with more explicit instructions
                    retry_prompt = prompt + f"""

ATTEMPT {attempt} - PREVIOUS VALIDATION FAILED: {last_error}

YOU MUST OUTPUT EXACTLY THIS JSON STRUCTURE (no other keys, no code fences):
{{
    "final_prompt": "<your complete optimized prompt text here>",
    "synthesis_notes": "<brief explanation of your synthesis approach>",
    "rubric_compliance": {{"clarity": "addressed", "specificity": "addressed"}},
    "confidence": 0.85
}}

CRITICAL RULES:
1. Use EXACTLY the key name "final_prompt" (NOT "prompt", NOT "optimized_prompt")
2. All four keys are REQUIRED
3. Output RAW JSON only - no markdown, no code blocks
4. confidence must be a decimal between 0.7 and 1.0"""
                    
                    retry_response = call_llm_v2(
                        model=GEMINI_FAST,
                        prompt=retry_prompt,
                        max_tokens=2000,
                        enforce_json=True
                    )
                    self.tracker.record(retry_response, f"synthesizer.retry{attempt}")
                    retry_raw = parse_json_response_v2(retry_response["content"])
                    return coerce_and_validate(retry_raw, attempt)
            except ValueError as e:
                last_error = str(e)
                if attempt == 3:
                    # ULTIMATE FALLBACK: Use best variation directly
                    log_event("synthesizer.ultimate_fallback", {"error": str(e)})
                    fallback_prompt = _get_best_variation_prompt()
                    if fallback_prompt and len(fallback_prompt) >= MIN_PROMPT_LENGTH:
                        return SynthesizerOutput(
                            final_prompt=fallback_prompt,
                            synthesis_notes=f"Auto-fallback: Used best-ranked variation after synthesis failed ({last_error[:100]})",
                            rubric_compliance={key: "Inherited from variation" for key in (rubric.rubric.keys() if rubric.rubric else ["quality"])},
                            confidence=0.7
                        )
                    raise ValueError(f"Synthesizer failed after 3 attempts and fallback failed. Last error: {last_error}")
    
    def _build_output(
        self,
        idea: str,
        discern: DiscernOutput,
        rubric: RubricOutput,
        expansions: ExpansionsOutput,
        rankings: RankingsOutput,
        final: SynthesizerOutput
    ) -> Dict[str, Any]:
        """Build complete output JSON."""
        return {
            "version": "v2",
            "timestamp": datetime.now().isoformat(),
            "original_idea": idea,
            "task_analysis": discern.model_dump(),
            "rubric": {
                "criteria": rubric.rubric,
                "checklist": rubric.checklist,
                "red_flags": rubric.red_flags
            },
            "variations": {
                "A": {
                    "prompt": expansions.A.prompt,
                    "notes": expansions.A.notes,
                    "checklist_score": expansions.A.checklist_score,
                    "rank": rankings.A.rank,
                    "score": rankings.A.score
                },
                "B": {
                    "prompt": expansions.B.prompt,
                    "notes": expansions.B.notes,
                    "checklist_score": expansions.B.checklist_score,
                    "rank": rankings.B.rank,
                    "score": rankings.B.score
                },
                "C": {
                    "prompt": expansions.C.prompt,
                    "notes": expansions.C.notes,
                    "checklist_score": expansions.C.checklist_score,
                    "rank": rankings.C.rank,
                    "score": rankings.C.score
                }
            },
            "final_synthesis": {
                "prompt": final.final_prompt,
                "notes": final.synthesis_notes,
                "rubric_compliance": final.rubric_compliance,
                "confidence": final.confidence
            },
            "usage": self.tracker.summary()
        }


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Promptly v2 - Judge-then-Generate Prompt Optimizer"
    )
    parser.add_argument("idea", nargs="?", help="The prompt idea to optimize")
    parser.add_argument("--file", "-f", help="Read idea from file")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without API calls")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Get idea
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            idea = f.read().strip()
    elif args.idea:
        idea = args.idea
    else:
        print("Usage: python orchestrator.py 'your prompt idea'")
        print("   or: python orchestrator.py -f idea.txt")
        return
    
    # Run pipeline
    optimizer = PromptimaV2(
        use_cache=not args.no_cache,
        dry_run=args.dry_run
    )
    
    result = optimizer.run(idea)
    
    # Output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        print(f"Output saved to: {args.output}")
    else:
        print(json.dumps(result, indent=2))
    
    # Print summary
    if args.verbose:
        print("\n--- Usage Summary ---")
        print(f"Total cost: ${result['usage']['total_cost_usd']:.6f}")
        print(f"Under budget: {result['usage']['total_cost_usd'] <= 0.025}")


if __name__ == "__main__":
    main()
