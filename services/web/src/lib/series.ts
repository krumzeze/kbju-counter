import { shiftDay } from "./format";

export interface Point {
  day: string;
  value: number;
}

const weekStart = (iso: string) => {
  const weekday = (new Date(`${iso}T12:00:00Z`).getUTCDay() + 6) % 7;
  return shiftDay(iso, -weekday);
};

/** Average per week (Monday first), counting only days where `counts` is true. */
export function weekly(points: Point[], counts: (p: Point) => boolean = (p) => p.value !== 0): Point[] {
  const groups = new Map<string, number[]>();
  for (const p of points) {
    const key = weekStart(p.day);
    if (!groups.has(key)) groups.set(key, []);
    if (counts(p)) groups.get(key)!.push(p.value);
  }
  return [...groups].map(([day, values]) => ({
    day,
    value: values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0,
  }));
}

/** Mean of all points within `days` days up to and including each point. */
export function trailingMean(points: Point[], days: number): Point[] {
  return points.map((p) => {
    const from = shiftDay(p.day, 1 - days);
    const window = points.filter((q) => q.day >= from && q.day <= p.day);
    return { day: p.day, value: window.reduce((s, q) => s + q.value, 0) / window.length };
  });
}

/** Evenly spaced round ticks covering [lo, hi]. */
export function niceTicks(lo: number, hi: number, count = 4): { ticks: number[]; lo: number; hi: number } {
  const raw = (hi - lo || Math.abs(hi) || 1) / count;
  const exp = 10 ** Math.floor(Math.log10(raw));
  const step = ([1, 2, 2.5, 5, 10].find((s) => s * exp >= raw) ?? 10) * exp;
  const start = Math.floor(lo / step) * step;
  const end = Math.ceil(hi / step) * step;
  const ticks: number[] = [];
  for (let t = start; t <= end + step / 2; t += step) ticks.push(Number(t.toFixed(6)));
  return { ticks, lo: start, hi: end };
}

export const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
