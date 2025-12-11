import json

import pytest

from consensus_prompt_optimizer.orchestrator import PromptimaV2
from consensus_prompt_optimizer.schemas import (
    DiscernOutput,
    RubricOutput,
    ExpansionsOutput,
    ExpansionVariant,
    RankingsOutput,
    RankerVariant,
    SynthesizerOutput,
)


class StubLLM:
    """Simple callable stub to feed canned JSON responses to the synthesizer."""

    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = 0

    def __call__(self, *_, **kwargs):
        idx = min(self.calls, len(self.payloads) - 1)
        self.calls += 1
        payload = self.payloads[idx]
        return {
            "content": json.dumps(payload),
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "model": kwargs.get("model", ""),
            "success": True,
        }


@pytest.fixture
def optimizer():
    return PromptimaV2(use_cache=False, dry_run=False)


@pytest.fixture
def synth_inputs():
    idea = "Test idea for generating a comprehensive prompt that helps users with their tasks effectively"
    discern = DiscernOutput(
        task_type="generation",
        complexity="moderate",
        domain="general",
        key_requirements=["clarity"],
        potential_pitfalls=["vagueness"],
        recommended_approach="structured",
    )
    rubric = RubricOutput(
        rubric={"clarity": "be clear"},
        checklist=["includes clarity"],
        red_flags=["vague"],
    )
    # Use prompts long enough to pass validation (50+ chars, 10+ words)
    expansions = ExpansionsOutput(
        A=ExpansionVariant(
            prompt="You are a helpful assistant. Please analyze this request carefully and provide a well-structured response that addresses all the key points mentioned.",
            notes="note A",
            checklist_score="1/1"
        ),
        B=ExpansionVariant(
            prompt="As an expert in this domain, carefully consider the following task and provide a detailed step-by-step solution that covers all requirements.",
            notes="note B",
            checklist_score="1/1"
        ),
        C=ExpansionVariant(
            prompt="You are a senior professional. Analyze this task thoroughly and deliver a comprehensive response that demonstrates expertise and attention to detail.",
            notes="note C",
            checklist_score="1/1"
        ),
    )
    rankings = RankingsOutput(
        A=RankerVariant(rank=2, score=0.7),
        B=RankerVariant(rank=3, score=0.6),
        C=RankerVariant(rank=1, score=0.9),
    )
    return idea, discern, rubric, expansions, rankings


def patch_llm(monkeypatch, payloads):
    stub = StubLLM(payloads)
    monkeypatch.setattr("consensus_prompt_optimizer.orchestrator.call_llm_v2", stub)
    return stub


# Valid test prompt that passes the minimum length (50+ chars) and word count (10+ words) checks
VALID_TEST_PROMPT = "You are an expert assistant helping with this task. Please analyze the requirements carefully and provide a comprehensive response that addresses all key points."

SHORT_VALID_PROMPT = "This is a sufficiently long test prompt that should pass the minimum length validation requirements for the synthesizer."


def test_synth_only_prompt_field(monkeypatch, optimizer, synth_inputs):
    payloads = [
        {"prompt": VALID_TEST_PROMPT},  # coerced
    ]
    stub = patch_llm(monkeypatch, payloads)

    out = optimizer._run_synthesizer(*synth_inputs)
    assert isinstance(out, SynthesizerOutput)
    assert out.final_prompt == VALID_TEST_PROMPT
    assert stub.calls == 1  # coerced without retry


def test_synth_renamed_key(monkeypatch, optimizer, synth_inputs):
    payloads = [
        {"optimized_prompt": VALID_TEST_PROMPT},  # coerced alias
    ]
    stub = patch_llm(monkeypatch, payloads)

    out = optimizer._run_synthesizer(*synth_inputs)
    assert isinstance(out, SynthesizerOutput)
    assert out.final_prompt == VALID_TEST_PROMPT
    assert stub.calls == 1


