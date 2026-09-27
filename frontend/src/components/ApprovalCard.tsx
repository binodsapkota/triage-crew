import { useState } from "react";
import type { TicketDraft } from "../types";

interface Props {
  draft: TicketDraft;
  busy: boolean;
  onDecide: (approved: boolean, edits: Partial<TicketDraft>, note?: string) => void;
}

const PRIORITIES: TicketDraft["priority"][] = ["low", "medium", "high", "urgent"];

export function ApprovalCard({ draft, busy, onDecide }: Props) {
  const [title, setTitle] = useState(draft.title);
  const [priority, setPriority] = useState(draft.priority);
  const [summary, setSummary] = useState(draft.summary);
  const [note, setNote] = useState("");

  const edits: Partial<TicketDraft> = {};
  if (title !== draft.title) edits.title = title;
  if (priority !== draft.priority) edits.priority = priority;
  if (summary !== draft.summary) edits.summary = summary;

  return (
    <div className="approval">
      <div className="approval-head">
        <span className="badge" style={{ background: "#ff8a4c" }}>HITL</span>
        <div>
          <div className="approval-title">Approval required: create support ticket</div>
          <div className="approval-sub">
            The Ticket Agent drafted this. Nothing is written until you approve.
          </div>
        </div>
      </div>

      <label className="field">
        <span>Title</span>
        <input value={title} onChange={(e) => setTitle(e.target.value)} disabled={busy} />
      </label>
      <div className="field-row">
        <label className="field">
          <span>Priority</span>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as TicketDraft["priority"])}
            disabled={busy}
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Category</span>
          <input value={draft.category} disabled />
        </label>
        <label className="field">
          <span>Order</span>
          <input value={draft.order_id ? `#${draft.order_id}` : "none"} disabled />
        </label>
      </div>
      <label className="field">
        <span>Summary</span>
        <textarea rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} disabled={busy} />
      </label>
      <label className="field">
        <span>Reviewer note (used if rejected)</span>
        <input
          value={note}
          placeholder="e.g. duplicate of an existing ticket"
          onChange={(e) => setNote(e.target.value)}
          disabled={busy}
        />
      </label>

      <div className="approval-actions">
        <button className="btn ghost" disabled={busy} onClick={() => onDecide(false, {}, note || undefined)}>
          Reject
        </button>
        <button className="btn primary" disabled={busy} onClick={() => onDecide(true, edits)}>
          {Object.keys(edits).length ? "Approve with edits" : "Approve and create"}
        </button>
      </div>
    </div>
  );
}
