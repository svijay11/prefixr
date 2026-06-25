"""EventBus — emits structured cache events to SQLite + WebSocket stream."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from prefixr.cache import SessionLedger


@dataclass
class CacheEvent:
    event_type: str  # cache_hit | cache_miss | summarize_triggered | pad_injected | anchor_split
    session_id: str
    turn_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: int = 0


EventHandler = Callable[[CacheEvent], None]


class EventBus:
    def __init__(self, ledger: SessionLedger):
        self.ledger = ledger
        self._handlers: list[EventHandler] = []
        self._ws_subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def subscribe_ws(self, session_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._ws_subscribers.setdefault(session_id, []).append(queue)
        return queue

    def unsubscribe_ws(self, session_id: str, queue: asyncio.Queue) -> None:
        subs = self._ws_subscribers.get(session_id, [])
        if queue in subs:
            subs.remove(queue)

    def emit(self, event: CacheEvent) -> int:
        import time

        if event.timestamp == 0:
            event.timestamp = int(time.time())

        event_id = self.ledger.record_event(
            event.session_id,
            event.event_type,
            event.payload,
            event.turn_id,
        )

        for handler in self._handlers:
            handler(event)

        for queue in self._ws_subscribers.get(event.session_id, []):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        return event_id

    async def stream_events(self, session_id: str):
        """Async generator for WebSocket event streaming."""
        queue = self.subscribe_ws(session_id)
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            self.unsubscribe_ws(session_id, queue)

    def emit_cache_hit(
        self,
        session_id: str,
        turn_id: int,
        tokens_cached: int,
        tokens_total: int,
    ) -> int:
        return self.emit(
            CacheEvent(
                event_type="cache_hit",
                session_id=session_id,
                turn_id=turn_id,
                payload={
                    "tokens_cached": tokens_cached,
                    "tokens_total": tokens_total,
                    "hit_rate": tokens_cached / tokens_total if tokens_total else 0,
                },
            )
        )

    def emit_cache_miss(
        self,
        session_id: str,
        turn_id: int,
        reason: str,
        tokens_total: int,
    ) -> int:
        return self.emit(
            CacheEvent(
                event_type="cache_miss",
                session_id=session_id,
                turn_id=turn_id,
                payload={"reason": reason, "tokens_total": tokens_total},
            )
        )

    def emit_action(
        self,
        session_id: str,
        turn_id: int | None,
        action: str,
        details: dict[str, Any],
    ) -> int:
        event_type = {
            "summarize": "summarize_triggered",
            "pad": "pad_injected",
            "anchor_split": "anchor_split",
        }.get(action, action)
        return self.emit(
            CacheEvent(
                event_type=event_type,
                session_id=session_id,
                turn_id=turn_id,
                payload=details,
            )
        )