def test_synth_confidence_below_threshold(monkeypatch, optimizer, synth_inputs):
    """Low confidence is now auto-clamped to 0.7 minimum instead of rejected."""
    payloads = [
        {
            "final_prompt": VALID_TEST_PROMPT,
            "synthesis_notes": "notes",
            "rubric_compliance": {"c": "done"},
            "confidence": 0.6,
        },
    ]
    stub = patch_llm(monkeypatch, payloads)

    # New behavior: low confidence is clamped to 0.7, not rejected
    out = optimizer._run_synthesizer(*synth_inputs)
    assert isinstance(out, SynthesizerOutput)
    assert out.confidence == 0.7  # Clamped to minimum
    assert stub.calls == 1  # No retry needed


def test_synth_empty_rubric(monkeypatch, optimizer, synth_inputs):
    """Empty rubric is now auto-filled with rubric keys instead of rejected."""
    payloads = [
        {"final_prompt": VALID_TEST_PROMPT, "synthesis_notes": "notes", "rubric_compliance": {}, "confidence": 0.9},
    ]
    stub = patch_llm(monkeypatch, payloads)

    # New behavior: empty rubric is auto-filled from input rubric
    out = optimizer._run_synthesizer(*synth_inputs)
    assert isinstance(out, SynthesizerOutput)
    assert "clarity" in out.rubric_compliance  # Auto-filled from input rubric
    assert stub.calls == 1


def test_synth_optimized_prompt_coerced(monkeypatch, optimizer, synth_inputs):
    payloads = [
        {"optimized_prompt": VALID_TEST_PROMPT},
    ]
    stub = patch_llm(monkeypatch, payloads)

    out = optimizer._run_synthesizer(*synth_inputs)
    assert out.final_prompt == VALID_TEST_PROMPT
    assert out.confidence >= 0.7
    assert stub.calls == 1


def test_synth_nested_result_structure(monkeypatch, optimizer, synth_inputs):
    """LLM wraps output in a 'result' key - should be unwrapped."""
    payloads = [
        {"result": {"prompt": VALID_TEST_PROMPT, "notes": "nested notes"}},
    ]
    stub = patch_llm(monkeypatch, payloads)

    out = optimizer._run_synthesizer(*synth_inputs)
    assert out.final_prompt == VALID_TEST_PROMPT
    assert stub.calls == 1


def test_synth_percentage_confidence(monkeypatch, optimizer, synth_inputs):
    """Confidence given as percentage (85) instead of decimal (0.85)."""
    payloads = [
        {"final_prompt": VALID_TEST_PROMPT, "synthesis_notes": "notes", "rubric_compliance": {"x": "y"}, "confidence": 85},
    ]
    stub = patch_llm(monkeypatch, payloads)

    out = optimizer._run_synthesizer(*synth_inputs)
    assert out.confidence == 0.85
    assert stub.calls == 1


def test_synth_alternative_notes_key(monkeypatch, optimizer, synth_inputs):
    """LLM uses 'rationale' instead of 'synthesis_notes'."""
    payloads = [
        {"final_prompt": VALID_TEST_PROMPT, "rationale": "my reasoning", "rubric_compliance": {"x": "y"}, "confidence": 0.9},
    ]
    stub = patch_llm(monkeypatch, payloads)

    out = optimizer._run_synthesizer(*synth_inputs)
    assert out.synthesis_notes == "my reasoning"
    assert stub.calls == 1


def test_synth_best_prompt_key(monkeypatch, optimizer, synth_inputs):
    """LLM uses 'best_prompt' instead of 'final_prompt'."""
    payloads = [
        {"best_prompt": VALID_TEST_PROMPT},
    ]
    stub = patch_llm(monkeypatch, payloads)

    out = optimizer._run_synthesizer(*synth_inputs)
    assert out.final_prompt == VALID_TEST_PROMPT
    assert stub.calls == 1
