import { MUSCLE_ORDER, muscleLabel } from "../lib/catalog";
import { tr } from "../lib/i18n";
import { BodyMap } from "./BodyMap";

export interface MuscleChoice {
  primary: string[];
  secondary: string[];
}

export const muscleValues = ({ primary, secondary }: MuscleChoice): Record<string, number> => ({
  ...Object.fromEntries(secondary.map((m) => [m, 0.35])),
  ...Object.fromEntries(primary.map((m) => [m, 1])),
});

/** Tap cycles a muscle: off, primary, secondary, off. */
export function MuscleEditor({ value, onChange }: { value: MuscleChoice; onChange: (v: MuscleChoice) => void }) {
  const toggle = (m: string) => {
    const without = (list: string[]) => list.filter((x) => x !== m);
    if (value.primary.includes(m)) {
      onChange({ primary: without(value.primary), secondary: [...value.secondary, m] });
    } else if (value.secondary.includes(m)) {
      onChange({ primary: value.primary, secondary: without(value.secondary) });
    } else {
      onChange({ primary: [...value.primary, m], secondary: value.secondary });
    }
  };
  const state = (m: string) =>
    value.primary.includes(m) ? "primary" : value.secondary.includes(m) ? "secondary" : "off";

  return (
    <div className="muscle-editor">
      <BodyMap values={muscleValues(value)} onPick={toggle} />
      <p className="muted small center">
        {tr(
          "Нажми на мышцу: один раз, если она основная, два раза, если вспомогательная.",
          "Tap a muscle once to mark it as primary, twice as secondary.",
        )}
      </p>
      <div className="chips">
        {MUSCLE_ORDER.map((m) => (
          <button
            key={m}
            type="button"
            className={`chip muscle-chip ${state(m)}`}
            aria-pressed={state(m) !== "off"}
            onClick={() => toggle(m)}
          >
            {muscleLabel(m)}
          </button>
        ))}
      </div>
      <div className="muscle-key small muted" aria-hidden>
        <span>
          <i className="swatch strong" /> {tr("Основные", "Primary")}
        </span>
        <span>
          <i className="swatch" /> {tr("Вспомогательные", "Secondary")}
        </span>
      </div>
    </div>
  );
}
