"""Real-model implementation for any OpenAI-compatible endpoint (OpenAI, Azure-compatible gateways, Ollama)."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.llm.base import (
    CrewLLM,
    Critique,
    Finding,
    TicketDraft,
    TriagePlan,
    extract_entities,
    order_specialists,
)
from app.llm.demo import DemoLLM

log = logging.getLogger(__name__)

TRIAGE_PROMPT = """You are the supervisor of a customer-support crew for Northwind Gear, an outdoor store.
Classify the customer's latest message and decide which specialists to consult.

Specialists:
- order_agent: looks up orders, shipments, and customer accounts. Use when an order/customer ID is present
  or the issue concerns a specific purchase (delivery, refund, damage).
- knowledge_agent: searches store policies (shipping, returns, damage, warranty, loyalty).
- ticket_agent: drafts a support ticket for human approval. Use only when the customer asks for a ticket,
  escalation, or follow-up.

Set ambiguous=true only if the message has no actionable request and no identifiers.
Write knowledge_query as a short keyword query for the policy search."""

REPLY_PROMPT = """You are the lead support agent for Northwind Gear writing the final reply to a customer.
Rules:
- Use ONLY facts from the findings JSON. Never invent order numbers, dates, amounts, or ticket IDs.
- Cite policies inline as [source-file.md].
- If findings show the order number is missing or the request is ambiguous, ask a clarifying question.
- If a ticket was created, give its ID and priority. If rejected, say a team member will review first.
- Warm, concise, under 150 words. Address the customer by first name when known."""

CRITIC_PROMPT = """You are a QA reviewer for customer-support replies. Check the draft reply against the findings.
Fail the reply if it: states facts not supported by findings, ignores a policy that applies, fails to ask
for missing information, or skips a ticket the customer requested (or that damage policy requires for a
delivered damaged item). If a specialist must run first, set suggested_agent. Be strict but brief."""

TICKET_PROMPT = """Draft a support ticket from the customer message and findings.
Priority rules: damaged deliveries are high; platinum customers get urgent for damage and at least high
otherwise; gold customers get at least high. Title under 80 characters and includes the order number
when known. Summary quotes the customer and lists the verified facts."""


def _context(message: str, triage: TriagePlan, findings: list[Finding], **extra) -> str:
    payload = {
        "customer_message": message,
        "triage": triage.model_dump(),
        "findings": [{k: f.get(k) for k in ("agent", "kind", "summary", "source")} for f in findings],
        **extra,
    }
    return json.dumps(payload, indent=2, default=str)


class OpenAILLM(CrewLLM):
    name = "openai"

    def __init__(self, model: str, api_key: str | None, base_url: str | None, temperature: float = 0.0):
        self.model = ChatOpenAI(
            model=model, api_key=api_key or "not-needed", base_url=base_url, temperature=temperature, timeout=60
        )
        self._fallback = DemoLLM()

    def _structured(self, schema, system: str, user: str):
        # function_calling is the most widely supported structured-output mode across compatible servers.
        runnable = self.model.with_structured_output(schema, method="function_calling")
        return runnable.invoke([SystemMessage(system), HumanMessage(user)])

    def triage(self, message: str, history: list[str]) -> TriagePlan:
        try:
            recent = "\n".join(f"- {h}" for h in history[-4:]) or "(none)"
            plan: TriagePlan = self._structured(
                TriagePlan, TRIAGE_PROMPT, f"Earlier customer messages:\n{recent}\n\nLatest message:\n{message}"
            )
        except Exception:
            log.exception("LLM triage failed; falling back to rules")
            return self._fallback.triage(message, history)
        orders, customers = extract_entities(message)
        plan.order_ids = list(dict.fromkeys([*orders, *plan.order_ids]))
        plan.customer_ids = list(dict.fromkeys([*customers, *plan.customer_ids]))
        plan.agents = order_specialists(plan.agents)
        return plan

    def write_reply(
        self, message: str, triage: TriagePlan, findings: list[Finding], feedback: list[str]
    ) -> str:
        try:
            user = _context(message, triage, findings, reviewer_feedback=feedback or None)
            return str(self.model.invoke([SystemMessage(REPLY_PROMPT), HumanMessage(user)]).content).strip()
        except Exception:
            log.exception("LLM reply failed; falling back to template")
            return self._fallback.write_reply(message, triage, findings, feedback)

    def critique(self, message: str, triage: TriagePlan, findings: list[Finding], reply: str) -> Critique:
        try:
            return self._structured(Critique, CRITIC_PROMPT, _context(message, triage, findings, draft_reply=reply))
        except Exception:
            log.exception("LLM critique failed; falling back to rules")
            return self._fallback.critique(message, triage, findings, reply)

    def draft_ticket(self, message: str, triage: TriagePlan, findings: list[Finding]) -> TicketDraft:
        try:
            return self._structured(TicketDraft, TICKET_PROMPT, _context(message, triage, findings))
        except Exception:
            log.exception("LLM ticket draft failed; falling back to rules")
            return self._fallback.draft_ticket(message, triage, findings)
