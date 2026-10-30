import { useState } from "react";
import { niceCeil, shortDate } from "../lib/format";
import { useWidth } from "../lib/useWidth";

interface Point {
  day: string;
  value: number;
}

interface Props {
  points: Point[];
  unit: string;
  height?: number;
  zeroBased?: boolean;
  className?: string;
}

const PAD = { top: 16, right: 16, bottom: 28, left: 44 };

export function LineChart({ points, unit, height = 220, zeroBased = false, className }: Props) {
  const [active, setActive] = useState<number | null>(null);
  const [ref, WIDTH] = useWidth<HTMLDivElement>(640);
  if (points.length === 0) return null;

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = max - min || 1;
  const lo = zeroBased ? 0 : min - spread * 0.15;
  const hi = zeroBased ? niceCeil(max) : max + spread * 0.15;

  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const x = (i: number) =>
    PAD.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const y = (v: number) => PAD.top + innerH - ((v - lo) / (hi - lo)) * innerH;

  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.value)}`).join(" ");
  const area = `${path} L${x(points.length - 1)},${PAD.top + innerH} L${x(0)},${PAD.top + innerH} Z`;
  const ticks = zeroBased ? [hi / 2, hi] : [lo + (hi - lo) * 0.2, (lo + hi) / 2, lo + (hi - lo) * 0.8];
  const labelEvery = Math.max(1, Math.ceil(points.length / Math.max(3, Math.floor(WIDTH / 90))));
  const shown = active ?? points.length - 1;

  return (
    <div ref={ref} className={className ? `chart ${className}` : "chart"}>
      <div className="chart-readout">
        <strong>
          {points[shown].value.toLocaleString("ru-RU", { maximumFractionDigits: 1 })} {unit}
        </strong>
        <span className="muted">{shortDate(points[shown].day)}</span>
      </div>
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        role="img"
        aria-label="График"
        onMouseLeave={() => setActive(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line className="chart-grid" x1={PAD.left} x2={WIDTH - PAD.right} y1={y(t)} y2={y(t)} />
            <text className="chart-axis" x={PAD.left - 8} y={y(t) + 4} textAnchor="end">
              {t.toFixed(spread < 5 ? 1 : 0)}
            </text>
          </g>
        ))}
        <path className="chart-area" d={area} />
        <path className="chart-line" d={path} />
        {points.map((p, i) => (
          <g key={p.day}>
            <circle
              className={i === shown ? "chart-dot active" : "chart-dot"}
              cx={x(i)}
              cy={y(p.value)}
              r={i === shown ? 6 : 3.5}
            />
            <rect
              x={x(i) - innerW / points.length / 2}
              y={PAD.top}
              width={innerW / points.length}
              height={innerH}
              fill="transparent"
              onMouseEnter={() => setActive(i)}
              onClick={() => setActive(i)}
            />
            {i % labelEvery === 0 && (
              <text className="chart-axis" x={x(i)} y={height - 8} textAnchor="middle">
                {shortDate(p.day)}
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}
