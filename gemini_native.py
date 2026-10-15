"""Minimal native Gemini adapter for Agent Manager's API-key egress route.

The managed gateway stores the upstream Gemini credential and expects each agent's
binding key in the ``API-Key`` header. Gemini's native API uses ``generateContent``;
this module deliberately contains no credential logging or persistence.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx


class GeminiNativeError(RuntimeError):
    """Raised when a native Gemini request cannot produce visible text."""


def uses_managed_native_gemini(provider: str) -> bool:
    """Return whether the platform egress binding requires the native protocol."""
    return (
        provider.strip().lower() == "gemini"
        and os.getenv("LLM_PROVIDER_AUTH_STYLE", "").strip().lower() == "api-key"
    )


def generate_content(
    *,
    base_url: str,
    api_key: str | None,
    model: str,
    system_instruction: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> tuple[str, int, int]:
    """Call Gemini ``generateContent`` through the configured egress route.

    Returns visible response text together with prompt and completion token counts.
    The gateway binding key is sent only in the API-Key header and is never returned
    or included in exceptions.
    """
    if not api_key:
        raise GeminiNativeError("Gemini gateway key is unavailable")

    contents = [_to_gemini_content(message) for message in messages]
    if not contents:
        raise GeminiNativeError("Gemini request has no user content")

    endpoint = (
        f"{base_url.rstrip('/')}/v1beta/models/"
        f"{quote(model, safe='._-')}:generateContent"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    try:
        response = httpx.post(
            endpoint,
            json=payload,
            headers={"Content-Type": "application/json", "API-Key": api_key},
            timeout=45.0,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise GeminiNativeError("Gemini native request unavailable") from exc

    text = _response_text(data)
    usage = data.get("usageMetadata") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        usage = {}
    return (
        text,
        _as_nonnegative_int(usage.get("promptTokenCount")),
        _as_nonnegative_int(usage.get("candidatesTokenCount")),
    )


def _to_gemini_content(message: dict[str, str]) -> dict[str, Any]:
    role = "model" if message.get("role") == "assistant" else "user"
    return {"role": role, "parts": [{"text": str(message.get("content", ""))}]}


def _response_text(data: Any) -> str:
    if not isinstance(data, dict):
        raise GeminiNativeError("Gemini returned an invalid response")
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise GeminiNativeError("Gemini returned no candidate")
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise GeminiNativeError("Gemini returned no text content")
    text = "".join(
        str(part.get("text", ""))
        for part in parts
        if isinstance(part, dict) and part.get("text") and not part.get("thought", False)
    ).strip()
    if not text:
        raise GeminiNativeError("Gemini returned no visible text")
    return text


def _as_nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
