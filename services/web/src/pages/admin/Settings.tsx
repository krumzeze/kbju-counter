import { adminApi, errorMessage } from "../../api/client";
import type { Prefs } from "../../api/types";
import { ErrorState, Spinner } from "../../components/States";
import { useAdminMutation, usePrefs } from "../../lib/adminQueries";

const ITEMS: { key: keyof Prefs; label: string; hint: string }[] = [
  { key: "new_users", label: "Новые пользователи", hint: "сообщение о каждой регистрации" },
  { key: "errors", label: "Ошибки распознавания", hint: "если за час больше 20% запросов с ошибкой" },
  { key: "daily", label: "Сводка за день", hint: "каждый вечер в 21:00" },
];

export function Settings() {
  const { data, isPending, error, refetch } = usePrefs();
  const save = useAdminMutation((body: Partial<Prefs>) => adminApi.savePrefs(body), "prefs");
  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  return (
    <section className="card">
      <h2>Уведомления в Telegram</h2>
      {ITEMS.map((item) => (
        <label key={item.key} className="toggle">
          <span className="user-cell">
            {item.label}
            <span className="muted small">{item.hint}</span>
          </span>
          <input
            type="checkbox"
            checked={data[item.key]}
            disabled={save.isPending}
            onChange={(e) => save.mutate({ [item.key]: e.target.checked })}
          />
        </label>
      ))}
      {save.error && <p className="error">{errorMessage(save.error)}</p>}
    </section>
  );
}
