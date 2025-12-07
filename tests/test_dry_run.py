"""
Unit test for dry-run mode.
Validates that --dry-run returns proper JSON skeleton and reasonable cost estimate.
"""

import json
import pytest
from consensus_prompt_optimizer.main import estimate_dry_run_cost


def test_dry_run_returns_valid_json():
    """Test that dry-run returns valid JSON with all required keys."""
    idea = "Write persuasive landing pages for SaaS products"
    result = estimate_dry_run_cost(idea)
    
    # Verify it's a dictionary
    assert isinstance(result, dict)
    
    # Verify all required top-level keys
    required_keys = ["input", "discern", "expansions", "critic", "final", "meta"]
    for key in required_keys:
        assert key in result, f"Missing required key: {key}"
    
    # Verify input matches
    assert result["input"] == idea
    
    # Verify discern structure
    assert "intent" in result["discern"]
    assert "audience" in result["discern"]
    assert "constraints" in result["discern"]
    assert "success_criteria" in result["discern"]
    assert "ambiguous" in result["discern"]
    
    # Verify expansions structure
    for variant in ["A", "B", "C"]:
        assert variant in result["expansions"]
        assert "prompt" in result["expansions"][variant]
        assert "notes" in result["expansions"][variant]
        assert "token_est" in result["expansions"][variant]
    
    # Verify critic structure
    for variant in ["A", "B", "C"]:
        assert variant in result["critic"]
        assert "issues" in result["critic"][variant]
        assert "rank" in result["critic"][variant]
    
    # Verify final structure
    assert "golden_prompt" in result["final"]
    assert "rationale" in result["final"]
    assert "token_est" in result["final"]
    assert "cost_est_usd" in result["final"]
    
    # Verify meta structure
    assert "seed" in result["meta"]
    assert "duration_s" in result["meta"]
    assert "models_used" in result["meta"]
    assert "estimated_total_cost_usd" in result["meta"]
    assert "dry_run" in result["meta"]
    assert result["meta"]["dry_run"] is True


def test_dry_run_cost_under_budget():
    """Test that dry-run estimates cost < $0.05."""
    idea = "Write persuasive landing pages for SaaS products"
    result = estimate_dry_run_cost(idea)
    
    cost = result["meta"]["estimated_total_cost_usd"]
    assert isinstance(cost, (int, float))
    assert cost < 0.05, f"Estimated cost ${cost} exceeds budget of $0.05"
    assert cost >= 0, "Cost should be non-negative"


def test_dry_run_different_ideas():
    """Test dry-run with various idea lengths."""
    ideas = [
        "Short idea",
        "Medium length idea that has more details",
        "Very long idea with lots of context and details that spans multiple sentences and provides extensive background information about what we want to accomplish with this prompt optimization task",
    ]
    
    for idea in ideas:
        result = estimate_dry_run_cost(idea)
        assert result["input"] == idea
        assert result["meta"]["estimated_total_cost_usd"] < 0.05


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
