import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorMessage } from "../api/client";
import type { SupportMessage } from "../api/types";
import { ErrorState, Spinner } from "../components/States";
import { locale, tr } from "../lib/i18n";
import { haptic, isMiniApp } from "../lib/telegram";

export function Support() {
  const client = useQueryClient();
  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["support"],
    queryFn: api.support,
    refetchInterval: 30_000,
  });
  const [text, setText] = useState("");
  const send = useMutation({
    mutationFn: () => api.sendSupport(text.trim()),
    onSuccess: (message) => {
      haptic("success");
      setText("");
      client.setQueryData<SupportMessage[]>(["support"], (old) => [...(old ?? []), message]);
    },
    onError: () => haptic("error"),
  });

  return (
    <div className="page">
      <h1>{tr("Поддержка", "Support")}</h1>
      <p className="muted">
        {isMiniApp
          ? tr(
              "Опиши вопрос или проблему. Ответ придёт в чат с ботом и появится здесь.",
              "Describe your question or problem. The reply will arrive in the bot chat and show up here.",
            )
          : tr(
              "Опиши вопрос или проблему. Ответ придёт в чат с ботом в Telegram и появится здесь.",
              "Describe your question or problem. The reply will arrive in the bot chat in Telegram and show up here.",
            )}
      </p>

      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : (
        data.length > 0 && (
          <div className="support-thread">
            {data.map((m) => (
              <div key={m.id} className={m.from_admin ? "support-msg reply" : "support-msg"}>
                <p>{m.text}</p>
                <span className="muted small">
                  {m.from_admin ? `${tr("Поддержка", "Support")} · ` : ""}
                  {new Date(m.created_at).toLocaleString(locale(), {
                    day: "numeric",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            ))}
          </div>
        )
      )}

      <textarea
        className="input"
        rows={4}
        maxLength={2000}
        placeholder={tr("Например: оплатил звёздами, но Premium не включился", "For example: I paid with Stars but Premium didn't turn on")}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {send.isError && <p className="error">{errorMessage(send.error)}</p>}
      <button
        className="btn btn-primary btn-block"
        disabled={text.trim().length < 2 || send.isPending}
        onClick={() => send.mutate()}
      >
        {send.isPending ? tr("Отправляю…", "Sending…") : tr("Отправить", "Send")}
      </button>
    </div>
  );
}
