import type { AgentId } from "./types";

export interface AgentMeta {
  name: string;
  badge: string;
  role: string;
  color: string;
}

export const AGENTS: Record<AgentId, AgentMeta> = {
  supervisor: { name: "Supervisor", badge: "SUP", role: "Triage and routing", color: "#8b7bff" },
  order_agent: { name: "Order Agent", badge: "ORD", role: "Orders and shipping", color: "#4da3ff" },
  knowledge_agent: { name: "Knowledge Agent", badge: "KB", role: "Policy search (BM25)", color: "#2ec4a6" },
  ticket_agent: { name: "Ticket Agent", badge: "TKT", role: "Drafts tickets", color: "#f5b543" },
  approval: { name: "Human Approval", badge: "HITL", role: "Approves write actions", color: "#ff8a4c" },
  critic: { name: "Critic", badge: "QA", role: "Grounding and completeness", color: "#ff6b9a" },
  finalize: { name: "Final Reply", badge: "OUT", role: "Sends the answer", color: "#7ed957" },
};

export const ROSTER: AgentId[] = [
  "supervisor",
  "order_agent",
  "knowledge_agent",
  "ticket_agent",
  "approval",
  "critic",
];
