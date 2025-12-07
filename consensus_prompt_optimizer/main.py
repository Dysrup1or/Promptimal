"""
Main CLI entry point for the Consensus Prompt Optimizer.
Orchestrates the 4-agent workflow with cost enforcement.
"""

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


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Consensus Prompt Optimizer - Multi-agent prompt optimization with cost < $0.05"
    )
    
    parser.add_argument(
        "--idea",
        type=str,
        help="Single prompt idea to optimize"
    )
    
    parser.add_argument(
        "--batch",
        type=str,
        help="Path to JSONL file with multiple ideas (one per line)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only estimate cost, do not make LLM calls"
    )
    
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=MAX_TOKENS_PER_CALL,
        help=f"Maximum tokens per LLM call (default: {MAX_TOKENS_PER_CALL})"
    )
    
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Enable parallel batch processing (if --batch is used)"
    )
    
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for reproducibility (default: {DEFAULT_SEED})"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: stdout)"
    )
    
    args = parser.parse_args()
    
    # Validation
    if not args.idea and not args.batch:
        parser.error("Either --idea or --batch must be provided")
    
    if args.idea and args.batch:
        parser.error("Cannot specify both --idea and --batch")
    
    return args


def estimate_dry_run_cost(idea: str) -> Dict[str, Any]:
    """
    Estimate the cost without making actual LLM calls.
    
    Args:
        idea: Raw prompt idea
    
    Returns:
        JSON skeleton with cost estimates
    """
    # Estimate token counts for each stage
    idea_tokens = estimate_tokens(idea)
    
    # Discerner (Gemini Flash): input = idea
    discerner_input = idea_tokens
    discerner_output = 100  # Estimated
    discerner_cost = estimate_cost_usd(GEMINI_FAST, discerner_input, discerner_output)
    
    # Expander (DeepSeek): input = discerner output
    expander_input = discerner_output
    expander_output = 350  # Capped
    expander_cost = estimate_cost_usd(DEEPSEEK_EXPAND, expander_input, expander_output)
    
    # Critic (Gemini Flash): input = expansions
    critic_input = expander_output
    critic_output = 150  # Estimated
    critic_cost = estimate_cost_usd(GEMINI_FAST, critic_input, critic_output)
    
    # Synthesizer (Gemini Flash): input = all previous
    synthesizer_input = discerner_output + expander_output + critic_output
    synthesizer_output = 200  # Estimated
    synthesizer_cost = estimate_cost_usd(GEMINI_FAST, synthesizer_input, synthesizer_output)
    
    total_cost = discerner_cost + expander_cost + critic_cost + synthesizer_cost
    
    return {
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


def run_optimization(idea: str, seed: int, max_tokens: int, dry_run: bool = False) -> Dict[str, Any]:
    """
    Run the full optimization workflow for a single idea.
    
    Args:
        idea: Raw prompt idea
        seed: Random seed
        max_tokens: Maximum tokens per LLM call
        dry_run: If True, only estimate cost
    
    Returns:
        Complete JSON result
    """
    start_time = time.time()
    set_seed(seed)
    reset_deepseek_counter()
    
    log_event("run.start", {"idea": idea, "seed": seed})
    
    if dry_run:
        return estimate_dry_run_cost(idea)
    
    models_used = []
    
    try:
        # STAGE 1: Discerner
        discern_response = call_llm(
            model=GEMINI_FAST,
            prompt=f"You are an expert prompt analyst. Your task is to parse a raw prompt idea into its atomic components.\n\nINPUT IDEA:\n{idea}\n\nYou MUST respond with ONLY valid JSON in this exact format (no additional text):\n{{\n  \"intent\": \"<what the user wants to achieve>\",\n  \"audience\": \"<who will use this prompt>\",\n  \"constraints\": [\"<constraint 1>\", \"<constraint 2>\", ...],\n  \"success_criteria\": \"<how to measure success>\",\n  \"ambiguous\": [\"<ambiguity 1>\", \"<ambiguity 2>\", ...]\n}}\n\nRules:\n- Be precise and concise\n- Extract ALL implicit and explicit constraints\n- Identify any ambiguous or unclear aspects in the \"ambiguous\" field\n- If no ambiguities, use empty array []\n- Output ONLY the JSON object, nothing else",
            max_tokens=max_tokens,
            enforce_json=True,
        )
        discern_json = parse_json_response(discern_response["content"])
        models_used.append(GEMINI_FAST)
        
        # STAGE 2: Expander (THE ONLY DEEPSEEK CALL)
        expander_response = call_llm(
            model=DEEPSEEK_EXPAND,
            prompt=f"You are a prompt engineering expert. Given the parsed idea below, create exactly THREE prompt variations.\n\nPARSED IDEA:\n{json.dumps(discern_json, indent=2)}\n\nCreate THREE variations with these exact characteristics:\n- Variation A: Direct role-based prompt (simple and clear)\n- Variation B: Chain-of-thought prompt (explicit step-by-step reasoning instructions)\n- Variation C: Role-immersive prompt with anti-hallucination guardrails\n\nYou MUST respond with ONLY valid JSON in this exact format (no additional text):\n{{\n  \"A\": {{\n    \"prompt\": \"<the actual prompt text for variation A>\",\n    \"notes\": \"<brief notes on the approach>\",\n    \"token_est\": <estimated tokens>\n  }},\n  \"B\": {{\n    \"prompt\": \"<the actual prompt text for variation B>\",\n    \"notes\": \"<brief notes on the approach>\",\n    \"token_est\": <estimated tokens>\n  }},\n  \"C\": {{\n    \"prompt\": \"<the actual prompt text for variation C>\",\n    \"notes\": \"<brief notes on the approach>\",\n    \"token_est\": <estimated tokens>\n  }}\n}}\n\nRequirements:\n- Each prompt must be complete and ready to use\n- Variation B MUST include explicit \"think step-by-step\" instructions\n- Variation C MUST include guardrails: require sources, explicit \"If you cannot verify a fact, say 'I don't know'.\"\n- Keep responses concise (you have a 350 token limit)\n- Output ONLY the JSON object, nothing else",
            max_tokens=350,  # STRICT LIMIT
            enforce_json=True,
        )
        expansions_json = parse_json_response(expander_response["content"])
        models_used.append(DEEPSEEK_EXPAND)
        
        # STAGE 3: Critic
        critic_response = call_llm(
            model=GEMINI_FAST,
            prompt=f"You are a prompt quality critic. Evaluate the three prompt variations below.\n\nEXPANSIONS:\n{json.dumps(expansions_json, indent=2)}\n\nFor each variation (A, B, C), identify potential issues and assign a rank (1=best, 2=middle, 3=worst).\n\nYou MUST respond with ONLY valid JSON in this exact format (no additional text):\n{{\n  \"A\": {{\n    \"issues\": [\"<issue 1>\", \"<issue 2>\", ...],\n    \"rank\": <1, 2, or 3>\n  }},\n  \"B\": {{\n    \"issues\": [\"<issue 1>\", \"<issue 2>\", ...],\n    \"rank\": <1, 2, or 3>\n  }},\n  \"C\": {{\n    \"issues\": [\"<issue 1>\", \"<issue 2>\", ...],\n    \"rank\": <1, 2, or 3>\n  }}\n}}\n\nEvaluation criteria:\n- Hallucination risk (does it encourage making things up?)\n- Ambiguity (is it clear what's expected?)\n- Missing constraints (are requirements omitted?)\n- Clarity and structure\n- If no issues, use empty array []\n- Ensure ranks are unique (1, 2, 3)\n- Output ONLY the JSON object, nothing else",
            max_tokens=max_tokens,
            enforce_json=True,
        )
        critic_json = parse_json_response(critic_response["content"])
        models_used.append(GEMINI_FAST)
        
        # STAGE 4: Synthesizer
        synthesizer_response = call_llm(
            model=GEMINI_FAST,
            prompt=f"You are a prompt synthesis expert. Create the final \"golden prompt\" by combining the best elements from all variations.\n\nDISCERN:\n{json.dumps(discern_json, indent=2)}\n\nEXPANSIONS:\n{json.dumps(expansions_json, indent=2)}\n\nCRITIQUE:\n{json.dumps(critic_json, indent=2)}\n\nCreate a SINGLE optimal prompt that:\n1. Incorporates the best elements from the top-ranked variations\n2. Addresses all identified issues\n3. MUST include these anti-hallucination guardrails:\n   - \"Provide sources for any factual claims\"\n   - \"Use stepwise reasoning for complex questions\"\n   - Explicitly state: \"If you cannot verify a fact, say 'I don't know'.\"\n4. MUST instruct the assistant to output final answers in strict JSON format\n\nYou MUST respond with ONLY valid JSON in this exact format (no additional text):\n{{\n  \"golden_prompt\": \"<the final optimized prompt>\",\n  \"rationale\": \"<explanation of design choices>\",\n  \"token_est\": <estimated tokens for the golden prompt>,\n  \"cost_est_usd\": <estimated cost to run this prompt, use 0.00 for gemini flash>\n}}\n\nRequirements:\n- The golden prompt must be production-ready\n- It must enforce structured JSON output from the assistant\n- Include all mandatory guardrails\n- Keep it concise but comprehensive\n- Output ONLY the JSON object, nothing else",
            max_tokens=max_tokens,
            enforce_json=True,
        )
        final_json = parse_json_response(synthesizer_response["content"])
        models_used.append(GEMINI_FAST)
        
        duration = time.time() - start_time
        
        # Assemble final result
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
        
        log_event("run.end", {"duration_s": duration, "success": True})
        
        return result
    
    except Exception as e:
        log_event("run.error", {"error": str(e)})
        raise


def main():
    """Main CLI entry point."""
    args = parse_args()
    
    # Handle batch mode
    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.exists():
            print(f"Error: Batch file not found: {args.batch}", file=sys.stderr)
            sys.exit(1)
        
        with open(batch_path, 'r') as f:
            ideas = [json.loads(line)["idea"] for line in f if line.strip()]
        
        results = []
        for idx, idea in enumerate(ideas):
            print(f"Processing idea {idx + 1}/{len(ideas)}...", file=sys.stderr)
            result = run_optimization(
                idea=idea,
                seed=args.seed + idx,  # Increment seed for each idea
                max_tokens=args.max_tokens,
                dry_run=args.dry_run,
            )
            results.append(result)
        
        output_data = {"results": results, "batch": True}
    
    # Handle single idea mode
    else:
        result = run_optimization(
            idea=args.idea,
            seed=args.seed,
            max_tokens=args.max_tokens,
            dry_run=args.dry_run,
        )
        output_data = result
    
    # Output result
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"Output written to: {args.output}", file=sys.stderr)
    else:
        print(json.dumps(output_data, indent=2))
    
    # Print golden prompt separately for easy viewing
    if not args.batch and not args.dry_run:
        print("\n" + "="*80, file=sys.stderr)
        print("GOLDEN PROMPT:", file=sys.stderr)
        print("="*80, file=sys.stderr)
        print(result["final"]["golden_prompt"], file=sys.stderr)
        print("="*80, file=sys.stderr)


if __name__ == "__main__":
    main()
