from __future__ import annotations

from typing import Any

from prefixr.providers.anthropic import AnthropicAdapter
from prefixr.providers.base import CacheEventData, ProviderAdapter
from prefixr.providers.deepseek import DeepSeekAdapter
from prefixr.providers.openai import OpenAIAdapter

__all__ = [
    "AnthropicAdapter",
    "OpenAIAdapter",
    "DeepSeekAdapter",
    "ProviderAdapter",
    "CacheEventData",
]


def get_adapter(provider: str) -> ProviderAdapter:
    adapters = {
        "anthropic": AnthropicAdapter,
        "openai": OpenAIAdapter,
        "deepseek": DeepSeekAdapter,
    }
    cls = adapters.get(provider)
    if cls is None:
        raise ValueError(f"Unknown provider: {provider}")
    return cls()


def detect_adapter(payload: dict[str, Any], active_providers: list[str] | None = None) -> ProviderAdapter:
    candidates = []
    for name in active_providers or ["anthropic", "openai", "deepseek"]:
        adapter = get_adapter(name)
        if adapter.detect_provider(payload):
            candidates.append(adapter)
    if not candidates:
        return OpenAIAdapter()
    return candidates[0]
