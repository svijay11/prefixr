"""OpenRouter provider adapter (OpenAI-compatible, vendor/model IDs)."""

from __future__ import annotations

import copy
from typing import Any

from prefixr.context import estimate_tokens, message_text
from prefixr.providers.anthropic import ANTHROPIC_MODEL_PRICING
from prefixr.providers.base import CacheEventData, ProviderAdapter
from prefixr.providers.gemini import GEMINI_MODEL_PRICING
from prefixr.providers.openai import OPENAI_MODEL_PRICING
from prefixr.scheduler import DEFAULT_PRICING, ProviderPricing

OPENROUTER_BASE_URL = "https://openrouter.ai/api"


def _model_suffix(model: str) -> str:
    return model.split("/", 1)[-1] if "/" in model else model


def _lookup_pricing(suffix: str, table: dict[str, tuple[float, float]]) -> tuple[float, float] | None:
    if suffix in table:
        return table[suffix]
    for key, prices in table.items():
        if suffix.startswith(key) or key in suffix:
            return prices
    return None


class OpenRouterAdapter(ProviderAdapter):
    def __init__(self):
        self._last_cached_tokens: dict[str, int] = {}

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def preprocess(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(payload)
        messages = result.get("messages", [])

        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]
        result["messages"] = system_msgs + other_msgs

        # Anthropic models on OpenRouter honor cache_control breakpoints
        model = result.get("model", "")
        if model.startswith("anthropic/"):
            for i, msg in enumerate(result["messages"]):
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

        return result

    def postprocess(self, response: dict[str, Any]) -> CacheEventData:
        usage = response.get("usage", {}) or {}
        tokens_input = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        details = usage.get("prompt_tokens_details", {}) or {}
        tokens_cached = (
            details.get("cached_tokens", 0)
            or usage.get("cache_read_input_tokens", 0)
            or usage.get("prompt_cache_hit_tokens", 0)
        )
        cache_creation = usage.get("cache_creation_input_tokens", 0)
        tokens_uncached = tokens_input - tokens_cached

        is_hit = tokens_cached > 0
        is_miss = tokens_input > 0 and tokens_cached == 0

        return CacheEventData(
            tokens_input=tokens_input,
            tokens_cached=tokens_cached,
            tokens_uncached=max(0, tokens_uncached),
            cache_creation_tokens=cache_creation,
            is_cache_hit=is_hit,
            is_cache_miss=is_miss,
            miss_reason="no_cached_tokens" if is_miss else "",
        )

    def detect_cache_bust(self, session_id: str, tokens_cached: int) -> bool:
        prev = self._last_cached_tokens.get(session_id, 0)
        self._last_cached_tokens[session_id] = tokens_cached
        return prev > 0 and tokens_cached < prev * 0.5

    def get_pricing(self, model: str) -> ProviderPricing:
        vendor = model.split("/", 1)[0] if "/" in model else ""
        suffix = _model_suffix(model)

        table = None
        fallback_key = "openrouter"
        if vendor == "openai":
            table = OPENAI_MODEL_PRICING
            fallback_key = "openai"
        elif vendor == "anthropic":
            table = ANTHROPIC_MODEL_PRICING
            fallback_key = "anthropic"
        elif vendor in ("google", "google-ai-studio"):
            table = GEMINI_MODEL_PRICING
            fallback_key = "gemini"
        elif vendor == "deepseek":
            fallback_key = "deepseek"

        if table:
            found = _lookup_pricing(suffix, table)
            if found:
                uncached, cached = found
                return ProviderPricing(
                    provider="openrouter",
                    price_uncached_per_mtok=uncached,
                    price_cached_per_mtok=cached,
                )

        return DEFAULT_PRICING[fallback_key]

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
        return "/" in model
