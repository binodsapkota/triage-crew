"""Deterministic stand-in for an LLM so the whole crew runs offline, in CI, and in evals."""

from __future__ import annotations

import re

from app.llm.base import (
    CrewLLM,
    Critique,
    Finding,
    TicketDraft,
    TriagePlan,
    extract_entities,
    order_specialists,
)

INTENT_PATTERNS: dict[str, str] = {
    "order_status": r"where('s| is)|\blate\b|delay|track|arrive\b|arriving|(hasn'?t|not|never) arrived|"
    r"\beta\b|shipped|shipping status|hasn'?t (come|shown)|still waiting",
    "refund_return": r"refund|\breturn|exchange|money back|(doesn'?t|does not|didn'?t) fit|too (small|big|large)|"
    r"wrong size",
    "damaged_item": r"damag|broken|snapped|crack|torn|defect|stopped working|(doesn'?t|does not|won'?t) work|"
    r"not working|won'?t (charge|turn on)",
    "ticket_request": r"ticket|escalat|complain|open a case|file a (claim|case)|manager|speak to|follow up",
    "policy_question": r"polic|warrant|how long|how many days|do you (offer|have|cover|ship)|can i|"
    r"what('s| is) (the|your)|allowed|eligible|cover",
}

QUERY_EXPANSIONS: dict[str, str] = {
    "order_status": "late delayed delivery tracking",
    "refund_return": "return refund window",
    "damaged_item": "damaged broken defective replacement report",
    "policy_question": "",
    "ticket_request": "",
}

def _first_sentences(text: str, n: int = 2) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:n])


def _find(findings: list[Finding], kind: str) -> list[Finding]:
    return [f for f in findings if f["kind"] == kind]


def _order_sentence(o: dict) -> str:
    items = ", ".join(i["name"] for i in o["items"])
    head = f"Your order #{o['id']} ({items})"
    status = o.get("shipment_status")
    if status == "delayed":
        reason = o["delay_reason"][0].lower() + o["delay_reason"][1:]
        return (f"{head} is delayed with {o['carrier']}: {reason}. It was promised for {o['promised_date']}, "
                f"and the revised ETA is {o['eta']}.")
    if status == "delivered":
        return f"{head} was delivered on {o['delivered_at']} by {o['carrier']} ({o['last_scan'].lower()})."
    if status == "in_transit":
        return f"{head} is on its way with {o['carrier']} and should arrive by {o['eta']}."
    if status == "label_created":
        return f"{head} is being packed and should arrive by {o['eta']}."
    return f"{head} has status {o['status']}."


