import { useState } from "react";
import { adminApi, errorMessage } from "../../api/client";
import type { Promo } from "../../api/types";
import { ErrorState, Spinner } from "../../components/States";
import { useAdminMutation, usePromos } from "../../lib/adminQueries";
import { date } from "../../lib/format";

export function Promos() {
  const { data, isPending, error, refetch } = usePromos();
  return (
    <>
      <CreatePromo />
      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : (
        <section className="card">
          <h2>Промокоды</h2>
          {data.length === 0 ? (
            <p className="muted">Ещё не создано ни одного</p>
          ) : (
            <ul className="list">
              {data.map((p) => (
                <PromoItem key={p.id} promo={p} />
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}

function CreatePromo() {
  const [code, setCode] = useState("");
  const [days, setDays] = useState("7");
  const [max, setMax] = useState("");
  const [expires, setExpires] = useState("");
  const [newOnly, setNewOnly] = useState(false);
  const [note, setNote] = useState("");
  const create = useAdminMutation(
    () =>
      adminApi.createPromo({
        code: code.trim() || undefined,
        days: Number(days),
        max_activations: max ? Number(max) : null,
        expires_at: expires ? new Date(`${expires}T23:59:59`).toISOString() : null,
        new_users_only: newOnly,
        note: note.trim() || undefined,
      }),
    "promos",
    "actions",
  );
  const valid = Number(days) >= 1 && Number(days) <= 365 && (!code || /^[A-Za-z0-9_-]{3,32}$/.test(code));

  return (
    <form
      className="card form"
      onSubmit={(e) => {
        e.preventDefault();
        if (!valid) return;
        create.mutate(undefined, {
          onSuccess: () => {
            setCode("");
            setMax("");
            setExpires("");
            setNote("");
          },
        });
      }}
    >
      <h2>Новый промокод</h2>
      <div className="fields-3">
        <label className="field">
          <span>Код</span>
          <input
            className="input mono"
            placeholder="случайный"
            value={code}
            maxLength={32}
            onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9_-]/g, ""))}
          />
        </label>
        <label className="field">
          <span>Дней доступа</span>
          <input
            className="input"
            inputMode="numeric"
            value={days}
            onChange={(e) => setDays(e.target.value.replace(/\D/g, ""))}
          />
        </label>
        <label className="field">
          <span>Лимит активаций</span>
          <input
            className="input"
            inputMode="numeric"
            placeholder="без лимита"
            value={max}
            onChange={(e) => setMax(e.target.value.replace(/\D/g, ""))}
          />
        </label>
      </div>
      <div className="row">
        <label className="field">
          <span>Действует до</span>
          <input className="input" type="date" value={expires} onChange={(e) => setExpires(e.target.value)} />
        </label>
        <label className="field">
          <span>Заметка</span>
          <input
            className="input"
            placeholder="для кого или откуда"
            maxLength={255}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
      </div>
      <label className="toggle">
        Только для новых пользователей (зарегистрированы не больше 7 дней назад)
        <input type="checkbox" checked={newOnly} onChange={(e) => setNewOnly(e.target.checked)} />
      </label>
      {create.error && <p className="error">{errorMessage(create.error)}</p>}
      <button className="btn btn-primary" disabled={!valid || create.isPending}>
        Создать
      </button>
    </form>
  );
}

function PromoItem({ promo: p }: { promo: Promo }) {
  const toggle = useAdminMutation(() => adminApi.patchPromo(p.id, { active: !p.active }), "promos", "actions");
  const [copied, setCopied] = useState(false);
  const expired = p.expires_at !== null && new Date(p.expires_at) < new Date();
  const exhausted = p.max_activations !== null && p.activations >= p.max_activations;

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <li className="stack">
      <div className="hbar-head">
        <span>
          <strong className="mono">{p.code}</strong> <span className="muted">+{p.days} дн.</span>
        </span>
        <span className="badges">
          {!p.active && <span className="badge expired">выключен</span>}
          {expired && <span className="badge expired">истёк</span>}
          {exhausted && <span className="badge expired">исчерпан</span>}
          {p.new_users_only && <span className="badge">для новых</span>}
        </span>
      </div>
      <span className="muted small">
        Активаций {p.activations}
        {p.max_activations !== null ? ` из ${p.max_activations}` : ""} · ещё пользуются {p.retained}
        {p.expires_at ? ` · до ${date(p.expires_at)}` : ""}
        {p.note ? ` · ${p.note}` : ""}
      </span>
      {p.max_activations !== null && (
        <div className="progress">
          <span style={{ width: `${Math.min(100, (p.activations / p.max_activations) * 100)}%` }} />
        </div>
      )}
      <div className="actions">
        <button className="btn" onClick={() => copy(p.code)}>
          Копировать код
        </button>
        {p.link && (
          <button className="btn" onClick={() => copy(p.link!)}>
            Копировать ссылку
          </button>
        )}
        <button className={p.active ? "btn danger" : "btn"} disabled={toggle.isPending} onClick={() => toggle.mutate(undefined)}>
          {p.active ? "Выключить" : "Включить"}
        </button>
        {copied && <span className="success small">Скопировано</span>}
      </div>
    </li>
  );
}
