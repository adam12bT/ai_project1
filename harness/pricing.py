"""
Per-million-token prices in USD, for Groq's API. Update here when prices
change — nowhere else in the codebase should hardcode a price.
Check https://groq.com/pricing for current numbers before you report a
cost figure in results/ or report.pdf. (Prices below current as of Sept 2026.)
"""
(input $ / MTok, output $ / MTok)
PRICES = {
"llama-3.3-70b-versatile": (0.59, 0.79),
"llama-3.1-8b-instant": (0.05, 0.08),
"openai/gpt-oss-120b": (0.15, 0.60),
"openai/gpt-oss-20b": (0.075, 0.30),
"qwen/qwen3-32b": (0.29, 0.59),
}

def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
if model not in PRICES:
raise KeyError(
f"No price entry for '{model}'. Add one to harness/pricing.py "
f"(check https://groq.com/pricing) before reporting cost for this model."
)
in_price, out_price = PRICES[model]
return (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price
