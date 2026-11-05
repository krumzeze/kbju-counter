import { useMutation } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import type { Plan } from "../api/types";
import { plural } from "../lib/format";
import { locale, tr } from "../lib/i18n";
import { useInvalidate, usePlans } from "../lib/queries";
import { haptic, isMiniApp, openExternal, webApp } from "../lib/telegram";

const SIGNS: Record<string, string> = { RUB: "₽", EUR: "€", USD: "$", XTR: "⭐" };

function price(plan: Plan, amount: number) {
  const value = plan.provider === "stars" ? amount : amount / 100;
  const text = value.toLocaleString(locale(), { maximumFractionDigits: plan.provider === "stars" ? 0 : 2 });
  return `${text} ${plan.currency ? (SIGNS[plan.currency] ?? plan.currency) : ""}`.trim();
}

function title(days: number) {
  if (days === 365) return tr("1 год", "1 year");
  if (days % 30 === 0) {
    const n = days / 30;
    return tr(`${n} ${plural(n, "месяц", "месяца", "месяцев")}`, `${n} ${n === 1 ? "month" : "months"}`);
  }
  return tr(`${days} ${plural(days, "день", "дня", "дней")}`, `${days} days`);
}

export function Plans() {
  const { data } = usePlans();
  if (!data?.length) return null;
  const stars = data.filter((p) => p.provider === "stars");
  const tribute = data.filter((p) => p.provider === "tribute");
  return (
    <>
      {stars.length > 0 && (
        <section className="plans">
          <h2>{tr("Оплата звёздами Telegram", "Pay with Telegram Stars")}</h2>
          <PlanList plans={stars} />
        </section>
      )}
      {tribute.length > 0 && (
        <section className="plans">
          <h2>{tr("Картой или СБП", "Card or SBP")}</h2>
          <PlanList plans={tribute} />
          <p className="muted small center">
            {tr("Оплата через Tribute, доступ продлится автоматически.", "Checkout via Tribute, access is extended automatically.")}
          </p>
        </section>
      )}
    </>
  );
}

function PlanList({ plans }: { plans: Plan[] }) {
  const best = plans.reduce((a, b) => (b.days > a.days ? b : a));
  return plans.map((plan) => (
    <PlanCard key={plan.code} plan={plan} featured={plan === best && plans.length > 1} />
  ));
}

function PlanCard({ plan, featured }: { plan: Plan; featured: boolean }) {
  const invalidate = useInvalidate();
  const buy = useMutation({
    mutationFn: async () => {
      if (plan.provider === "tribute") {
        openExternal((isMiniApp ? plan.link : plan.web_link) ?? "");
        return;
      }
      const { link } = await api.starsInvoice(plan.days);
      if (!webApp?.openInvoice) {
        openExternal(link);
        return;
      }
      webApp.openInvoice(link, (status) => {
        if (status === "paid") {
          haptic("success");
          // The bot records the payment a moment after Telegram reports it.
          setTimeout(() => void invalidate("me", "day"), 1500);
        } else if (status === "failed") {
          haptic("error");
        }
      });
    },
  });
  const monthly = plan.amount !== null && plan.days > 31 ? plan.amount / (plan.days / 30) : null;
  return (
    <>
      <button
        className={featured ? "card plan featured" : "card plan"}
        disabled={buy.isPending}
        onClick={() => buy.mutate()}
      >
        <span className="plan-info">
          <strong>{title(plan.days)}</strong>
          {monthly !== null && (
            <span className="muted small">
              {price(plan, Math.round(monthly))} {tr("в месяц", "per month")}
            </span>
          )}
        </span>
        {featured && <span className="plan-badge">{tr("Выгодно", "Best value")}</span>}
        <span className="plan-price">
          {plan.amount !== null ? tr(`Купить за ${price(plan, plan.amount)}`, `Buy for ${price(plan, plan.amount)}`) : tr("Купить", "Buy")}
        </span>
      </button>
      {buy.isError && <p className="error">{errorMessage(buy.error)}</p>}
    </>
  );
}
