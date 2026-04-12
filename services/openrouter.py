"""
OpenRouter LLM client for the AI assistant.

Uses open-weights models via the OpenRouter API (OpenAI-compatible).
Uses json_schema structured output for reliable, typed responses.
"""
from __future__ import annotations

import json
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


async def chat_completion(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    json_schema: dict | None = None,
) -> dict:
    """
    Send a chat completion request to OpenRouter.

    If json_schema is provided, uses response_format type=json_schema
    (structured output with enum constraints). Otherwise returns raw text.
    """
    model = model or settings.openrouter_model

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sentinel.civil42.pl",
        "X-Title": "SENTINEL Crisis Dashboard",
    }

    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_schema:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": json_schema,
        }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{OPENROUTER_BASE}/chat/completions",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()

    data = resp.json()

    if "choices" not in data or not data["choices"]:
        err = data.get("error", {})
        logger.error("OpenRouter API error: %s | full: %s", err.get("message", data), data)
        raise ValueError(f"OpenRouter error: {err.get('message', 'no choices returned')}")

    choice = data["choices"][0]
    message = choice["message"]
    content = message.get("content") or ""
    model_used = data.get("model", model)

    logger.info("OpenRouter raw message keys: %s", list(message.keys()))

    if not content.strip():
        for alt_key in ("reasoning", "reasoning_content"):
            alt = message.get(alt_key)
            if alt and isinstance(alt, str) and "{" in alt:
                content = alt
                break

    if not content.strip():
        logger.warning("OpenRouter returned empty content. Full message: %s", message)
        raise ValueError("LLM returned empty content")

    logger.info("OpenRouter response from %s (%d tokens), content length=%d",
                model_used, data.get("usage", {}).get("total_tokens", 0), len(content))

    if json_schema:
        parsed = _parse_json_defensive(content)
        if isinstance(parsed, dict):
            parsed["_model"] = model_used
        else:
            parsed = {"_raw": parsed, "_model": model_used}
        return parsed

    return {"text": content, "_model": model_used}


def _parse_json_defensive(content: str) -> dict:
    """Parse JSON with defensive handling for markdown-wrapped and think-wrapped responses."""
    text = content.strip()

    think_end = text.find("</think>")
    if think_end != -1:
        text = text[think_end + len("</think>"):].strip()

    if text.startswith("/no_think"):
        text = text.split("\n", 1)[-1].strip()

    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)
