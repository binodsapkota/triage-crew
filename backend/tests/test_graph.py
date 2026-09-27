from app.llm.base import Critique
from app.llm.demo import DemoLLM
from tests.conftest import agents_run, final


def test_late_order_consults_order_and_knowledge(run):
    _, events = run("Where is my order 1042? It was supposed to arrive last week.")
    assert agents_run(events) == [
        "supervisor", "order_agent", "supervisor", "knowledge_agent", "supervisor", "critic",
    ]
    result = final(events)
    assert result["critique"]["passed"]
    assert "#1042" in result["reply"] and "[shipping.md]" in result["reply"]


def test_tool_calls_are_streamed(run):
    _, events = run("Where is my order 1042?")
    tools = [e["tool"] for e in events if e["type"] == "tool_call"]
    assert tools == ["get_order", "search_policies"]


def test_ticket_requires_human_approval(crew, run):
    runner, deps = crew
    tid, events = run("Order 1047 arrived damaged, one tent pole is snapped. Please open a ticket.")
    assert events[-1]["type"] == "approval_required"
    assert events[-1]["draft"]["priority"] == "urgent"  # platinum customer + damage
    assert not any(e["type"] == "final" for e in events)
    assert deps.store.query("SELECT * FROM tickets") == []

    resumed = list(runner.resume(tid, {"approved": True, "edits": {"priority": "high"}}))
    tickets = deps.store.query("SELECT * FROM tickets")
    assert len(tickets) == 1 and tickets[0]["priority"] == "high"
    assert "T-1001" in final(resumed)["reply"]
    assert runner.pending_approval(tid) is None


def test_rejected_ticket_is_not_created(crew, run):
    runner, deps = crew
    tid, _ = run("Please open a ticket about order 1043")
    resumed = list(runner.resume(tid, {"approved": False, "note": "duplicate"}))
    assert deps.store.query("SELECT * FROM tickets") == []
    assert "haven't opened a ticket" in final(resumed)["reply"]


def test_critic_forces_clarifying_question(run):
    _, events = run("It stopped working again and honestly I'm done with this.")
    critics = [e for e in events if e["type"] == "agent_end" and e["agent"] == "critic"]
    assert len(critics) == 2
    assert "Sent back for revision" in critics[0]["summary"]
    result = final(events)
    assert result["critique"]["passed"] and "?" in result["reply"]


def test_critic_can_add_a_specialist(run):
    # Damage reported on a delivered order without asking for a ticket: policy says open one anyway.
    _, events = run("My order 1047 arrived damaged.")
    assert events[-1]["type"] == "approval_required"
    critic = next(e for e in events if e["type"] == "agent_end" and e["agent"] == "critic")
    assert "ticket_agent" in critic["summary"]


def test_follow_up_turn_resets_working_memory(crew, run):
    runner, _ = crew
    tid, _ = run("Where is my order 1042?")
    _, events = run("Thanks. What is your return window?", thread_id=tid)
    result = final(events)
    assert [f["kind"] for f in result["findings"]].count("order") == 1
    assert len(runner.history(tid)["messages"]) == 4


class StubbornCritic(DemoLLM):
    def critique(self, message, triage, findings, reply):
        return Critique(passed=False, issues=["never satisfied"])


def test_revision_budget_releases_reply(settings):
    from app.graph.build import build_default
    from app.graph.runner import CrewRunner

    graph, _ = build_default(settings, llm=StubbornCritic(), persistent=False)
    events = list(CrewRunner(graph).start("t", "What's your warranty on boots?"))
    result = final(events)
    assert result["critique"]["released_with_issues"]
    assert result["reply"]
