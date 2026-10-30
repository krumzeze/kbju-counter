import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage, type UserQuery } from "../../api/client";
import type { UserFilter, UserRow, UserSort } from "../../api/types";
import { ErrorState, Spinner } from "../../components/States";
import { useUsers } from "../../lib/adminQueries";
import { ago, date, displayName, round, usd } from "../../lib/format";

const PAGE = 50;

const FILTERS: { value: UserFilter; label: string }[] = [
  { value: "all", label: "Все" },
  { value: "trial", label: "Триал" },
  { value: "active", label: "Подписка" },
  { value: "expired", label: "Истёк" },
  { value: "inactive", label: "Неактивны 7+ дней" },
  { value: "blocked", label: "Заблокированы" },
  { value: "admins", label: "Админы" },
];

const SORTS: { value: UserSort; label: string }[] = [
  { value: "created_at", label: "Дата регистрации" },
  { value: "last_seen_at", label: "Последняя активность" },
  { value: "analyses", label: "Распознавания" },
  { value: "cost", label: "Расходы на LLM" },
  { value: "access_until", label: "Доступ до" },
];

export const STATUS_LABELS: Record<string, string> = {
  trial: "триал",
  active: "подписка",
  lifetime: "навсегда",
  expired: "истёк",
};

export function Users() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState<UserQuery>({
    q: "",
    filter: "all",
    sort: "created_at",
    desc: true,
    offset: 0,
    limit: PAGE,
  });
  const { data, isPending, error, refetch, isFetching } = useUsers(query);
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => setQuery((q) => ({ ...q, q: search, offset: 0 })), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const update = (patch: Partial<UserQuery>) => setQuery((q) => ({ ...q, offset: 0, ...patch }));
  const open = (user: UserRow) => navigate(`/admin/users/${user.id}`);

  return (
    <>
      <div className="toolbar">
        <input
          className="input"
          type="search"
          placeholder="Username, имя или Telegram ID"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="select"
          aria-label="Сортировка"
          value={query.sort}
          onChange={(e) => update({ sort: e.target.value as UserSort })}
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <button
          className="btn small"
          aria-label="Направление сортировки"
          onClick={() => update({ desc: !query.desc })}
        >
          {query.desc ? "↓ по убыванию" : "↑ по возрастанию"}
        </button>
      </div>
      <div className="chips">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            className="chip"
            aria-pressed={query.filter === f.value}
            onClick={() => update({ filter: f.value })}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : (
        <section className="card">
          <div className="card-head">
            <h2>Найдено: {round(data.total)}</h2>
            {isFetching && <span className="muted small">обновляю…</span>}
          </div>
          {data.items.length === 0 ? (
            <p className="muted">Никого не нашлось</p>
          ) : (
            <>
              <div className="table-wrap desktop">
                <table className="table users">
                  <thead>
                    <tr>
                      <th>Пользователь</th>
                      <th>Статус</th>
                      <th>Доступ до</th>
                      <th>Регистрация</th>
                      <th>Активность</th>
                      <th className="num">Распознаваний</th>
                      <th className="num">LLM</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((u) => (
                      <tr key={u.id} onClick={() => open(u)}>
                        <td>
                          <div className="user-cell">
                            <strong>{displayName(u)}</strong>
                            <span className="muted small">{u.id}</span>
                          </div>
                        </td>
                        <td>
                          <UserBadges user={u} />
                        </td>
                        <td>{u.status === "lifetime" ? "∞" : date(u.access_until)}</td>
                        <td>{date(u.created_at)}</td>
                        <td>{ago(u.last_seen_at)}</td>
                        <td className="num">{round(u.analyses)}</td>
                        <td className="num">{usd(u.cost_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="user-cards">
                {data.items.map((u) => (
                  <button key={u.id} className="card user-card" onClick={() => open(u)}>
                    <div className="user-cell">
                      <strong>{displayName(u)}</strong>
                      <span className="muted small">
                        {ago(u.last_seen_at)} · {round(u.analyses)} распозн. · {usd(u.cost_usd)}
                      </span>
                    </div>
                    <UserBadges user={u} />
                  </button>
                ))}
              </div>
            </>
          )}
          <div className="actions" style={{ marginTop: 12, justifyContent: "space-between" }}>
            <button
              className="btn small"
              disabled={query.offset === 0}
              onClick={() => setQuery((q) => ({ ...q, offset: Math.max(0, q.offset - PAGE) }))}
            >
              ← Назад
            </button>
            <span className="muted small" style={{ alignSelf: "center" }}>
              {data.total ? `${query.offset + 1}–${Math.min(query.offset + PAGE, data.total)}` : ""}
            </span>
            <button
              className="btn small"
              disabled={query.offset + PAGE >= data.total}
              onClick={() => setQuery((q) => ({ ...q, offset: q.offset + PAGE }))}
            >
              Дальше →
            </button>
          </div>
        </section>
      )}
    </>
  );
}

export function UserBadges({ user }: { user: UserRow }) {
  return (
    <span className="badges">
      <span className={`badge ${user.status}`}>{STATUS_LABELS[user.status]}</span>
      {user.is_admin && <span className="badge">админ</span>}
      {user.is_blocked && <span className="badge warn">заблокирован</span>}
      {user.bot_blocked && <span className="badge warn">бот в блоке</span>}
    </span>
  );
}
