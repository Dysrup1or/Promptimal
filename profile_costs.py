"""Offline cost profiling for Catalyze runs.

This script runs the pipeline in `--dry-run` mode (no API calls) while recording
estimated token usage and cost per stage. It then reports average cost per run
for different input sizes.

Usage:
  python Promptly/profile_costs.py
  python Promptly/profile_costs.py --runs 5
  python Promptly/profile_costs.py --json

Notes:
- Estimates use stage-level assumed output token counts in
  `Promptly/consensus_prompt_optimizer/orchestrator.py`.
- Pricing comes from `Promptly/consensus_prompt_optimizer/llm_wrapper_v2.py`.
"""

from __future__ import annotations

import argparse
import io
import json
import contextlib
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from consensus_prompt_optimizer.orchestrator import PromptimaV2
from consensus_prompt_optimizer.llm_wrapper_v2 import count_tokens


@dataclass(frozen=True)
class RunResult:
    size_label: str
    idea_tokens: int
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    by_stage: List[Dict[str, Any]]


def _size_bucket(idea_tokens: int) -> str:
    if idea_tokens <= 64:
        return "small"
    if idea_tokens <= 256:
        return "medium"
    return "large"


def _sample_ideas() -> List[str]:
    # Designed to cover different input sizes without any external dependencies.
    return [
        "Rewrite my email asking for a meeting in a polite tone.",
        "Create a prompt that helps an assistant generate a weekly workout plan for a beginner with limited equipment. Include constraints, safety cautions, and a simple output format.",
        (
            "I need a meta-prompt for an AI assistant to analyze a messy project description and produce a crisp technical spec.\n\n"
            "Context: We have a small team building a web app with a Python API and a Next.js frontend. The input will be rough notes, partial requirements, and contradictory constraints.\n\n"
            "The prompt must instruct the assistant to: (1) summarize intent, (2) list open questions, (3) propose an implementation plan with milestones, (4) define acceptance criteria, and (5) include a risks/mitigations section.\n\n"
            "Hard constraints: no invented facts; call out assumptions; provide a structured Markdown output; keep it concise but complete; add a final self-check against the constraints."
        ),
        (
            "Build a meta-prompt that turns raw stakeholder notes into a complete product requirements document (PRD) and an engineering-ready implementation plan.\n\n"
            "Raw notes may include: feature requests, bugs, customer quotes, analytics snippets, and a partially wrong mental model of the system.\n\n"
            "The prompt must force the assistant to ask clarifying questions first when key information is missing. If information is missing, the assistant must label it as an assumption and keep a separate assumptions list.\n\n"
            "Required PRD sections (in this exact order):\n"
            "1) Problem statement\n"
            "2) Goals (measurable)\n"
            "3) Non-goals\n"
            "4) User stories (at least 6)\n"
            "5) Scope (MVP vs later)\n"
            "6) Data model changes (if any)\n"
            "7) API contract sketch (endpoints, request/response shapes)\n"
            "8) UI behavior sketch (key screens, empty/error/loading states)\n"
            "9) Edge cases\n"
            "10) Risks + mitigations\n"
            "11) Acceptance criteria (testable; at least 12 bullets)\n\n"
            "Engineering plan requirements:\n"
            "- Propose milestones for a 2-week sprint, including an order of operations\n"
            "- Include a test plan (unit/integration/e2e)\n"
            "- Include observability requirements (logs/metrics/traces)\n"
            "- Include performance considerations\n"
            "- Include a rollback plan\n\n"
            "Hard constraints:\n"
            "- Do not fabricate facts.\n"
            "- If a requirement conflicts with another, flag the conflict explicitly and propose a resolution path.\n"
            "- Output must be Markdown.\n"
            "- Add a final self-check that verifies each required section is present and that assumptions are clearly marked."
        ),
    ]


def _run_once(idea: str) -> RunResult:
    optimizer = PromptimaV2(use_cache=False, dry_run=True)

    # Suppress verbose telemetry printing during profiling.
    with contextlib.redirect_stdout(io.StringIO()):
        result = optimizer.run(idea)

    usage = result.get("usage") or {}
    by_stage = usage.get("by_stage") or []

    idea_tokens = count_tokens(idea)
    size_label = _size_bucket(idea_tokens)

    return RunResult(
        size_label=size_label,
        idea_tokens=idea_tokens,
        total_cost_usd=float(usage.get("total_cost_usd") or 0.0),
        total_input_tokens=int(usage.get("total_input_tokens") or 0),
        total_output_tokens=int(usage.get("total_output_tokens") or 0),
        by_stage=by_stage,
    )


def _mean(values: List[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline cost profiling (dry-run estimates)")
    parser.add_argument("--runs", type=int, default=5, help="Runs per sample idea (default: 5)")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    ideas = _sample_ideas()

    results: List[RunResult] = []
    for _ in range(max(1, args.runs)):
        for idea in ideas:
            results.append(_run_once(idea))

    # Group by size bucket
    buckets: Dict[str, List[RunResult]] = {"small": [], "medium": [], "large": []}
    for r in results:
        buckets[r.size_label].append(r)

    summary: Dict[str, Any] = {
        "note": "All values are offline estimates from --dry-run (no API calls).",
        "runs_total": len(results),
        "by_size": {},
    }

    for size_label, items in buckets.items():
        if not items:
            continue
        summary["by_size"][size_label] = {
            "runs": len(items),
            "avg_idea_tokens": round(_mean([float(i.idea_tokens) for i in items]), 1),
            "avg_total_input_tokens": round(_mean([float(i.total_input_tokens) for i in items]), 1),
            "avg_total_output_tokens": round(_mean([float(i.total_output_tokens) for i in items]), 1),
            "avg_total_cost_usd": round(_mean([float(i.total_cost_usd) for i in items]), 6),
        }

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    # Pretty text output
    print("Offline cost profiling (dry-run estimates)\n")
    for size_label in ["small", "medium", "large"]:
        row = summary["by_size"].get(size_label)
        if not row:
            continue
        print(
            f"{size_label:6} | runs={row['runs']:2} | avg idea tokens={row['avg_idea_tokens']:6} | "
            f"avg cost=${row['avg_total_cost_usd']:.6f} | avg in/out tokens={row['avg_total_input_tokens']:.1f}/{row['avg_total_output_tokens']:.1f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
