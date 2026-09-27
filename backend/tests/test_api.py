import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import parse_sse


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings, persistent=False)) as c:
        yield c


def test_health_and_scenarios(client):
    assert client.get("/api/health").json() == {"status": "ok", "llm_provider": "demo"}
    assert len(client.get("/api/scenarios").json()) == 5


def test_chat_streams_events_and_final_reply(client):
    res = client.post("/api/chat", json={"message": "What's your warranty on hiking boots?"})
    assert res.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(res.text)
    types = [e["type"] for e in events]
    assert types[0] == "thread" and types[-1] == "done" and "final" in types


def test_approval_flow_over_http(client):
    events = parse_sse(client.post("/api/chat", json={"message": "Order 1047 is damaged, open a ticket"}).text)
    tid = events[0]["thread_id"]
    assert any(e["type"] == "approval_required" for e in events)

    blocked = client.post("/api/chat", json={"message": "hello?", "thread_id": tid})
    assert blocked.status_code == 409

    resumed = parse_sse(client.post(f"/api/threads/{tid}/resume", json={"approved": True}).text)
    assert any(e["type"] == "final" for e in resumed)
    assert client.get("/api/tickets").json()[0]["order_id"] == "1047"
    assert client.post(f"/api/threads/{tid}/resume", json={"approved": True}).status_code == 409


def test_rejects_empty_message(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422
