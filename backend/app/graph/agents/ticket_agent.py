"""Ticket drafting and the human approval gate.

Drafting and approval are separate nodes on purpose: on resume LangGraph re-runs the interrupted node
from the top, so the approval node must not do anything non-idempotent before interrupt().
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from app.graph.context import Deps, NodeContext, traced
from app.graph.state import make_finding, user_messages
from app.llm.base import TriagePlan
from app.tools.tickets import create_ticket

AGENT = "ticket_agent"
EDITABLE_FIELDS = ("title", "priority", "category", "summary")


def make_ticket_agent(deps: Deps):
    @traced(AGENT, "Ticket Agent")
    def ticket_agent(state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        draft = deps.llm.draft_ticket(
            user_messages(state)[-1], TriagePlan(**state["triage"]), state.get("findings", [])
        ).model_dump()
        ctx.summary = f"Drafted {draft['priority']}-priority {draft['category']} ticket; awaiting human approval."
        ctx.details["draft"] = draft
        return {
            "pending_action": {"type": "create_ticket", "draft": draft},
            "completed": [*state.get("completed", []), AGENT],
        }

    return ticket_agent


def make_approval(deps: Deps):
    @traced("approval", "Human Approval")
    def approval(state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        draft = state["pending_action"]["draft"]
        decision = interrupt({"kind": "ticket_approval", "draft": draft})

        findings = list(state.get("findings", []))
        if decision.get("approved"):
            edits = {k: v for k, v in (decision.get("edits") or {}).items() if k in EDITABLE_FIELDS and v}
            final = {**draft, **edits}
            ticket = ctx.tool("create_ticket", final, lambda: create_ticket(deps.store, final))
            summary = f"Ticket {ticket['id']} created ({ticket['priority']} priority, {ticket['category']}): " \
                      f"{ticket['title']}"
            findings.append(make_finding(AGENT, "ticket_created", summary, ticket, f"tickets/{ticket['id']}"))
            ctx.summary = f"Approved by reviewer{' with edits' if edits else ''}. {summary}"
        else:
            note = decision.get("note") or "no reason given"
            findings.append(make_finding(AGENT, "ticket_rejected", f"Reviewer rejected the ticket draft ({note})."))
            ctx.summary = f"Rejected by reviewer ({note}). No ticket created."

        ctx.details["decision"] = decision
        return {"findings": findings, "pending_action": None}

    return approval
