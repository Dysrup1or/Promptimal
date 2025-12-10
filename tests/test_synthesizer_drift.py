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
    idea = "Test idea"
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
    expansions = ExpansionsOutput(
        A=ExpansionVariant(prompt="Prompt A", notes="note A", checklist_score="1/1"),
        B=ExpansionVariant(prompt="Prompt B", notes="note B", checklist_score="1/1"),
        C=ExpansionVariant(prompt="Prompt C", notes="note C", checklist_score="1/1"),
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


def test_synth_only_prompt_field(monkeypatch, optimizer, synth_inputs):
    payloads = [
        {"prompt": "foo"},  # coerced
    ]
    stub = patch_llm(monkeypatch, payloads)

    out = optimizer._run_synthesizer(*synth_inputs)
    assert isinstance(out, SynthesizerOutput)
    assert out.final_prompt == "foo"
    assert stub.calls == 1  # coerced without retry


def test_synth_renamed_key(monkeypatch, optimizer, synth_inputs):
    payloads = [
        {"optimized_prompt": "bad"},  # coerced alias
    ]
    stub = patch_llm(monkeypatch, payloads)

    out = optimizer._run_synthesizer(*synth_inputs)
    assert isinstance(out, SynthesizerOutput)
    assert out.final_prompt == "bad"
    assert stub.calls == 1


def test_synth_confidence_below_threshold(monkeypatch, optimizer, synth_inputs):
    payloads = [
        {
            "final_prompt": "ok",
            "synthesis_notes": "notes",
            "rubric_compliance": {"c": "done"},
            "confidence": 0.6,
        },
    ]
    stub = patch_llm(monkeypatch, payloads)

    with pytest.raises(ValueError):
        optimizer._run_synthesizer(*synth_inputs)
    assert stub.calls == 2  # initial attempt + retry


def test_synth_empty_rubric(monkeypatch, optimizer, synth_inputs):
    payloads = [
        {"final_prompt": "ok", "synthesis_notes": "notes", "rubric_compliance": {}, "confidence": 0.9},
        {"final_prompt": "ok", "synthesis_notes": "notes", "rubric_compliance": {}, "confidence": 0.9},
    ]
    stub = patch_llm(monkeypatch, payloads)

    with pytest.raises(ValueError):
        optimizer._run_synthesizer(*synth_inputs)
    assert stub.calls == 2


def test_synth_optimized_prompt_coerced(monkeypatch, optimizer, synth_inputs):
    payloads = [
        {"optimized_prompt": "coerced result"},
    ]
    stub = patch_llm(monkeypatch, payloads)

    out = optimizer._run_synthesizer(*synth_inputs)
    assert out.final_prompt == "coerced result"
    assert out.confidence >= 0.7
    assert stub.calls == 1
