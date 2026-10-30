import { PromoCard, ReferralCard } from "../components/Growth";

export function Paywall() {
  return (
    <div className="page">
      <div className="card paywall">
        <span className="feature-icon">⏳</span>
        <h1>Пробный период закончился</h1>
        <p className="muted">
          Скоро здесь появится подписка. Все твои записи сохранены и будут доступны сразу после
          продления.
        </p>
      </div>
      <PromoCard />
      <ReferralCard />
    </div>
  );
}
