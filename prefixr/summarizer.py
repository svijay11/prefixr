"""Pluggable summarizer — calls cheap model when pruning wins."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx

from prefixr.context import message_text


class Summarizer(ABC):
    @abstractmethod
    async def summarize(
        self,
        messages: list[dict[str, Any]],
        volatile_indices: list[int],
    ) -> str:
        ...


class AnthropicSummarizer(Summarizer):
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com"

    async def summarize(
        self,
        messages: list[dict[str, Any]],
        volatile_indices: list[int],
    ) -> str:
        volatile_msgs = [messages[i] for i in volatile_indices if i < len(messages)]
        content = "\n\n".join(
            f"[{m.get('role', 'unknown')}]: {message_text(m.get('content', ''))}"
            for m in volatile_msgs
        )
        prompt = (
            "Summarize the following conversation history concisely. "
            "Preserve key facts, decisions, and context needed for continuation. "
            "Output only the summary, no preamble.\n\n"
            f"{content}"
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            blocks = data.get("content", [])
            return "".join(
                b.get("text", "") for b in blocks if b.get("type") == "text"
            )


class OpenAISummarizer(Summarizer):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com"

    async def summarize(
        self,
        messages: list[dict[str, Any]],
        volatile_indices: list[int],
    ) -> str:
        volatile_msgs = [messages[i] for i in volatile_indices if i < len(messages)]
        content = "\n\n".join(
            f"[{m.get('role', 'unknown')}]: {message_text(m.get('content', ''))}"
            for m in volatile_msgs
        )
        prompt = (
            "Summarize the following conversation history concisely. "
            "Preserve key facts, decisions, and context needed for continuation. "
            "Output only the summary, no preamble.\n\n"
            f"{content}"
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


def create_summarizer(
    provider: str,
    api_key: str,
    model: str,
) -> Summarizer:
    if provider == "openai":
        return OpenAISummarizer(api_key, model)
    return AnthropicSummarizer(api_key, model)


def apply_summary(
    messages: list[dict[str, Any]],
    summary: str,
    volatile_indices: list[int],
) -> list[dict[str, Any]]:
    """Replace volatile messages with a frozen summary anchor."""
    stable = [m for i, m in enumerate(messages) if i not in volatile_indices]
    summary_msg = {
        "role": "user",
        "content": f"[Context summary — prior conversation compressed]\n{summary}",
    }
    return stable + [summary_msg]
