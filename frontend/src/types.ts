export type AgentId =
  | "supervisor"
  | "order_agent"
  | "knowledge_agent"
  | "ticket_agent"
  | "approval"
  | "critic"
  | "finalize";

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  result_preview: string;
  duration_ms: number;
}

export interface TicketDraft {
  title: string;
  category: string;
  priority: "low" | "medium" | "high" | "urgent";
  summary: string;
  customer_id: string | null;
  order_id: string | null;
}

export interface Critique {
  passed: boolean;
  issues: string[];
  grounded: boolean;
  suggested_agent: string | null;
  released_with_issues: boolean;
}

export type CrewEvent =
  | { type: "thread"; thread_id: string }
  | { type: "agent_start"; agent: AgentId; label: string; started_at: string }
  | ({ type: "tool_call"; agent: AgentId } & ToolCall)
  | {
      type: "agent_end";
      agent: AgentId;
      label: string;
      summary: string;
      details: Record<string, unknown>;
      tools: ToolCall[];
      duration_ms: number;
    }
  | { type: "approval_required"; thread_id: string; kind: string; draft: TicketDraft }
  | {
      type: "final";
      thread_id: string;
      reply: string;
      critique: Critique | null;
      trace: unknown[];
    }
  | { type: "error"; message: string }
  | { type: "done" };

export type StepStatus = "running" | "done" | "waiting";

export interface TraceStep {
  id: number;
  agent: AgentId;
  label: string;
  status: StepStatus;
  summary?: string;
  details?: Record<string, unknown>;
  tools: ToolCall[];
  duration_ms?: number;
}

export interface TraceTurn {
  id: number;
  message: string;
  steps: TraceStep[];
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  critique?: Critique | null;
  revisions?: number;
}

export interface Scenario {
  id: string;
  title: string;
  message: string;
  highlights: string;
}

export interface Ticket {
  id: string;
  title: string;
  priority: string;
  category: string;
  order_id: string | null;
  created_at: string;
}
