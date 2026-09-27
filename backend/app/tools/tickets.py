from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.data.store import Store

PRIORITIES = ("low", "medium", "high", "urgent")


def _next_id(store: Store) -> str:
    rows = store.query("SELECT id FROM tickets")
    highest = max((int(r["id"].split("-")[1]) for r in rows), default=1000)
    return f"T-{highest + 1}"


def create_ticket(store: Store, draft: dict[str, Any]) -> dict[str, Any]:
    priority = draft.get("priority", "medium")
    if priority not in PRIORITIES:
        priority = "medium"
    ticket = {
        "id": _next_id(store),
        "customer_id": draft.get("customer_id"),
        "order_id": draft.get("order_id"),
        "title": draft.get("title") or "Support request",
        "category": draft.get("category") or "general",
        "priority": priority,
        "summary": draft.get("summary") or "",
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    store.execute(
        "INSERT INTO tickets (id, customer_id, order_id, title, category, priority, summary, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuple(ticket.values()),
    )
    return ticket


def list_tickets(store: Store, limit: int = 20) -> list[dict[str, Any]]:
    return store.query("SELECT * FROM tickets ORDER BY created_at DESC, id DESC LIMIT ?", (limit,))
