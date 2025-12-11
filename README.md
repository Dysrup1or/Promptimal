# ⚗️ Catalyze - Prompt Transformation Engine

A production-ready AI-powered platform that transforms raw prompt ideas into bulletproof, production-ready prompts using multi-stage consensus optimization.

## Overview

Catalyze orchestrates 5 AI stages to transform a raw prompt idea into a production-ready "golden prompt":

1. **Discerner** (Gemini Flash) - Parses raw ideas into structured components
2. **Expander** (DeepSeek, single call ≤350 tokens) - Generates 3 prompt variations (role-based, CoT, role-immersive)
3. **Critic** (Gemini Flash) - Evaluates variations and identifies issues
4. **Synthesizer** (Gemini Flash) - Creates the final optimized prompt with anti-hallucination guardrails

## Cost Constraints

- **Target**: < $0.05 USD per run
- **Enforcement**: Only ONE DeepSeek call (≤350 tokens) per run
- **Other calls**: Gemini Flash (free/cheap)
- **Token cap**: 2,000 tokens per LLM call (configurable)

## Installation

```bash
# Clone or navigate to the project directory
cd Promptimal

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys
```

## Configuration

**Required API Keys:**
- `GEMINI_API_KEY` - Google Gemini API key
- `DEEPSEEK_API_KEY` - DeepSeek API key

**Optional:**
- `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` - For telemetry (production monitoring)

## Usage

### Single Prompt Optimization

```bash
python -m consensus_prompt_optimizer.main \
  --idea "I want a prompt that writes persuasive landing pages for indie SaaS products"
```

### Dry Run (Cost Estimation Only)

```bash
python -m consensus_prompt_optimizer.main \
  --idea "Write persuasive landing pages" \
  --dry-run
```

### Batch Processing

Create a JSONL file (`ideas.jsonl`):
```jsonl
{"idea": "Write persuasive landing pages for SaaS"}
{"idea": "Analyze customer feedback for sentiment"}
{"idea": "Generate technical documentation from code"}
```

Run batch:
```bash
python -m consensus_prompt_optimizer.main \
  --batch ideas.jsonl \
  --parallel
```

### CLI Flags

- `--idea <text>` - Single prompt idea to optimize
- `--batch <path>` - Path to JSONL file with multiple ideas
- `--dry-run` - Only estimate cost, no LLM calls
- `--max-tokens <int>` - Override default token limit (default: 2000)
- `--parallel` - Enable parallel batch processing
- `--seed <int>` - Random seed for reproducibility (default: 42)
- `--output <path>` - Write output to file instead of stdout

## Output Format

The tool outputs a strict JSON schema:

```json
{
  "input": "<original idea>",
  "discern": {
    "intent": "...",
    "audience": "...",
    "constraints": [...],
    "success_criteria": "...",
    "ambiguous": [...]
  },
  "expansions": {
    "A": {"prompt": "...", "notes": "...", "token_est": 0},
    "B": {"prompt": "...", "notes": "...", "token_est": 0},
    "C": {"prompt": "...", "notes": "...", "token_est": 0}
  },
  "critic": {
    "A": {"issues": [...], "rank": 0},
    "B": {"issues": [...], "rank": 0},
    "C": {"issues": [...], "rank": 0}
  },
  "final": {
    "golden_prompt": "...",
    "rationale": "...",
    "token_est": 0,
    "cost_est_usd": 0.0
  },
  "meta": {
    "seed": 42,
    "duration_s": 0.0,
    "models_used": [...]
  }
}
```

## Anti-Hallucination Guardrails

Every golden prompt includes mandatory guardrails:
- Require sources for factual claims
- Enforce stepwise reasoning
- Explicit instruction: **"If you cannot verify a fact, say 'I don't know'."**
- Structured JSON output format enforcement

## Focus-Retention Guardrails (v2.1)

The pipeline includes three layers of protection against **execution creep** (when complex user inputs cause the system to execute instructions instead of optimizing them into prompts):

### 1. Identity Assertions
Each pipeline stage has an explicit identity block that prevents role drift:
```
[IDENTITY: Prompt Expansion Agent]
TASK: Create three PROMPT variations—not implementations.
META-RULE: The user's idea describes what a FUTURE LLM should do. You REFINE
those instructions into better prompts. You do NOT execute them yourself.
CREATIVITY: Full freedom in style (role-based, CoT, structured, conversational).
```

### 2. Execution Creep Checks
Expander and Synthesizer stages include negative examples that clarify the distinction:
```
EXECUTION CREEP CHECK:
Example input: "Create a landing page with testimonials"
  ❌ WRONG: Output HTML/React code for a landing page
  ✅ RIGHT: Output a PROMPT like "You are a copywriter. Write landing page copy..."
```

### 3. Constraint Repositioning
Critical constraints are positioned at the **start** and **end** of prompts (avoiding the "lost in the middle" effect where LLMs forget central instructions):
- MANDATORY/CRITICAL rules moved to immediately after identity block
- FINAL CHECK assertion before JSON output schema

### Creativity Preservation
These guardrails explicitly **allow**:
- All action verbs: generate, create, produce, build, write, craft, develop, construct, design
- All prompt styles: role-based, chain-of-thought, few-shot, structured, conversational
- Full creative latitude in prompt engineering techniques

Research basis: arXiv 2402.01822 (Building Guardrails for LLMs), arXiv 2502.04362 (Lost in the Middle effect)

## Architecture

```
consensus_prompt_optimizer/
├── __init__.py          # Package init
├── main.py              # CLI entry point + orchestration
├── config.py            # Model routing, pricing, settings
├── agents.py            # 4 CrewAI agent definitions
├── tasks.py             # CrewAI task factory functions
├── utils.py             # Token/cost estimators, retry logic
└── llm_wrapper.py       # LiteLLM with single DeepSeek enforcement
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_dry_run.py -v
```

## Example Run

```bash
python -m consensus_prompt_optimizer.main \
  --idea "I want a prompt that writes persuasive landing pages for indie SaaS products" \
  --seed 42
```

**Expected Output:**
- Complete JSON with all agent outputs
- Golden prompt with anti-hallucination guardrails
- Cost estimate < $0.05
- Only 1 DeepSeek call logged in metadata

## Next Steps (40% → 80% → 100%)

**Current: 60% Complete**

**To reach 80%:**
- Add iterative critic refinement (max 3 iterations)
- Implement Langfuse telemetry integration
- Add tiktoken for accurate token counting
- Enhance error handling and validation

**To reach 100%:**
- Add prompt testing/validation framework
- Implement caching for repeated ideas
- Add export formats (Markdown, PDF)
- Build web UI for easier access
- Add more prompt strategy variations

## License

MIT
