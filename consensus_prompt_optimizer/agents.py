"""
CrewAI Agent definitions for the Consensus Prompt Optimizer.
Defines 4 agents: Discerner, Expander, Critic, and Synthesizer.
"""

from crewai import Agent
from config import GEMINI_FAST, DEEPSEEK_EXPAND


# ============================================================================
# AGENT 1: DISCERNER
# ============================================================================
# Purpose: Parse raw idea into atomic components and identify ambiguities
# Model: Gemini Flash (cheap/fast)
# Output: {"intent": str, "audience": str, "constraints": [str], "success_criteria": str, "ambiguous": [str]}

DISCERNER_PROMPT_TEMPLATE = """You are an expert prompt analyst. Your task is to parse a raw prompt idea into its atomic components.

INPUT IDEA:
{idea}

You MUST respond with ONLY valid JSON in this exact format (no additional text):
{{
  "intent": "<what the user wants to achieve>",
  "audience": "<who will use this prompt>",
  "constraints": ["<constraint 1>", "<constraint 2>", ...],
  "success_criteria": "<how to measure success>",
  "ambiguous": ["<ambiguity 1>", "<ambiguity 2>", ...]
}}

Rules:
- Be precise and concise
- Extract ALL implicit and explicit constraints
- Identify any ambiguous or unclear aspects in the "ambiguous" field
- If no ambiguities, use empty array []
- Output ONLY the JSON object, nothing else
"""

discerner_agent = Agent(
    role="Prompt Discerner",
    goal="Parse raw prompt ideas into structured components and identify ambiguities",
    backstory="You are an expert at analyzing prompts and extracting their core components. "
              "You identify what the user truly wants and spot gaps or unclear requirements.",
    llm=GEMINI_FAST,
    verbose=True,
    allow_delegation=False,
)


# ============================================================================
# AGENT 2: EXPANDER
# ============================================================================
# Purpose: Generate 3 prompt variations (A: role-based, B: CoT, C: role-immersive with guardrails)
# Model: DeepSeek (THE ONLY DEEPSEEK CALL, ≤350 tokens)
# Output: {"A": {prompt, notes, token_est}, "B": {...}, "C": {...}}

EXPANDER_PROMPT_TEMPLATE = """You are a prompt engineering expert. Given the parsed idea below, create exactly THREE prompt variations.

PARSED IDEA:
{discern_json}

Create THREE variations with these exact characteristics:
- Variation A: Direct role-based prompt (simple and clear)
- Variation B: Chain-of-thought prompt (explicit step-by-step reasoning instructions)
- Variation C: Role-immersive prompt with anti-hallucination guardrails

You MUST respond with ONLY valid JSON in this exact format (no additional text):
{{
  "A": {{
    "prompt": "<the actual prompt text for variation A>",
    "notes": "<brief notes on the approach>",
    "token_est": <estimated tokens>
  }},
  "B": {{
    "prompt": "<the actual prompt text for variation B>",
    "notes": "<brief notes on the approach>",
    "token_est": <estimated tokens>
  }},
  "C": {{
    "prompt": "<the actual prompt text for variation C>",
    "notes": "<brief notes on the approach>",
    "token_est": <estimated tokens>
  }}
}}

Requirements:
- Each prompt must be complete and ready to use
- Variation B MUST include explicit "think step-by-step" instructions
- Variation C MUST include guardrails: require sources, explicit "If you cannot verify a fact, say 'I don't know'."
- Keep responses concise (you have a 350 token limit)
- Output ONLY the JSON object, nothing else
"""

expander_agent = Agent(
    role="Prompt Expander",
    goal="Generate three distinct, high-quality prompt variations using different techniques",
    backstory="You are a master prompt engineer who understands different prompting strategies: "
              "direct role-based, chain-of-thought, and role-immersive with guardrails. "
              "You create prompts that minimize hallucinations and maximize clarity.",
    llm=DEEPSEEK_EXPAND,
    verbose=True,
    allow_delegation=False,
)


# ============================================================================
# AGENT 3: CRITIC
# ============================================================================
# Purpose: Evaluate prompt variations and rank them
# Model: Gemini Flash (cheap/fast)
# Output: {"A": {issues: [str], rank: int}, "B": {...}, "C": {...}}

CRITIC_PROMPT_TEMPLATE = """You are a prompt quality critic. Evaluate the three prompt variations below.

EXPANSIONS:
{expansions_json}

For each variation (A, B, C), identify potential issues and assign a rank (1=best, 2=middle, 3=worst).

You MUST respond with ONLY valid JSON in this exact format (no additional text):
{{
  "A": {{
    "issues": ["<issue 1>", "<issue 2>", ...],
    "rank": <1, 2, or 3>
  }},
  "B": {{
    "issues": ["<issue 1>", "<issue 2>", ...],
    "rank": <1, 2, or 3>
  }},
  "C": {{
    "issues": ["<issue 1>", "<issue 2>", ...],
    "rank": <1, 2, or 3>
  }}
}}

Evaluation criteria:
- Hallucination risk (does it encourage making things up?)
- Ambiguity (is it clear what's expected?)
- Missing constraints (are requirements omitted?)
- Clarity and structure
- If no issues, use empty array []
- Ensure ranks are unique (1, 2, 3)
- Output ONLY the JSON object, nothing else
"""

critic_agent = Agent(
    role="Prompt Critic",
    goal="Evaluate prompt variations and identify potential issues",
    backstory="You are a meticulous prompt evaluator with deep expertise in identifying "
              "hallucination risks, ambiguities, and missing constraints. "
              "You rank prompts based on quality and robustness.",
    llm=GEMINI_FAST,
    verbose=True,
    allow_delegation=False,
)


# ============================================================================
# AGENT 4: SYNTHESIZER
# ============================================================================
# Purpose: Create the final "golden prompt" by synthesizing best elements
# Model: Gemini Flash (cheap/fast)
# Output: {"golden_prompt": str, "rationale": str, "token_est": int, "cost_est_usd": float}

SYNTHESIZER_PROMPT_TEMPLATE = """You are a prompt synthesis expert. Create the final "golden prompt" by combining the best elements from all variations.

DISCERN:
{discern_json}

EXPANSIONS:
{expansions_json}

CRITIQUE:
{critic_json}

Create a SINGLE optimal prompt that:
1. Incorporates the best elements from the top-ranked variations
2. Addresses all identified issues
3. MUST include these anti-hallucination guardrails:
   - "Provide sources for any factual claims"
   - "Use stepwise reasoning for complex questions"
   - Explicitly state: "If you cannot verify a fact, say 'I don't know'."
4. MUST instruct the assistant to output final answers in strict JSON format

You MUST respond with ONLY valid JSON in this exact format (no additional text):
{{
  "golden_prompt": "<the final optimized prompt>",
  "rationale": "<explanation of design choices>",
  "token_est": <estimated tokens for the golden prompt>,
  "cost_est_usd": <estimated cost to run this prompt, use $0.00 for gemini flash>
}}

Requirements:
- The golden prompt must be production-ready
- It must enforce structured JSON output from the assistant
- Include all mandatory guardrails
- Keep it concise but comprehensive
- Output ONLY the JSON object, nothing else
"""

synthesizer_agent = Agent(
    role="Prompt Synthesizer",
    goal="Create the final optimized 'golden prompt' with anti-hallucination guardrails",
    backstory="You are a prompt synthesis expert who combines the best elements from multiple "
              "variations to create a single, optimal prompt. You ensure all guardrails are "
              "in place to prevent hallucinations and enforce structured output.",
    llm=GEMINI_FAST,
    verbose=True,
    allow_delegation=False,
)
