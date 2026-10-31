import { PromoCard, ReferralCard } from "../components/Growth";
import { Plans } from "../components/Plans";
import { tr } from "../lib/i18n";

export function Paywall() {
  return (
    <div className="page">
      <div className="card paywall">
        <span className="feature-icon">⏳</span>
        <h1>{tr("Пробный период закончился", "Your free trial has ended")}</h1>
        <p className="muted">
          {tr(
            "Все твои записи сохранены и будут доступны сразу после оплаты.",
            "All your entries are saved and will be available right after you subscribe.",
          )}
        </p>
      </div>
      <Plans />
      <PromoCard />
      <ReferralCard />
    </div>
  );
}
