"""Tests for cost optimization math."""

import pytest

from prefixr.scheduler import (
    ANTHROPIC_CHECKPOINTS,
    CacheOptimizer,
    ProviderPricing,
    cost_anchor_split,
    cost_pad,
    cost_preserve,
    cost_summarize,
    estimate_turn_cost,
    padding_tokens_needed,
)


@pytest.fixture
def anthropic_pricing():
    return ProviderPricing(
        provider="anthropic",
        price_uncached_per_mtok=3.0,
        price_cached_per_mtok=0.3,
    )


@pytest.fixture
def openai_pricing():
    return ProviderPricing(
        provider="openai",
        price_uncached_per_mtok=2.5,
        price_cached_per_mtok=1.25,
    )


class TestEstimateTurnCost:
    def test_all_uncached(self, anthropic_pricing):
        est = estimate_turn_cost(10000, 0, anthropic_pricing)
        assert est.tokens_uncached == 10000
        assert est.cache_hit_rate == 0.0
        assert est.cost_usd == pytest.approx(10000 * 3.0 / 1_000_000)

    def test_all_cached(self, anthropic_pricing):
        est = estimate_turn_cost(10000, 10000, anthropic_pricing)
        assert est.tokens_cached == 10000
        assert est.cache_hit_rate == 1.0
        assert est.cost_usd == pytest.approx(10000 * 0.3 / 1_000_000)

    def test_partial_cache(self, anthropic_pricing):
        est = estimate_turn_cost(10000, 8000, anthropic_pricing)
        assert est.tokens_uncached == 2000
        assert est.cache_hit_rate == 0.8


class TestCostPreserve:
    def test_zero_hit_rate(self, anthropic_pricing):
        cost = cost_preserve(10000, 0.0, anthropic_pricing, 5)
        assert cost > 0

    def test_high_hit_rate_cheaper(self, anthropic_pricing):
        low = cost_preserve(10000, 0.1, anthropic_pricing, 5)
        high = cost_preserve(10000, 0.9, anthropic_pricing, 5)
        assert high < low

    def test_horizon_scales_cost(self, anthropic_pricing):
        cost_5 = cost_preserve(10000, 0.5, anthropic_pricing, 5)
        cost_10 = cost_preserve(10000, 0.5, anthropic_pricing, 10)
        assert cost_10 > cost_5


class TestCostSummarize:
    def test_summarize_can_be_cheaper_at_low_hit_rate(self, anthropic_pricing):
        from prefixr.scheduler import SUMMARIZER_PRICING

        summarizer = SUMMARIZER_PRICING["claude-haiku-4-5"]
        preserve = cost_preserve(50000, 0.1, anthropic_pricing, 5)
        summarize = cost_summarize(
            50000, 30000, 0.1, anthropic_pricing, summarizer, 5
        )
        # At very low hit rate with large volatile tail, summarize should win
        assert summarize < preserve

    def test_summarize_more_expensive_at_high_hit_rate(self, anthropic_pricing):
        from prefixr.scheduler import SUMMARIZER_PRICING

        summarizer = SUMMARIZER_PRICING["claude-haiku-4-5"]
        preserve = cost_preserve(10000, 0.95, anthropic_pricing, 5)
        summarize = cost_summarize(
            10000, 2000, 0.95, anthropic_pricing, summarizer, 5
        )
        assert preserve < summarize


class TestPadding:
    def test_padding_tokens_needed(self):
        assert padding_tokens_needed(500) == 1024 - 500
        assert padding_tokens_needed(1024) == 2048 - 1024
        assert padding_tokens_needed(5000) == 0

    def test_cost_pad_improves_over_low_hit_rate(self, anthropic_pricing):
        cost, pad = cost_pad(10000, 900, 0.2, anthropic_pricing, 5)
        preserve = cost_preserve(10000, 0.2, anthropic_pricing, 5)
        assert pad > 0
        assert cost < preserve


class TestAnchorSplit:
    def test_anchor_split_recovers_hit_rate(self, anthropic_pricing):
        cost = cost_anchor_split(20000, 15000, 5000, 0.2, anthropic_pricing, 5)
        preserve = cost_preserve(20000, 0.2, anthropic_pricing, 5)
        assert cost < preserve


class TestCacheOptimizer:
    def test_decide_returns_valid_action(self, anthropic_pricing):
        opt = CacheOptimizer(anthropic_pricing, horizon_turns=5)
        decision = opt.decide(
            tokens_total=30000,
            tokens_cached=3000,
            rolling_hit_rate=0.1,
            stable_tokens=20000,
            volatile_tokens=10000,
            stable_block_tokens=800,
        )
        assert decision.action in ("preserve", "summarize", "pad", "anchor_split")
        assert decision.horizon_turns == 5
        assert len(decision.reasoning) > 0

    def test_preserve_when_hit_rate_high(self, anthropic_pricing):
        opt = CacheOptimizer(anthropic_pricing, horizon_turns=5, padding_enabled=False)
        decision = opt.decide(
            tokens_total=5000,
            tokens_cached=4750,
            rolling_hit_rate=0.95,
            stable_tokens=0,
            volatile_tokens=0,
            stable_block_tokens=0,
        )
        assert decision.action == "preserve"

    def test_openai_cached_cheaper_than_uncached(self, openai_pricing):
        uncached = estimate_turn_cost(10000, 0, openai_pricing)
        cached = estimate_turn_cost(10000, 10000, openai_pricing)
        assert cached.cost_usd < uncached.cost_usd
        # OpenAI cache is ~50% vs Anthropic ~10%
        ratio = cached.cost_usd / uncached.cost_usd
        assert 0.4 < ratio < 0.6
