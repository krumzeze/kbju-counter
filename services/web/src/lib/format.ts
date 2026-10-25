export const round = (n: number) => Math.round(n).toLocaleString("ru-RU");

export function todayIso(): string {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

export function shiftDay(iso: string, days: number): string {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function dayLabel(iso: string): string {
  if (iso === todayIso()) return "Сегодня";
  if (iso === shiftDay(todayIso(), -1)) return "Вчера";
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    weekday: "short",
  });
}

export const shortDate = (iso: string) =>
  new Date(`${iso}T12:00:00Z`).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });

export function daysLeft(isoDateTime: string): number {
  return Math.max(0, Math.ceil((new Date(isoDateTime).getTime() - Date.now()) / 86400000));
}

export function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}
