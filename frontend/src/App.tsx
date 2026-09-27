import { useCallback, useEffect, useRef, useState } from "react";
import { fetchHealth, fetchScenarios, fetchTickets, streamEvents } from "./api";
import { AgentTrace } from "./components/AgentTrace";
import { ApprovalCard } from "./components/ApprovalCard";
import { ChatPanel } from "./components/ChatPanel";
import { ScenarioPicker } from "./components/ScenarioPicker";
import type {
  AgentId,
  ChatMessage,
  CrewEvent,
  Scenario,
  Ticket,
  TicketDraft,
  TraceStep,
  TraceTurn,
} from "./types";

function updateLastTurn(turns: TraceTurn[], fn: (steps: TraceStep[]) => TraceStep[]): TraceTurn[] {
  if (!turns.length) return turns;
  const last = turns[turns.length - 1];
  return [...turns.slice(0, -1), { ...last, steps: fn(last.steps) }];
}

function findLastIndex(steps: TraceStep[], agent: AgentId, statuses: TraceStep["status"][]): number {
  for (let i = steps.length - 1; i >= 0; i--) {
    if (steps[i].agent === agent && statuses.includes(steps[i].status)) return i;
  }
  return -1;
}

export default function App() {
  const [provider, setProvider] = useState<string | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [turns, setTurns] = useState<TraceTurn[]>([]);
  const [activeAgent, setActiveAgent] = useState<AgentId | null>(null);
  const [pending, setPending] = useState<TicketDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const ids = useRef(0);

  useEffect(() => {
    fetchHealth().then((h) => setProvider(h.llm_provider)).catch(() => setProvider("offline"));
    fetchScenarios().then(setScenarios).catch(() => undefined);
    fetchTickets().then(setTickets).catch(() => undefined);
  }, []);

  const handleEvent = useCallback((e: CrewEvent) => {
    switch (e.type) {
      case "thread":
        setThreadId(e.thread_id);
        break;
      case "agent_start":
        setActiveAgent(e.agent);
        setTurns((t) =>
          updateLastTurn(t, (steps) => {
            const waiting = findLastIndex(steps, e.agent, ["waiting"]);
            if (waiting >= 0) {
              return steps.map((s, i) => (i === waiting ? { ...s, status: "running" } : s));
            }
            return [...steps, { id: ++ids.current, agent: e.agent, label: e.label, status: "running", tools: [] }];
          }),
        );
        break;
      case "tool_call":
        setTurns((t) =>
          updateLastTurn(t, (steps) => {
            const idx = findLastIndex(steps, e.agent, ["running"]);
            if (idx < 0) return steps;
            const { type: _type, agent: _agent, ...call } = e;
            return steps.map((s, i) => (i === idx ? { ...s, tools: [...s.tools, call] } : s));
          }),
        );
        break;
      case "agent_end":
        setTurns((t) =>
          updateLastTurn(t, (steps) => {
            const idx = findLastIndex(steps, e.agent, ["running"]);
            if (idx < 0) return steps;
            return steps.map((s, i) =>
              i === idx
                ? { ...s, status: "done", summary: e.summary, details: e.details, tools: e.tools, duration_ms: e.duration_ms }
                : s,
            );
          }),
        );
        break;
      case "approval_required":
        setPending(e.draft);
        setActiveAgent("approval");
        setTurns((t) =>
          updateLastTurn(t, (steps) => {
            const idx = findLastIndex(steps, "approval", ["running"]);
            return steps.map((s, i) =>
              i === idx ? { ...s, status: "waiting", summary: "Paused. A human must approve the ticket draft." } : s,
            );
          }),
        );
        break;
      case "final": {
        const critics = (e.trace as { agent: string }[]).filter((s) => s.agent === "critic").length;
        setMessages((m) => [
          ...m,
          { role: "assistant", content: e.reply, critique: e.critique, revisions: Math.max(0, critics - 1) },
        ]);
        setActiveAgent(null);
        break;
      }
      case "error":
        setMessages((m) => [...m, { role: "system", content: `Error: ${e.message}` }]);
        break;
      case "done":
        fetchTickets().then(setTickets).catch(() => undefined);
        break;
    }
  }, []);

  const run = useCallback(
    async (path: string, body: unknown) => {
      setBusy(true);
      try {
        await streamEvents(path, body, handleEvent);
      } catch (err) {
        setMessages((m) => [...m, { role: "system", content: String(err) }]);
      } finally {
        setBusy(false);
      }
    },
    [handleEvent],
  );

  const send = (message: string) => {
    if (busy || pending) return;
    setMessages((m) => [...m, { role: "user", content: message }]);
    setTurns((t) => [...t, { id: ++ids.current, message, steps: [] }]);
    void run("/api/chat", { message, thread_id: threadId });
  };

  const decide = (approved: boolean, edits: Partial<TicketDraft>, note?: string) => {
    if (!threadId) return;
    setPending(null);
    void run(`/api/threads/${threadId}/resume`, { approved, edits, note });
  };

  const reset = () => {
    setThreadId(null);
    setMessages([]);
    setTurns([]);
    setPending(null);
    setActiveAgent(null);
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img src="/favicon.svg" alt="" width={28} height={28} />
          <div>
            <h1>Triage Crew</h1>
            <p>Multi-agent support triage for Northwind Gear</p>
          </div>
        </div>
        <div className="topbar-actions">
          {provider && (
            <span className={`provider ${provider}`}>
              {provider === "demo" ? "Demo mode (no API key)" : provider === "offline" ? "API offline" : `LLM: ${provider}`}
            </span>
          )}
          <button className="btn ghost" onClick={reset} disabled={busy}>New incident</button>
        </div>
      </header>

      <main className="layout">
        <ChatPanel
          messages={messages}
          busy={busy}
          inputDisabled={busy || pending !== null}
          onSend={send}
          header={
            <>
              {messages.length === 0 && (
                <div className="hero">
                  <h2>One supervisor. Four specialists. A human in the loop.</h2>
                  <p>
                    Each message is triaged by a supervisor agent, routed to specialists that call real tools
                    (orders database, policy search, ticketing), checked by a critic for grounding, and paused
                    for your approval before anything is written.
                  </p>
                </div>
              )}
              <ScenarioPicker
                scenarios={scenarios}
                disabled={busy || pending !== null}
                compact={messages.length > 0}
                onPick={send}
              />
            </>
          }
          footer={pending && <ApprovalCard key={JSON.stringify(pending)} draft={pending} busy={busy} onDecide={decide} />}
        />
        <AgentTrace turns={turns} activeAgent={activeAgent} tickets={tickets} />
      </main>
    </div>
  );
}
