"""Test cache ledger."""

import pytest

from prefixr.cache import SessionLedger


@pytest.fixture
def ledger(tmp_path):
    db = tmp_path / "test.db"
    l = SessionLedger(db)
    yield l
    l.close()


class TestSessionLedger:
    def test_create_and_record_turn(self, ledger):
        sid = ledger.create_session("anthropic", "claude-sonnet-4-5")
        turn_id = ledger.record_turn(
            sid, 10000, 8000, "preserve", 0.05, 0.02, "test reasoning"
        )
        assert turn_id > 0

        stats = ledger.session_stats(sid)
        assert stats.turn_count == 1
        assert stats.hit_rate == 0.8
        assert stats.tokens_cached == 8000

    def test_rolling_hit_rate(self, ledger):
        sid = ledger.create_session("openai", "gpt-4o")
        ledger.record_turn(sid, 1000, 500, "preserve", 0.01, 0, "")
        ledger.record_turn(sid, 1000, 800, "preserve", 0.01, 0, "")
        rate = ledger.rolling_hit_rate(sid)
        assert rate == pytest.approx(0.65)

    def test_events(self, ledger):
        sid = ledger.create_session("anthropic", "claude-haiku-4-5")
        turn_id = ledger.record_turn(sid, 5000, 4000, "pad", 0.02, 0.01, "")
        ledger.record_event(sid, "cache_hit", {"tokens": 4000}, turn_id)
        events = ledger.get_events(sid)
        assert len(events) == 1
        assert events[0]["event_type"] == "cache_hit"

    def test_reset(self, ledger):
        sid = ledger.create_session("openai", "gpt-4o")
        ledger.record_turn(sid, 1000, 500, "preserve", 0.01, 0, "")
        ledger.reset()
        assert ledger.list_sessions() == []
