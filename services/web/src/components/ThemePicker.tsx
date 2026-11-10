import { useState } from "react";
import { tr } from "../lib/i18n";
import { ACCENTS, SCHEMES, saveAccent, saveScheme, savedAccent, savedScheme } from "../lib/theme";

export function ThemePicker() {
  const [scheme, setScheme] = useState(savedScheme);
  const [accent, setAccent] = useState(savedAccent);
  return (
    <div className="card field">
      <span>{tr("Оформление", "Appearance")}</span>
      <div className="segmented" role="tablist" aria-label={tr("Схема", "Scheme")}>
        {SCHEMES.map((s) => (
          <button
            key={s.key}
            type="button"
            role="tab"
            aria-selected={scheme === s.key}
            onClick={() => {
              saveScheme(s.key);
              setScheme(s.key);
            }}
          >
            {tr(s.ru, s.en)}
          </button>
        ))}
      </div>
      <span className="theme-group-title">{tr("Акцент", "Accent")}</span>
      <div className="accents">
        {ACCENTS.map((a) => (
          <button
            key={a.key}
            type="button"
            className="accent-option"
            aria-pressed={accent === a.key}
            onClick={() => {
              saveAccent(a.key);
              setAccent(a.key);
            }}
          >
            <span className="accent-swatch" style={{ background: a.color }} aria-hidden />
            {tr(a.ru, a.en)}
          </button>
        ))}
      </div>
    </div>
  );
}
