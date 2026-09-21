"""
Structured output for both the explainer system and the judge.

We force JSON by giving Groq a single tool and requiring tool_choice to use
it (OpenAI-compatible function calling). This means the harness never has
to regex-parse free text out of a model response — every field either
parses or the run fails loudly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import groq

# --- Explainer output --------------------------------------------------

EXPLAIN_TOOL = {
    "name": "submit_explanation",
    "description": "Submit a plain-English explanation of a SQL query.",
    "input_schema": {
        "type": "object",
        "properties": {
            "explanation": {
                "type": "string",
                "description": "Plain-English explanation of what the query does. No SQL jargon a non-technical reader wouldn't know.",
            },
            "clauses_covered": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short list of the SQL clauses/features this explanation addresses, e.g. ['JOIN', 'GROUP BY', 'HAVING'].",
            },
        },
        "required": ["explanation", "clauses_covered"],
    },
}

# --- Judge output --------------------------------------------------------

JUDGE_TOOL = {
    "name": "submit_verdict",
    "description": "Submit a grade for a candidate SQL explanation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["pass", "fail"],
                "description": "pass if the explanation is correct, complete, and invents nothing; fail otherwise.",
            },
            "score": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "1 (unusable) to 5 (excellent) quality score.",
            },
            "reason": {
                "type": "string",
                "description": "One or two sentences: what's right or wrong, citing the specific clause if relevant.",
            },
        },
        "required": ["verdict", "score", "reason"],
    },
}


@dataclass
class CallResult:
    data: dict[str, Any]
    input_tokens: int
    output_tokens: int


def _to_openai_tool(tool: dict) -> dict:
    """Convert our Anthropic-style tool dict ({name, description, input_schema})
    into the OpenAI/Groq function-calling shape."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        },
    }


def call_with_tool(
    client: "groq.Groq",
    model: str,
    system: str,
    user_content: str,
    tool: dict,
    max_tokens: int,
) -> CallResult:
    """Call Groq, forcing it to respond via the given tool. Returns the
    parsed tool arguments plus token counts for cost tracking.

    gpt-oss models sometimes spend part of their output budget on hidden
    reasoning before emitting the tool call, which can truncate the JSON
    mid-way if max_tokens is too tight. We ask for low reasoning effort to
    reduce that, and retry once with a larger budget if the JSON still
    comes back truncated/invalid — better than failing the whole run on
    one flaky item.
    """
    extra_kwargs = {}
    if model.startswith("openai/gpt-oss"):
        extra_kwargs["reasoning_effort"] = "low"

    last_error = None
    for attempt, tokens in enumerate([max_tokens, max_tokens * 3]):
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=tokens,
                tools=[_to_openai_tool(tool)],
                tool_choice={"type": "function", "function": {"name": tool["name"]}},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                **extra_kwargs,
            )
        except groq.BadRequestError as e:
            last_error = e
            continue  # likely truncated tool call JSON — retry with a bigger budget

        message = response.choices[0].message
        if not message.tool_calls:
            last_error = ValueError(f"No tool call in response: {message}")
            continue
        call = message.tool_calls[0]
        try:
            data = json.loads(call.function.arguments)
        except json.JSONDecodeError as e:
            last_error = ValueError(f"Model returned invalid JSON in tool arguments: {call.function.arguments!r}")
            continue
        return CallResult(
            data=data,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

    raise ValueError(f"Failed after retry with larger max_tokens: {last_error}") from last_error


def read_jsonl(path) -> list[dict]:
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def write_jsonl(path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
