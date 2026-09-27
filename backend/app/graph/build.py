from __future__ import annotations

import sqlite3
from pathlib import Path

from langchain_core.messages import AIMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.config import Settings
from app.data.store import Store
from app.graph.agents.critic_agent import make_critic
from app.graph.agents.knowledge_agent import make_knowledge_agent
from app.graph.agents.order_agent import make_order_agent
from app.graph.agents.ticket_agent import make_approval, make_ticket_agent
from app.graph.context import Deps
from app.graph.state import CrewState
from app.graph.supervisor import make_supervisor
from app.llm.base import CrewLLM
from app.llm.provider import get_llm
from app.tools.knowledge import KnowledgeBase

SUPERVISOR_ROUTES = {
    "order_agent": "order_agent",
    "knowledge_agent": "knowledge_agent",
    "ticket_agent": "ticket_agent",
    "critic": "critic",
    "finalize": "finalize",
}


def _finalize(state: CrewState) -> dict:
    reply = state.get("draft_reply") or ""
    return {"final_reply": reply, "messages": [AIMessage(reply)]}


def build_graph(deps: Deps, checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    g = StateGraph(CrewState)
    g.add_node("supervisor", make_supervisor(deps))
    g.add_node("order_agent", make_order_agent(deps))
    g.add_node("knowledge_agent", make_knowledge_agent(deps))
    g.add_node("ticket_agent", make_ticket_agent(deps))
    g.add_node("approval", make_approval(deps))
    g.add_node("critic", make_critic(deps))
    g.add_node("finalize", _finalize)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", lambda s: s["route"], SUPERVISOR_ROUTES)
    g.add_edge("order_agent", "supervisor")
    g.add_edge("knowledge_agent", "supervisor")
    g.add_edge("ticket_agent", "approval")
    g.add_edge("approval", "supervisor")
    g.add_conditional_edges("critic", lambda s: s["route"], {"finalize": "finalize", "supervisor": "supervisor"})
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())


def sqlite_checkpointer(path: Path) -> SqliteSaver:
    path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(str(path), check_same_thread=False))


def build_default(
    settings: Settings, llm: CrewLLM | None = None, persistent: bool = True
) -> tuple[CompiledStateGraph, Deps]:
    store = Store(settings.resolve(settings.db_path)) if persistent else Store()
    deps = Deps(llm=llm or get_llm(settings), store=store, kb=KnowledgeBase(), settings=settings)
    checkpointer = sqlite_checkpointer(settings.resolve(settings.checkpoint_path)) if persistent else None
    return build_graph(deps, checkpointer), deps
