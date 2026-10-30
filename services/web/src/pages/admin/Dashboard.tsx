import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client";
import type { AccessStatus, Dashboard as Data } from "../../api/types";
import { BarChart } from "../../components/BarChart";
import { LineChart } from "../../components/LineChart";
import { ErrorState, Spinner } from "../../components/States";
import { useDashboard } from "../../lib/adminQueries";
import { percent, round, usd } from "../../lib/format";

const STATUSES: { key: AccessStatus; label: string; color: string }[] = [
  { key: "trial", label: "Триал", color: "var(--series-1)" },
  { key: "active", label: "Подписка", color: "var(--series-2)" },
  { key: "lifetime", label: "Навсегда", color: "var(--series-3)" },
  { key: "expired", label: "Истёк", color: "var(--series-rest)" },
];

const FUNNEL: Record<string, string> = {
  registered: "Зарегистрировались",
  profile: "Заполнили анкету",
  first_meal: "Записали еду",
  active_3_days: "Активны 3+ дня",
};

const RAMP = ["var(--ramp-1)", "var(--ramp-2)", "var(--ramp-3)", "var(--ramp-4)"];

export function Dashboard() {
  const { data, isPending, error, refetch } = useDashboard();
  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  return (
    <>
      <section className="kpis">
        <Kpi label="Пользователей" value={round(data.users_total)} sub={`+${data.new_today} сегодня`} />
        <Kpi label="Новых за 7 дней" value={round(data.new_7d)} sub={`${data.new_30d} за 30 дней`} />
        <Kpi label="DAU" value={round(data.dau)} sub={`WAU ${data.wau} · MAU ${data.mau}`} />
        <Kpi
          label="Липкость DAU/MAU"
          value={data.mau ? percent(data.dau / data.mau) : "—"}
          sub="доля ежедневных"
        />
        <Kpi label="LLM за месяц" value={usd(data.cost_month)} sub={`прогноз ${usd(data.cost_forecast)}`} />
        <Kpi
          label="Ошибки за сутки"
          value={percent(data.error_rate_24h)}
          sub={`${data.requests_24h} распознаваний`}
        />
      </section>

      <div className="grid-2">
        <section className="card">
          <div className="card-head">
            <h2>Новые пользователи</h2>
            <span className="muted small">30 дней</span>
          </div>
          <BarChart
            label="Новые пользователи по дням"
            points={data.series.map((p) => ({ day: p.day, value: p.new_users }))}
            format={(v) => round(v)}
          />
        </section>
        <section className="card">
          <div className="card-head">
            <h2>Активные пользователи</h2>
            <span className="muted small">записали хоть что-то за день</span>
          </div>
          <LineChart
            className="series"
            zeroBased
            unit="чел."
            points={data.series.map((p) => ({ day: p.day, value: p.active_users }))}
          />
        </section>
      </div>

      <div className="grid-2">
        <StatusCard data={data} />
        <FunnelCard data={data} />
      </div>

      <div className="grid-2">
        <section className="card">
          <div className="card-head">
            <h2>Расходы на LLM</h2>
            <span className="muted small">сегодня {usd(data.cost_today)}</span>
          </div>
          <BarChart
            label="Расходы на LLM по дням"
            points={data.series.map((p) => ({ day: p.day, value: p.cost_usd }))}
            format={usd}
          />
        </section>
        <section className="card">
          <div className="card-head">
            <h2>Качество распознавания</h2>
            <span className="muted small">24 часа</span>
          </div>
          <dl className="metric-list">
            <Metric label="Запросов" value={round(data.requests_24h)} />
            <Metric label="Ошибок" value={percent(data.error_rate_24h)} />
            <Metric label="«Нет еды на фото»" value={percent(data.no_food_rate_24h)} />
            <Metric label="Цена запроса" value={data.avg_cost === null ? "—" : usd(data.avg_cost)} />
            <Metric label="Задержка p50" value={seconds(data.latency_p50_ms)} />
            <Metric label="Задержка p95" value={seconds(data.latency_p95_ms)} />
          </dl>
          <div className="card-head" style={{ marginTop: 20 }}>
            <h2>Распознавания по дням</h2>
          </div>
          <BarChart
            label="Распознавания по дням"
            height={140}
            points={data.series.map((p) => ({ day: p.day, value: p.analyses }))}
            format={(v) => round(v)}
          />
        </section>
      </div>

      <div className="grid-2">
        <section className="card">
          <div className="card-head">
            <h2>Откуда пришли</h2>
            <span className="muted small">30 дней</span>
          </div>
          {data.sources.length === 0 ? (
            <p className="muted">Пока нет регистраций</p>
          ) : (
            <HBars items={data.sources.map((s) => ({ label: sourceLabel(s.key), value: s.count }))} />
          )}
        </section>
        <section className="card">
          <div className="card-head">
            <h2>Рост</h2>
          </div>
          <dl className="metric-list">
            <Metric label="Пришли по приглашению" value={round(data.referred_users)} />
            <Metric label="Реферальных наград" value={round(data.referral_rewards)} />
            <Metric label="Промокодов за 30 дней" value={round(data.promo_redemptions_30d)} />
            <Metric label="Заблокировали бота" value={round(data.bot_blocked)} />
          </dl>
          <div className="actions" style={{ marginTop: 16 }}>
            <Link className="btn" to="/admin/promos">
              Промокоды
            </Link>
            <Link className="btn" to="/admin/referrals">
              Рефералы
            </Link>
          </div>
        </section>
      </div>
    </>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="card kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      <span className="kpi-sub">{sub}</span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function StatusCard({ data }: { data: Data }) {
  const total = STATUSES.reduce((sum, s) => sum + data.statuses[s.key], 0);
  return (
    <section className="card">
      <div className="card-head">
        <h2>Статусы доступа</h2>
        <span className="muted small">заблокировано {data.blocked}</span>
      </div>
      {total > 0 && (
        <div className="stacked" role="img" aria-label="Распределение по статусам">
          {STATUSES.filter((s) => data.statuses[s.key] > 0).map((s) => (
            <span
              key={s.key}
              title={`${s.label}: ${data.statuses[s.key]}`}
              style={{ flex: data.statuses[s.key], background: s.color }}
            />
          ))}
        </div>
      )}
      <ul className="legend">
        {STATUSES.map((s) => (
          <li key={s.key}>
            <i style={{ background: s.color }} />
            {s.label} <strong>{data.statuses[s.key]}</strong>
            {total > 0 && <span className="muted">{percent(data.statuses[s.key] / total)}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function FunnelCard({ data }: { data: Data }) {
  const first = data.funnel[0]?.count || 0;
  return (
    <section className="card">
      <div className="card-head">
        <h2>Воронка</h2>
        <span className="muted small">от регистрации</span>
      </div>
      <ol className="hbars">
        {data.funnel.map((step, i) => {
          const share = first ? step.count / first : 0;
          const prev = i > 0 ? data.funnel[i - 1].count : 0;
          return (
            <li key={step.key}>
              <div className="hbar-head">
                <span>{FUNNEL[step.key] ?? step.key}</span>
                <span>
                  <strong>{round(step.count)}</strong>{" "}
                  <span className="muted">
                    {i === 0 ? "" : `${percent(prev ? step.count / prev : null)} от шага`}
                  </span>
                </span>
              </div>
              <div className="hbar-track">
                <div
                  className="hbar-fill"
                  style={{ width: `${share * 100}%`, background: RAMP[i] ?? RAMP[RAMP.length - 1] }}
                />
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export function HBars({ items }: { items: { label: string; value: number }[] }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="hbars">
      {items.map((item) => (
        <li key={item.label}>
          <div className="hbar-head">
            <span className="mono">{item.label}</span>
            <span>{round(item.value)}</span>
          </div>
          <div className="hbar-track">
            <div className="hbar-fill" style={{ width: `${(item.value / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function sourceLabel(key: string): string {
  if (key === "direct") return "напрямую";
  if (key === "referral") return "приглашения";
  if (key.startsWith("p_")) return `промо ${key.slice(2)}`;
  return key;
}

function seconds(ms: number | null): string {
  return ms === null ? "—" : `${(ms / 1000).toFixed(1)} с`;
}
