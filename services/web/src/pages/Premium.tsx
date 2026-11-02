import { Link } from "react-router-dom";
import type { Me } from "../api/types";
import { Art } from "../components/Art";
import { PromoCard, ReferralCard } from "../components/Growth";
import { Plans } from "../components/Plans";
import { tr } from "../lib/i18n";

const PERKS = () => [
  tr("Распознавание еды по фото и описанию", "Food recognition from photos and text"),
  tr("Норма калорий по твоему реальному расходу", "Calorie target based on your real expenditure"),
  tr("Вся история веса и прогресса в упражнениях", "Full weight and exercise progress history"),
  tr("Аналитика тренировок за месяцы", "Workout analytics over months"),
];

export function Premium({ me }: { me: Me }) {
  return (
    <div className="page">
      <div className="card peach paywall">
        <Art name="paywall" fallback={<span className="feature-icon">⭐</span>} />
        <h1>{me.has_access ? tr("Premium", "Premium") : tr("Открой Premium", "Get Premium")}</h1>
        {!me.has_access && (
          <p className="muted">
            {tr(
              "Учёт еды вручную, тренировки, шаги, вода и напоминания остаются бесплатными.",
              "Manual food logging, workouts, steps, water and reminders stay free.",
            )}
          </p>
        )}
        <ul className="perks">
          {PERKS().map((perk) => (
            <li key={perk}>{perk}</li>
          ))}
        </ul>
      </div>
      {me.status !== "lifetime" && <Plans />}
      <PromoCard />
      <ReferralCard />
      <Link to="/support" className="card premium-note">
        <span>{tr("Проблема с оплатой? Напиши нам", "Payment issue? Contact us")}</span>
        <span aria-hidden>💬</span>
      </Link>
    </div>
  );
}
