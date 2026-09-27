import type { Scenario } from "../types";

interface Props {
  scenarios: Scenario[];
  disabled: boolean;
  compact: boolean;
  onPick: (message: string) => void;
}

export function ScenarioPicker({ scenarios, disabled, compact, onPick }: Props) {
  if (!scenarios.length) return null;
  return (
    <div className={`scenarios${compact ? " compact" : ""}`}>
      <div className="scenarios-label">{compact ? "More incidents" : "Try a real-world incident"}</div>
      <div className="scenario-list">
        {scenarios.map((s) => (
          <button
            key={s.id}
            className="scenario"
            disabled={disabled}
            onClick={() => onPick(s.message)}
            title={s.message}
          >
            <span className="scenario-title">{s.title}</span>
            <span className="scenario-hint">{s.highlights}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
