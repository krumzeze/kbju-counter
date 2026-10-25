import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api/client";

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
        <h1>Белок</h1>
        <p className="lead">
          Сфотографируй тарелку, и я посчитаю калории и БЖУ. Записывай подходы в зале, шаги и вес,
          а норма на день подстроится под твою активность.
        </p>
        <div ref={widget} className="widget" />
        {config.data && !config.data.bot_username && (
          <p className="muted small">Вход через Telegram ещё не настроен на сервере.</p>
        )}
        {error && <p className="error">{error}</p>}
        <p className="muted small">Первые 4 дня бесплатно. Данные синхронизируются с ботом.</p>
      </section>

      <section className="features">
        <div className="card">
          <span className="feature-icon">📸</span>
          <h3>КБЖУ по фото</h3>
          <p className="muted">Нейросеть узнаёт блюда и оценивает порцию. Порцию легко поправить.</p>
        </div>
        <div className="card">
          <span className="feature-icon">🏋️</span>
          <h3>Дневник тренировок</h3>
          <p className="muted">Подходы, рабочие веса и график расчётного максимума по каждому упражнению.</p>
        </div>
        <div className="card">
          <span className="feature-icon">📈</span>
          <h3>Живая норма</h3>
          <p className="muted">Шаги и тренировки добавляют калории к норме, цель задаёт дефицит или профицит.</p>
        </div>
      </section>
    </div>
  );
}
