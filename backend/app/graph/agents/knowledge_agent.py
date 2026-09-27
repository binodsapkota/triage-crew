from __future__ import annotations

from typing import Any

from app.graph.context import Deps, NodeContext, traced
from app.graph.state import make_finding, user_messages

AGENT = "knowledge_agent"


def make_knowledge_agent(deps: Deps):
    @traced(AGENT, "Knowledge Agent")
    def knowledge_agent(state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        query = state["triage"].get("knowledge_query") or user_messages(state)[-1]
        passages = ctx.tool("search_policies", {"query": query}, lambda: deps.kb.search(query))

        if passages:
            new = [
                make_finding(AGENT, "policy", f"{p.section} [{p.source}]: {p.text}", p.to_dict(), p.source)
                for p in passages
            ]
            ctx.summary = "Retrieved " + ", ".join(f"'{p.section}' from {p.source}" for p in passages) + "."
        else:
            new = [make_finding(AGENT, "no_policy", "No relevant policy found for this request.")]
            ctx.summary = new[0]["summary"]

        return {
            "findings": [*state.get("findings", []), *new],
            "completed": [*state.get("completed", []), AGENT],
        }

    return knowledge_agent
