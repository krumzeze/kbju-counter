import { useState } from "react";
import { readoutDate, shortDate } from "../lib/format";
import { locale, tr } from "../lib/i18n";
import { type Point, niceTicks } from "../lib/series";
import { useWidth } from "../lib/useWidth";

interface Props {
  points: Point[];
  unit: string;
  height?: number;
  zeroBased?: boolean;
  className?: string;
  trend?: { points: Point[]; label: string; pointsLabel: string };
}

const PAD = { top: 16, right: 16, bottom: 28 };

export function LineChart({ points, unit, height = 220, zeroBased = false, className, trend }: Props) {
  const [active, setActive] = useState<number | null>(null);
  const [ref, WIDTH] = useWidth<HTMLDivElement>(640);
  if (points.length === 0) return null;

  const values = [...points, ...(trend?.points ?? [])].map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min || Math.abs(max) * 0.02 || 1) * 0.1;
  const scale = zeroBased ? niceTicks(0, max, 2) : niceTicks(min - pad, max + pad, 3);
  const step = scale.ticks[1] - scale.ticks[0] || 1;
  const digits = step < 1 ? 1 : 0;
  const fmt = (v: number, d = digits) =>
    v.toLocaleString(locale(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const ticks = zeroBased ? scale.ticks.filter((t) => t > 0) : scale.ticks;
  const left = Math.max(28, Math.max(...ticks.map((t) => fmt(t).length)) * 7 + 14);

  const innerW = WIDTH - left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const x = (i: number) => left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const y = (v: number) => PAD.top + innerH - ((v - scale.lo) / (scale.hi - scale.lo)) * innerH;
  const line = (ps: Point[]) => ps.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.value)}`).join(" ");

  const path = line(points);
  const area = `${path} L${x(points.length - 1)},${PAD.top + innerH} L${x(0)},${PAD.top + innerH} Z`;
  const labelEvery = Math.max(1, Math.ceil(points.length / Math.max(2, Math.floor(innerW / 52))));
  const shown = active ?? points.length - 1;
  const shownTrend = trend?.points[shown];

  return (
    <div ref={ref} className={["chart", className, trend && "with-trend"].filter(Boolean).join(" ")}>
      <div className="chart-readout">
        <strong>
          {fmt(points[shown].value, 1)} {unit}
        </strong>
        <span className="muted">
          {readoutDate(points[shown].day)}
          {shownTrend && ` · ${tr("тренд", "trend")} ${fmt(shownTrend.value, 1)}`}
        </span>
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={tr("График", "Chart")} onMouseLeave={() => setActive(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line className="chart-grid" x1={left} x2={WIDTH - PAD.right} y1={y(t)} y2={y(t)} />
            <text className="chart-axis" x={left - 8} y={y(t) + 4} textAnchor="end">
              {fmt(t)}
            </text>
          </g>
        ))}
        {zeroBased && <path className="chart-area" d={area} />}
        <path className="chart-line" d={path} />
        {trend && <path className="chart-trend" d={line(trend.points)} />}
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
            {(points.length - 1 - i) % labelEvery === 0 && (
              <text className="chart-axis" x={x(i)} y={height - 8} textAnchor="middle">
                {shortDate(p.day)}
              </text>
            )}
          </g>
        ))}
      </svg>
      {trend && (
        <div className="chart-legend">
          <span className="chart-legend-item">
            <span className="chart-legend-dot" aria-hidden />
            {trend.pointsLabel}
          </span>
          <span className="chart-legend-item">
            <span className="chart-legend-trend" aria-hidden />
            {trend.label}
          </span>
        </div>
      )}
    </div>
  );
}
