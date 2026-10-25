import type { Macros } from "../api/types";
import { round } from "../lib/format";

const ROWS = [
  { key: "protein", label: "Белки", className: "protein" },
  { key: "fat", label: "Жиры", className: "fat" },
  { key: "carbs", label: "Углеводы", className: "carbs" },
] as const;

export function MacroBars({ eaten, target }: { eaten: Macros; target: Macros | null }) {
  return (
    <div className="macros">
      {ROWS.map(({ key, label, className }) => {
        const value = eaten[key];
        const goal = target?.[key];
        const pct = goal ? Math.min(100, (value / goal) * 100) : 0;
        return (
          <div key={key} className="macro">
            <div className="macro-head">
              <span>{label}</span>
              <span className="muted">
                {round(value)}
                {goal ? ` / ${round(goal)}` : ""} г
              </span>
            </div>
            <div className="bar">
              <div className={`bar-fill ${className}`} style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