class DemoLLM(CrewLLM):
    name = "demo"

    def triage(self, message: str, history: list[str]) -> TriagePlan:
        text = message.lower()
        intents = [i for i, pattern in INTENT_PATTERNS.items() if re.search(pattern, text)]
        order_ids, customer_ids = extract_entities(message)
        if not order_ids and not customer_ids:
            for past in reversed(history):
                order_ids, customer_ids = extract_entities(past)
                if order_ids or customer_ids:
                    break

        agents: list[str] = []
        needs_facts = {"order_status", "refund_return", "damaged_item"} & set(intents)
        if order_ids or customer_ids or needs_facts:
            agents.append("order_agent")
        if {"order_status", "refund_return", "damaged_item", "policy_question"} & set(intents):
            agents.append("knowledge_agent")
        if "ticket_request" in intents:
            agents.append("ticket_agent")
        # A general policy question ("how many days...", "do you cover...") needs no order lookup
        # unless the customer referenced a specific order or account.
        if "policy_question" in intents and not (order_ids or customer_ids):
            agents = [a for a in agents if a != "order_agent"]

        query = " ".join([message, *(QUERY_EXPANSIONS[i] for i in intents)]).strip()
        ambiguous = not intents and not order_ids and not customer_ids
        agents = order_specialists(agents)
        reason = (
            "No actionable intent or identifiers found; ask the customer to clarify."
            if ambiguous
            else f"Detected {', '.join(intents) or 'an account lookup'}; consulting {', '.join(agents)}."
        )
        return TriagePlan(
            intents=intents,
            order_ids=order_ids,
            customer_ids=customer_ids,
            agents=agents,
            knowledge_query=query,
            ambiguous=ambiguous,
            reason=reason,
        )

    def write_reply(
        self, message: str, triage: TriagePlan, findings: list[Finding], feedback: list[str]
    ) -> str:
        orders = _find(findings, "order")
        name = orders[0]["data"]["customer_name"].split()[0] if orders else None
        lines = [f"Hi {name}," if name else "Hi there,"]

        if not findings:
            lines.append("Thanks for reaching out, and I'm sorry for the frustration.")
        for f in orders:
            lines.append(_order_sentence(f["data"]))
        for f in _find(findings, "order_not_found"):
            lines.append(f"I couldn't find that order in our system: {f['summary']}")
        for f in _find(findings, "customer_orders"):
            summary = ", ".join(f"#{o['id']} ({o['status']})" for o in f["data"]["orders"])
            lines.append(f"I found these recent orders on your account: {summary}.")
        for f in _find(findings, "policy"):
            lines.append(f"Our policy on {f['data']['section'].lower()} [{f['source']}]: "
                         f"{_first_sentences(f['data']['text'])}")
        for f in _find(findings, "ticket_created"):
            t = f["data"]
            lines.append(f"I've opened ticket {t['id']} ({t['priority']} priority) so our team can follow up.")
        for _ in _find(findings, "ticket_rejected"):
            lines.append("I haven't opened a ticket yet; a team member will review your request first.")

        if feedback:
            if triage.ambiguous or _find(findings, "order_missing") or _find(findings, "order_not_found"):
                lines.append(
                    "So I can help, could you share the order number from your confirmation email "
                    "and tell me which item is affected?"
                )
            else:
                lines.append("Let me know if there is anything else I can help with.")
        return "\n\n".join(lines).strip()

    def critique(self, message: str, triage: TriagePlan, findings: list[Finding], reply: str) -> Critique:
        issues: list[str] = []
        suggested = None
        asks_question = "?" in reply
        if triage.ambiguous and not asks_question:
            issues.append("The request is ambiguous; the reply should ask a clarifying question instead of guessing.")
        if _find(findings, "order_missing") and not asks_question:
            issues.append("Order details are needed but no order number was found; ask the customer for it.")
        if _find(findings, "order_not_found") and not asks_question:
            issues.append("The order number does not exist; ask the customer to double-check it.")
        has_ticket = bool(_find(findings, "ticket_created") or _find(findings, "ticket_rejected"))
        delivered = [f for f in _find(findings, "order") if f["data"].get("shipment_status") == "delivered"]
        if "damaged_item" in triage.intents and delivered and not has_ticket:
            issues.append("Damage and warranty policy require a ticket for delivered items reported "
                          "damaged or defective.")
            suggested = "ticket_agent"
        if "ticket_request" in triage.intents and not has_ticket:
            issues.append("The customer asked for a ticket but none was created or reviewed.")
            suggested = "ticket_agent"
        return Critique(passed=not issues, issues=issues, suggested_agent=suggested)

    def draft_ticket(self, message: str, triage: TriagePlan, findings: list[Finding]) -> TicketDraft:
        orders = _find(findings, "order")
        order = orders[0]["data"] if orders else None
        intents = set(triage.intents)
        if "damaged_item" in intents:
            physical = re.search(r"damag|broken|snapped|crack|torn", message.lower())
            category, what = ("damage", "Damaged delivery") if physical else ("warranty", "Defective item")
        elif "refund_return" in intents:
            category, what = "return", "Return request"
        elif "order_status" in intents:
            category, what = "shipping", "Delivery issue"
        else:
            category, what = "general", "Customer request"

        priority = "high" if category == "damage" else "medium"
        tier = order["customer_tier"] if order else None
        if tier == "platinum":
            priority = "urgent" if category == "damage" else "high"
        elif tier == "gold" and priority == "medium":
            priority = "high"

        item = order["items"][0]["name"] if order else None
        title = f"{what}: {item} (order #{order['id']})" if order else what
        facts = " ".join(f["summary"] for f in orders)
        summary = f'Customer wrote: "{message.strip()}" {facts}'.strip()
        return TicketDraft(
            title=title,
            category=category,
            priority=priority,
            summary=summary,
            customer_id=order["customer_id"] if order else (triage.customer_ids or [None])[0],
            order_id=order["id"] if order else (triage.order_ids or [None])[0],
        )
