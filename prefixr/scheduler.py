"""Cost optimization core — the math lives here."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

# Anthropic checkpoints at 1024, 2048, 4096 tokens
ANTHROPIC_CHECKPOINTS = (1024, 2048, 4096)
# Approximate chars-per-token for padding estimation
CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class ProviderPricing:
    """Per-million-token input pricing for a provider/model."""

    price_uncached_per_mtok: float
    price_cached_per_mtok: float
    provider: str

    @property
    def price_uncached(self) -> float:
        return self.price_uncached_per_mtok / 1_000_000

    @property
    def price_cached(self) -> float:
        return self.price_cached_per_mtok / 1_000_000


# Default pricing (USD per million input tokens). Cached rates reflect provider discounts.
DEFAULT_PRICING: dict[str, ProviderPricing] = {
  "anthropic": ProviderPricing(
      provider="anthropic",
      price_uncached_per_mtok=3.00,
      price_cached_per_mtok=0.30,  # ~10% of base
  ),
  "openai": ProviderPricing(
      provider="openai",
      price_uncached_per_mtok=2.50,
      price_cached_per_mtok=1.25,  # ~50% of base
  ),
  "deepseek": ProviderPricing(
      provider="deepseek",
      price_uncached_per_mtok=0.27,
      price_cached_per_mtok=0.07,  # ~26% of base
  ),
  "gemini": ProviderPricing(
      provider="gemini",
      price_uncached_per_mtok=0.30,
      price_cached_per_mtok=0.075,  # ~25% with context caching
  ),
}

# Cheap summarizer models (USD per million input tokens)
SUMMARIZER_PRICING: dict[str, ProviderPricing] = {
  "claude-haiku-4-5": ProviderPricing(
      provider="anthropic",
      price_uncached_per_mtok=0.80,
      price_cached_per_mtok=0.08,
  ),
  "gpt-4o-mini": ProviderPricing(
      provider="openai",
      price_uncached_per_mtok=0.15,
      price_cached_per_mtok=0.075,
  ),
}


@dataclass
class TurnCostEstimate:
    tokens_total: int
    tokens_cached: int
    tokens_uncached: int
    cache_hit_rate: float
    cost_usd: float


@dataclass
class OptimizationDecision:
    action: Literal["preserve", "summarize", "pad", "anchor_split"]
    expected_savings_usd: float
    horizon_turns: int
    reasoning: str


def estimate_turn_cost(
    tokens_total: int,
    tokens_cached: int,
    pricing: ProviderPricing,
) -> TurnCostEstimate:
    """Compute cost for a single turn given token counts and pricing."""
    tokens_cached = max(0, min(tokens_cached, tokens_total))
    tokens_uncached = tokens_total - tokens_cached
    cache_hit_rate = tokens_cached / tokens_total if tokens_total > 0 else 0.0
    cost_usd = (
        tokens_uncached * pricing.price_uncached
        + tokens_cached * pricing.price_cached
    )
    return TurnCostEstimate(
        tokens_total=tokens_total,
        tokens_cached=tokens_cached,
        tokens_uncached=tokens_uncached,
        cache_hit_rate=cache_hit_rate,
        cost_usd=cost_usd,
    )


def cost_preserve(
    tokens_total: int,
    rolling_hit_rate: float,
    pricing: ProviderPricing,
    horizon_turns: int,
    *,
    context_growth_per_turn: float = 0.05,
) -> float:
    """
    Cost of keeping raw history for the next N turns, assuming current cache
    hit rate holds. Context grows slightly each turn (new messages).
    """
    total = 0.0
    hit_rate = max(0.0, min(1.0, rolling_hit_rate))
    tokens = float(tokens_total)

    for turn in range(horizon_turns):
        tokens_cached = int(tokens * hit_rate)
        estimate = estimate_turn_cost(int(tokens), tokens_cached, pricing)
        total += estimate.cost_usd
        tokens *= 1.0 + context_growth_per_turn

    return total


def cost_summarize(
    tokens_total: int,
    volatile_tokens: int,
    rolling_hit_rate: float,
    pricing: ProviderPricing,
    summarizer_pricing: ProviderPricing,
    horizon_turns: int,
    *,
    summary_output_tokens: int = 512,
    post_summary_hit_rate: float = 0.85,
    context_growth_per_turn: float = 0.03,
) -> float:
    """
    Cost of summarizing now: one full uncached summarizer call plus projected
    savings from a cleaner context over the next N turns.
    """
    # Summarizer input: volatile tail + small overhead
    summarizer_input = volatile_tokens + 256
    summarize_call_cost = (
        summarizer_input * summarizer_pricing.price_uncached
        + summary_output_tokens * summarizer_pricing.price_uncached
    )

    # After summarization: context shrinks, hit rate improves
    reduced_tokens = tokens_total - volatile_tokens + summary_output_tokens
    reduced_tokens = max(reduced_tokens, summary_output_tokens)

    future_cost = cost_preserve(
        reduced_tokens,
        post_summary_hit_rate,
        pricing,
        horizon_turns,
        context_growth_per_turn=context_growth_per_turn,
    )

    # One cache-bust turn on the main model (full uncached payload before summary applies)
    bust_turn = estimate_turn_cost(tokens_total, 0, pricing)

    return summarize_call_cost + bust_turn.cost_usd + future_cost


def padding_tokens_needed(stable_block_tokens: int) -> int:
    """Tokens needed to push a stable block past the next Anthropic checkpoint."""
    for checkpoint in ANTHROPIC_CHECKPOINTS:
        if stable_block_tokens < checkpoint:
            return checkpoint - stable_block_tokens
    return 0


def cost_pad(
    tokens_total: int,
    stable_block_tokens: int,
    rolling_hit_rate: float,
    pricing: ProviderPricing,
    horizon_turns: int,
) -> tuple[float, int]:
    """
    Cost if we inject padding to align stable block to next checkpoint.
    Returns (total_cost, padding_tokens).
    """
    pad_tokens = padding_tokens_needed(stable_block_tokens)
    if pad_tokens == 0:
        return float("inf"), 0

    # Padding is one-time uncached cost, then improves hit rate
    improved_hit_rate = min(1.0, rolling_hit_rate + 0.15)
    padded_total = tokens_total + pad_tokens

    pad_cost = pad_tokens * pricing.price_uncached
    future = cost_preserve(
        padded_total,
        improved_hit_rate,
        pricing,
        horizon_turns,
    )
    return pad_cost + future, pad_tokens


def cost_anchor_split(
    tokens_total: int,
    stable_tokens: int,
    volatile_tokens: int,
    rolling_hit_rate: float,
    pricing: ProviderPricing,
    horizon_turns: int,
) -> float:
    """
    Cost if we restructure so stable blocks are frozen anchors.
    Anchor splitting typically recovers ~20-40% hit rate without busting cache.
    """
    if stable_tokens <= 0:
        return float("inf")

    stable_ratio = stable_tokens / tokens_total if tokens_total > 0 else 0.0
    recovered_hit_rate = min(1.0, max(rolling_hit_rate, stable_ratio * 0.95))

    return cost_preserve(
        tokens_total,
        recovered_hit_rate,
        pricing,
        horizon_turns,
        context_growth_per_turn=0.04,
    )


class CacheOptimizer:
    """Evaluates preserve vs summarize vs pad vs anchor_split on every turn."""

    def __init__(
        self,
        pricing: ProviderPricing,
        horizon_turns: int = 5,
        summarizer_model: str = "claude-haiku-4-5",
        padding_enabled: bool = True,
    ):
        self.pricing = pricing
        self.horizon_turns = horizon_turns
        self.summarizer_model = summarizer_model
        self.padding_enabled = padding_enabled
        self.summarizer_pricing = SUMMARIZER_PRICING.get(
            summarizer_model,
            SUMMARIZER_PRICING["claude-haiku-4-5"],
        )

    def decide(
        self,
        tokens_total: int,
        tokens_cached: int,
        rolling_hit_rate: float,
        *,
        stable_tokens: int = 0,
        volatile_tokens: int = 0,
        stable_block_tokens: int = 0,
    ) -> OptimizationDecision:
        """
        Evaluate all strategies and return the cheapest action.
        Strategies are evaluated in order: anchor_split, pad, summarize, preserve.
        """
        preserve_cost = cost_preserve(
            tokens_total,
            rolling_hit_rate,
            self.pricing,
            self.horizon_turns,
        )

        best_action: Literal["preserve", "summarize", "pad", "anchor_split"] = "preserve"
        best_cost = preserve_cost
        reasoning = (
            f"Preserve cache: {rolling_hit_rate:.1%} hit rate over "
            f"{self.horizon_turns} turns costs ${preserve_cost:.6f}"
        )

        # 1. Anchor splitting
        if stable_tokens > 0 and volatile_tokens > 0:
            anchor_cost = cost_anchor_split(
                tokens_total,
                stable_tokens,
                volatile_tokens,
                rolling_hit_rate,
                self.pricing,
                self.horizon_turns,
            )
            if anchor_cost < best_cost:
                savings = preserve_cost - anchor_cost
                best_cost = anchor_cost
                best_action = "anchor_split"
                stable_ratio = stable_tokens / tokens_total if tokens_total > 0 else 0
                reasoning = (
                    f"Anchor split: freeze {stable_tokens} stable tokens "
                    f"({stable_ratio:.0%} of context), projected cost "
                    f"${anchor_cost:.6f} vs preserve ${preserve_cost:.6f}, "
                    f"saves ${savings:.6f} over {self.horizon_turns} turns"
                )

        # 2. Padding injection
        if self.padding_enabled and stable_block_tokens > 0:
            pad_cost, pad_tokens = cost_pad(
                tokens_total,
                stable_block_tokens,
                rolling_hit_rate,
                self.pricing,
                self.horizon_turns,
            )
            if pad_cost < best_cost:
                savings = preserve_cost - pad_cost
                best_cost = pad_cost
                best_action = "pad"
                next_cp = stable_block_tokens + pad_tokens
                reasoning = (
                    f"Pad injection: add {pad_tokens} tokens to reach "
                    f"{next_cp}-token checkpoint, projected cost "
                    f"${pad_cost:.6f} vs preserve ${preserve_cost:.6f}, "
                    f"saves ${savings:.6f} over {self.horizon_turns} turns"
                )

        # 3. Summarization (last resort before preserve)
        if volatile_tokens > 0:
            summarize_cost = cost_summarize(
                tokens_total,
                volatile_tokens,
                rolling_hit_rate,
                self.pricing,
                self.summarizer_pricing,
                self.horizon_turns,
            )
            if summarize_cost < best_cost:
                savings = preserve_cost - summarize_cost
                best_cost = summarize_cost
                best_action = "summarize"
                reasoning = (
                    f"Summarize: compress {volatile_tokens} volatile tokens "
                    f"via {self.summarizer_model}, projected cost "
                    f"${summarize_cost:.6f} vs preserve ${preserve_cost:.6f}, "
                    f"saves ${savings:.6f} over {self.horizon_turns} turns"
                )

        expected_savings = preserve_cost - best_cost

        if best_action == "preserve":
            reasoning = (
                f"Preserve: no strategy beats current {rolling_hit_rate:.1%} "
                f"hit rate; projected ${preserve_cost:.6f} over "
                f"{self.horizon_turns} turns"
            )

        return OptimizationDecision(
            action=best_action,
            expected_savings_usd=max(0.0, expected_savings),
            horizon_turns=self.horizon_turns,
            reasoning=reasoning,
        )

    def estimate_current_turn(
        self,
        tokens_total: int,
        tokens_cached: int,
    ) -> TurnCostEstimate:
        return estimate_turn_cost(tokens_total, tokens_cached, self.pricing)

    def baseline_cost_no_prefixr(
        self,
        tokens_total: int,
        horizon_turns: int | None = None,
    ) -> float:
        """Cost if every token were uncached (no optimization)."""
        n = horizon_turns or self.horizon_turns
        tokens = float(tokens_total)
        total = 0.0
        for _ in range(n):
            total += tokens * self.pricing.price_uncached
            tokens *= 1.05
        return total
