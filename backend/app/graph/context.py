"""Shared plumbing for nodes: dependency bundle, live event emission, and trace recording."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, TypeVar

from langgraph.config import get_stream_writer

from app.config import Settings
from app.data.store import Store
from app.llm.base import CrewLLM
from app.tools.knowledge import KnowledgeBase

T = TypeVar("T")


@dataclass
class Deps:
    llm: CrewLLM
    store: Store
    kb: KnowledgeBase
    settings: Settings


def _preview(value: Any, limit: int = 400) -> str:
    def default(o: Any) -> Any:
        return o.to_dict() if hasattr(o, "to_dict") else str(o)

    text = json.dumps(value, default=default)
    return text if len(text) <= limit else text[: limit - 3] + "..."


class NodeContext:
    def __init__(self, agent: str) -> None:
        self.agent = agent
        self.summary = ""
        self.details: dict[str, Any] = {}
        self.tools: list[dict[str, Any]] = []
        try:
            self._writer = get_stream_writer()
        except Exception:
            self._writer = None

    def emit(self, event_type: str, **payload: Any) -> None:
        if self._writer:
            self._writer({"type": event_type, "agent": self.agent, **payload})

    def tool(self, name: str, args: dict[str, Any], call: Callable[[], T]) -> T:
        start = perf_counter()
        result = call()
        record = {
            "tool": name,
            "args": args,
            "result_preview": _preview(result),
            "duration_ms": round((perf_counter() - start) * 1000, 1),
        }
        self.tools.append(record)
        self.emit("tool_call", **record)
        return result


NodeFn = Callable[[dict[str, Any], NodeContext], dict[str, Any]]


def traced(agent: str, label: str) -> Callable[[NodeFn], Callable[[dict[str, Any]], dict[str, Any]]]:
    """Wrap a node so it streams agent_start/agent_end events and appends a trace entry to state."""

    def decorator(fn: NodeFn) -> Callable[[dict[str, Any]], dict[str, Any]]:
        # Not functools.wraps: LangGraph inspects the node signature, which must stay (state) only.
        def node(state: dict[str, Any]) -> dict[str, Any]:
            ctx = NodeContext(agent)
            started_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            ctx.emit("agent_start", label=label, started_at=started_at)
            start = perf_counter()
            update = fn(state, ctx)
            entry = {
                "agent": agent,
                "label": label,
                "summary": ctx.summary,
                "details": ctx.details,
                "tools": ctx.tools,
                "started_at": started_at,
                "duration_ms": round((perf_counter() - start) * 1000, 1),
            }
            update["trace"] = [*state.get("trace", []), entry]
            ctx.emit("agent_end", **{k: v for k, v in entry.items() if k != "agent"})
            return update

        node.__name__ = agent
        return node

    return decorator
