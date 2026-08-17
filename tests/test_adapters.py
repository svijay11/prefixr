"""Tests for provider adapters."""

import pytest

from prefixr.providers.gemini import GeminiAdapter
from prefixr.providers.anthropic import AnthropicAdapter
from prefixr.providers.deepseek import DeepSeekAdapter
from prefixr.providers.openai import OpenAIAdapter
from prefixr.providers.openrouter import OpenRouterAdapter
from prefixr.providers import detect_adapter


class TestAnthropicAdapter:
    @pytest.fixture
    def adapter(self):
        return AnthropicAdapter()

    def test_postprocess_reads_cache_tokens(self, adapter):
        response = {
            "usage": {
                "input_tokens": 10000,
                "cache_read_input_tokens": 8000,
                "cache_creation_input_tokens": 0,
            }
        }
        data = adapter.postprocess(response)
        assert data.tokens_cached == 8000
        assert data.tokens_uncached == 2000
        assert data.is_cache_hit is True

    def test_postprocess_cache_miss(self, adapter):
        response = {
            "usage": {
                "input_tokens": 10000,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 10000,
            }
        }
        data = adapter.postprocess(response)
        assert data.is_cache_miss is True
        assert data.cache_creation_tokens == 10000

    def test_preprocess_injects_cache_control(self, adapter):
        payload = {
            "model": "claude-sonnet-4-5",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
        }
        result = adapter.preprocess(payload)
        system_content = result["messages"][0]["content"]
        assert isinstance(system_content, list)
        assert system_content[0]["cache_control"] == {"type": "ephemeral"}

    def test_detect_provider(self, adapter):
        assert adapter.detect_provider({"model": "claude-opus-4-6"}) is True
        assert adapter.detect_provider({"model": "gpt-4o"}) is False


class TestOpenAIAdapter:
    @pytest.fixture
    def adapter(self):
        return OpenAIAdapter()

    def test_postprocess_reads_cached_tokens(self, adapter):
        response = {
            "usage": {
                "prompt_tokens": 5000,
                "prompt_tokens_details": {"cached_tokens": 4000},
            }
        }
        data = adapter.postprocess(response)
        assert data.tokens_cached == 4000
        assert data.is_cache_hit is True

    def test_preprocess_orders_system_first(self, adapter):
        payload = {
            "model": "gpt-4o",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "system", "content": "Be helpful"},
            ],
        }
        result = adapter.preprocess(payload)
        assert result["messages"][0]["role"] == "system"

    def test_detect_cache_bust(self, adapter):
        assert adapter.detect_cache_bust("sess1", 5000) is False
        assert adapter.detect_cache_bust("sess1", 1000) is True

    def test_detect_provider_skips_openrouter_ids(self, adapter):
        assert adapter.detect_provider({"model": "gpt-4o"}) is True
        assert adapter.detect_provider({"model": "openai/gpt-4o"}) is False


class TestDeepSeekAdapter:
    @pytest.fixture
    def adapter(self):
        return DeepSeekAdapter()

    def test_postprocess_with_cache_hit_tokens(self, adapter):
        response = {
            "usage": {
                "prompt_tokens": 8000,
                "prompt_cache_hit_tokens": 6000,
            }
        }
        data = adapter.postprocess(response)
        assert data.tokens_cached == 6000

    def test_postprocess_heuristic_fallback(self, adapter):
        response = {"usage": {"prompt_tokens": 10000}}
        data = adapter.postprocess(response)
        assert data.tokens_cached > 0


class TestGeminiAdapter:
    @pytest.fixture
    def adapter(self):
        return GeminiAdapter()

    def test_detect_provider(self, adapter):
        assert adapter.detect_provider({"model": "gemini-2.5-flash"}) is True
        assert adapter.detect_provider({"model": "gpt-4o"}) is False

    def test_postprocess_reads_cached_tokens(self, adapter):
        response = {
            "usage": {
                "prompt_tokens": 10000,
                "prompt_tokens_details": {"cached_tokens": 6000},
            }
        }
        data = adapter.postprocess(response)
        assert data.tokens_cached == 6000
        assert data.is_cache_hit is True

    def test_preprocess_orders_system_first(self, adapter):
        payload = {
            "model": "gemini-2.5-flash",
            "messages": [
                {"role": "user", "content": "Hi"},
                {"role": "system", "content": "Be helpful"},
            ],
        }
        result = adapter.preprocess(payload)
        assert result["messages"][0]["role"] == "system"


class TestOpenRouterAdapter:
    @pytest.fixture
    def adapter(self):
        return OpenRouterAdapter()

    def test_detect_vendor_slash_models(self, adapter):
        assert adapter.detect_provider({"model": "openai/gpt-4o"}) is True
        assert adapter.detect_provider({"model": "anthropic/claude-sonnet-4-5"}) is True
        assert adapter.detect_provider({"model": "google/gemini-2.5-flash"}) is True
        assert adapter.detect_provider({"model": "gpt-4o"}) is False
        assert adapter.detect_provider({"model": "claude-sonnet-4-5"}) is False

    def test_postprocess_openai_style_cache(self, adapter):
        response = {
            "usage": {
                "prompt_tokens": 5000,
                "prompt_tokens_details": {"cached_tokens": 4000},
            }
        }
        data = adapter.postprocess(response)
        assert data.tokens_cached == 4000
        assert data.is_cache_hit is True

    def test_postprocess_anthropic_style_cache(self, adapter):
        response = {
            "usage": {
                "prompt_tokens": 10000,
                "cache_read_input_tokens": 8000,
            }
        }
        data = adapter.postprocess(response)
        assert data.tokens_cached == 8000
        assert data.tokens_uncached == 2000

    def test_preprocess_orders_system_first(self, adapter):
        payload = {
            "model": "openai/gpt-4o",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "system", "content": "Be helpful"},
            ],
        }
        result = adapter.preprocess(payload)
        assert result["messages"][0]["role"] == "system"

    def test_preprocess_injects_cache_control_for_anthropic_models(self, adapter):
        payload = {
            "model": "anthropic/claude-sonnet-4-5",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
        }
        result = adapter.preprocess(payload)
        system_content = result["messages"][0]["content"]
        assert isinstance(system_content, list)
        assert system_content[0]["cache_control"] == {"type": "ephemeral"}

    def test_pricing_uses_upstream_vendor(self, adapter):
        pricing = adapter.get_pricing("openai/gpt-4o")
        assert pricing.price_uncached_per_mtok == 2.50
        assert pricing.provider == "openrouter"


class TestDetectAdapter:
    def test_openrouter_before_openai_for_slash_models(self):
        adapter = detect_adapter({"model": "openai/gpt-4o"})
        assert adapter.provider_name == "openrouter"

    def test_native_openai_unchanged(self):
        adapter = detect_adapter({"model": "gpt-4o"})
        assert adapter.provider_name == "openai"

    def test_native_anthropic_unchanged(self):
        adapter = detect_adapter({"model": "claude-sonnet-4-5"})
        assert adapter.provider_name == "anthropic"
