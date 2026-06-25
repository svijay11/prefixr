# Prefixr

Local-first, provider cache-aware context scheduler for LLM API calls.

Prefixr runs as a local proxy on your machine, intercepting outbound API payloads bound for Anthropic, OpenAI, or DeepSeek before they leave your system. On every turn, it runs a cost optimization algorithm that computes whether it is cheaper to preserve the existing prefix cache or to summarize/prune context now and accept a one-turn cache bust in exchange for savings over the next N turns.

Everything runs on your machine with your own API keys. No data leaves your machine except the API calls you were already making — Prefixr just makes them cheaper.

## Install

```bash
pip install prefixr
```

Or one-liner (pipx-managed):

```bash
curl -fsSL prefixr.dev/install | bash
```

## Quick Start

```bash
prefixr init          # configure API keys
prefixr run           # start proxy + dashboard
```

Open the dashboard at [http://localhost:4242/dashboard](http://localhost:4242/dashboard).

Point any OpenAI-compatible tool at `http://localhost:4242/v1` — zero code changes.

```bash
curl http://localhost:4242/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## Python SDK

```python
from prefixr import PrefixrClient

# Drop-in OpenAI replacement
client = PrefixrClient(provider="openai")
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}]
)

# Drop-in Anthropic replacement
client = PrefixrClient(provider="anthropic")
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}]
)

# Session stats
stats = client.session_stats()
print(f"Cache hit rate: {stats.hit_rate:.1%}")
print(f"Saved: ${stats.cost_saved_usd:.4f}")
```

## How It Works

On every turn, before the payload goes out, Prefixr evaluates:

- **cost_preserve(N)** — cost of keeping raw history for the next N turns at current cache hit rate
- **cost_summarize(N)** — cost of summarizing now plus projected savings from cleaner context

If preserve costs more, Prefixr triggers summarization. Otherwise it tries cache alignment strategies first:

1. **Anchor splitting** — freeze stable blocks (system prompt, docs) vs volatile tail
2. **Padding injection** — align blocks to provider cache checkpoints (1024/2048/4096 for Anthropic)
3. **Timestamp scrubbing** — replace timestamps, UUIDs, and nonces that silently bust cache
4. **Summarization** — compress volatile tail via cheap model (last resort)

## CLI

```bash
prefixr init                          # interactive setup
prefixr run                           # start proxy + dashboard
prefixr run --port 4242               # custom port
prefixr run --providers anthropic,openai
prefixr stats                         # lifetime stats
prefixr stats --session <id>          # specific session
prefixr stats --json                  # machine-readable
prefixr sessions                      # list sessions
prefixr doctor                        # verify setup
prefixr reset                         # clear session ledger
prefixr update                        # self-update via pip
```

## Configuration

Config lives at `~/.prefixr/config.json`:

```json
{
  "anthropic_api_key": "...",
  "openai_api_key": "...",
  "deepseek_api_key": "...",
  "port": 4242,
  "optimizer": {
    "horizon_turns": 5,
    "summarizer_model": "claude-haiku-4-5",
    "summarizer_provider": "anthropic",
    "padding_enabled": true,
    "timestamp_scrubbing": true
  }
}
```

## Architecture

```
Your Agent / curl / Python script
        │
        ▼
  Prefixr Local Proxy (FastAPI, port 4242)
        │
        ├── SessionLedger (SQLite) ← token offsets, cache events, cost deltas
        ├── CacheOptimizer ← cost_preserve(N) vs cost_summarize(N)
        ├── ContextManipulator ← anchor split, padding, timestamp scrub
        ├── ProviderAdapter ← Anthropic, OpenAI, DeepSeek
        └── EventBus → Dashboard (WebSocket live feed)
```

## Development

```bash
git clone https://github.com/svijay11/prefixr
cd prefixr
pip install -e ".[dev]"
pytest
prefixr run
```

## License

MIT
