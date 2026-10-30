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

export const usd = (n: number) =>
  `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: n < 1 && n > 0 ? 4 : 2 })}`;

export const percent = (n: number | null) => (n === null ? "—" : `${Math.round(n * 100)}%`);

export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

export const date = (iso: string) => new Date(iso).toLocaleDateString("ru-RU");

export function ago(iso: string | null): string {
  if (!iso) return "никогда";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 5) return "только что";
  if (minutes < 60) return `${minutes} мин назад`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} ч назад`;
  const days = Math.round(hours / 24);
  return `${days} ${plural(days, "день", "дня", "дней")} назад`;
}

export function displayName(user: { id: number; username: string | null; first_name: string | null }) {
  if (user.username) return `@${user.username}`;
  return user.first_name || String(user.id);
}

export function niceCeil(value: number): number {
  if (value <= 0) return 1;
  const exp = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => s * exp >= value) ?? 10;
  return step * exp;
}
