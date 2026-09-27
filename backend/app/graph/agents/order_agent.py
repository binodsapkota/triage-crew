from __future__ import annotations

from typing import Any

from app.graph.context import Deps, NodeContext, traced
from app.graph.state import make_finding
from app.tools.orders import describe_order, get_order, list_orders

AGENT = "order_agent"
MAX_ORDERS = 3


def make_order_agent(deps: Deps):
    @traced(AGENT, "Order Agent")
    def order_agent(state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        triage = state["triage"]
        new: list[dict[str, Any]] = []

        if triage["order_ids"]:
            for oid in triage["order_ids"][:MAX_ORDERS]:
                order = ctx.tool("get_order", {"order_id": oid}, lambda oid=oid: get_order(deps.store, oid))
                if order:
                    new.append(make_finding(AGENT, "order", describe_order(order), order, f"orders/{oid}"))
                else:
                    new.append(make_finding(AGENT, "order_not_found", f"No order #{oid} exists in the system."))
        elif triage["customer_ids"]:
            cid = triage["customer_ids"][0]
            orders = ctx.tool("list_orders", {"customer_id": cid}, lambda: list_orders(deps.store, cid))
            summary = f"Customer {cid} has {len(orders)} recent orders: " + ", ".join(
                f"#{o['id']} ({o['status']})" for o in orders
            )
            new.append(make_finding(AGENT, "customer_orders", summary, {"customer_id": cid, "orders": orders}))
        else:
            new.append(make_finding(
                AGENT, "order_missing", "The customer did not provide an order number or customer ID."
            ))

        ctx.summary = " ".join(f["summary"] for f in new)
        return {
            "findings": [*state.get("findings", []), *new],
            "completed": [*state.get("completed", []), AGENT],
        }

    return order_agent
