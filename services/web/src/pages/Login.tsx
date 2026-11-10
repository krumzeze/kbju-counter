import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api/client";
import { Logo } from "../components/Logo";
import { tr } from "../lib/i18n";

export function Login({ onToken }: { onToken: (token: string) => void }) {
  const config = useQuery({ queryKey: ["config"], queryFn: api.config });
  const widget = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const bot = config.data?.bot_username;
    if (!bot || !widget.current) return;
    window.onTelegramAuth = (user) => {
      api.authWidget(user).then(
        ({ token }) => onToken(token),
        (e) => setError(errorMessage(e)),
      );
    };
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.dataset.telegramLogin = bot;
    script.dataset.size = "large";
    script.dataset.radius = "12";
    script.dataset.onauth = "onTelegramAuth(user)";
    script.dataset.requestAccess = "write";
    widget.current.replaceChildren(script);
    return () => {
      delete window.onTelegramAuth;
    };
  }, [config.data, onToken]);

  return (
    <div className="landing">
      <header className="landing-top">
        <Logo size={36} />
        <span>belok</span>
      </header>
      <section className="hero">
        <h1>{tr("Калории по фото, тренировки и вес в одном месте", "Calories from a photo, workouts and weight in one place")}</h1>
        <p className="lead">
          {tr(
            "Сфотографируй тарелку, и я посчитаю калории и БЖУ. Записывай подходы в зале, шаги и вес, а норма на день подстроится под твою активность.",
            "Snap your plate and I'll count the calories and macros. Log gym sets, steps and weight, and your daily target adapts to your activity.",
          )}
        </p>
        <div ref={widget} className="widget" />
        {config.data && !config.data.bot_username && (
          <p className="muted small">
            {tr("Вход через Telegram ещё не настроен на сервере.", "Telegram sign-in isn't configured on the server yet.")}
          </p>
        )}
        {error && <p className="error">{error}</p>}
        <p className="muted small">
          {tr("Первые 4 дня бесплатно. Данные общие с мини-приложением в Telegram.", "First 4 days free. Your data is shared with the Telegram mini app.")}
        </p>
      </section>

      <section className="card hero demo" aria-label={tr("Пример распознавания", "Recognition example")}>
        <span className="eyebrow">{tr("Например, по фото", "For example, from a photo")}</span>
        <p className="demo-title">{tr("Гречка с курицей", "Buckwheat with chicken")}</p>
        <p className="summary-big">540</p>
        <p className="summary-sub">{tr("ккал · гречка 200 г, филе 150 г", "kcal · buckwheat 200 g, fillet 150 g")}</p>
        <div className="macros">
          <Macro label={tr("Белки", "Protein")} value={42} />
          <Macro label={tr("Жиры", "Fat")} value={14} />
          <Macro label={tr("Углеводы", "Carbs")} value={58} />
        </div>
      </section>

      <ol className="features">
        <li>
          <span className="feature-num">01</span>
          <div>
            <h3>{tr("КБЖУ по фото", "Macros from a photo")}</h3>
            <p>
              {tr(
                "Нейросеть узнаёт блюда и оценивает порцию. Порцию легко поправить.",
                "AI recognizes dishes and estimates the portion. Adjusting it takes a tap.",
              )}
            </p>
          </div>
        </li>
        <li>
          <span className="feature-num">02</span>
          <div>
            <h3>{tr("Дневник тренировок", "Workout log")}</h3>
            <p>
              {tr(
                "Подходы, рабочие веса и график расчётного максимума по каждому упражнению.",
                "Sets, working weights and an estimated 1RM chart for every exercise.",
              )}
            </p>
          </div>
        </li>
        <li>
          <span className="feature-num">03</span>
          <div>
            <h3>{tr("Живая норма", "Adaptive target")}</h3>
            <p>
              {tr(
                "Шаги и тренировки добавляют калории к норме, цель задаёт дефицит или профицит.",
                "Steps and workouts add calories to your target, your goal sets a deficit or surplus.",
              )}
            </p>
          </div>
        </li>
      </ol>
    </div>
  );
}

function Macro({ label, value }: { label: string; value: number }) {
  return (
    <div className="macro">
      <span className="macro-name">{label}</span>
      <span className="macro-value">
        {value}
        <small> {tr("г", "g")}</small>
      </span>
    </div>
  );
}
