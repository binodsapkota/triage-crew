from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.graph.message import add_messages


class CrewState(TypedDict, total=False):
    # Conversation history persists across turns in the same thread.
    messages: Annotated[list[AnyMessage], add_messages]

    # Everything below is per-turn working memory, reset by new_turn().
    triage: dict[str, Any] | None
    plan: list[str]
    completed: list[str]
    route: str
    findings: list[dict[str, Any]]
    pending_action: dict[str, Any] | None
    draft_reply: str | None
    critique: dict[str, Any] | None
    revisions: int
    steps: int
    final_reply: str | None
    trace: list[dict[str, Any]]


def new_turn(message: str) -> dict[str, Any]:
    return {
        "messages": [HumanMessage(message)],
        "triage": None,
        "plan": [],
        "completed": [],
        "route": "",
        "findings": [],
        "pending_action": None,
        "draft_reply": None,
        "critique": None,
        "revisions": 0,
        "steps": 0,
        "final_reply": None,
        "trace": [],
    }


def user_messages(state: CrewState) -> list[str]:
    return [str(m.content) for m in state.get("messages", []) if isinstance(m, HumanMessage)]


def make_finding(
    agent: str, kind: str, summary: str, data: dict[str, Any] | None = None, source: str | None = None
) -> dict[str, Any]:
    return {"agent": agent, "kind": kind, "summary": summary, "data": data or {}, "source": source}
