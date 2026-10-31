export type Lang = "ru" | "en";

function detect(): Lang {
  const code = window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code ?? navigator.language;
  return /^(ru|uk|be|kk|uz|ky)\b/i.test(code ?? "") ? "ru" : "en";
}

export const detectedLang = detect();
let current: Lang = detectedLang;
setLang(detectedLang);

export function setLang(lang: Lang) {
  current = lang;
  document.documentElement.lang = lang;
  document.title = lang === "ru" ? "Белок" : "Belok";
}

export const getLang = () => current;

export const tr = (ru: string, en: string) => (current === "ru" ? ru : en);

export const locale = () => (current === "ru" ? "ru-RU" : "en-US");
