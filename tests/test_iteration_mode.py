import pytest

# Add parent to path for imports (mirrors existing tests)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "consensus_prompt_optimizer"))

from consensus_prompt_optimizer.llm_wrapper_v2 import (
    clear_cache,
    get_idea_hash,
    lookup_generated_prompt,
    save_to_cache,
)
from consensus_prompt_optimizer.orchestrator import PromptimaV2
from consensus_prompt_optimizer.schemas import (
    ExpansionVariant,
    ExpansionsOutput,
    RubricOutput,
)


def test_prompt_output_is_indexed_on_cache_save():
    clear_cache()

    final_prompt = (
        "You are an expert assistant. Follow the user's instructions exactly. "
        "Produce a structured output with clear sections and self-checks."
    )

    result = {
        "version": "v2",
        "final_synthesis": {"prompt": final_prompt},
    }

    idea = "Original idea for testing prompt index"
    save_to_cache(idea, result)

    meta = lookup_generated_prompt(final_prompt)
    assert meta is not None
    assert meta.get("idea_hash") == get_idea_hash(idea)


def test_ranker_penalizes_high_similarity_in_iteration_mode():
    optimizer = PromptimaV2(use_cache=False, dry_run=True)

    baseline = (
        "You are a senior assistant. Analyze the request carefully, ask clarifying questions if needed, "
        "and then produce a structured response with an explicit output format and self-check."
    )

    expansions = ExpansionsOutput(
        A=ExpansionVariant(
            prompt=(
                "You are an expert assistant. Do the task using a strict checklist. "
                "Return output in a defined template with assumptions and edge cases."
            ),
            notes="A",
            checklist_score="N/A",
        ),
        B=ExpansionVariant(
            prompt=(
                "Act as a specialist. Restate requirements, then provide the response in numbered steps. "
                "Include a final verification section before answering."
            ),
            notes="B",
            checklist_score="N/A",
        ),
        C=ExpansionVariant(
            prompt=baseline,  # identical to baseline: should be penalized
            notes="C",
            checklist_score="N/A",
        ),
    )

    rubric = RubricOutput(
        rubric={"clarity": "be clear"},
        checklist=["has format"],
        red_flags=["vague"],
    )

    rankings = optimizer._run_ranker(expansions, rubric, baseline_prompt=baseline)

    # In dry_run, C starts as rank 1 score 0.9, but it should be pushed down
    # because it's effectively a paraphrase/identical to the baseline.
    assert rankings.C.rank == 3
    assert rankings.A.rank == 1
    assert rankings.B.rank == 2
    assert rankings.C.score < rankings.B.score < rankings.A.score
