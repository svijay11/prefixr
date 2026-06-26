"""OpenAI provider adapter."""

from __future__ import annotations

import copy
from typing import Any

from prefixr.context import estimate_tokens, message_text
from prefixr.providers.base import CacheEventData, ProviderAdapter
from prefixr.scheduler import DEFAULT_PRICING, ProviderPricing

OPENAI_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 1.25),
    "gpt-4o-mini": (0.15, 0.075),
    "gpt-4.1": (2.00, 1.00),
    "o1": (15.0, 7.50),
    "o3-mini": (1.10, 0.55),
}


class OpenAIAdapter(ProviderAdapter):
    def __init__(self):
        self._last_cached_tokens: dict[str, int] = {}

    @property
    def provider_name(self) -> str:
        return "openai"

    def preprocess(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(payload)
        messages = result.get("messages", [])

        # System message always first, never modified — maximize prefix stability
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]
        result["messages"] = system_msgs + other_msgs
        return result

    def postprocess(self, response: dict[str, Any]) -> CacheEventData:
        usage = response.get("usage", {})
        tokens_input = usage.get("prompt_tokens", 0)
        details = usage.get("prompt_tokens_details", {}) or {}
        tokens_cached = details.get("cached_tokens", 0)
        tokens_uncached = tokens_input - tokens_cached

        is_hit = tokens_cached > 0
        is_miss = tokens_input > 0 and tokens_cached == 0

        return CacheEventData(
            tokens_input=tokens_input,
            tokens_cached=tokens_cached,
            tokens_uncached=max(0, tokens_uncached),
            is_cache_hit=is_hit,
            is_cache_miss=is_miss,
            miss_reason="no_cached_tokens" if is_miss else "",
        )

    def detect_cache_bust(
        self, session_id: str, tokens_cached: int
    ) -> bool:
        prev = self._last_cached_tokens.get(session_id, 0)
        self._last_cached_tokens[session_id] = tokens_cached
        return prev > 0 and tokens_cached < prev * 0.5

    def get_pricing(self, model: str) -> ProviderPricing:
        if model in OPENAI_MODEL_PRICING:
            uncached, cached = OPENAI_MODEL_PRICING[model]
            return ProviderPricing(
                provider="openai",
                price_uncached_per_mtok=uncached,
                price_cached_per_mtok=cached,
            )
        return DEFAULT_PRICING["openai"]

    def extract_messages(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return payload.get("messages", [])

    def set_messages(
        self, payload: dict[str, Any], messages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        result = copy.deepcopy(payload)
        result["messages"] = messages
        return result

    def estimate_input_tokens(self, payload: dict[str, Any]) -> int:
        total = 0
        for msg in payload.get("messages", []):
            total += estimate_tokens(message_text(msg.get("content", "")))
        return total

    def detect_provider(self, payload: dict[str, Any]) -> bool:
        model = payload.get("model", "")
        return not model.startswith("claude-") and not model.startswith("deepseek-") and not model.startswith("gemini-")
