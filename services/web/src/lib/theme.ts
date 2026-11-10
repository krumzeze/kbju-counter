import { webApp } from "./telegram";

export type Scheme = "auto" | "light" | "dark";

export interface Accent {
  key: string;
  ru: string;
  en: string;
  color: string;
}

export const ACCENTS: Accent[] = [
  { key: "lime", ru: "Лайм", en: "Lime", color: "#d4f25a" },
  { key: "orange", ru: "Апельсин", en: "Orange", color: "#ff8a3d" },
  { key: "blue", ru: "Небо", en: "Sky", color: "#7cc4ff" },
  { key: "pink", ru: "Малина", en: "Raspberry", color: "#ff9ec4" },
];

export const SCHEMES: { key: Scheme; ru: string; en: string }[] = [
  { key: "auto", ru: "Как в системе", en: "System" },
  { key: "light", ru: "Светлая", en: "Light" },
  { key: "dark", ru: "Тёмная", en: "Dark" },
];

const BG = { light: "#efeee9", dark: "#0d0d0c" };

// deepcode ignore HardcodedNonCryptoSecret: localStorage key names, not secrets
const SCHEME_KEY = "belok.scheme";
const ACCENT_KEY = "belok.accent";
const LEGACY_KEY = "belok.theme";

const LEGACY: Record<string, [Scheme, string]> = {
  sea: ["light", "blue"],
  lavender: ["light", "blue"],
  terracotta: ["light", "orange"],
  berry: ["light", "pink"],
  black: ["dark", "lime"],
  graphite: ["dark", "lime"],
  "night-sea": ["dark", "blue"],
  plum: ["dark", "pink"],
};

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // the choice still applies for this session
  }
}

function migrate() {
  const legacy = read(LEGACY_KEY);
  if (!legacy) return;
  const [scheme, accent] = LEGACY[legacy] ?? ["auto", "lime"];
  if (!read(SCHEME_KEY)) write(SCHEME_KEY, scheme);
  if (!read(ACCENT_KEY)) write(ACCENT_KEY, accent);
  try {
    localStorage.removeItem(LEGACY_KEY);
  } catch {
    // nothing to clean up
  }
}

export function savedScheme(): Scheme {
  const value = read(SCHEME_KEY);
  return SCHEMES.some((s) => s.key === value) ? (value as Scheme) : "auto";
}

export function savedAccent(): string {
  const value = read(ACCENT_KEY);
  return ACCENTS.some((a) => a.key === value) ? value! : ACCENTS[0].key;
}

const media = window.matchMedia?.("(prefers-color-scheme: dark)");

function systemDark(): boolean {
  if (webApp?.colorScheme) return webApp.colorScheme === "dark";
  return media?.matches ?? false;
}

export function applyTheme() {
  const scheme = savedScheme();
  const dark = scheme === "dark" || (scheme === "auto" && systemDark());
  const root = document.documentElement;
  root.dataset.scheme = dark ? "dark" : "light";
  root.dataset.accent = savedAccent();
  const bg = dark ? BG.dark : BG.light;
  webApp?.setHeaderColor?.(bg);
  webApp?.setBackgroundColor?.(bg);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", bg);
}

export function initTheme() {
  migrate();
  applyTheme();
  media?.addEventListener?.("change", applyTheme);
  webApp?.onEvent?.("themeChanged", applyTheme);
}

export function saveScheme(scheme: Scheme) {
  write(SCHEME_KEY, scheme);
  applyTheme();
}

export function saveAccent(key: string) {
  write(ACCENT_KEY, key);
  applyTheme();
}
