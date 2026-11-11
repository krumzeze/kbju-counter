import { useState } from "react";
import { readoutDate, shortDate } from "../lib/format";
import { type Point, niceTicks } from "../lib/series";
import { useWidth } from "../lib/useWidth";

export interface Goal {
  value: number;
  kind: "limit" | "target";
  label: string;
}

export interface LegendItem {
  cls: string;
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
  tone?: string;
  legend?: LegendItem[];
  xLabel?: (point: Point) => string;
  readoutLabel?: (point: Point) => string;
}

const PAD = { top: 12, right: 8, bottom: 28 };
const GAP = 2;

export function BarChart({
  points,
  format,
  label,
  unit,
  goal,
  period = "day",
  height = 200,
  tone,
  legend,
  xLabel = (p) => shortDate(p.day),
  readoutLabel = (p) => readoutDate(p.day, period),
}: Props) {
  const [active, setActive] = useState<number | null>(null);
  const [ref, WIDTH] = useWidth<HTMLDivElement>(640);
  if (points.length === 0) return null;

  const values = points.map((p) => p.value);
  const max = Math.max(...values, goal ? goal.value * 1.1 : 0, 0);
  const min = Math.min(...values, 0);
  const integers = values.every(Number.isInteger);
  const scale =
    min < 0
      ? niceTicks(min, max, 4)
      : integers && max <= 10
        ? { lo: 0, hi: Math.max(2, Math.ceil(max / 2) * 2), ticks: [] as number[] }
        : niceTicks(0, max, 2);
  const ticks = scale.ticks.length ? scale.ticks.filter((t) => t !== 0) : [scale.hi / 2, scale.hi];
  const left = Math.max(28, Math.max(...ticks.map((t) => format(t).length)) * 7 + 14);
  const innerW = WIDTH - left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const slot = innerW / points.length;
  const barW = Math.max(2, slot - GAP);
  const y = (v: number) => PAD.top + innerH - ((v - scale.lo) / (scale.hi - scale.lo)) * innerH;
  const zero = y(0);
  const labelEvery = Math.max(1, Math.ceil(points.length / Math.max(2, Math.floor(innerW / 52))));
  const shown = active ?? points.length - 1;
  const barClass = (value: number, i: number) => {
    const classes = ["chart-bar"];
    if (goal?.kind === "limit" && value > goal.value * 1.1) classes.push("over");
    else if (goal?.kind === "target" && value < goal.value) classes.push("under");
    if (active !== null && i !== active) classes.push("dim");
    return classes.join(" ");
  };
  const unitText = (v: number) => (unit ? ` ${typeof unit === "function" ? unit(v) : unit}` : "");

  return (
    <div ref={ref} className={tone ? `chart ${tone}` : "chart"}>
      <div className="chart-readout">
        <strong>
          {format(points[shown].value)}
          {unitText(points[shown].value)}
        </strong>
        <span className="muted">{readoutLabel(points[shown])}</span>
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={label} onMouseLeave={() => setActive(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line className="chart-grid" x1={left} x2={WIDTH - PAD.right} y1={y(t)} y2={y(t)} />
            <text className="chart-axis" x={left - 8} y={y(t) + 4} textAnchor="end">
              {format(t)}
            </text>
          </g>
        ))}
        {points.map((p, i) => {
          const x = left + i * slot + GAP / 2;
          const h = p.value === 0 ? 0 : Math.max(2, Math.abs(zero - y(p.value)));
          const r = Math.min(4, barW / 2, h);
          return (
            <g key={i}>
              {h > 0 && (
                <path
                  className={barClass(p.value, i)}
                  d={p.value > 0 ? roundedTop(x, zero - h, barW, h, r) : roundedBottom(x, zero, barW, h, r)}
                />
              )}
              <rect
                x={left + i * slot}
                y={PAD.top}
                width={slot}
                height={innerH}
                fill="transparent"
                onMouseEnter={() => setActive(i)}
                onClick={() => setActive(i)}
              />
              {(points.length - 1 - i) % labelEvery === 0 && (
                <text className="chart-axis" x={x + barW / 2} y={height - 8} textAnchor="middle">
                  {xLabel(p)}
                </text>
              )}
            </g>
          );
        })}
        <line className="chart-grid chart-zero" x1={left} x2={WIDTH - PAD.right} y1={zero} y2={zero} />
        {goal && <line className="chart-goal" x1={left} x2={WIDTH - PAD.right} y1={y(goal.value)} y2={y(goal.value)} />}
      </svg>
      {(goal || legend) && (
        <div className="chart-legend">
          {legend?.map((item) => (
            <span key={item.cls} className="chart-legend-item">
              <svg className="chart-legend-swatch" viewBox="0 0 10 10" aria-hidden>
                <rect className={`chart-bar ${item.cls}`} width="10" height="10" rx="3" />
              </svg>
              {item.label}
            </span>
          ))}
          {goal && (
            <span className="chart-legend-item">
              <span className="chart-legend-goal" aria-hidden />
              {goal.label}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function roundedTop(x: number, y: number, w: number, h: number, r: number): string {
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
}

function roundedBottom(x: number, y: number, w: number, h: number, r: number): string {
  const b = y + h;
  return `M${x},${y} V${b - r} Q${x},${b} ${x + r},${b} H${x + w - r} Q${x + w},${b} ${x + w},${b - r} V${y} Z`;
}
