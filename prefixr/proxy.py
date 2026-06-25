"""FastAPI proxy server — intercepts and optimizes LLM API calls."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from prefixr.cache import SessionLedger
from prefixr.config import PrefixrConfig
from prefixr.context import ContextManipulator
from prefixr.events import EventBus
from prefixr.providers import detect_adapter, get_adapter
from prefixr.scheduler import CacheOptimizer, padding_tokens_needed
from prefixr.summarizer import apply_summary, create_summarizer

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
RETRY_STATUS_CODES = {429, 529}
MAX_RETRIES = 3
BASE_BACKOFF = 1.0

PROVIDER_URLS = {
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com",
    "deepseek": "https://api.deepseek.com",
}


class PrefixrProxy:
    def __init__(
        self,
        config: PrefixrConfig,
        active_providers: list[str] | None = None,
        db_path: Path | None = None,
    ):
        self.config = config
        self.active_providers = active_providers or ["anthropic", "openai", "deepseek"]
        self.ledger = SessionLedger(db_path)
        self.event_bus = EventBus(self.ledger)
        self.manipulator = ContextManipulator(
            timestamp_scrubbing=config.optimizer.timestamp_scrubbing,
            padding_enabled=config.optimizer.padding_enabled,
        )
        self._session_map: dict[str, str] = {}  # request session header -> ledger session id

    def _get_summarizer(self):
        opt = self.config.optimizer
        api_key = self.config.get_api_key(opt.summarizer_provider)
        return create_summarizer(opt.summarizer_provider, api_key, opt.summarizer_model)

    def _resolve_session(
        self,
        session_header: str | None,
        provider: str,
        model: str,
    ) -> str:
        if session_header and session_header in self._session_map:
            return self._session_map[session_header]
        sid = self.ledger.get_or_create_session(
            session_header,
            provider,
            model,
            self.config.to_dict(),
        )
        if session_header:
            self._session_map[session_header] = sid
        return sid

    async def optimize_payload(
        self,
        payload: dict[str, Any],
        adapter,
        session_id: str,
    ) -> tuple[dict[str, Any], str, str]:
        """Run optimizer and apply context manipulation. Returns (payload, action, reasoning)."""
        messages = adapter.extract_messages(payload)
        analysis = self.manipulator.analyze(messages)
        tokens_total = adapter.estimate_input_tokens(payload)
        rolling_hit_rate = self.ledger.rolling_hit_rate(session_id)

        pricing = adapter.get_pricing(payload.get("model", ""))
        optimizer = CacheOptimizer(
            pricing=pricing,
            horizon_turns=self.config.optimizer.horizon_turns,
            summarizer_model=self.config.optimizer.summarizer_model,
            padding_enabled=self.config.optimizer.padding_enabled,
        )

        decision = optimizer.decide(
            tokens_total=tokens_total,
            tokens_cached=int(tokens_total * rolling_hit_rate),
            rolling_hit_rate=rolling_hit_rate,
            stable_tokens=analysis.stable_tokens,
            volatile_tokens=analysis.volatile_tokens,
            stable_block_tokens=analysis.stable_block_tokens,
        )

        action = decision.action
        pad_tokens = 0
        if action == "pad":
            pad_tokens = padding_tokens_needed(analysis.stable_block_tokens)

        # Apply context manipulation
        if action in ("anchor_split", "pad", "preserve"):
            messages = self.manipulator.preprocess(
                messages,
                action if action != "preserve" else "preserve",
                stable_block_tokens=analysis.stable_block_tokens,
                pad_tokens=pad_tokens,
            )
        elif action == "summarize" and analysis.volatile_messages:
            try:
                summarizer = self._get_summarizer()
                summary = await summarizer.summarize(messages, analysis.volatile_messages)
                messages = apply_summary(messages, summary, analysis.volatile_messages)
                self.event_bus.emit_action(
                    session_id, None, "summarize",
                    {"summary_length": len(summary), "volatile_count": len(analysis.volatile_messages)},
                )
            except Exception as e:
                logger.warning("Summarizer failed, falling back to preserve: %s", e)
                action = "preserve"
                messages = self.manipulator.preprocess(messages, "preserve")

        payload = adapter.set_messages(payload, messages)
        payload = adapter.preprocess(payload)
        return payload, action, decision.reasoning

    async def forward_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> httpx.Response:
        backoff = BASE_BACKOFF
        last_resp = None

        for attempt in range(MAX_RETRIES + 1):
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.request(method, url, headers=headers, json=body)
                last_resp = resp
                if resp.status_code not in RETRY_STATUS_CODES:
                    return resp
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(backoff)
                    backoff *= 2

        return last_resp  # type: ignore[return-value]

    async def handle_chat_completions(
        self,
        payload: dict[str, Any],
        session_header: str | None,
        auth_header: str | None,
    ) -> JSONResponse:
        adapter = detect_adapter(payload, self.active_providers)
        provider = adapter.provider_name
        model = payload.get("model", "unknown")
        session_id = self._resolve_session(session_header, provider, model)

        payload, action, reasoning = await self.optimize_payload(payload, adapter, session_id)

        api_key = self.config.get_api_key(provider)
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        if not api_key:
            raise HTTPException(401, f"No API key configured for {provider}")

        base_url = PROVIDER_URLS.get(provider, PROVIDER_URLS["openai"])
        url = f"{base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        resp = await self.forward_request("POST", url, headers, payload)

        if resp.status_code != 200:
            return JSONResponse(status_code=resp.status_code, content=resp.json())

        data = resp.json()
        cache_data = adapter.postprocess(data)

        pricing = adapter.get_pricing(model)
        optimizer = CacheOptimizer(pricing, self.config.optimizer.horizon_turns)
        turn_cost = optimizer.estimate_current_turn(
            cache_data.tokens_input, cache_data.tokens_cached
        )
        baseline = optimizer.baseline_cost_no_prefixr(cache_data.tokens_input, 1)
        cost_saved = max(0, baseline - turn_cost.cost_usd)

        turn_id = self.ledger.record_turn(
            session_id=session_id,
            tokens_input=cache_data.tokens_input,
            tokens_cached=cache_data.tokens_cached,
            action_taken=action,
            cost_usd=turn_cost.cost_usd,
            cost_saved_usd=cost_saved,
            optimizer_reasoning=reasoning,
        )

        if cache_data.is_cache_hit:
            self.event_bus.emit_cache_hit(
                session_id, turn_id, cache_data.tokens_cached, cache_data.tokens_input
            )
        if cache_data.is_cache_miss:
            self.event_bus.emit_cache_miss(
                session_id, turn_id, cache_data.miss_reason, cache_data.tokens_input
            )
        if action in ("pad", "anchor_split", "summarize"):
            self.event_bus.emit_action(session_id, turn_id, action, {"reasoning": reasoning})

        return JSONResponse(content=data)

    async def handle_messages(
        self,
        payload: dict[str, Any],
        session_header: str | None,
        auth_header: str | None,
        api_key_header: str | None,
    ) -> JSONResponse:
        adapter = get_adapter("anthropic")
        model = payload.get("model", "unknown")
        session_id = self._resolve_session(session_header, "anthropic", model)

        payload, action, reasoning = await self.optimize_payload(payload, adapter, session_id)

        api_key = api_key_header or self.config.anthropic_api_key
        if not api_key:
            raise HTTPException(401, "No Anthropic API key configured")

        url = f"{PROVIDER_URLS['anthropic']}/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        resp = await self.forward_request("POST", url, headers, payload)

        if resp.status_code != 200:
            try:
                return JSONResponse(status_code=resp.status_code, content=resp.json())
            except Exception:
                return JSONResponse(status_code=resp.status_code, content={"error": resp.text})

        data = resp.json()
        cache_data = adapter.postprocess(data)

        pricing = adapter.get_pricing(model)
        optimizer = CacheOptimizer(pricing, self.config.optimizer.horizon_turns)
        turn_cost = optimizer.estimate_current_turn(
            cache_data.tokens_input, cache_data.tokens_cached
        )
        baseline = optimizer.baseline_cost_no_prefixr(cache_data.tokens_input, 1)
        cost_saved = max(0, baseline - turn_cost.cost_usd)

        turn_id = self.ledger.record_turn(
            session_id=session_id,
            tokens_input=cache_data.tokens_input,
            tokens_cached=cache_data.tokens_cached,
            action_taken=action,
            cost_usd=turn_cost.cost_usd,
            cost_saved_usd=cost_saved,
            optimizer_reasoning=reasoning,
        )

        if cache_data.is_cache_hit:
            self.event_bus.emit_cache_hit(
                session_id, turn_id, cache_data.tokens_cached, cache_data.tokens_input
            )
        if cache_data.is_cache_miss:
            self.event_bus.emit_cache_miss(
                session_id, turn_id, cache_data.miss_reason, cache_data.tokens_input
            )
        if action in ("pad", "anchor_split", "summarize"):
            self.event_bus.emit_action(session_id, turn_id, action, {"reasoning": reasoning})

        return JSONResponse(content=data)


def create_app(
    config: PrefixrConfig | None = None,
    active_providers: list[str] | None = None,
    db_path: Path | None = None,
) -> FastAPI:
    config = config or PrefixrConfig.load()
    proxy = PrefixrProxy(config, active_providers, db_path)

    app = FastAPI(title="Prefixr", version="0.1.0")

    def check_auth(x_prefixr_key: Optional[str] = Header(None, alias="X-Prefixr-Key")):
        if config.prefixr_api_key and x_prefixr_key != config.prefixr_api_key:
            raise HTTPException(401, "Invalid Prefixr API key")

    @app.post("/v1/chat/completions")
    async def chat_completions(
        request: Request,
        authorization: Optional[str] = Header(None),
        x_prefixr_session: Optional[str] = Header(None, alias="X-Prefixr-Session"),
        x_prefixr_key: Optional[str] = Header(None, alias="X-Prefixr-Key"),
    ):
        check_auth(x_prefixr_key)
        payload = await request.json()
        return await proxy.handle_chat_completions(payload, x_prefixr_session, authorization)

    @app.post("/v1/messages")
    async def messages(
        request: Request,
        x_api_key: Optional[str] = Header(None, alias="x-api-key"),
        x_prefixr_session: Optional[str] = Header(None, alias="X-Prefixr-Session"),
        x_prefixr_key: Optional[str] = Header(None, alias="X-Prefixr-Key"),
    ):
        check_auth(x_prefixr_key)
        payload = await request.json()
        return await proxy.handle_messages(payload, x_prefixr_session, None, x_api_key)

    @app.get("/sessions")
    async def list_sessions():
        sessions = proxy.ledger.list_sessions()
        return [asdict(s) for s in sessions]

    @app.get("/sessions/{session_id}")
    async def get_session(session_id: str):
        session = proxy.ledger.get_session(session_id)
        if not session:
            raise HTTPException(404, "Session not found")
        turns = proxy.ledger.get_turns(session_id)
        events = proxy.ledger.get_events(session_id)
        return {
            "session": session,
            "turns": [asdict(t) for t in turns],
            "events": events,
        }

    @app.get("/sessions/{session_id}/stats")
    async def session_stats(session_id: str):
        stats = proxy.ledger.session_stats(session_id)
        if stats.turn_count == 0 and not proxy.ledger.get_session(session_id):
            raise HTTPException(404, "Session not found")
        return asdict(stats)

    @app.get("/stats")
    async def lifetime_stats():
        return proxy.ledger.lifetime_stats()

    @app.websocket("/sessions/{session_id}/stream")
    async def stream_session(websocket: WebSocket, session_id: str):
        await websocket.accept()
        queue = proxy.event_bus.subscribe_ws(session_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    await websocket.send_json({
                        "event_type": event.event_type,
                        "session_id": event.session_id,
                        "turn_id": event.turn_id,
                        "payload": event.payload,
                        "timestamp": event.timestamp,
                    })
                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "ping"})
        except WebSocketDisconnect:
            pass
        finally:
            proxy.event_bus.unsubscribe_ws(session_id, queue)

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "providers": proxy.active_providers,
            "port": config.port,
        }

    @app.get("/dashboard")
    async def dashboard():
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"message": "Dashboard not built. Run dashboard build."})

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.state.proxy = proxy
    app.state.config = config
    return app
