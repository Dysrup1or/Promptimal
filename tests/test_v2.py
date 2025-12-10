"""
Tests for Promptly v2 - Judge-then-Generate workflow.

Tests cover:
1. Schema validation
2. Individual stage functions (dry run)
3. Full pipeline dry run
4. Caching functionality
5. Token tracking
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "consensus_prompt_optimizer"))

from consensus_prompt_optimizer.schemas import (
    DiscernOutput,
    RubricOutput,
    ExpansionsOutput,
    RankingsOutput,
    SynthesizerOutput,
    ExpansionVariant,
    RankerVariant,
    validate_stage_output,
    minify_json,
    ANTI_LAME_CHECKLIST
)

from consensus_prompt_optimizer.llm_wrapper_v2 import (
    count_tokens,
    calculate_cost,
    compress_prompt,
    get_idea_hash,
    parse_json_response_v2,
    TokenTracker
)

from consensus_prompt_optimizer.orchestrator import PromptimaV2


# ============================================================================
# SCHEMA VALIDATION TESTS
# ============================================================================

class TestDiscernOutput:
    """Test DiscernOutput schema."""
    
    def test_valid_discern(self):
        data = {
            "task_type": "generation",
            "complexity": "moderate",
            "domain": "technical",
            "key_requirements": ["clarity", "examples"],
            "potential_pitfalls": ["vagueness"],
            "recommended_approach": "structured"
        }
        result = DiscernOutput(**data)
        assert result.task_type == "generation"
        assert len(result.key_requirements) == 2
    
    def test_empty_lists_valid(self):
        data = {
            "task_type": "analysis",
            "complexity": "simple",
            "domain": "general",
            "key_requirements": [],
            "potential_pitfalls": [],
            "recommended_approach": ""
        }
        result = DiscernOutput(**data)
        assert result.key_requirements == []


class TestRubricOutput:
    """Test RubricOutput schema."""
    
    def test_valid_rubric(self):
        data = {
            "rubric": {
                "clarity": "prompt should be clear and unambiguous",
                "specificity": "include concrete examples"
            },
            "checklist": [
                "has examples",
                "specifies format",
                "includes constraints"
            ],
            "red_flags": [
                "vague instructions",
                "no output format"
            ]
        }
        result = RubricOutput(**data)
        assert len(result.rubric) == 2
        assert len(result.checklist) == 3
        assert len(result.red_flags) == 2
    
    def test_minimum_items(self):
        """Rubric can have minimal items."""
        data = {
            "rubric": {"key": "value"},
            "checklist": ["item"],
            "red_flags": []
        }
        result = RubricOutput(**data)
        assert len(result.rubric) == 1


class TestExpansionsOutput:
    """Test ExpansionsOutput schema."""
    
    def test_valid_expansions(self):
        data = {
            "A": {"prompt": "Prompt A text", "notes": "concise approach", "checklist_score": "4/6"},
            "B": {"prompt": "Prompt B text", "notes": "detailed approach", "checklist_score": "5/6"},
            "C": {"prompt": "Prompt C text", "notes": "structured approach", "checklist_score": "6/6"}
        }
        result = ExpansionsOutput(**data)
        assert result.A.prompt == "Prompt A text"
        assert result.B.checklist_score == "5/6"


class TestRankingsOutput:
    """Test RankingsOutput schema."""
    
    def test_valid_rankings(self):
        data = {
            "A": {"rank": 2, "score": 0.75},
            "B": {"rank": 3, "score": 0.60},
            "C": {"rank": 1, "score": 0.90}
        }
        result = RankingsOutput(**data)
        assert result.A.rank == 2
        assert result.C.score == 0.90
    
    def test_unique_ranks_validation(self):
        """Test that duplicate ranks are rejected by validate_stage_output."""
        data = {
            "A": {"rank": 1, "score": 0.75},
            "B": {"rank": 1, "score": 0.60},  # Duplicate!
            "C": {"rank": 2, "score": 0.90}
        }
        with pytest.raises(ValueError, match="unique"):
            validate_stage_output(data, RankingsOutput)


class TestSynthesizerOutput:
    """Test SynthesizerOutput schema."""
    
    def test_valid_synthesizer(self):
        data = {
            "final_prompt": "This is the final optimized prompt.",
            "synthesis_notes": "Combined best elements from A and C",
            "rubric_compliance": {
                "clarity": "addressed through explicit instructions",
                "specificity": "added concrete examples"
            },
            "confidence": 0.85
        }
        result = SynthesizerOutput(**data)
        assert "final" in result.final_prompt
        assert result.confidence == 0.85


# ============================================================================
# LLM WRAPPER V2 TESTS
# ============================================================================

class TestTokenCounting:
    """Test token counting utilities."""
    
    def test_count_tokens_basic(self):
        text = "Hello, world!"
        tokens = count_tokens(text)
        assert tokens > 0
        assert tokens < 10
    
    def test_count_tokens_longer(self):
        text = "This is a longer sentence with more words and punctuation."
        tokens = count_tokens(text)
        assert tokens > 10


class TestCostCalculation:
    """Test cost calculation."""
    
    def test_deepseek_cost(self):
        cost = calculate_cost(1000, 500, "deepseek/deepseek-chat")
        # Input: 1000/1M * 0.14 = 0.00014
        # Output: 500/1M * 0.28 = 0.00014
        assert 0.00025 < cost < 0.00035
    
    def test_gemini_free(self):
        cost = calculate_cost(1000, 500, "gemini/gemini-2.0-flash")
        assert cost == 0.0
    
    def test_groq_cost(self):
        """Test Groq Llama 3.3 70B cost calculation."""
        cost = calculate_cost(2000, 4000, "groq/llama-3.3-70b-versatile")
        # Input: 2000/1M * 0.59 = 0.00118
        # Output: 4000/1M * 0.79 = 0.00316
        # Total: ~0.00434
        assert 0.004 < cost < 0.005


class TestPromptCompression:
    """Test prompt compression."""
    
    def test_whitespace_normalization(self):
        text = "Hello    world\n\n\n\nTest"
        compressed = compress_prompt(text)
        assert "    " not in compressed
        assert "\n\n\n" not in compressed
    
    def test_truncation(self):
        long_text = "A" * 10000
        compressed = compress_prompt(long_text, max_chars=1000)
        assert len(compressed) <= 1000
        assert "TRUNCATED" in compressed


class TestIdeaHashing:
    """Test SHA-256 idea hashing."""
    
    def test_hash_consistency(self):
        idea = "Write a prompt for summarizing articles"
        hash1 = get_idea_hash(idea)
        hash2 = get_idea_hash(idea)
        assert hash1 == hash2
    
    def test_case_insensitive(self):
        idea1 = "Test Idea"
        idea2 = "test idea"
        assert get_idea_hash(idea1) == get_idea_hash(idea2)
    
    def test_hash_length(self):
        idea = "Any idea"
        hash_val = get_idea_hash(idea)
        assert len(hash_val) == 16


class TestJsonParsing:
    """Test JSON response parsing."""
    
    def test_clean_json(self):
        content = '{"key": "value"}'
        result = parse_json_response_v2(content)
        assert result["key"] == "value"
    
    def test_markdown_wrapped(self):
        content = '```json\n{"key": "value"}\n```'
        result = parse_json_response_v2(content)
        assert result["key"] == "value"
    
    def test_trailing_comma_fix(self):
        content = '{"key": "value",}'
        result = parse_json_response_v2(content)
        assert result["key"] == "value"


class TestTokenTracker:
    """Test token tracking."""
    
    def test_record_and_summary(self):
        tracker = TokenTracker()
        tracker.record({
            "model": "gemini/gemini-1.5-flash",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost": 0.0
        }, "test_stage")
        
        summary = tracker.summary()
        assert summary["total_calls"] == 1
        assert summary["total_input_tokens"] == 100
        assert summary["total_output_tokens"] == 50
    
    def test_budget_check(self):
        tracker = TokenTracker()
        tracker.record({"cost": 0.01}, "stage1")
        tracker.record({"cost": 0.01}, "stage2")
        
        assert tracker.is_under_budget(0.025)
        assert not tracker.is_under_budget(0.015)


# ============================================================================
# ORCHESTRATOR TESTS (DRY RUN)
# ============================================================================

class TestOrchestratorDryRun:
    """Test orchestrator in dry run mode."""
    
    def test_dry_run_basic(self):
        """Dry run should complete without API calls."""
        optimizer = PromptimaV2(use_cache=False, dry_run=True)
        result = optimizer.run("Create a prompt for code review")
        
        assert "version" in result
        assert result["version"] == "v2"
        assert "final_synthesis" in result
        assert "usage" in result
    
    def test_dry_run_structure(self):
        """Check output structure matches expected format."""
        optimizer = PromptimaV2(use_cache=False, dry_run=True)
        result = optimizer.run("Test idea")
        
        # Top-level keys
        assert "original_idea" in result
        assert "task_analysis" in result
        assert "rubric" in result
        assert "variations" in result
        assert "final_synthesis" in result
        
        # Variations structure
        assert "A" in result["variations"]
        assert "B" in result["variations"]
        assert "C" in result["variations"]
        
        for var in ["A", "B", "C"]:
            assert "prompt" in result["variations"][var]
            assert "rank" in result["variations"][var]


# ============================================================================
# ANTI-LAME CHECKLIST TESTS
# ============================================================================

class TestAntiLameChecklist:
    """Test the anti-lame checklist constant."""
    
    def test_checklist_exists(self):
        assert len(ANTI_LAME_CHECKLIST) >= 10
    
    def test_checklist_items_are_strings(self):
        for item in ANTI_LAME_CHECKLIST:
            assert isinstance(item, str)
            assert len(item) > 5


# ============================================================================
# MINIFY JSON TESTS
# ============================================================================

class TestMinifyJson:
    """Test JSON minification."""
    
    def test_minify_removes_whitespace(self):
        data = {"key": "value", "list": [1, 2, 3]}
        result = minify_json(data)
        assert "\n" not in result
        assert "  " not in result


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
