import type { Macros } from "../api/types";
import { round } from "../lib/format";
import { tr } from "../lib/i18n";

const rows = () =>
  [
    { key: "protein", label: tr("Белки", "Protein") },
    { key: "fat", label: tr("Жиры", "Fat") },
    { key: "carbs", label: tr("Углеводы", "Carbs") },
  ] as const;

export function MacroBars({ eaten, target }: { eaten: Macros; target: Macros | null }) {
  return (
    <div className="macros">
      {rows().map(({ key, label }) => {
        const value = eaten[key];
        const goal = target?.[key];
        const pct = goal ? Math.min(100, (value / goal) * 100) : 0;
        return (
          <div key={key} className="macro">
            <span className="macro-name">{label}</span>
            <div className="bar">
              <div className={`bar-fill ${key}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="macro-value">
              {round(value)}
              {goal ? `/${round(goal)}` : ""} {tr("г", "g")}
            </span>
          </div>
        );
      })}
    </div>
  );
}
