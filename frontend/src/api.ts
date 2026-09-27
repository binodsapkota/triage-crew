import type { CrewEvent, Scenario, Ticket } from "./types";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const fetchHealth = () => getJson<{ status: string; llm_provider: string }>("/api/health");
export const fetchScenarios = () => getJson<Scenario[]>("/api/scenarios");
export const fetchTickets = () => getJson<Ticket[]>("/api/tickets");

/** POST that returns a server-sent event stream; EventSource only supports GET, so parse manually. */
export async function streamEvents(
  path: string,
  body: unknown,
  onEvent: (event: CrewEvent) => void,
): Promise<void> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Request failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice(6))
        .join("\n");
      if (data) onEvent(JSON.parse(data) as CrewEvent);
    }
  }
}
