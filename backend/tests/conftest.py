from __future__ import annotations

import json
import uuid

import pytest

from app.config import Settings
from app.graph.build import build_default
from app.graph.runner import CrewRunner


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        llm_provider="demo",
        db_path=tmp_path / "northwind.db",
        checkpoint_path=tmp_path / "checkpoints.db",
    )


@pytest.fixture
def crew(settings):
    graph, deps = build_default(settings, persistent=False)
    yield CrewRunner(graph), deps
    deps.store.close()


@pytest.fixture
def run(crew):
    """Run one message on a fresh thread. Returns (thread_id, events)."""
    runner, _ = crew

    def _run(message: str, thread_id: str | None = None):
        tid = thread_id or uuid.uuid4().hex
        return tid, list(runner.start(tid, message))

    return _run


def final(events: list[dict]) -> dict:
    return next(e for e in events if e["type"] == "final")


def agents_run(events: list[dict]) -> list[str]:
    return [e["agent"] for e in events if e["type"] == "agent_end"]


def parse_sse(text: str) -> list[dict]:
    out = []
    for block in text.strip().split("\n\n"):
        data = [line[6:] for line in block.splitlines() if line.startswith("data: ")]
        if data:
            out.append(json.loads(data[0]))
    return out
