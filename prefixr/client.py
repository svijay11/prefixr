"""Python SDK — drop-in Anthropic/OpenAI replacement."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class SessionStats:
    session_id: str
    hit_rate: float
    tokens_input: int
    tokens_cached: int
    tokens_uncached: int
    cost_usd: float
    cost_saved_usd: float
    turn_count: int


class PrefixrClient:
    def __init__(
        self,
        provider: str = "openai",
        base_url: str = "http://localhost:4242",
        session_id: str | None = None,
        api_key: str | None = None,
    ):
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id or str(uuid.uuid4())
        self.api_key = api_key
        self._client = httpx.Client(timeout=120.0)

        if provider == "anthropic":
            self.messages = _AnthropicMessages(self)
        else:
            self.chat = _OpenAIChat(self)

    def _headers(self) -> dict[str, str]:
        headers = {"X-Prefixr-Session": self.session_id}
        if self.api_key:
            if self.provider == "anthropic":
                headers["x-api-key"] = self.api_key
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def session_stats(self) -> SessionStats:
        resp = self._client.get(
            f"{self.base_url}/sessions/{self.session_id}/stats",
        )
        resp.raise_for_status()
        data = resp.json()
        return SessionStats(
            session_id=data["session_id"],
            hit_rate=data["hit_rate"],
            tokens_input=data["tokens_input"],
            tokens_cached=data["tokens_cached"],
            tokens_uncached=data["tokens_uncached"],
            cost_usd=data["cost_usd"],
            cost_saved_usd=data["cost_saved_usd"],
            turn_count=data["turn_count"],
        )

    def close(self) -> None:
        self._client.close()


class _OpenAIChat:
    def __init__(self, client: PrefixrClient):
        self._client = client
        self.completions = self

    def create(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client._client.post(
            f"{self._client.base_url}/v1/chat/completions",
            headers=self._client._headers(),
            json=kwargs,
        )
        resp.raise_for_status()
        return resp.json()


class _AnthropicMessages:
    def __init__(self, client: PrefixrClient):
        self._client = client

    def create(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client._client.post(
            f"{self._client.base_url}/v1/messages",
            headers=self._client._headers(),
            json=kwargs,
        )
        resp.raise_for_status()
        return resp.json()
