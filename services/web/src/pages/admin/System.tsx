import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { adminApi, errorMessage } from "../../api/client";
import type { AppError, CheckStatus, FeatureKey, HealthCheck } from "../../api/types";
import { ErrorState, Spinner } from "../../components/States";
import { useAdminMutation, useErrors, useFeatures, useHealth } from "../../lib/adminQueries";
import { dateTime } from "../../lib/format";

export const FEATURE_LABELS: Record<FeatureKey, string> = {
  photo: "Распознавание по фото",
  text: "Распознавание по тексту",
  voice: "Голосовые в боте",
  barcode: "Штрихкоды",
  reminders: "Напоминания",
  payments: "Оплата",
  widgets: "Виджеты в чате",
  assistant: "AI-ассистент",
};

const FEATURE_HINTS: Record<FeatureKey, string> = {
  photo: "вкладка «Фото», запросы к Claude",
  text: "вкладка «Текст», запросы к Claude",
  voice: "распознавание речи и Claude",
  barcode: "сканер и поиск в Open Food Facts, ручной ввод остаётся",
  reminders: "рассылка напоминаний ботом",
  payments: "тарифы в профиле; оплаты, которые уже прошли, всё равно зачислятся",
  widgets: "карточка дня, правка граммов и напоминания виджетами; без них бот шлёт текст",
  assistant: "чат с AI и разбор недели в Premium, запросы к Claude",
};

const DEPENDS_ON: Record<FeatureKey, string[]> = {
  photo: ["anthropic"],
  text: ["anthropic"],
  voice: ["stt", "anthropic", "worker:bot"],
  barcode: ["food_db"],
  reminders: ["worker:reminders", "telegram"],
  payments: ["tribute"],
  widgets: ["telegram"],
  assistant: ["anthropic"],
};

const CHECK_LABELS: Record<string, string> = {
  database: "База данных",
  redis: "Redis",
  telegram: "Telegram Bot API",
  anthropic: "Claude API",
  stt: "Распознавание речи",
  food_db: "Open Food Facts",
  tribute: "Tribute",
  "worker:bot": "Процесс бота",
  "worker:reminders": "Цикл напоминаний",
  "worker:monitor": "Мониторинг и сводки",
};

const STATUS: Record<CheckStatus, { label: string; className: string }> = {
  ok: { label: "работает", className: "active" },
  warn: { label: "есть проблемы", className: "caution" },
  fail: { label: "не работает", className: "warn" },
  off: { label: "не настроено", className: "expired" },
};

const SEVERITY: CheckStatus[] = ["fail", "warn", "off", "ok"];

export function System() {
  return (
    <>
      <Features />
      <Services />
      <Errors />
    </>
  );
}

function Features() {
  const features = useFeatures();
  const health = useHealth();
  const client = useQueryClient();
  const toggle = useMutation({
    mutationFn: ({ key, enabled }: { key: FeatureKey; enabled: boolean }) =>
      adminApi.setFeature(key, enabled),
    onSuccess: (flags) => {
      client.setQueryData(["admin", "features"], flags);
      client.invalidateQueries({ queryKey: ["admin", "actions"] });
      client.invalidateQueries({ queryKey: ["me"] });
    },
  });
  if (features.isPending) return <Spinner />;
  if (features.error)
    return <ErrorState message={errorMessage(features.error)} onRetry={() => features.refetch()} />;

  const checks = new Map(health.data?.checks.map((c) => [c.key, c]));
  return (
    <section className="card">
      <h2>Функции</h2>
      <p className="muted small">
        Выключенная функция пропадает у пользователей сразу в приложении и в течение 15 секунд в боте.
        Перезапуск не нужен.
      </p>
      {features.data.map((f) => {
        const status = worst(DEPENDS_ON[f.key].map((k) => checks.get(k)));
        return (
          <label key={f.key} className="toggle">
            <span className="user-cell">
              <span className="feature-name">
                {FEATURE_LABELS[f.key] ?? f.key}
                {status && <StatusBadge status={status} />}
              </span>
              <span className="muted small">{FEATURE_HINTS[f.key]}</span>
            </span>
            <input
              type="checkbox"
              checked={f.enabled}
              disabled={toggle.isPending}
              onChange={(e) => toggle.mutate({ key: f.key, enabled: e.target.checked })}
            />
          </label>
        );
      })}
      {toggle.error && <p className="error">{errorMessage(toggle.error)}</p>}
    </section>
  );
}

function Services() {
  const { data, isPending, error, refetch, isFetching } = useHealth();
  return (
    <section className="card">
      <div className="section-head">
        <h2>Сервисы</h2>
        <button className="btn small" disabled={isFetching} onClick={() => refetch()}>
          {isFetching ? "Проверяю…" : "Проверить"}
        </button>
      </div>
      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : (
        <>
          <p className="muted small">Проверено {dateTime(data.checked_at)}</p>
          <ul className="list">
            {data.checks.map((c) => (
              <li key={c.key} className="health-row">
                <span className="user-cell">
                  {CHECK_LABELS[c.key] ?? c.key}
                  {c.detail && <span className="muted small">{c.detail}</span>}
                </span>
                <span className="health-status">
                  <StatusBadge status={c.status} />
                  {c.latency_ms !== null && <span className="muted small">{c.latency_ms} мс</span>}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

const SOURCES: Record<AppError["source"], string> = { api: "API", bot: "Бот", web: "Приложение" };

function Errors() {
  const { data, isPending, error, refetch } = useErrors();
  const resolve = useAdminMutation(adminApi.resolveErrors, "errors");
  return (
    <section className="card">
      <div className="section-head">
        <h2>Ошибки</h2>
        {data && data.length > 0 && (
          <button className="btn small" disabled={resolve.isPending} onClick={() => resolve.mutate(undefined)}>
            Очистить всё
          </button>
        )}
      </div>
      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : data.length === 0 ? (
        <p className="muted">За последние 30 дней ошибок нет</p>
      ) : (
        <ul className="list">
          {data.map((e) => (
            <ErrorRow key={e.fingerprint} error={e} onResolve={() => resolve.mutate(e.fingerprint)} />
          ))}
        </ul>
      )}
      {resolve.error && <p className="error">{errorMessage(resolve.error)}</p>}
    </section>
  );
}

function ErrorRow({ error: e, onResolve }: { error: AppError; onResolve: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="error-row">
      <button className="error-head" onClick={() => setOpen(!open)}>
        <span className="badge expired">{SOURCES[e.source] ?? e.source}</span>
        <span className="error-message">{e.message}</span>
        <span className="muted small">×{e.count}</span>
      </button>
      <div className="muted small">
        {e.path && <code>{e.path}</code>} {dateTime(e.last_seen)}
        {e.count > 1 && `, впервые ${dateTime(e.first_seen)}`}
        {e.user_id && (
          <>
            {", "}
            <Link className="positive" to={`/admin/users/${e.user_id}`}>пользователь {e.user_id}</Link>
          </>
        )}
      </div>
      {open && (
        <>
          {e.detail && <pre className="error-detail">{e.detail}</pre>}
          <button className="btn small" onClick={onResolve}>
            Исправлено
          </button>
        </>
      )}
    </li>
  );
}

function StatusBadge({ status }: { status: CheckStatus }) {
  const s = STATUS[status];
  return <span className={`badge ${s.className}`}>{s.label}</span>;
}

function worst(checks: (HealthCheck | undefined)[]): CheckStatus | null {
  const statuses = checks.filter((c) => c !== undefined).map((c) => c.status);
  if (statuses.length === 0) return null;
  return SEVERITY.find((s) => statuses.includes(s)) ?? null;
}
