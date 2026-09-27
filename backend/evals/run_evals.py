"""Golden-set evaluation for the crew.

Usage (from backend/):
    python -m evals.run_evals                 # demo mode, used in CI
    LLM_PROVIDER=openai python -m evals.run_evals --min-routing 0.8

Metrics:
    routing accuracy   specialists that actually ran == expected set
    grounded rate      critic found no invented order numbers, ticket IDs, or amounts
    mention rate       reply contains every must_mention string
    ticket accuracy    a ticket was proposed exactly when expected (HITL auto-approved here)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from app.config import Settings
from app.graph.build import build_default
from app.graph.runner import CrewRunner

GOLDEN = Path(__file__).with_name("golden.json")
SPECIALISTS = {"order_agent", "knowledge_agent", "ticket_agent"}


def run_case(runner: CrewRunner, case: dict) -> dict:
    start = time.perf_counter()
    events = list(runner.start(case["id"], case["message"]))
    proposed_ticket = False
    while events and events[-1]["type"] == "approval_required":
        proposed_ticket = True
        events += list(runner.resume(case["id"], {"approved": True}))
    latency = (time.perf_counter() - start) * 1000

    final = next(e for e in events if e["type"] == "final")
    ran = {e["agent"] for e in events if e["type"] == "agent_end"} & SPECIALISTS
    expected = set(case["expected_agents"])
    reply = final["reply"] or ""
    missing = [m for m in case.get("must_mention", []) if m.lower() not in reply.lower()]
    return {
        "id": case["id"],
        "routing_ok": ran == expected,
        "ran": sorted(ran),
        "expected": sorted(expected),
        "grounded": bool(final["critique"] and final["critique"]["grounded"]),
        "mentions_ok": not missing,
        "missing": missing,
        "ticket_ok": proposed_ticket == case.get("expect_ticket", False),
        "latency_ms": latency,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-routing", type=float, default=0.9)
    parser.add_argument("--json", type=Path, help="Write per-case results to this file.")
    args = parser.parse_args()

    settings = Settings()
    graph, deps = build_default(settings, persistent=False)
    runner = CrewRunner(graph)
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
    results = [run_case(runner, c) for c in cases]

    def rate(key: str) -> float:
        return sum(r[key] for r in results) / len(results)

    metrics = {
        "Routing accuracy": rate("routing_ok"),
        "Grounded replies": rate("grounded"),
        "Required facts mentioned": rate("mentions_ok"),
        "Ticket proposal accuracy": rate("ticket_ok"),
    }
    avg_latency = sum(r["latency_ms"] for r in results) / len(results)

    print(f"\nTriage Crew evals  |  provider={deps.llm.name}  |  cases={len(results)}\n")
    print("| Metric | Score |\n|---|---|")
    for name, value in metrics.items():
        print(f"| {name} | {value:.0%} |")
    print(f"| Avg latency per case | {avg_latency:.0f} ms |\n")

    failures = [r for r in results if not (r["routing_ok"] and r["grounded"] and r["mentions_ok"] and r["ticket_ok"])]
    for r in failures:
        print(f"FAIL {r['id']}: ran={r['ran']} expected={r['expected']} missing={r['missing']} "
              f"grounded={r['grounded']} ticket_ok={r['ticket_ok']}")

    if args.json:
        args.json.write_text(json.dumps({"metrics": metrics, "results": results}, indent=2), encoding="utf-8")

    return 0 if metrics["Routing accuracy"] >= args.min_routing else 1


if __name__ == "__main__":
    sys.exit(main())
