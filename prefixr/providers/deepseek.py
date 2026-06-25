"""DeepSeek provider adapter."""

from __future__ import annotations

import copy
from typing import Any

from prefixr.context import estimate_tokens, message_text
from prefixr.providers.base import CacheEventData, ProviderAdapter
from prefixr.scheduler import DEFAULT_PRICING, ProviderPricing


class DeepSeekAdapter(ProviderAdapter):
    @property
    def provider_name(self) -> str:
        return "deepseek"

    def preprocess(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(payload)
        messages = result.get("messages", [])

        # Stable prefix ordering: system first
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]
        result["messages"] = system_msgs + other_msgs
        return result

    def postprocess(self, response: dict[str, Any]) -> CacheEventData:
        usage = response.get("usage", {})
        tokens_input = usage.get("prompt_tokens", 0)

        # DeepSeek may return cached tokens in prompt_cache_hit_tokens
        tokens_cached = usage.get("prompt_cache_hit_tokens", 0)
        if tokens_cached == 0:
            details = usage.get("prompt_tokens_details", {}) or {}
            tokens_cached = details.get("cached_tokens", 0)

        # Heuristic fallback if provider doesn't return cache details
        if tokens_cached == 0 and tokens_input > 0:
            # Estimate ~40% hit rate for repeated prefixes
            tokens_cached = int(tokens_input * 0.4)

        tokens_uncached = tokens_input - tokens_cached
        is_hit = tokens_cached > 0

        return CacheEventData(
            tokens_input=tokens_input,
            tokens_cached=tokens_cached,
            tokens_uncached=max(0, tokens_uncached),
            is_cache_hit=is_hit,
            is_cache_miss=not is_hit and tokens_input > 0,
            miss_reason="heuristic_estimate" if tokens_cached > 0 else "no_cache_data",
        )

    def get_pricing(self, model: str) -> ProviderPricing:
        return DEFAULT_PRICING["deepseek"]

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
        return model.startswith("deepseek-")
