"""Supervisor: the LLM plans once per turn, then deterministic routing executes the plan."""

from __future__ import annotations

from typing import Any

from app.graph.context import Deps, NodeContext, traced
from app.graph.state import user_messages
from app.llm.base import TriagePlan


def make_supervisor(deps: Deps):
    @traced("supervisor", "Supervisor")
    def supervisor(state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        steps = state.get("steps", 0) + 1
        messages = user_messages(state)
        message, history = messages[-1], messages[:-1]
        findings = state.get("findings", [])
        update: dict[str, Any] = {"steps": steps}

        triage_data = state.get("triage")
        plan = list(state.get("plan", []))
        if triage_data is None:
            triage = deps.llm.triage(message, history)
            triage_data, plan = triage.model_dump(), list(triage.agents)
            update |= {"triage": triage_data, "plan": plan}
            ctx.details["triage"] = triage_data
        triage = TriagePlan(**triage_data)

        if steps > deps.settings.max_supervisor_steps:
            reply = state.get("draft_reply") or deps.llm.write_reply(message, triage, findings, [])
            ctx.summary = f"Step budget ({deps.settings.max_supervisor_steps}) exhausted; releasing best reply."
            return update | {"draft_reply": reply, "route": "finalize"}

        completed = state.get("completed", [])
        pending = [a for a in plan if a not in completed]
        if pending:
            nxt = pending[0]
            position = plan.index(nxt) + 1
            prefix = f"{triage.reason} " if "triage" in update else ""
            ctx.summary = f"{prefix}Routing to {nxt} (step {position} of {len(plan)})."
            ctx.details["route"] = nxt
            return update | {"route": nxt}

        critique = state.get("critique")
        feedback = critique["issues"] if critique and not critique["passed"] else []
        reply = deps.llm.write_reply(message, triage, findings, feedback)
        ctx.details["route"] = "critic"
        if feedback:
            ctx.summary = f"Revised the reply to address {len(feedback)} critic issue(s); sending back for review."
        elif not plan:
            ctx.summary = f"{triage.reason} Drafted a reply and sent it to the critic."
        else:
            ctx.summary = f"All specialists reported ({len(findings)} findings). Drafted reply for the critic."
        return update | {"draft_reply": reply, "route": "critic"}

    return supervisor
