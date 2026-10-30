import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api, errorMessage } from "../api/client";
import { plural } from "../lib/format";
import { useInvalidate } from "../lib/queries";
import { haptic, shareLink } from "../lib/telegram";

export function PromoCard() {
  const [code, setCode] = useState("");
  const invalidate = useInvalidate();
  const redeem = useMutation({
    mutationFn: () => api.redeemPromo(code),
    onSuccess: () => {
      haptic("success");
      setCode("");
      invalidate("me");
    },
    onError: () => haptic("error"),
  });
  const failure =
    redeem.error instanceof ApiError && redeem.error.detail === "not_found"
      ? "Такого промокода нет"
      : redeem.error && errorMessage(redeem.error);

  return (
    <form
      className="card stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (code.trim()) redeem.mutate();
      }}
    >
      <h2>Промокод</h2>
      <div className="inline-form">
        <input
          className="input mono"
          placeholder="BELOK"
          value={code}
          maxLength={32}
          autoCapitalize="characters"
          onChange={(e) => setCode(e.target.value.toUpperCase())}
        />
        <button className="btn btn-primary" disabled={!code.trim() || redeem.isPending}>
          Применить
        </button>
      </div>
      {failure && <p className="error small">{failure}</p>}
      {redeem.data && (
        <p className="success small">
          +{redeem.data.days} {plural(redeem.data.days, "день", "дня", "дней")} доступа 🎉
        </p>
      )}
    </form>
  );
}

export function ReferralCard() {
  const { data } = useQuery({ queryKey: ["referral"], queryFn: api.referral });
  const [copied, setCopied] = useState(false);
  if (!data?.link) return null;
  const link = data.link;

  return (
    <section className="card stack">
      <h2>Пригласи друзей</h2>
      <p className="muted small">
        Друг получит {data.trial_days} дней бесплатно, а ты +{data.reward_days} дней доступа за каждую
        его оплату подписки.
      </p>
      <input className="input mono" readOnly value={link} onFocus={(e) => e.target.select()} />
      <div className="actions">
        <button
          className="btn btn-primary"
          onClick={() => shareLink(link, "Считаю калории по фото в Белке, попробуй:")}
        >
          Поделиться
        </button>
        <button
          className="btn"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(link);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            } catch {
              setCopied(false);
            }
          }}
        >
          {copied ? "Скопировано" : "Копировать"}
        </button>
      </div>
      <div className="stats-row three">
        <div className="stat">
          <strong>{data.invited}</strong>
          <span className="muted">пригласил</span>
        </div>
        <div className="stat">
          <strong>{data.paid}</strong>
          <span className="muted">оплатили</span>
        </div>
        <div className="stat">
          <strong>{data.days}</strong>
          <span className="muted">дней получил</span>
        </div>
      </div>
    </section>
  );
}
