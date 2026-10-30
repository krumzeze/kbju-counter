import { useState } from "react";
import { adminApi, errorMessage } from "../../api/client";
import type { Broadcast, Segment } from "../../api/types";
import { ErrorState, Spinner } from "../../components/States";
import { useAdminMutation, useBroadcasts, useSegments } from "../../lib/adminQueries";
import { dateTime, round } from "../../lib/format";
import { confirmAction } from "../../lib/telegram";

const SEGMENTS: { value: Segment; label: string }[] = [
  { value: "all", label: "Все" },
  { value: "trial", label: "На триале" },
  { value: "active", label: "С подпиской" },
  { value: "expired", label: "Доступ истёк" },
  { value: "inactive", label: "Неактивны 7+ дней" },
];

const STATUS: Record<Broadcast["status"], string> = {
  draft: "черновик",
  sending: "отправляется",
  done: "отправлена",
  cancelled: "остановлена",
};

export function Broadcasts() {
  const [text, setText] = useState("");
  const [segment, setSegment] = useState<Segment>("all");
  const segments = useSegments();
  const list = useBroadcasts();
  const create = useAdminMutation(
    () => adminApi.createBroadcast(text, segment),
    "broadcasts",
  );
  const size = segments.data?.find((s) => s.key === segment)?.count;

  return (
    <>
      <section className="card stack">
        <div className="card-head">
          <h2>Новая рассылка</h2>
          <span className="muted small">HTML: &lt;b&gt;, &lt;i&gt;, &lt;a href&gt;, &lt;code&gt;</span>
        </div>
        <textarea
          className="input"
          rows={5}
          maxLength={4096}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Что нового в Белке…"
        />
        <div className="chips">
          {SEGMENTS.map((s) => (
            <button
              key={s.value}
              className="chip"
              aria-pressed={segment === s.value}
              onClick={() => setSegment(s.value)}
            >
              {s.label}
              {segments.data && (
                <span className="muted"> {segments.data.find((x) => x.key === s.value)?.count}</span>
              )}
            </button>
          ))}
        </div>
        <p className="muted small">
          Сначала сообщение придёт тебе как превью, потом его можно отправить
          {size !== undefined ? ` ${round(size)} получателям` : ""}. Заблокированные и те, кто
          заблокировал бота, не получат.
        </p>
        <button
          className="btn btn-primary"
          disabled={!text.trim() || create.isPending}
          onClick={() => create.mutate(undefined, { onSuccess: () => setText("") })}
        >
          Отправить превью себе
        </button>
        {create.error && <p className="error">{errorMessage(create.error)}</p>}
      </section>

      {list.isPending ? (
        <Spinner />
      ) : list.error ? (
        <ErrorState message={errorMessage(list.error)} onRetry={() => list.refetch()} />
      ) : (
        <section className="card">
          <h2>История</h2>
          {list.data.length === 0 ? (
            <p className="muted">Рассылок ещё не было</p>
          ) : (
            <ul className="list">
              {list.data.map((b) => (
                <BroadcastItem key={b.id} broadcast={b} />
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}

function BroadcastItem({ broadcast: b }: { broadcast: Broadcast }) {
  const send = useAdminMutation(() => adminApi.sendBroadcast(b.id), "broadcasts", "actions");
  const cancel = useAdminMutation(() => adminApi.cancelBroadcast(b.id), "broadcasts", "actions");
  const done = b.sent + b.failed + b.blocked;
  const segment = SEGMENTS.find((s) => s.value === b.segment)?.label ?? b.segment;

  return (
    <li className="stack">
      <div className="hbar-head">
        <strong>
          #{b.id} · {segment}
        </strong>
        <span className="muted small">
          {STATUS[b.status]} · {dateTime(b.created_at)}
        </span>
      </div>
      <p className="preview small">{b.text}</p>
      {b.status !== "draft" && (
        <>
          <div className="progress" role="progressbar" aria-valuenow={done} aria-valuemax={b.total}>
            <span style={{ width: `${b.total ? Math.min(100, (done / b.total) * 100) : 100}%` }} />
          </div>
          <span className="muted small">
            доставлено {b.sent} · заблокировали бота {b.blocked} · ошибок {b.failed} · всего {b.total}
          </span>
        </>
      )}
      <div className="actions">
        {b.status === "draft" && (
          <button
            className="btn btn-primary"
            disabled={send.isPending}
            onClick={async () => {
              if (await confirmAction(`Отправить рассылку #${b.id}? Это нельзя отменить для уже доставленных.`))
                send.mutate(undefined);
            }}
          >
            Отправить всем
          </button>
        )}
        {(b.status === "draft" || b.status === "sending") && (
          <button className="btn danger" disabled={cancel.isPending} onClick={() => cancel.mutate(undefined)}>
            {b.status === "draft" ? "Удалить черновик" : "Остановить"}
          </button>
        )}
      </div>
      {(send.error || cancel.error) && <p className="error">{errorMessage(send.error ?? cancel.error)}</p>}
    </li>
  );
}
