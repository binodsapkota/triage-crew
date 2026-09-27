from __future__ import annotations

import json
import re
from typing import Any

from app.graph.context import Deps, NodeContext, traced
from app.graph.state import user_messages
from app.llm.base import TriagePlan, order_specialists

AGENT = "critic"

# Order numbers, ticket IDs, and dollar amounts are the facts a support reply must never invent.
_FACT_RE = re.compile(r"\bT-\d{4}\b|#\d{4,6}\b|\$\d+(?:\.\d{2})?")


def grounding_issues(reply: str, findings: list[dict[str, Any]]) -> list[str]:
    corpus = " ".join(f"{f['summary']} {json.dumps(f.get('data', {}), default=str)}" for f in findings)
    ungrounded = sorted({fact for fact in _FACT_RE.findall(reply) if fact.lstrip("#") not in corpus})
    return [f"Reply states '{fact}', which no specialist finding supports." for fact in ungrounded]


def make_critic(deps: Deps):
    @traced(AGENT, "Critic")
    def critic(state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        reply = state["draft_reply"] or ""
        findings = state.get("findings", [])
        triage = TriagePlan(**state["triage"])
        review = deps.llm.critique(user_messages(state)[-1], triage, findings, reply)
        grounding = grounding_issues(reply, findings)
        issues = [*grounding, *review.issues]
        revisions = state.get("revisions", 0)

        critique = {
            "passed": not issues,
            "issues": issues,
            "grounded": not grounding,
            "suggested_agent": review.suggested_agent,
            "released_with_issues": False,
        }
        ctx.details["critique"] = critique

        if not issues:
            ctx.summary = "Approved: reply is grounded in findings and complete."
            return {"critique": critique, "route": "finalize"}

        if revisions >= deps.settings.max_revisions:
            critique["released_with_issues"] = True
            ctx.summary = f"Revision budget used; releasing with {len(issues)} open issue(s): {issues[0]}"
            return {"critique": critique, "route": "finalize"}

        plan = list(state.get("plan", []))
        completed = state.get("completed", [])
        if review.suggested_agent and review.suggested_agent not in completed:
            plan = order_specialists([*plan, review.suggested_agent])
        extra = f" Requested {review.suggested_agent}." if review.suggested_agent else ""
        ctx.summary = f"Sent back for revision: {'; '.join(issues)}{extra}"
        return {"critique": critique, "plan": plan, "revisions": revisions + 1, "route": "supervisor"}

    return critic
