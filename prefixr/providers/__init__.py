from __future__ import annotations

from typing import Any

from prefixr.providers.gemini import GeminiAdapter
from prefixr.providers.anthropic import AnthropicAdapter
from prefixr.providers.base import CacheEventData, ProviderAdapter
from prefixr.providers.deepseek import DeepSeekAdapter
from prefixr.providers.openai import OpenAIAdapter

__all__ = [
    "AnthropicAdapter",
    "OpenAIAdapter",
    "DeepSeekAdapter",
    "GeminiAdapter",
    "ProviderAdapter",
    "CacheEventData",
]


def get_adapter(provider: str) -> ProviderAdapter:
    adapters = {
        "anthropic": AnthropicAdapter,
        "openai": OpenAIAdapter,
        "deepseek": DeepSeekAdapter,
        "gemini": GeminiAdapter,
    }
    cls = adapters.get(provider)
    if cls is None:
        raise ValueError(f"Unknown provider: {provider}")
    return cls()


def detect_adapter(payload: dict[str, Any], active_providers: list[str] | None = None) -> ProviderAdapter:
    # Order matters: specific detectors before openai fallback
    order = active_providers or ["anthropic", "gemini", "deepseek", "openai"]
    candidates = []
    for name in order:
        adapter = get_adapter(name)
        if adapter.detect_provider(payload):
            candidates.append(adapter)
    if not candidates:
        return OpenAIAdapter()
    return candidates[0]
