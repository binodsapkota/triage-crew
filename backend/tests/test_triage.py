import pytest

from app.graph.agents.critic_agent import grounding_issues
from app.llm.base import extract_entities
from app.llm.demo import DemoLLM


@pytest.mark.parametrize(
    ("message", "agents"),
    [
        ("Where is my order 1042?", ["order_agent", "knowledge_agent"]),
        ("I want a refund for order #1045", ["order_agent", "knowledge_agent"]),
        ("What's your warranty on tents?", ["knowledge_agent"]),
        ("Order 1047 arrived damaged, open a ticket", ["order_agent", "knowledge_agent", "ticket_agent"]),
        ("Show recent orders for C-102", ["order_agent"]),
        ("hello", []),
    ],
)
def test_demo_triage_routes(message, agents):
    assert DemoLLM().triage(message, []).agents == agents


def test_triage_flags_ambiguous():
    plan = DemoLLM().triage("ugh, seriously", [])
    assert plan.ambiguous and plan.agents == []


def test_triage_uses_history_for_follow_ups():
    plan = DemoLLM().triage("please open a ticket for that", ["Where is my order 1042?"])
    assert plan.order_ids == ["1042"]
    assert plan.agents == ["order_agent", "ticket_agent"]


def test_extract_entities():
    assert extract_entities("order #1042 and 1043 for c-101") == (["1042", "1043"], ["C-101"])
    assert extract_entities("30 days, 2026 season") == ([], [])


def test_grounding_flags_invented_facts():
    findings = [{"summary": "Order #1042 is delayed", "data": {"id": "1042"}}]
    assert grounding_issues("Your order #1042 is delayed.", findings) == []
    issues = grounding_issues("Order #1042 is delayed; I opened T-1009 and refunded $40.", findings)
    assert len(issues) == 2
