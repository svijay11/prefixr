"""SQLite session ledger — tracks token byte-offsets, cache events, cost deltas."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path.home() / ".prefixr" / "sessions.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    provider TEXT,
    model TEXT,
    created_at INTEGER,
    config_json TEXT
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    turn_number INTEGER,
    timestamp INTEGER,
    tokens_input INTEGER,
    tokens_cached INTEGER,
    tokens_uncached INTEGER,
    cache_hit_rate REAL,
    action_taken TEXT,
    cost_usd REAL,
    cost_saved_usd REAL,
    optimizer_reasoning TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    turn_id INTEGER,
    event_type TEXT,
    payload_json TEXT,
    timestamp INTEGER
);

CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_turn ON events(turn_id);
"""


@dataclass
class SessionSummary:
    id: str
    provider: str
    model: str
    created_at: int
    turn_count: int
    total_tokens_input: int
    total_tokens_cached: int
    avg_hit_rate: float
    total_cost_usd: float
    total_cost_saved_usd: float


@dataclass
class TurnRecord:
    id: int
    session_id: str
    turn_number: int
    timestamp: int
    tokens_input: int
    tokens_cached: int
    tokens_uncached: int
    cache_hit_rate: float
    action_taken: str
    cost_usd: float
    cost_saved_usd: float
    optimizer_reasoning: str


@dataclass
class SessionStats:
    session_id: str
    turn_count: int
    hit_rate: float
    tokens_input: int
    tokens_cached: int
    tokens_uncached: int
    cost_usd: float
    cost_saved_usd: float


