"""Integration tests against proxy."""

import pytest
from fastapi.testclient import TestClient

from prefixr.config import PrefixrConfig
from prefixr.proxy import create_app


@pytest.fixture
def client(tmp_path):
    config = PrefixrConfig()
    db = tmp_path / "test.db"
    app = create_app(config, ["openai", "anthropic", "deepseek"], db)
    return TestClient(app)


class TestProxyEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_list_sessions_empty(self, client):
        resp = client.get("/sessions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_lifetime_stats(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_count" in data

    def test_session_not_found(self, client):
        resp = client.get("/sessions/nonexistent/stats")
        assert resp.status_code == 404

    def test_chat_completions_no_key(self, client):
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert resp.status_code == 401

    def test_messages_no_key(self, client):
        resp = client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4-5",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert resp.status_code == 401
