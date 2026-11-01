import { type ReactNode, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { adminApi, errorMessage } from "../../api/client";
import type { UserDetail as Detail, UserPatch } from "../../api/types";
import { BarChart } from "../../components/BarChart";
import { ErrorState, Spinner } from "../../components/States";
import { useAdminMutation, useUser, useUserAction } from "../../lib/adminQueries";
import { ago, date, dateTime, displayName, percent, round, usd } from "../../lib/format";
import { confirmAction } from "../../lib/telegram";
import { ActionText } from "./Log";
import { STATUS_LABELS, UserBadges } from "./Users";

const GOALS: Record<string, string> = { lose: "похудеть", maintain: "держать вес", gain: "набрать" };

export function UserDetail() {
  const id = Number(useParams().id);
  const { data: user, isPending, error, refetch } = useUser(id);
  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  return (
    <>
      <div className="page-head">
        <div className="user-cell">
          <h1>{displayName(user)}</h1>
          <span className="muted small">
            {user.first_name} · ID {user.id}
            {user.username && (
              <>
                {" · "}
                <a className="positive" href={`https://t.me/${user.username}`} target="_blank" rel="noreferrer">
                  открыть в Telegram
                </a>
              </>
            )}
          </span>
        </div>
        <UserBadges user={user} />
      </div>

      <div className="grid-2">
        <AccessCard user={user} />
        <ModerationCard user={user} />
      </div>

      <div className="grid-2">
        <section className="card">
          <div className="card-head">
            <h2>Профиль</h2>
            <span className="muted small">зарегистрирован {date(user.created_at)}</span>
          </div>
          <dl className="metric-list">
            <Fact label="Пол, возраст" value={`${user.sex === "f" ? "Ж" : user.sex === "m" ? "М" : "—"}, ${user.age ?? "—"}`} />
            <Fact label="Рост / вес" value={`${user.height_cm ?? "—"} см / ${user.weight_kg ?? "—"} кг`} />
            <Fact label="Цель" value={user.goal ? GOALS[user.goal] : "—"} />
            <Fact label="Часовой пояс" value={user.timezone} />
            <Fact label="Источник" value={user.source ?? "напрямую"} />
            <Fact label="Был в сети" value={ago(user.last_seen_at)} />
          </dl>
        </section>
        <section className="card">
          <div className="card-head">
            <h2>Рефералы и LLM</h2>
          </div>
          <dl className="metric-list">
            <Fact
              label="Пригласил его"
              value={
                user.referred_by ? (
                  <Link className="positive" to={`/admin/users/${user.referred_by.id}`}>
                    {displayName(user.referred_by)}
                  </Link>
                ) : (
                  "—"
                )
              }
            />
            <Fact label="Пригласил сам" value={`${user.invited} · оплатили ${user.invited_paid}`} />
            <Fact label="Дней за рефералов" value={round(user.referral_days)} />
            <Fact label="Запросов к LLM" value={round(user.llm_requests)} />
            <Fact label="Ошибок" value={user.llm_requests ? percent(user.llm_errors / user.llm_requests) : "—"} />
            <Fact label="Потрачено" value={usd(user.cost_usd)} />
          </dl>
        </section>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Записи еды по дням</h2>
          <span className="muted small">30 дней</span>
        </div>
        <BarChart
          label="Записи еды по дням"
          height={160}
          points={user.activity.map((a) => ({ day: a.day, value: a.meals }))}
          format={(v) => round(v)}
        />
        <p className="muted small" style={{ marginTop: 8 }}>
          За 30 дней: приёмов пищи {sum(user.activity, "meals")} · подходов {sum(user.activity, "sets")} ·
          дней с шагами {user.activity.filter((a) => a.steps > 0).length}
        </p>
      </section>

      <MessageCard user={user} />

      <div className="grid-2">
        <section className="card">
          <h2>Последняя еда</h2>
          {user.meals.length === 0 ? (
            <p className="muted">Пока ничего</p>
          ) : (
            <ul className="list">
              {user.meals.map((m) => (
                <li key={m.id}>
                  <div className="hbar-head">
                    <strong>
                      {m.source === "photo" ? "📸" : m.source === "manual" ? "🍽️" : "✍️"} {m.title}
                    </strong>
                    <span>{round(m.totals.kcal)} ккал</span>
                  </div>
                  <span className="muted small">
                    {dateTime(m.created_at)} · {m.items.map((i) => i.name).join(", ")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card">
          <h2>Запросы к LLM</h2>
          {user.llm.length === 0 ? (
            <p className="muted">Пока ничего</p>
          ) : (
            <ul className="list">
              {user.llm.map((c) => (
                <li key={c.created_at} className="hbar-head">
                  <span>
                    {c.ok ? (c.no_food ? "🍽️ нет еды" : "✅") : "❌ ошибка"}{" "}
                    <span className="muted small">
                      {dateTime(c.created_at)} · {c.kind}
                    </span>
                  </span>
                  <span className="muted small">
                    {(c.latency_ms / 1000).toFixed(1)} с · {c.cost_usd === null ? "—" : usd(c.cost_usd)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="grid-2">
        <section className="card">
          <h2>Промокоды</h2>
          {user.redemptions.length === 0 ? (
            <p className="muted">Не активировал</p>
          ) : (
            <ul className="list">
              {user.redemptions.map((r) => (
                <li key={r.code} className="hbar-head">
                  <span className="mono">{r.code}</span>
                  <span className="muted small">
                    +{r.days} дн. · {date(r.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card">
          <h2>Действия админов</h2>
          {user.actions.length === 0 ? (
            <p className="muted">Не было</p>
          ) : (
            <ul className="list">
              {user.actions.map((a) => (
                <li key={a.id}>
                  <ActionText action={a} />
                  <div className="muted small">
                    {dateTime(a.created_at)} · {a.admin ? displayName(a.admin) : "—"}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <DangerZone user={user} />
    </>
  );
}

function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function AccessCard({ user }: { user: Detail }) {
  const [days, setDays] = useState("30");
  const grant = useUserAction(user.id, (n: number) => adminApi.grant(user.id, n));
  const revoke = useUserAction(user.id, () => adminApi.revoke(user.id));
  const lifetime = useUserAction(user.id, (value: boolean) =>
    adminApi.patchUser(user.id, { lifetime_access: value }),
  );
  const error = grant.error ?? revoke.error ?? lifetime.error;
  const n = Number(days);

  return (
    <section className="card stack">
      <div className="card-head">
        <h2>Доступ</h2>
        <span className={`badge ${user.status}`}>{STATUS_LABELS[user.status]}</span>
      </div>
      <p>
        {user.status === "lifetime"
          ? "Бесплатно навсегда"
          : user.status === "expired"
            ? `Истёк ${date(user.access_until)}`
            : `До ${dateTime(user.access_until)}`}
        <span className="muted small"> · триал до {date(user.trial_ends_at)}</span>
      </p>
      <div className="inline-form">
        <input
          className="input"
          inputMode="numeric"
          value={days}
          onChange={(e) => setDays(e.target.value.replace(/\D/g, ""))}
          aria-label="Дней"
        />
        <button
          className="btn btn-primary"
          disabled={!(n >= 1 && n <= 3650) || grant.isPending}
          onClick={() => grant.mutate(n)}
        >
          +{n || 0} дн.
        </button>
      </div>
      <div className="chips">
        {[7, 30, 90, 365].map((d) => (
          <button key={d} className="chip" onClick={() => setDays(String(d))}>
            {d} дн.
          </button>
        ))}
      </div>
      <div className="actions">
        <button className="btn" onClick={() => lifetime.mutate(!user.lifetime_access)}>
          {user.lifetime_access ? "Убрать «навсегда»" : "Бесплатно навсегда"}
        </button>
        <button
          className="btn danger"
          disabled={user.status === "expired"}
          onClick={async () => {
            if (await confirmAction("Забрать доступ у пользователя?")) revoke.mutate(undefined);
          }}
        >
          Забрать доступ
        </button>
      </div>
      {error && <p className="error">{errorMessage(error)}</p>}
    </section>
  );
}

function ModerationCard({ user }: { user: Detail }) {
  const patch = useUserAction(user.id, (body: UserPatch) => adminApi.patchUser(user.id, body));
  const [limit, setLimit] = useState(user.daily_limit === null ? "" : String(user.daily_limit));

  return (
    <section className="card stack">
      <h2>Управление</h2>
      <label className="toggle">
        Заблокирован
        <input
          type="checkbox"
          checked={user.is_blocked}
          onChange={async (e) => {
            const value = e.target.checked;
            if (!value || (await confirmAction("Заблокировать пользователя? Бот перестанет ему отвечать.")))
              patch.mutate({ is_blocked: value });
          }}
        />
      </label>
      <label className="toggle">
        Админ
        <input
          type="checkbox"
          checked={user.is_admin}
          onChange={async (e) => {
            const value = e.target.checked;
            const text = value ? "Сделать админом? Он увидит всех пользователей." : "Снять права админа?";
            if (await confirmAction(text)) patch.mutate({ is_admin: value });
          }}
        />
      </label>
      <div className="field">
        <span>Свой лимит распознаваний в день</span>
        <div className="inline-form">
          <input
            className="input"
            inputMode="numeric"
            placeholder="по умолчанию"
            value={limit}
            onChange={(e) => setLimit(e.target.value.replace(/\D/g, ""))}
          />
          <button
            className="btn"
            disabled={patch.isPending}
            onClick={() => patch.mutate({ daily_limit: limit === "" ? null : Number(limit) })}
          >
            Сохранить
          </button>
        </div>
      </div>
      {patch.error && <p className="error">{errorMessage(patch.error)}</p>}
    </section>
  );
}

function MessageCard({ user }: { user: Detail }) {
  const [text, setText] = useState("");
  const send = useAdminMutation((value: string) => adminApi.message(user.id, value), "user");

  return (
    <section className="card stack">
      <div className="card-head">
        <h2>Написать от имени бота</h2>
        <span className="muted small">поддерживается HTML: &lt;b&gt;, &lt;i&gt;, &lt;a&gt;</span>
      </div>
      <textarea
        className="input"
        rows={3}
        maxLength={4096}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Привет! Продлил тебе доступ на месяц 🙂"
      />
      <div className="actions">
        <button
          className="btn btn-primary"
          disabled={!text.trim() || send.isPending || user.bot_blocked}
          onClick={() => send.mutate(text, { onSuccess: () => setText("") })}
        >
          Отправить
        </button>
        {user.bot_blocked && <span className="muted small">Пользователь заблокировал бота</span>}
        {send.isSuccess && <span className="success small">Отправлено</span>}
      </div>
      {send.error && <p className="error">{errorMessage(send.error)}</p>}
    </section>
  );
}

function DangerZone({ user }: { user: Detail }) {
  const navigate = useNavigate();
  const remove = useAdminMutation(() => adminApi.deleteUser(user.id), "users", "dashboard");
  return (
    <section className="card stack">
      <h2>Удаление</h2>
      <p className="muted small">
        Удалит пользователя и все его данные: еду, тренировки, вес. Отменить нельзя. Используй по
        запросу пользователя.
      </p>
      <button
        className="btn danger"
        disabled={remove.isPending}
        onClick={async () => {
          if (await confirmAction(`Удалить ${displayName(user)} со всеми данными?`))
            remove.mutate(undefined, { onSuccess: () => navigate("/admin/users", { replace: true }) });
        }}
      >
        Удалить пользователя
      </button>
      {remove.error && <p className="error">{errorMessage(remove.error)}</p>}
    </section>
  );
}

function sum(days: Detail["activity"], key: "meals" | "sets"): number {
  return days.reduce((total, d) => total + d[key], 0);
}
