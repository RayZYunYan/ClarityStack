"""Minimal Anthropic Messages API client for automation flows."""

from __future__ import annotations

import os
from typing import Any

import requests

ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5"


def get_anthropic_api_key() -> str | None:
    """Return the configured Anthropic API key, if present."""
    return (
        os.getenv("ANTHROPIC_API_KEY", "").strip()
        or os.getenv("CLAUDE_API_KEY", "").strip()
        or None
    )


def get_anthropic_model() -> str:
    """Return the configured Anthropic model name."""
    return os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def call_anthropic(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    max_tokens: int = 1800,
    timeout: int = 60,
) -> str:
    """Submit a single-turn prompt to the Anthropic Messages API."""
    api_key = get_anthropic_api_key()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured.")

    payload: dict[str, Any] = {
        "model": model or get_anthropic_model(),
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    response = requests.post(
        ANTHROPIC_ENDPOINT,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    content_blocks = body.get("content", [])
    text_blocks = [
        block.get("text", "").strip()
        for block in content_blocks
        if block.get("type") == "text" and block.get("text")
    ]
    if not text_blocks:
        raise RuntimeError("Anthropic returned no text content.")
    return "\n".join(text_blocks).strip()
