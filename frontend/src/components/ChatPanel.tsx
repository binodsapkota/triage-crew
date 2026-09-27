import { useEffect, useRef, useState, type ReactNode } from "react";
import type { ChatMessage } from "../types";

interface Props {
  messages: ChatMessage[];
  busy: boolean;
  inputDisabled: boolean;
  onSend: (message: string) => void;
  header?: ReactNode;
  footer?: ReactNode;
}

function renderContent(text: string) {
  const parts = text.split(/(\[[\w.-]+\.md\])/g);
  return parts.map((part, i) =>
    /^\[[\w.-]+\.md\]$/.test(part) ? (
      <span key={i} className="cite">{part.slice(1, -1)}</span>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

function CritiqueBadge({ message }: { message: ChatMessage }) {
  if (!message.critique) return null;
  const { critique, revisions = 0 } = message;
  const label = critique.released_with_issues
    ? "Released with open issues"
    : revisions > 0
      ? `Critic approved after ${revisions} revision${revisions > 1 ? "s" : ""}`
      : "Critic approved";
  return (
    <div className={`critique ${critique.released_with_issues ? "warn" : "ok"}`}>
      {label}
      {critique.grounded ? " · grounded in findings" : " · grounding issues"}
    </div>
  );
}

export function ChatPanel({ messages, busy, inputDisabled, onSend, header, footer }: Props) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, footer]);

  const submit = () => {
    const text = draft.trim();
    if (!text || inputDisabled) return;
    onSend(text);
    setDraft("");
  };

  return (
    <section className="chat">
      <div className="chat-scroll">
        {header}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="msg-role">{m.role === "user" ? "Customer" : m.role === "assistant" ? "Triage Crew" : "System"}</div>
            <div className="msg-body">{renderContent(m.content)}</div>
            {m.role === "assistant" && <CritiqueBadge message={m} />}
          </div>
        ))}
        {busy && <div className="typing">Crew is working<span>.</span><span>.</span><span>.</span></div>}
        {footer}
        <div ref={endRef} />
      </div>
      <div className="composer">
        <textarea
          rows={2}
          value={draft}
          placeholder={inputDisabled ? "Resolve the approval above to continue" : "Describe a customer issue..."}
          disabled={inputDisabled}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button className="btn primary" disabled={inputDisabled || !draft.trim()} onClick={submit}>
          Send
        </button>
      </div>
    </section>
  );
}
