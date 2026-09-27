"""Contracts between the graph and whichever model backs it (demo rules or a real LLM)."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field

Intent = Literal["order_status", "refund_return", "damaged_item", "ticket_request", "policy_question"]
SpecialistName = Literal["order_agent", "knowledge_agent", "ticket_agent"]
Priority = Literal["low", "medium", "high", "urgent"]

SPECIALIST_ORDER: tuple[str, ...] = ("order_agent", "knowledge_agent", "ticket_agent")

Finding = dict[str, Any]


class TriagePlan(BaseModel):
    """Supervisor's structured read of the customer message."""

    intents: list[Intent] = Field(default_factory=list, description="Every intent present in the message.")
    order_ids: list[str] = Field(default_factory=list, description="Order numbers mentioned, digits only.")
    customer_ids: list[str] = Field(default_factory=list, description="Customer IDs like C-101.")
    agents: list[SpecialistName] = Field(default_factory=list, description="Specialists to consult, in order.")
    knowledge_query: str = Field("", description="Search query for the policy knowledge base.")
    ambiguous: bool = Field(False, description="True when the request is too vague to act on.")
    reason: str = Field("", description="One sentence explaining the routing decision.")


class TicketDraft(BaseModel):
    title: str
    category: Literal["shipping", "return", "damage", "warranty", "general"]
    priority: Priority
    summary: str
    customer_id: str | None = None
    order_id: str | None = None


class Critique(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    suggested_agent: SpecialistName | None = Field(
        None, description="A specialist that should run before the reply is revised, if any."
    )


class CrewLLM(ABC):
    """Every model-backed decision the crew makes goes through this interface."""

    name: str

    @abstractmethod
    def triage(self, message: str, history: list[str]) -> TriagePlan: ...

    @abstractmethod
    def write_reply(
        self, message: str, triage: TriagePlan, findings: list[Finding], feedback: list[str]
    ) -> str: ...

    @abstractmethod
    def critique(self, message: str, triage: TriagePlan, findings: list[Finding], reply: str) -> Critique: ...

    @abstractmethod
    def draft_ticket(self, message: str, triage: TriagePlan, findings: list[Finding]) -> TicketDraft: ...


_ORDER_RE = re.compile(r"(?:order\s*(?:number|no\.?)?\s*#?\s*|#)(\d{4,6})\b|\b(10\d{2})\b", re.I)
_CUSTOMER_RE = re.compile(r"\bC-\d{3}\b", re.I)


def extract_entities(text: str) -> tuple[list[str], list[str]]:
    """Deterministic ID extraction. Also used to backstop LLM triage so IDs are never hallucinated away."""
    orders: list[str] = []
    for a, b in _ORDER_RE.findall(text):
        oid = a or b
        if oid not in orders:
            orders.append(oid)
    customers = list(dict.fromkeys(c.upper() for c in _CUSTOMER_RE.findall(text)))
    return orders, customers


def order_specialists(agents: list[str]) -> list[str]:
    """Canonical execution order: facts first, policy second, write actions last."""
    unique = set(agents)
    return [a for a in SPECIALIST_ORDER if a in unique]
