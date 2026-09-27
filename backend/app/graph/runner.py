"""Turns graph execution into a flat stream of UI-friendly events (used by the API and the evals)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.graph.state import new_turn

Event = dict[str, Any]


class CrewRunner:
    def __init__(self, graph: CompiledStateGraph) -> None:
        self.graph = graph

    @staticmethod
    def _config(thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}

    def pending_approval(self, thread_id: str) -> dict[str, Any] | None:
        snapshot = self.graph.get_state(self._config(thread_id))
        for task in snapshot.tasks:
            for intr in task.interrupts:
                return intr.value
        return None

    def start(self, thread_id: str, message: str) -> Iterator[Event]:
        yield from self._run(new_turn(message), thread_id)

    def resume(self, thread_id: str, decision: dict[str, Any]) -> Iterator[Event]:
        yield from self._run(Command(resume=decision), thread_id)

    def _run(self, graph_input: Any, thread_id: str) -> Iterator[Event]:
        config = self._config(thread_id)
        for mode, chunk in self.graph.stream(graph_input, config, stream_mode=["custom", "updates"]):
            if mode == "custom":
                yield chunk
            elif "__interrupt__" in chunk:
                for intr in chunk["__interrupt__"]:
                    yield {"type": "approval_required", "thread_id": thread_id, **intr.value}

        values = self.graph.get_state(config).values
        if self.pending_approval(thread_id) is None:
            yield {
                "type": "final",
                "thread_id": thread_id,
                "reply": values.get("final_reply"),
                "critique": values.get("critique"),
                "findings": values.get("findings", []),
                "trace": values.get("trace", []),
            }

    def history(self, thread_id: str) -> dict[str, Any]:
        values = self.graph.get_state(self._config(thread_id)).values
        messages = [
            {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": str(m.content)}
            for m in values.get("messages", [])
            if isinstance(m, (HumanMessage, AIMessage))
        ]
        return {
            "thread_id": thread_id,
            "messages": messages,
            "trace": values.get("trace", []),
            "findings": values.get("findings", []),
            "pending_approval": self.pending_approval(thread_id),
        }
