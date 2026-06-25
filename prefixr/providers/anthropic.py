"""Anthropic provider adapter."""

from __future__ import annotations

import copy
from typing import Any

from prefixr.context import estimate_tokens, message_text
from prefixr.providers.base import CacheEventData, ProviderAdapter
from prefixr.scheduler import DEFAULT_PRICING, ProviderPricing

# Model-specific pricing overrides (USD per million input tokens)
ANTHROPIC_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-6": (15.0, 1.50),
    "claude-sonnet-4-5": (3.0, 0.30),
    "claude-haiku-4-5": (0.80, 0.08),
}


class AnthropicAdapter(ProviderAdapter):
    @property
    def provider_name(self) -> str:
        return "anthropic"

    def preprocess(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(payload)
        messages = result.get("messages", [])

        # Inject cache_control on stable anchor messages
        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            if role == "system" or (role == "user" and i == 0):
                content = msg.get("content")
                if isinstance(content, str):
                    msg["content"] = [
                        {
                            "type": "text",
                            "text": content,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            block["cache_control"] = {"type": "ephemeral"}

        result["messages"] = messages
        return result

    def postprocess(self, response: dict[str, Any]) -> CacheEventData:
        usage = response.get("usage", {})
        tokens_input = usage.get("input_tokens", 0)
        tokens_cached = usage.get("cache_read_input_tokens", 0)
        cache_creation = usage.get("cache_creation_input_tokens", 0)
        tokens_uncached = tokens_input - tokens_cached

        is_hit = tokens_cached > 0
        is_miss = cache_creation > 0 or (tokens_input > 0 and tokens_cached == 0)

        miss_reason = ""
        if is_miss and not is_hit:
            miss_reason = "no_cache_read"
        elif cache_creation > 0:
            miss_reason = "cache_creation"

        return CacheEventData(
            tokens_input=tokens_input,
            tokens_cached=tokens_cached,
            tokens_uncached=max(0, tokens_uncached),
            cache_creation_tokens=cache_creation,
            is_cache_hit=is_hit,
            is_cache_miss=is_miss,
            miss_reason=miss_reason,
        )

    def get_pricing(self, model: str) -> ProviderPricing:
        if model in ANTHROPIC_MODEL_PRICING:
            uncached, cached = ANTHROPIC_MODEL_PRICING[model]
            return ProviderPricing(
                provider="anthropic",
                price_uncached_per_mtok=uncached,
                price_cached_per_mtok=cached,
            )
        return DEFAULT_PRICING["anthropic"]

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
        system = payload.get("system", "")
        if system:
            total += estimate_tokens(system if isinstance(system, str) else str(system))
        return total

    def detect_provider(self, payload: dict[str, Any]) -> bool:
        model = payload.get("model", "")
        return model.startswith("claude-")
