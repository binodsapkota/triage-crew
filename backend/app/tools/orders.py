from __future__ import annotations

import json
from typing import Any

from app.data.store import Store

_ORDER_SQL = """
SELECT o.id, o.customer_id, o.status, o.placed_at, o.total, o.items,
       c.name AS customer_name, c.tier AS customer_tier,
       s.carrier, s.tracking, s.status AS shipment_status, s.promised_date, s.eta,
       s.delivered_at, s.last_scan, s.delay_reason
FROM orders o
JOIN customers c ON c.id = o.customer_id
LEFT JOIN shipments s ON s.order_id = o.id
"""


def _hydrate(store: Store, row: dict[str, Any]) -> dict[str, Any]:
    items = json.loads(row.pop("items"))
    skus = [i["sku"] for i in items]
    placeholders = ",".join("?" for _ in skus)
    names = {
        p["sku"]: p["name"]
        for p in store.query(f"SELECT sku, name FROM products WHERE sku IN ({placeholders})", tuple(skus))
    }
    row["items"] = [{"sku": i["sku"], "name": names.get(i["sku"], i["sku"]), "qty": i["qty"]} for i in items]
    return row


def get_order(store: Store, order_id: str) -> dict[str, Any] | None:
    rows = store.query(_ORDER_SQL + " WHERE o.id = ?", (str(order_id),))
    return _hydrate(store, rows[0]) if rows else None


def list_orders(store: Store, customer_id: str, limit: int = 5) -> list[dict[str, Any]]:
    rows = store.query(
        _ORDER_SQL + " WHERE o.customer_id = ? ORDER BY o.placed_at DESC LIMIT ?",
        (customer_id.upper(), limit),
    )
    return [_hydrate(store, r) for r in rows]


def describe_order(order: dict[str, Any]) -> str:
    """One-paragraph factual summary used as an agent finding."""
    items = ", ".join(f"{i['name']} x{i['qty']}" for i in order["items"])
    parts = [
        f"Order #{order['id']} for {order['customer_name']} ({order['customer_id']}, {order['customer_tier']} tier)"
        f" contains {items}; status is {order['status']}."
    ]
    status = order.get("shipment_status")
    if status == "delivered":
        parts.append(f"Delivered on {order['delivered_at']} by {order['carrier']} ({order['last_scan']}).")
    elif status == "delayed":
        parts.append(
            f"Shipment via {order['carrier']} is delayed: {order['delay_reason']}. "
            f"Promised {order['promised_date']}, revised ETA {order['eta']}. Last scan: {order['last_scan']}."
        )
    elif status == "in_transit":
        parts.append(f"In transit with {order['carrier']}, ETA {order['eta']}. Last scan: {order['last_scan']}.")
    elif status == "label_created":
        parts.append(f"Label created, not yet handed to {order['carrier']}. Expected delivery {order['eta']}.")
    return " ".join(parts)
