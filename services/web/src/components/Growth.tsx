import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api, errorMessage } from "../api/client";
import { daysWord } from "../lib/format";
import { tr } from "../lib/i18n";
import { useInvalidate } from "../lib/queries";
import { Art } from "./Art";
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
      ? tr("Такого промокода нет", "This promo code doesn't exist")
      : redeem.error && errorMessage(redeem.error);

  return (
    <form
      className="card stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (code.trim()) redeem.mutate();
      }}
    >
      <h2>{tr("Промокод", "Promo code")}</h2>
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
          {tr("Применить", "Apply")}
        </button>
      </div>
      {failure && <p className="error small">{failure}</p>}
      {redeem.data && (
        <p className="success small">
          +{redeem.data.days} {daysWord(redeem.data.days)} {tr("доступа", "of access")} 🎉
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
    <section className="card sand stack">
      <div className="invite-head">
        <h2>{tr("Пригласи друзей", "Invite friends")}</h2>
        <Art name="invite" />
      </div>
      <p className="muted small">
        {tr(
          `Друг получит ${data.trial_days} дней бесплатно, а ты +${data.reward_days} дней доступа за каждую его оплату подписки.`,
          `Your friend gets ${data.trial_days} free days, and you get +${data.reward_days} days of access for each subscription payment they make.`,
        )}
      </p>
      <input className="input mono" readOnly value={link} onFocus={(e) => e.target.select()} />
      <div className="actions">
        <button
          className="btn btn-primary"
          onClick={() => shareLink(
              link,
              tr("Считаю калории по фото в Белке, попробуй:", "I count calories from photos with Belok, try it:"),
            )}
        >
          {tr("Поделиться", "Share")}
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
          {copied ? tr("Скопировано", "Copied") : tr("Копировать", "Copy")}
        </button>
      </div>
      <div className="stats-row three">
        <div className="stat">
          <strong>{data.invited}</strong>
          <span className="muted">{tr("пригласил", "invited")}</span>
        </div>
        <div className="stat">
          <strong>{data.paid}</strong>
          <span className="muted">{tr("оплатили", "paid")}</span>
        </div>
        <div className="stat">
          <strong>{data.days}</strong>
          <span className="muted">{tr("дней получил", "days earned")}</span>
        </div>
      </div>
    </section>
  );
}
