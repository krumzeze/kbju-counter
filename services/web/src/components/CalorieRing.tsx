import { tr } from "../lib/i18n";

const SIZE = 96;
const STROKE = 9;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function CalorieRing({ eaten, target }: { eaten: number; target: number }) {
  const ratio = target > 0 ? eaten / target : 0;
  const dash = CIRCUMFERENCE * Math.min(ratio, 1);
  return (
    <div className="ring">
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden>
        <circle className="ring-track" cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} strokeWidth={STROKE} />
        <circle
          className={ratio > 1 ? "ring-value ring-over" : "ring-value"}
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          strokeWidth={STROKE}
          strokeDasharray={`${dash} ${CIRCUMFERENCE}`}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
        />
      </svg>
      <div className="ring-label">
        <strong>{Math.round(ratio * 100)}%</strong>
        <span>{tr("ккал", "kcal")}</span>
      </div>
    </div>
  );
}
