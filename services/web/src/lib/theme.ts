import { webApp } from "./telegram";

export interface Theme {
  key: string;
  ru: string;
  en: string;
  /** Base, tile and accent colors in 60/30/10 proportion. */
  swatch: [string, string, string];
}

export const THEMES: Theme[] = [
  { key: "sage", ru: "Шалфей", en: "Sage", swatch: ["#f6f4ef", "#d3e4c8", "#6f8a66"] },
  { key: "sea", ru: "Море", en: "Sea", swatch: ["#f2f5f5", "#cde5e3", "#33768f"] },
  { key: "lavender", ru: "Лаванда", en: "Lavender", swatch: ["#f5f4f8", "#dcd5ef", "#6e60a6"] },
  { key: "terracotta", ru: "Терракота", en: "Terracotta", swatch: ["#f7f2ed", "#f4cdb4", "#a65a3a"] },
  { key: "berry", ru: "Ягоды", en: "Berry", swatch: ["#f8f3f4", "#f1d0da", "#a24c68"] },
];

// deepcode ignore HardcodedNonCryptoSecret: localStorage key name, not a secret
const STORAGE_KEY = "belok.theme";

export function savedTheme(): string {
  try {
    const key = localStorage.getItem(STORAGE_KEY);
    if (THEMES.some((t) => t.key === key)) return key!;
  } catch {
    // storage can be unavailable in private mode
  }
  return THEMES[0].key;
}

export function applyTheme(key: string) {
  const theme = THEMES.find((t) => t.key === key) ?? THEMES[0];
  if (theme.key === THEMES[0].key) delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme.key;
  webApp?.setHeaderColor?.(theme.swatch[0]);
  webApp?.setBackgroundColor?.(theme.swatch[0]);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme.swatch[0]);
}

export function saveTheme(key: string) {
  try {
    localStorage.setItem(STORAGE_KEY, key);
  } catch {
    // the theme still applies for this session
  }
  applyTheme(key);
}
