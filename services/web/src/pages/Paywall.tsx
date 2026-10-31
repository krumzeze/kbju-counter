import { PromoCard, ReferralCard } from "../components/Growth";
import { tr } from "../lib/i18n";

export function Paywall() {
  return (
    <div className="page">
      <div className="card paywall">
        <span className="feature-icon">⏳</span>
        <h1>{tr("Пробный период закончился", "Your free trial has ended")}</h1>
        <p className="muted">
          {tr(
            "Скоро здесь появится подписка. Все твои записи сохранены и будут доступны сразу после продления.",
            "Subscriptions are coming soon. All your entries are saved and will be available as soon as you renew.",
          )}
        </p>
      </div>
      <PromoCard />
      <ReferralCard />
    </div>
  );
}
