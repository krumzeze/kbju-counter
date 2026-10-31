import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api/client";
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
      <section className="hero">
        <img src="/favicon.svg" alt="" width={72} height={72} />
        <h1>{tr("Белок", "Belok")}</h1>
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
          {tr("Первые 4 дня бесплатно. Данные синхронизируются с ботом.", "First 4 days free. Your data syncs with the bot.")}
        </p>
      </section>

      <section className="features">
        <div className="card">
          <span className="feature-icon">📸</span>
          <h3>{tr("КБЖУ по фото", "Macros from a photo")}</h3>
          <p className="muted">
            {tr(
              "Нейросеть узнаёт блюда и оценивает порцию. Порцию легко поправить.",
              "AI recognizes dishes and estimates the portion. Adjusting it takes a tap.",
            )}
          </p>
        </div>
        <div className="card">
          <span className="feature-icon">🏋️</span>
          <h3>{tr("Дневник тренировок", "Workout log")}</h3>
          <p className="muted">
            {tr(
              "Подходы, рабочие веса и график расчётного максимума по каждому упражнению.",
              "Sets, working weights and an estimated 1RM chart for every exercise.",
            )}
          </p>
        </div>
        <div className="card">
          <span className="feature-icon">📈</span>
          <h3>{tr("Живая норма", "Adaptive target")}</h3>
          <p className="muted">
            {tr(
              "Шаги и тренировки добавляют калории к норме, цель задаёт дефицит или профицит.",
              "Steps and workouts add calories to your target, your goal sets a deficit or surplus.",
            )}
          </p>
        </div>
      </section>
    </div>
  );
}
