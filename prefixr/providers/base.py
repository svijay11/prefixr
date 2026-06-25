"""Provider adapter base interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from prefixr.scheduler import ProviderPricing


@dataclass
class CacheEventData:
    tokens_input: int
    tokens_cached: int
    tokens_uncached: int
    cache_creation_tokens: int = 0
    is_cache_hit: bool = False
    is_cache_miss: bool = False
    miss_reason: str = ""


class ProviderAdapter(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    def preprocess(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Inject cache hints and restructuring."""
        ...

    @abstractmethod
    def postprocess(self, response: dict[str, Any]) -> CacheEventData:
        """Extract hit/miss data from provider response."""
        ...

    @abstractmethod
    def get_pricing(self, model: str) -> ProviderPricing:
        ...

    @abstractmethod
    def extract_messages(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def set_messages(self, payload: dict[str, Any], messages: list[dict[str, Any]]) -> dict[str, Any]:
        ...

    @abstractmethod
    def estimate_input_tokens(self, payload: dict[str, Any]) -> int:
        ...

    def detect_provider(self, payload: dict[str, Any]) -> bool:
        return True
