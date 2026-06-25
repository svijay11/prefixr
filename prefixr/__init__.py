"""Prefixr — local-first, provider cache-aware context scheduler for LLM API calls."""

from prefixr.client import PrefixrClient
from prefixr.scheduler import (
    CacheOptimizer,
    OptimizationDecision,
    ProviderPricing,
    TurnCostEstimate,
)

__version__ = "0.1.0"
__all__ = [
    "PrefixrClient",
    "CacheOptimizer",
    "OptimizationDecision",
    "ProviderPricing",
    "TurnCostEstimate",
    "__version__",
]
