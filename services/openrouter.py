"""
OpenRouter LLM client for the AI assistant.

Uses open-weights models (default: Qwen3 8B) via the OpenRouter API,
which is OpenAI-compatible. Supports structured JSON output.
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
    json_mode: bool = True,
) -> dict:
    """
    Send a chat completion request to OpenRouter.

    Returns the parsed JSON content if json_mode=True, else raw text in {"text": ...}.
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

    if json_mode:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{OPENROUTER_BASE}/chat/completions",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()

    data = resp.json()
    choice = data["choices"][0]
    message = choice["message"]
    content = message.get("content") or ""
    model_used = data.get("model", model)

    logger.info("OpenRouter raw message keys: %s", list(message.keys()))

    # Qwen3 may return content=None when thinking is enabled
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

    if json_mode:
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

    # Strip <think>...</think> blocks (Qwen3 default behavior)
    think_end = text.find("</think>")
    if think_end != -1:
        text = text[think_end + len("</think>"):].strip()

    # Strip /no_think prefix
    if text.startswith("/no_think"):
        text = text.split("\n", 1)[-1].strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # drop opening fence line
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Find the first { and last } to extract JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)
