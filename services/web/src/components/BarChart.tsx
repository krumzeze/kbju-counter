import { useState } from "react";
import { niceCeil, shortDate } from "../lib/format";
import { useWidth } from "../lib/useWidth";

interface Point {
  day: string;
  value: number;
}

interface Props {
  points: Point[];
  format: (value: number) => string;
  label: string;
  height?: number;
}

const PAD = { top: 12, right: 8, bottom: 28, left: 44 };
const GAP = 2;

export function BarChart({ points, format, label, height = 200 }: Props) {
  const [active, setActive] = useState<number | null>(null);
  const [ref, WIDTH] = useWidth<HTMLDivElement>(640);
  if (points.length === 0) return null;

  const max = Math.max(...points.map((p) => p.value));
  const integers = points.every((p) => Number.isInteger(p.value));
  const top = integers && max <= 10 ? Math.max(2, Math.ceil(max / 2) * 2) : niceCeil(max);
  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const slot = innerW / points.length;
  const barW = Math.max(2, slot - GAP);
  const y = (v: number) => PAD.top + innerH - (v / top) * innerH;
  const labelEvery = Math.max(1, Math.ceil(points.length / Math.max(3, Math.floor(WIDTH / 90))));
  const shown = active ?? points.length - 1;

  return (
    <div ref={ref} className="chart">
      <div className="chart-readout">
        <strong>{format(points[shown].value)}</strong>
        <span className="muted">{shortDate(points[shown].day)}</span>
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
                  className={active !== null && i !== active ? "chart-bar dim" : "chart-bar"}
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
              {i % labelEvery === 0 && (
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
      </svg>
    </div>
  );
}

function roundedTop(x: number, y: number, w: number, h: number, r: number): string {
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
}
