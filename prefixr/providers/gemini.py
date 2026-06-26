"""Google Gemini provider adapter (OpenAI-compatible endpoint)."""

from __future__ import annotations

import copy
from typing import Any

from prefixr.context import estimate_tokens, message_text
from prefixr.providers.base import CacheEventData, ProviderAdapter
from prefixr.scheduler import DEFAULT_PRICING, ProviderPricing

# USD per million input tokens (uncached, cached)
GEMINI_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 0.075),
    "gemini-2.5-pro": (1.25, 0.3125),
    "gemini-2.0-flash": (0.10, 0.025),
    "gemini-1.5-flash": (0.075, 0.01875),
    "gemini-1.5-pro": (1.25, 0.3125),
}

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


class GeminiAdapter(ProviderAdapter):
    @property
    def provider_name(self) -> str:
        return "gemini"

    def preprocess(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(payload)
        messages = result.get("messages", [])

        # Stable prefix: system messages first (maximizes implicit cache on 2.5+)
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]
        result["messages"] = system_msgs + other_msgs
        return result

    def postprocess(self, response: dict[str, Any]) -> CacheEventData:
        usage = response.get("usage", {})
        tokens_input = usage.get("prompt_tokens", 0)

        details = usage.get("prompt_tokens_details", {}) or {}
        tokens_cached = details.get("cached_tokens", 0)

        # Native Gemini usage_metadata (OpenAI compat may nest this)
        meta = response.get("usage_metadata", {}) or usage.get("usage_metadata", {})
        if tokens_cached == 0 and meta:
            tokens_cached = meta.get("cached_content_token_count", 0)

        # Gemini 2.5+ implicit cache — estimate if no explicit cache data
        if tokens_cached == 0 and tokens_input > 0:
            tokens_cached = int(tokens_input * 0.25)

        tokens_uncached = max(0, tokens_input - tokens_cached)
        is_hit = tokens_cached > 0

        return CacheEventData(
            tokens_input=tokens_input,
            tokens_cached=tokens_cached,
            tokens_uncached=tokens_uncached,
            is_cache_hit=is_hit,
            is_cache_miss=tokens_input > 0 and tokens_cached == 0,
            miss_reason="heuristic_estimate" if is_hit and not details.get("cached_tokens") else (
                "no_cached_tokens" if not is_hit else ""
            ),
        )

    def get_pricing(self, model: str) -> ProviderPricing:
        for prefix, (uncached, cached) in GEMINI_MODEL_PRICING.items():
            if model.startswith(prefix) or prefix in model:
                return ProviderPricing(
                    provider="gemini",
                    price_uncached_per_mtok=uncached,
                    price_cached_per_mtok=cached,
                )
        return DEFAULT_PRICING["gemini"]

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
        model = payload.get("model", "").lower()
        return model.startswith("gemini-") or model.startswith("models/gemini")

    @staticmethod
    def chat_completions_url() -> str:
        return f"{GEMINI_BASE_URL}/chat/completions"
