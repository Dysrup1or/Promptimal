"""
CrewAI Task definitions for the Consensus Prompt Optimizer.
Defines the sequential workflow for the 4 agents.
"""

from crewai import Task
from agents import (
    discerner_agent,
    expander_agent,
    critic_agent,
    synthesizer_agent,
    DISCERNER_PROMPT_TEMPLATE,
    EXPANDER_PROMPT_TEMPLATE,
    CRITIC_PROMPT_TEMPLATE,
    SYNTHESIZER_PROMPT_TEMPLATE,
)


def create_discern_task(idea: str) -> Task:
    """
    Create the Discerner task to parse the raw idea.
    
    Args:
        idea: Raw prompt idea string
    
    Returns:
        CrewAI Task object
    """
    return Task(
        description=DISCERNER_PROMPT_TEMPLATE.format(idea=idea),
        agent=discerner_agent,
        expected_output="JSON object with intent, audience, constraints, success_criteria, and ambiguous fields",
    )


def create_expander_task(discern_json: str) -> Task:
    """
    Create the Expander task to generate 3 prompt variations.
    
    Args:
        discern_json: JSON string from Discerner output
    
    Returns:
        CrewAI Task object
    """
    return Task(
        description=EXPANDER_PROMPT_TEMPLATE.format(discern_json=discern_json),
        agent=expander_agent,
        expected_output="JSON object with A, B, C variations, each containing prompt, notes, and token_est",
    )


def create_critic_task(expansions_json: str) -> Task:
    """
    Create the Critic task to evaluate prompt variations.
    
    Args:
        expansions_json: JSON string from Expander output
    
    Returns:
        CrewAI Task object
    """
    return Task(
        description=CRITIC_PROMPT_TEMPLATE.format(expansions_json=expansions_json),
        agent=critic_agent,
        expected_output="JSON object with A, B, C critiques, each containing issues and rank",
    )


def create_synthesizer_task(discern_json: str, expansions_json: str, critic_json: str) -> Task:
    """
    Create the Synthesizer task to produce the final golden prompt.
    
    Args:
        discern_json: JSON string from Discerner output
        expansions_json: JSON string from Expander output
        critic_json: JSON string from Critic output
    
    Returns:
        CrewAI Task object
    """
    return Task(
        description=SYNTHESIZER_PROMPT_TEMPLATE.format(
            discern_json=discern_json,
            expansions_json=expansions_json,
            critic_json=critic_json,
        ),
        agent=synthesizer_agent,
        expected_output="JSON object with golden_prompt, rationale, token_est, and cost_est_usd",
    )
