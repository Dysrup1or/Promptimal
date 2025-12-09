"""Estimate tokens for complex prompt."""
import tiktoken

enc = tiktoken.get_encoding('cl100k_base')

# Your prompt
prompt = """Write a prompt that builds a system around the below workflows
Working automated pipeline: Lead Source → CRM (Airtable/HubSpot) → Instant contact (Twilio SMS + Email) → Sales notification (Slack) → AI lead-summaries (OpenAI) → Calendar booking (Calendly integration)."""

input_tokens = len(enc.encode(prompt))
print(f"Input prompt tokens: {input_tokens}")

# Estimate output for each stage
estimates = {
    "Discerner": 200,
    "CriticFirst": 800,
    "Expander (DeepSeek)": 2500,  # 3 detailed variations
    "Ranker": 100,
    "Synthesizer": 1500
}

total_output = sum(estimates.values())
print(f"\nEstimated output tokens per stage:")
for stage, tokens in estimates.items():
    print(f"  {stage}: ~{tokens}")
print(f"\nTotal estimated output: ~{total_output} tokens")

# Cost estimate
deepseek_cost = 2500 * 0.28 / 1_000_000
print(f"\nEstimated DeepSeek cost: ${deepseek_cost:.6f}")
print(f"Gemini cost: $0.00 (free tier)")
print(f"Total estimated: ~${deepseek_cost:.6f}")
print(f"\nCurrent limits are sufficient: DeepSeek cap = 4000 tokens")
