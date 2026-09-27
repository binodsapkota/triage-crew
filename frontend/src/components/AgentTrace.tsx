import { useEffect, useRef, useState } from "react";
import { AGENTS, ROSTER } from "../agents";
import type { AgentId, Ticket, TraceStep, TraceTurn } from "../types";

interface Props {
  turns: TraceTurn[];
  activeAgent: AgentId | null;
  tickets: Ticket[];
}

function Roster({ turns, activeAgent }: { turns: TraceTurn[]; activeAgent: AgentId | null }) {
  const last = turns[turns.length - 1];
  const used = new Set(last?.steps.map((s) => s.agent));
  return (
    <div className="roster">
      {ROSTER.map((id) => {
        const meta = AGENTS[id];
        const state = activeAgent === id ? "active" : used.has(id) ? "used" : "idle";
        return (
          <div key={id} className={`roster-item ${state}`} title={meta.role}>
            <span className="badge" style={{ background: meta.color }}>{meta.badge}</span>
            <span className="roster-name">{meta.name}</span>
          </div>
        );
      })}
    </div>
  );
}

function StepDetails({ step }: { step: TraceStep }) {
  const triage = step.details?.triage as Record<string, unknown> | undefined;
  const draft = step.details?.draft as Record<string, unknown> | undefined;
  const critique = step.details?.critique as { issues?: string[] } | undefined;
  return (
    <div className="step-details">
      {triage && (
        <dl>
          <dt>intents</dt><dd>{(triage.intents as string[]).join(", ") || "none"}</dd>
          <dt>orders</dt><dd>{(triage.order_ids as string[]).join(", ") || "none"}</dd>
          <dt>plan</dt><dd>{(triage.agents as string[]).join(" → ") || "reply directly"}</dd>
        </dl>
      )}
      {draft && (
        <dl>
          <dt>title</dt><dd>{String(draft.title)}</dd>
          <dt>priority</dt><dd>{String(draft.priority)}</dd>
        </dl>
      )}
      {critique?.issues?.length ? (
        <ul className="issues">{critique.issues.map((i) => <li key={i}>{i}</li>)}</ul>
      ) : null}
      {step.tools.map((t, i) => (
        <div key={i} className="tool">
          <div className="tool-head">
            <code>{t.tool}({Object.entries(t.args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})</code>
            <span className="muted">{t.duration_ms} ms</span>
          </div>
          <pre>{t.result_preview}</pre>
        </div>
      ))}
    </div>
  );
}

function Step({ step }: { step: TraceStep }) {
  const [open, setOpen] = useState(false);
  const meta = AGENTS[step.agent];
  const expandable = step.tools.length > 0 || Object.keys(step.details ?? {}).length > 0;
  return (
    <li className={`step ${step.status}`} style={{ ["--agent" as string]: meta.color }}>
      <div className="step-dot" />
      <div className="step-card">
        <button className="step-head" onClick={() => expandable && setOpen(!open)} disabled={!expandable}>
          <span className="badge" style={{ background: meta.color }}>{meta.badge}</span>
          <span className="step-label">{step.label}</span>
          {step.tools.length > 0 && <span className="chip">{step.tools.length} tool{step.tools.length > 1 ? "s" : ""}</span>}
          <span className="step-time">
            {step.status === "running" ? "running" : step.status === "waiting" ? "waiting for you" : `${step.duration_ms} ms`}
          </span>
        </button>
        {step.summary && <div className="step-summary">{step.summary}</div>}
        {open && <StepDetails step={step} />}
      </div>
    </li>
  );
}

export function AgentTrace({ turns, activeAgent, tickets }: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  return (
    <aside className="trace">
      <div className="trace-header">
        <h2>Agent trace</h2>
        <span className="muted">Who did what, live</span>
      </div>
      <Roster turns={turns} activeAgent={activeAgent} />
      <div className="trace-scroll">
        {turns.length === 0 && (
          <div className="empty">
            Pick an incident. You will see the supervisor triage it, specialists call tools, and the critic
            review the reply before it is sent.
          </div>
        )}
        {turns.map((turn) => (
          <div key={turn.id} className="turn">
            <div className="turn-message">"{turn.message}"</div>
            <ol className="timeline">
              {turn.steps.map((s) => <Step key={s.id} step={s} />)}
            </ol>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      {tickets.length > 0 && (
        <div className="tickets">
          <h3>Tickets created</h3>
          {tickets.slice(0, 4).map((t) => (
            <div key={t.id} className="ticket">
              <span className={`prio ${t.priority}`}>{t.priority}</span>
              <span className="ticket-id">{t.id}</span>
              <span className="ticket-title">{t.title}</span>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
