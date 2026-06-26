# Using Prefixr with Cursor

## Cursor does not have its own API provider

Cursor is a **client**, not an LLM provider. There is no "Cursor API key" to add to Prefixr.

When you use Cursor, you either:
- Use **Cursor's built-in models** (billed through Cursor subscription) — Prefixr cannot intercept these
- Use **Bring Your Own Key (BYOK)** with OpenAI, Anthropic, or Google keys — Prefixr **can** optimize these

Tab autocomplete, some Composer features, and other Cursor-native features stay on Cursor's backend and **won't** route through Prefixr.

## How to use Prefixr with Cursor (BYOK)

### 1. Start Prefixr locally

```bash
prefixr init    # add your OpenAI / Anthropic / Gemini keys
prefixr run
```

### 2. Configure Cursor

1. Open **Cursor Settings** → **Models**
2. Enable **Override OpenAI Base URL**
3. Set Base URL to:
   ```
   http://localhost:4242/v1
   ```
4. Set **OpenAI API Key** to any non-empty string (e.g. `prefixr`) — Prefixr uses keys from `~/.prefixr/config.json` unless you pass `Authorization` in requests
5. **Add custom model** with the exact model ID you want, e.g.:
   - `gpt-4o` (OpenAI)
   - `claude-sonnet-4-5` (Anthropic — use `/v1/messages` path separately if needed)
   - `gemini-2.5-flash` (Gemini)

### 3. Watch the dashboard

Open http://localhost:4242/dashboard while coding in Cursor. You'll see cache hits and savings for chat requests that route through Prefixr.

## Which models work?

| Model type | Routes through Prefixr? | Notes |
|------------|---------------------------|-------|
| Custom OpenAI-compatible chat | Yes | Override base URL to `localhost:4242/v1` |
| Anthropic Claude (BYOK) | Yes | May need OpenAI-compat wrapper or direct API config |
| Gemini (BYOK) | Yes | Use model name `gemini-2.5-flash` etc. |
| Cursor Tab / native Composer | No | Locked to Cursor backend |

## Troubleshooting

- **401 errors** — Run `prefixr init` and add the provider key for the model you're using
- **Model not found** — Add the exact model ID in Cursor's custom models list
- **No stats in dashboard** — Confirm Cursor is using your custom base URL, not Cursor's default endpoint
- **Connection refused** — Make sure `prefixr run` is still running in a terminal

## References

- [Cursor API keys docs](https://docs.cursor.com/advanced/api-keys)
- [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai)
