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
from .config import GEMINI_FAST, DEEPSEEK_CHEAP, DEEPSEEK_TOKEN_CAP
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
        """Stage 3: Generate variations with rubric guidance (DeepSeek - SINGLE CALL)."""
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
        
        response = call_llm_v2(
            model=DEEPSEEK_CHEAP,  # THE SINGLE DEEPSEEK CALL
            prompt=prompt,
            max_tokens=DEEPSEEK_TOKEN_CAP,  # 350 token cap
            enforce_json=True
        )
        self.tracker.record(response, "expander")
        
        raw = parse_json_response_v2(response["content"])
        return validate_stage_output(raw, ExpansionsOutput)
    
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

        def coerce_and_validate(data: Dict[str, Any]) -> SynthesizerOutput:
            # Coerce stray "prompt" into final_prompt only if we can satisfy schema after checks
            if isinstance(data, dict) and "prompt" in data and (
                "final_prompt" not in data or "synthesis_notes" not in data or "confidence" not in data
            ):
                data = {
                    "final_prompt": data.get("final_prompt") or data.get("prompt"),
                    "synthesis_notes": data.get("synthesis_notes") or "Auto-coerced from 'prompt' field due to model drift.",
                    "rubric_compliance": data.get("rubric_compliance") or {},
                    "confidence": data.get("confidence") or 0.5,
                }

            # Hard validation before Pydantic: non-empty strings, non-empty rubric, confidence in [0,1] and >= 0.7
            if not isinstance(data, dict):
                raise ValueError("Synthesizer output is not a JSON object")

            def _is_non_empty_str(x: Any) -> bool:
                return isinstance(x, str) and len(x.strip()) > 0

            if not _is_non_empty_str(data.get("final_prompt")):
                raise ValueError("final_prompt missing or empty")
            if not _is_non_empty_str(data.get("synthesis_notes")):
                raise ValueError("synthesis_notes missing or empty")

            rc = data.get("rubric_compliance")
            if not isinstance(rc, dict) or len(rc) == 0:
                raise ValueError("rubric_compliance missing or empty")

            conf = data.get("confidence")
            if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
                raise ValueError("confidence missing or out of range")
            if conf < 0.7:
                raise ValueError("confidence below threshold")

            return validate_stage_output(data, SynthesizerOutput)

        try:
            return coerce_and_validate(raw)
        except ValueError:
            # Retry once with explicit schema correction to avoid optimized_prompt / missing keys
            retry_prompt = prompt + "\n\nPREVIOUS ATTEMPT FAILED VALIDATION. Output STRICT JSON with EXACT keys: final_prompt, synthesis_notes, rubric_compliance (non-empty object), confidence (0-1, at least 0.7). Do NOT add or rename keys. Do NOT include code fences."
            retry_response = call_llm_v2(
                model=GEMINI_FAST,
                prompt=retry_prompt,
                max_tokens=2000,
                enforce_json=True
            )
            self.tracker.record(retry_response, "synthesizer.retry")
            retry_raw = parse_json_response_v2(retry_response["content"])
            return coerce_and_validate(retry_raw)
    
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
