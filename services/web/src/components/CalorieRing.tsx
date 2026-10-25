import { round } from "../lib/format";

interface Props {
  eaten: number;
  target: number | null;
}

const SIZE = 184;
const STROKE = 14;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function CalorieRing({ eaten, target }: Props) {
  const ratio = target ? eaten / target : 0;
  const over = ratio > 1;
  const dash = CIRCUMFERENCE * Math.min(ratio, 1);
  const left = target ? target - eaten : null;

  return (
    <div className="ring">
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden>
        <circle className="ring-track" cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} strokeWidth={STROKE} />
        <circle
          className={over ? "ring-value ring-over" : "ring-value"}
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          strokeWidth={STROKE}
          strokeDasharray={`${dash} ${CIRCUMFERENCE}`}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
        />
      </svg>
      <div className="ring-label">
        {left === null ? (
          <>
            <strong>{round(eaten)}</strong>
            <span>ккал съедено</span>
          </>
        ) : (
          <>
            <strong>{round(Math.abs(left))}</strong>
            <span>{left >= 0 ? "ккал осталось" : "ккал сверх нормы"}</span>
            <small>
              {round(eaten)} из {round(target!)}
            </small>
          </>
        )}
      </div>
    </div>
  );
}
