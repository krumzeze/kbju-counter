import { useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client";
import type { AdminAction } from "../../api/types";
import { ErrorState, Spinner } from "../../components/States";
import { useActions } from "../../lib/adminQueries";
import { dateTime, displayName } from "../../lib/format";

const PAGE = 50;

const FIELDS: Record<string, string> = {
  is_blocked: "блокировка",
  is_admin: "права админа",
  lifetime_access: "доступ навсегда",
  daily_limit: "дневной лимит",
};

export function Log() {
  const [offset, setOffset] = useState(0);
  const { data, isPending, error, refetch } = useActions(offset);
  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  return (
    <section className="card">
      <h2>Журнал действий</h2>
      {data.length === 0 ? (
        <p className="muted">Пока пусто</p>
      ) : (
        <ul className="list">
          {data.map((a) => (
            <li key={a.id}>
              <ActionText action={a} />
              <div className="muted small">
                {dateTime(a.created_at)} · {a.admin ? displayName(a.admin) : "удалённый админ"}
              </div>
            </li>
          ))}
        </ul>
      )}
      <div className="actions" style={{ marginTop: 12, justifyContent: "space-between" }}>
        <button className="btn small" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>
          ← Новее
        </button>
        <button
          className="btn small"
          disabled={data.length < PAGE}
          onClick={() => setOffset(offset + PAGE)}
        >
          Старее →
        </button>
      </div>
    </section>
  );
}

export function ActionText({ action }: { action: AdminAction }) {
  const d = action.details ?? {};
  const target = action.target ? (
    <Link className="positive" to={`/admin/users/${action.target.id}`}>
      {displayName(action.target)}
    </Link>
  ) : action.target_user_id ? (
    <span>{String(d.username ? `@${d.username}` : action.target_user_id)}</span>
  ) : null;

  if (action.action.startsWith("set_")) {
    const field = action.action.slice(4);
    return (
      <span>
        {FIELDS[field] ?? field}: {format(d.old)} → {format(d.new)} у {target}
      </span>
    );
  }
  switch (action.action) {
    case "grant_days":
      return (
        <span>
          +{String(d.days)} дн. доступа для {target}
        </span>
      );
    case "revoke_access":
      return <span>Забрал доступ у {target}</span>;
    case "message":
      return (
        <span>
          Сообщение для {target}: <span className="muted">«{String(d.text ?? "")}»</span>
        </span>
      );
    case "delete_user":
      return <span>Удалил пользователя {target}</span>;
    case "create_promo":
      return (
        <span>
          Создал промокод <span className="mono">{String(d.code)}</span> на {String(d.days)} дн.
        </span>
      );
    case "update_promo":
      return (
        <span>
          Изменил промокод <span className="mono">{String(d.code)}</span>
        </span>
      );
    case "send_broadcast":
      return <span>Запустил рассылку #{String(d.broadcast_id)}</span>;
    case "cancel_broadcast":
      return <span>Остановил рассылку #{String(d.broadcast_id)}</span>;
    default:
      return <span>{action.action}</span>;
  }
}

function format(value: unknown): string {
  if (value === true) return "да";
  if (value === false) return "нет";
  if (value === null || value === undefined) return "по умолчанию";
  return String(value);
}
