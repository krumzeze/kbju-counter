import { useState } from "react";
import { tr } from "../lib/i18n";
import { saveTheme, savedTheme, THEMES } from "../lib/theme";

export function ThemePicker() {
  const [current, setCurrent] = useState(savedTheme);
  return (
    <div className="card field">
      <span>{tr("Цветовая тема", "Color theme")}</span>
      <div className="themes">
        {THEMES.map((theme) => (
          <button
            key={theme.key}
            type="button"
            className="theme-option"
            aria-pressed={current === theme.key}
            onClick={() => {
              saveTheme(theme.key);
              setCurrent(theme.key);
            }}
          >
            <span className="theme-swatch" aria-hidden>
              {theme.swatch.map((color) => (
                <span key={color} style={{ background: color }} />
              ))}
            </span>
            {tr(theme.ru, theme.en)}
          </button>
        ))}
      </div>
    </div>
  );
}
