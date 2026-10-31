import type { Plan } from "../api/types";
import { plural } from "../lib/format";
import { locale, tr } from "../lib/i18n";
import { usePlans } from "../lib/queries";
import { isMiniApp, openExternal } from "../lib/telegram";

const SIGNS: Record<string, string> = { RUB: "₽", EUR: "€", USD: "$" };

function price(amount: number, currency: string | null) {
  const value = (amount / 100).toLocaleString(locale(), { maximumFractionDigits: 2 });
  return `${value} ${currency ? (SIGNS[currency] ?? currency) : ""}`.trim();
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
  const best = data.reduce((a, b) => (b.days > a.days ? b : a));
  return (
    <section className="plans">
      {data.map((plan) => (
        <PlanCard key={plan.code} plan={plan} featured={plan === best && data.length > 1} />
      ))}
      <p className="muted small center">
        {tr(
          "Оплата через Tribute: СБП или звёзды Telegram. Доступ продлится автоматически.",
          "Checkout via Tribute: SBP or Telegram Stars. Access is extended automatically.",
        )}
      </p>
    </section>
  );
}

function PlanCard({ plan, featured }: { plan: Plan; featured: boolean }) {
  const monthly = plan.amount !== null && plan.days > 31 ? plan.amount / (plan.days / 30) : null;
  return (
    <button className={featured ? "card plan featured" : "card plan"} onClick={() => openExternal(isMiniApp ? plan.link : plan.web_link)}>
      <span className="plan-info">
        <strong>{title(plan.days)}</strong>
        {monthly !== null && (
          <span className="muted small">
            {price(monthly, plan.currency)} {tr("в месяц", "per month")}
          </span>
        )}
      </span>
      {featured && <span className="plan-badge">{tr("Выгодно", "Best value")}</span>}
      <span className="plan-price">
        {plan.amount !== null ? price(plan.amount, plan.currency) : tr("Купить", "Buy")}
      </span>
    </button>
  );
}