class SessionLedger:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def create_session(
        self,
        provider: str,
        model: str,
        config: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        now = int(time.time())
        self._conn.execute(
            "INSERT INTO sessions (id, provider, model, created_at, config_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (sid, provider, model, now, json.dumps(config or {})),
        )
        self._conn.commit()
        return sid

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "provider": row["provider"],
            "model": row["model"],
            "created_at": row["created_at"],
            "config": json.loads(row["config_json"] or "{}"),
        }

    def get_or_create_session(
        self,
        session_id: str | None,
        provider: str,
        model: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        if session_id:
            existing = self.get_session(session_id)
            if existing:
                return session_id
        return self.create_session(provider, model, config, session_id)

    def record_turn(
        self,
        session_id: str,
        tokens_input: int,
        tokens_cached: int,
        action_taken: str,
        cost_usd: float,
        cost_saved_usd: float,
        optimizer_reasoning: str,
    ) -> int:
        tokens_uncached = tokens_input - tokens_cached
        hit_rate = tokens_cached / tokens_input if tokens_input > 0 else 0.0
        turn_number = self._conn.execute(
            "SELECT COALESCE(MAX(turn_number), 0) + 1 FROM turns WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        now = int(time.time())
        cursor = self._conn.execute(
            "INSERT INTO turns "
            "(session_id, turn_number, timestamp, tokens_input, tokens_cached, "
            "tokens_uncached, cache_hit_rate, action_taken, cost_usd, "
            "cost_saved_usd, optimizer_reasoning) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                turn_number,
                now,
                tokens_input,
                tokens_cached,
                tokens_uncached,
                hit_rate,
                action_taken,
                cost_usd,
                cost_saved_usd,
                optimizer_reasoning,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def record_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
        turn_id: int | None = None,
    ) -> int:
        now = int(time.time())
        cursor = self._conn.execute(
            "INSERT INTO events (session_id, turn_id, event_type, payload_json, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, turn_id, event_type, json.dumps(payload), now),
        )
        self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def get_turns(self, session_id: str) -> list[TurnRecord]:
        rows = self._conn.execute(
            "SELECT * FROM turns WHERE session_id = ? ORDER BY turn_number",
            (session_id,),
        ).fetchall()
        return [
            TurnRecord(
                id=row["id"],
                session_id=row["session_id"],
                turn_number=row["turn_number"],
                timestamp=row["timestamp"],
                tokens_input=row["tokens_input"],
                tokens_cached=row["tokens_cached"],
                tokens_uncached=row["tokens_uncached"],
                cache_hit_rate=row["cache_hit_rate"],
                action_taken=row["action_taken"],
                cost_usd=row["cost_usd"],
                cost_saved_usd=row["cost_saved_usd"],
                optimizer_reasoning=row["optimizer_reasoning"],
            )
            for row in rows
        ]

    def get_events(
        self, session_id: str, turn_id: int | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        if turn_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE session_id = ? AND turn_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (session_id, turn_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE session_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "turn_id": row["turn_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"] or "{}"),
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def rolling_hit_rate(self, session_id: str, window: int = 10) -> float:
        rows = self._conn.execute(
            "SELECT cache_hit_rate FROM turns WHERE session_id = ? "
            "ORDER BY turn_number DESC LIMIT ?",
            (session_id, window),
        ).fetchall()
        if not rows:
            return 0.0
        return sum(r["cache_hit_rate"] for r in rows) / len(rows)

    def session_stats(self, session_id: str) -> SessionStats:
        row = self._conn.execute(
            "SELECT "
            "COUNT(*) as turn_count, "
            "COALESCE(SUM(tokens_input), 0) as tokens_input, "
            "COALESCE(SUM(tokens_cached), 0) as tokens_cached, "
            "COALESCE(SUM(tokens_uncached), 0) as tokens_uncached, "
            "COALESCE(AVG(cache_hit_rate), 0) as hit_rate, "
            "COALESCE(SUM(cost_usd), 0) as cost_usd, "
            "COALESCE(SUM(cost_saved_usd), 0) as cost_saved_usd "
            "FROM turns WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return SessionStats(
            session_id=session_id,
            turn_count=row["turn_count"],
            hit_rate=row["hit_rate"],
            tokens_input=row["tokens_input"],
            tokens_cached=row["tokens_cached"],
            tokens_uncached=row["tokens_uncached"],
            cost_usd=row["cost_usd"],
            cost_saved_usd=row["cost_saved_usd"],
        )

    def list_sessions(self) -> list[SessionSummary]:
        rows = self._conn.execute(
            "SELECT s.id, s.provider, s.model, s.created_at, "
            "COUNT(t.id) as turn_count, "
            "COALESCE(SUM(t.tokens_input), 0) as total_tokens_input, "
            "COALESCE(SUM(t.tokens_cached), 0) as total_tokens_cached, "
            "COALESCE(AVG(t.cache_hit_rate), 0) as avg_hit_rate, "
            "COALESCE(SUM(t.cost_usd), 0) as total_cost_usd, "
            "COALESCE(SUM(t.cost_saved_usd), 0) as total_cost_saved_usd "
            "FROM sessions s LEFT JOIN turns t ON s.id = t.session_id "
            "GROUP BY s.id ORDER BY s.created_at DESC"
        ).fetchall()
        return [
            SessionSummary(
                id=row["id"],
                provider=row["provider"],
                model=row["model"],
                created_at=row["created_at"],
                turn_count=row["turn_count"],
                total_tokens_input=row["total_tokens_input"],
                total_tokens_cached=row["total_tokens_cached"],
                avg_hit_rate=row["avg_hit_rate"],
                total_cost_usd=row["total_cost_usd"],
                total_cost_saved_usd=row["total_cost_saved_usd"],
            )
            for row in rows
        ]

    def lifetime_stats(self) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT "
            "COUNT(DISTINCT session_id) as session_count, "
            "COUNT(*) as turn_count, "
            "COALESCE(SUM(tokens_input), 0) as tokens_input, "
            "COALESCE(SUM(tokens_cached), 0) as tokens_cached, "
            "COALESCE(AVG(cache_hit_rate), 0) as hit_rate, "
            "COALESCE(SUM(cost_saved_usd), 0) as cost_saved_usd "
            "FROM turns"
        ).fetchone()
        return {
            "session_count": row["session_count"],
            "turn_count": row["turn_count"],
            "tokens_input": row["tokens_input"],
            "tokens_cached": row["tokens_cached"],
            "hit_rate": row["hit_rate"],
            "cost_saved_usd": row["cost_saved_usd"],
        }

    def reset(self) -> None:
        self._conn.executescript(
            "DELETE FROM events; DELETE FROM turns; DELETE FROM sessions;"
        )
        self._conn.commit()

    def last_turn_cached_tokens(self, session_id: str) -> int:
        row = self._conn.execute(
            "SELECT tokens_cached FROM turns WHERE session_id = ? "
            "ORDER BY turn_number DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return row["tokens_cached"] if row else 0
