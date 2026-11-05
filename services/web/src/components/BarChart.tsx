import { useState } from "react";
import { niceCeil, readoutDate, shortDate } from "../lib/format";
import { useWidth } from "../lib/useWidth";

interface Point {
  day: string;
  value: number;
}

export interface Goal {
  value: number;
  kind: "limit" | "target";
  label: string;
}

interface Props {
  points: Point[];
  format: (value: number) => string;
  label: string;
  unit?: string | ((value: number) => string);
  goal?: Goal;
  period?: "day" | "week";
  height?: number;
}

const PAD = { top: 12, right: 8, bottom: 28, left: 44 };
const GAP = 2;

export function BarChart({ points, format, label, unit, goal, period = "day", height = 200 }: Props) {
  const [active, setActive] = useState<number | null>(null);
  const [ref, WIDTH] = useWidth<HTMLDivElement>(640);
  if (points.length === 0) return null;

  const max = Math.max(...points.map((p) => p.value), goal ? goal.value * 1.1 : 0);
  const integers = points.every((p) => Number.isInteger(p.value));
  const top = integers && max <= 10 ? Math.max(2, Math.ceil(max / 2) * 2) : niceCeil(max);
  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const slot = innerW / points.length;
  const barW = Math.max(2, slot - GAP);
  const y = (v: number) => PAD.top + innerH - (v / top) * innerH;
  const labelEvery = Math.max(1, Math.ceil(points.length / Math.max(2, Math.floor(innerW / 52))));
  const shown = active ?? points.length - 1;
  const barClass = (value: number, i: number) => {
    const classes = ["chart-bar"];
    if (goal?.kind === "limit" && value > goal.value * 1.1) classes.push("over");
    if (goal?.kind === "target" && value < goal.value) classes.push("under");
    if (active !== null && i !== active) classes.push("dim");
    return classes.join(" ");
  };

  return (
    <div ref={ref} className="chart">
      <div className="chart-readout">
        <strong>
          {format(points[shown].value)}
          {unit && ` ${typeof unit === "function" ? unit(points[shown].value) : unit}`}
        </strong>
        <span className="muted">{readoutDate(points[shown].day, period)}</span>
      </div>
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        role="img"
        aria-label={label}
        onMouseLeave={() => setActive(null)}
      >
        {[top / 2, top].map((t) => (
          <g key={t}>
            <line className="chart-grid" x1={PAD.left} x2={WIDTH - PAD.right} y1={y(t)} y2={y(t)} />
            <text className="chart-axis" x={PAD.left - 8} y={y(t) + 4} textAnchor="end">
              {format(t)}
            </text>
          </g>
        ))}
        {points.map((p, i) => {
          const x = PAD.left + i * slot + GAP / 2;
          const h = p.value > 0 ? Math.max(2, PAD.top + innerH - y(p.value)) : 0;
          return (
            <g key={p.day}>
              {h > 0 && (
                <path
                  className={barClass(p.value, i)}
                  d={roundedTop(x, PAD.top + innerH - h, barW, h, Math.min(4, barW / 2, h))}
                />
              )}
              <rect
                x={PAD.left + i * slot}
                y={PAD.top}
                width={slot}
                height={innerH}
                fill="transparent"
                onMouseEnter={() => setActive(i)}
                onClick={() => setActive(i)}
              />
              {(points.length - 1 - i) % labelEvery === 0 && (
                <text className="chart-axis" x={x + barW / 2} y={height - 8} textAnchor="middle">
                  {shortDate(p.day)}
                </text>
              )}
            </g>
          );
        })}
        <line
          className="chart-grid"
          x1={PAD.left}
          x2={WIDTH - PAD.right}
          y1={PAD.top + innerH}
          y2={PAD.top + innerH}
          strokeDasharray="0"
        />
        {goal && (
          <g className="chart-goal">
            <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y(goal.value)} y2={y(goal.value)} />
            <text x={WIDTH - PAD.right} y={y(goal.value) - 6} textAnchor="end">
              {goal.label}
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}

function roundedTop(x: number, y: number, w: number, h: number, r: number): string {
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
}
