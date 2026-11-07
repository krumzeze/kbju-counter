import { useMutation } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Goal as BodyGoal, Macros, Stats as StatsData, StatsDay, WeightPoint } from "../api/types";
import { BarChart, type Goal, type LegendItem } from "../components/BarChart";
import { LineChart } from "../components/LineChart";
import { PremiumNote } from "../components/PremiumNote";
import { ErrorState, Spinner } from "../components/States";
import { STEP_GOAL, count, daysWord, decimal, round, shiftDay, signedDecimal, signedRound, todayIso } from "../lib/format";
import { locale, tr } from "../lib/i18n";
import { useInvalidate, useMe, useStats, useWeights } from "../lib/queries";
import { type Point, mean, trailingMean, weekly } from "../lib/series";
import { haptic } from "../lib/telegram";

const PERIODS = [7, 30, 90] as const;
type Period = (typeof PERIODS)[number];
const WEEKLY_FROM = 90;
const TOLERANCE = 0.1;
const KCAL_PER_KG = 7700;
const TREND_DAYS = 7;

export function Stats() {
  const [period, setPeriod] = useState<Period>(30);
  const stats = useStats(period);
  const weights = useWeights();
  const goal = useMe().data?.goal ?? null;
  const from = shiftDay(todayIso(), 1 - period);
  const inPeriod = (weights.data ?? []).filter((p) => p.day >= from);
  const weightDelta = inPeriod.length > 1 ? inPeriod.at(-1)!.weight_kg - inPeriod[0].weight_kg : null;
  const weeklyMode = period >= WEEKLY_FROM;

  const statsBody = (render: (data: StatsData) => ReactNode) =>
    stats.isPending ? (
      <Spinner />
    ) : stats.error ? (
      <ErrorState message={errorMessage(stats.error)} onRetry={() => stats.refetch()} />
    ) : (
      render(stats.data)
    );

  return (
    <div className="page stats-page">
      <header className="stats-head">
        <h1>{tr("Статистика", "Stats")}</h1>
        <div className="chips period-chips" role="group" aria-label={tr("Период", "Period")}>
          {PERIODS.map((p) => (
            <button key={p} className="chip" aria-pressed={period === p} onClick={() => setPeriod(p)}>
              {p} {tr("дн", "d")}
            </button>
          ))}
        </div>
      </header>
      {stats.data?.limited && <PremiumNote />}

      <div className="stats-grid">
        <div className="stats-col">
          <WeightSection points={weights.data} inPeriod={inPeriod} delta={weightDelta} goal={goal} />
          {statsBody((data) => (
            <NutritionSection stats={data} weeklyMode={weeklyMode} />
          ))}
        </div>
        <div className="stats-col">
          {stats.data && (
            <>
              <BalanceSection stats={stats.data} goal={goal} weightDelta={weightDelta} weeklyMode={weeklyMode} />
              <ActivitySection stats={stats.data} weeklyMode={weeklyMode} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* Weight */

function WeightSection({
  points,
  inPeriod,
  delta,
  goal,
}: {
  points: WeightPoint[] | undefined;
  inPeriod: WeightPoint[];
  delta: number | null;
  goal: BodyGoal | null;
}) {
  if (!points) return null;
  const last = points.at(-1);
  const series = points.map((p) => ({ day: p.day, value: p.weight_kg }));
  const trend = trailingMean(series, TREND_DAYS).filter((p) => p.day >= (inPeriod[0]?.day ?? ""));

  return (
    <section className="stats-section order-weight">
      <h2>{tr("Вес", "Weight")}</h2>
      <div className="kpis">
        <WeightNowCard last={last?.weight_kg ?? null} />
        <Kpi
          label={tr("За период", "This period")}
          value={delta === null ? "—" : signedDecimal(delta)}
          unit={delta === null ? undefined : tr("кг", "kg")}
          tone={delta === null ? undefined : weightTone(delta, goal)}
          sub={
            delta === null
              ? tr("нужно 2 взвешивания", "needs 2 weigh-ins")
              : tr(`с ${decimal(inPeriod[0].weight_kg)} кг`, `from ${decimal(inPeriod[0].weight_kg)} kg`)
          }
        />
      </div>
      {inPeriod.length > 1 ? (
        <section className="card">
          <LineChart
            points={inPeriod.map((p) => ({ day: p.day, value: p.weight_kg }))}
            unit={tr("кг", "kg")}
            trend={{
              points: trend,
              pointsLabel: tr("взвешивания", "weigh-ins"),
              label: tr("тренд за 7 дней", "7-day trend"),
            }}
          />
        </section>
      ) : (
        <p className="muted small">
          {tr(
            "Взвешивайся утром натощак хотя бы пару раз в неделю, и здесь появится график с трендом.",
            "Weigh yourself in the morning a couple of times a week and a trend chart will appear here.",
          )}
        </p>
      )}
    </section>
  );
}

function weightTone(delta: number, goal: BodyGoal | null): "good" | "bad" | undefined {
  if (!goal || Math.abs(delta) < 0.05) return undefined;
  if (goal === "maintain") return Math.abs(delta) <= 1 ? "good" : "bad";
  return (goal === "lose") === delta < 0 ? "good" : "bad";
}

function WeightNowCard({ last }: { last: number | null }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const invalidate = useInvalidate();
  const save = useMutation({
    mutationFn: (kg: number) => api.saveWeight(kg),
    onSuccess: async () => {
      haptic("success");
      setValue("");
      setEditing(false);
      await invalidate("weights", "day", "me", "stats");
    },
  });
  const kg = Number(value.replace(",", "."));
  const valid = kg >= 30 && kg <= 300;

  if (editing) {
    return (
      <form
        className="card kpi kpi-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) save.mutate(kg);
        }}
      >
        <span className="kpi-label">{tr("Вес сегодня, кг", "Today's weight, kg")}</span>
        <div className="kpi-form-row">
          <input
            className="input"
            inputMode="decimal"
            autoFocus
            placeholder={last ? decimal(last) : "75,0"}
            value={value}
            onChange={(e) => setValue(e.target.value.replace(/[^\d.,]/g, ""))}
          />
          <button className="btn btn-primary small" disabled={!valid || save.isPending}>
            OK
          </button>
        </div>
        {save.isError ? (
          <span className="error small">{errorMessage(save.error)}</span>
        ) : (
          <span className="kpi-sub">
            {tr("Лучше утром натощак · ", "Best in the morning · ")}
            <button type="button" className="link-button" onClick={() => setEditing(false)}>
              {tr("отмена", "cancel")}
            </button>
          </span>
        )}
      </form>
    );
  }

  return (
    <Kpi
      label={tr("Сейчас", "Now")}
      value={last === null ? "—" : decimal(last)}
      unit={last === null ? undefined : tr("кг", "kg")}
      action={
        <button className="kpi-action" onClick={() => setEditing(true)}>
          + {tr("Записать", "Log")}
        </button>
      }
    />
  );
}

/* Calorie balance */

function BalanceSection({
  stats,
  goal,
  weightDelta,
  weeklyMode,
}: {
  stats: StatsData;
  goal: BodyGoal | null;
  weightDelta: number | null;
  weeklyMode: boolean;
}) {
  const counted = stats.days.filter((d) => d.eaten.kcal > 0 && d.burned !== null);
  const countedDays = new Set(counted.map((d) => d.day));
  const balance = (d: StatsDay) => d.eaten.kcal - (d.burned ?? 0);
  const total = counted.reduce((s, d) => s + balance(d), 0);
  const daily: Point[] = stats.days.map((d) => ({ day: d.day, value: countedDays.has(d.day) ? balance(d) : 0 }));
  const points = weeklyMode ? weekly(daily, (p) => countedDays.has(p.day)) : daily;
  const tone = (v: number) =>
    !goal || goal === "maintain" ? (Math.abs(v) <= 250 ? "good" : "bad") : (goal === "lose") === v < 0 ? "good" : "bad";
  const legend: LegendItem[] =
    goal === "gain"
      ? [
          { cls: "good", label: tr("профицит", "surplus") },
          { cls: "bad", label: tr("дефицит", "deficit") },
        ]
      : goal === "lose"
        ? [
            { cls: "good", label: tr("дефицит", "deficit") },
            { cls: "bad", label: tr("профицит", "surplus") },
          ]
        : [
            { cls: "good", label: tr("около нуля", "near zero") },
            { cls: "bad", label: tr("заметно в плюс или минус", "far from zero") },
          ];

  return (
    <section className="stats-section order-balance">
      <h2>{tr("Баланс калорий", "Calorie balance")}</h2>
      {counted.length === 0 ? (
        <p className="muted">
          {stats.days.some((d) => d.burned !== null)
            ? tr("Появится, когда запишешь еду хотя бы за один день.", "Appears once you log food for a day.")
            : tr("Заполни профиль, чтобы считать расход калорий.", "Fill in your profile to estimate expenditure.")}
        </p>
      ) : (
        <section className="card">
          <div className="balance-summary">
            <div>
              <span className={`balance-total ${tone(total / counted.length)}`}>
                {signedRound(total)} {tr("ккал", "kcal")}
              </span>
              <span className="muted small">
                {tr(`за ${counted.length} ${daysWord(counted.length)} с записями`, `over ${counted.length} logged ${daysWord(counted.length)}`)}
              </span>
            </div>
            <dl className="balance-kg">
              <dt>{tr("по балансу", "expected")}</dt>
              <dd>
                ≈ {signedDecimal(total / KCAL_PER_KG)} {tr("кг", "kg")}
              </dd>
              {weightDelta !== null && (
                <>
                  <dt>{tr("на весах", "on the scale")}</dt>
                  <dd>
                    {signedDecimal(weightDelta)} {tr("кг", "kg")}
                  </dd>
                </>
              )}
            </dl>
          </div>
          <BarChart
            key={String(weeklyMode)}
            tone="balance"
            points={points}
            period={weeklyMode ? "week" : "day"}
            format={(n) => signedRound(n)}
            unit={weeklyMode ? tr("ккал в день", "kcal a day") : tr("ккал", "kcal")}
            classify={tone}
            legend={legend}
            label={tr("Баланс калорий по дням", "Daily calorie balance")}
          />
          <p className="chart-note">
            {tr(
              "Съедено минус потрачено за день. Минус означает дефицит, и вес идёт вниз, плюс означает профицит. Около 7 700 ккал дают 1 кг. Дни без записей еды не учитываются.",
              "Eaten minus burned. Below zero is a deficit and weight goes down, above zero is a surplus. About 7,700 kcal make 1 kg. Days without food logs are skipped.",
            )}
          </p>
        </section>
      )}
    </section>
  );
}

/* Nutrition */

type Metric = keyof Macros;

const METRICS: { key: Metric; label: () => string; title: () => string; kind: Goal["kind"] }[] = [
  { key: "kcal", label: () => tr("Ккал", "Kcal"), title: () => tr("Калории по дням", "Calories per day"), kind: "limit" },
  { key: "protein", label: () => tr("Белки", "Protein"), title: () => tr("Белки по дням", "Protein per day"), kind: "target" },
  { key: "fat", label: () => tr("Жиры", "Fat"), title: () => tr("Жиры по дням", "Fat per day"), kind: "limit" },
  { key: "carbs", label: () => tr("Углеводы", "Carbs"), title: () => tr("Углеводы по дням", "Carbs per day"), kind: "limit" },
];

const limitLegend = (): LegendItem[] => [
  { cls: "base", label: tr("в норме", "on target") },
  { cls: "over", label: tr("больше нормы", "over target") },
];

const targetLegend = (met: string, under: string): LegendItem[] => [
  { cls: "base", label: met },
  { cls: "under", label: under },
];

function offTarget(value: number, goal: number | undefined, kind: Goal["kind"]): boolean {
  if (!goal) return false;
  return kind === "limit" ? value > goal * (1 + TOLERANCE) : value < goal;
}

function NutritionSection({ stats, weeklyMode }: { stats: StatsData; weeklyMode: boolean }) {
  const [metric, setMetric] = useState<Metric>("kcal");
  const logged = stats.days.filter((d) => d.eaten.kcal > 0);
  const loggedDays = new Set(logged.map((d) => d.day));
  const avg = (m: Metric) => mean(logged.map((d) => d.eaten[m]));
  const m = METRICS.find((x) => x.key === metric)!;
  const unit = metric === "kcal" ? tr("ккал", "kcal") : tr("г", "g");
  const goal = stats.target?.[metric];
  const daily = stats.days.map((d) => ({ day: d.day, value: d.eaten[metric] }));
  const points = weeklyMode ? weekly(daily, (p) => loggedDays.has(p.day)) : daily;

  return (
    <section className="stats-section order-nutrition">
      <h2>{tr("Питание", "Nutrition")}</h2>
      {logged.length === 0 ? (
        <p className="muted">{tr("За этот период еды не записано.", "No food logged in this period.")}</p>
      ) : (
        <>
          <div className="metric-tiles four" role="tablist" aria-label={tr("Показатель", "Metric")}>
            {METRICS.map((x) => {
              const value = avg(x.key);
              const target = stats.target?.[x.key];
              return (
                <MetricTile
                  key={x.key}
                  tone={x.key}
                  label={x.label()}
                  value={x.key === "kcal" ? round(value) : `${round(value)} ${tr("г", "g")}`}
                  sub={target ? tr(`из ${round(target)}`, `of ${round(target)}`) : undefined}
                  warn={offTarget(value, target, x.kind)}
                  selected={metric === x.key}
                  onSelect={() => setMetric(x.key)}
                />
              );
            })}
          </div>
          <p className="tiles-caption">{tr("Среднее в день за дни с записями", "Daily average over logged days")}</p>
          <section className="card">
            <BarChart
              key={`${metric}-${weeklyMode}`}
              tone={metric}
              points={points}
              period={weeklyMode ? "week" : "day"}
              format={(n) => round(n)}
              unit={weeklyMode ? `${unit} ${tr("в день", "a day")}` : unit}
              goal={
                goal
                  ? { value: goal, kind: m.kind, label: tr(`норма ${round(goal)} ${unit}`, `target ${round(goal)} ${unit}`) }
                  : undefined
              }
              legend={
                goal
                  ? m.kind === "limit"
                    ? limitLegend()
                    : targetLegend(tr("норма выполнена", "target met"), tr("меньше нормы", "under target"))
                  : undefined
              }
              label={m.title()}
            />
          </section>
          <MacroSplit logged={logged} target={stats.target} />
          {stats.days.length >= 30 && logged.length >= 10 && <WeekdayCard logged={logged} target={stats.target} />}
        </>
      )}
    </section>
  );
}

const MACRO_KEYS = ["protein", "fat", "carbs"] as const;

function MacroSplit({ logged, target }: { logged: StatsDay[]; target: Macros | null }) {
  const shares = (p: number, f: number, c: number) => {
    const total = p * 4 + f * 9 + c * 4 || 1;
    return { protein: (p * 4) / total, fat: (f * 9) / total, carbs: (c * 4) / total };
  };
  const rows = [
    {
      label: tr("Факт", "Actual"),
      value: shares(
        mean(logged.map((d) => d.eaten.protein)),
        mean(logged.map((d) => d.eaten.fat)),
        mean(logged.map((d) => d.eaten.carbs)),
      ),
    },
    ...(target ? [{ label: tr("Норма", "Target"), value: shares(target.protein, target.fat, target.carbs) }] : []),
  ];
  const names = { protein: tr("белки", "protein"), fat: tr("жиры", "fat"), carbs: tr("углеводы", "carbs") };

  return (
    <section className="card">
      <h3 className="card-title">{tr("Состав рациона", "Macro split")}</h3>
      <p className="chart-note top">
        {tr("Какая доля калорий приходит из белков, жиров и углеводов", "Share of calories from protein, fat and carbs")}
      </p>
      <div className="split">
        {rows.map((row) => (
          <div key={row.label} className="split-row">
            <span className="split-label">{row.label}</span>
            <div className="split-bar">
              {MACRO_KEYS.map((k) => (
                <span key={k} className={`split-seg ${k}`} style={{ width: `${row.value[k] * 100}%` }}>
                  {row.value[k] >= 0.12 && `${Math.round(row.value[k] * 100)}%`}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="chart-legend">
        {MACRO_KEYS.map((k) => (
          <span key={k} className="chart-legend-item">
            <span className={`split-dot ${k}`} aria-hidden />
            {names[k]}
          </span>
        ))}
      </div>
    </section>
  );
}

const weekdayName = (i: number, format: "short" | "long") =>
  new Date(Date.UTC(2024, 0, 1 + i, 12)).toLocaleDateString(locale(), { weekday: format, timeZone: "UTC" });

const weekdayOf = (iso: string) => (new Date(`${iso}T12:00:00Z`).getUTCDay() + 6) % 7;

function WeekdayCard({ logged, target }: { logged: StatsDay[]; target: Macros | null }) {
  const points = Array.from({ length: 7 }, (_, i) => ({
    day: `wd-${i}`,
    value: mean(logged.filter((d) => weekdayOf(d.day) === i).map((d) => d.eaten.kcal)),
  }));
  const index = (p: Point) => Number(p.day.slice(3));

  return (
    <section className="card">
      <h3 className="card-title">{tr("По дням недели", "By weekday")}</h3>
      <p className="chart-note top">
        {tr("Сколько калорий в среднем приходится на каждый день недели", "Average calories on each day of the week")}
      </p>
      <BarChart
        points={points}
        format={(n) => round(n)}
        unit={tr("ккал", "kcal")}
        goal={
          target
            ? { value: target.kcal, kind: "limit", label: tr(`норма ${round(target.kcal)}`, `target ${round(target.kcal)}`) }
            : undefined
        }
        legend={target ? limitLegend() : undefined}
        xLabel={(p) => weekdayName(index(p), "short")}
        readoutLabel={(p) => tr(`в среднем, ${weekdayName(index(p), "long")}`, `on average, ${weekdayName(index(p), "long")}`)}
        label={tr("Калории по дням недели", "Calories by weekday")}
        height={170}
      />
    </section>
  );
}

/* Activity */

function ActivitySection({ stats, weeklyMode }: { stats: StatsData; weeklyMode: boolean }) {
  const [metric, setMetric] = useState<"steps" | "water">("steps");
  const stepDays = stats.days.filter((d) => d.steps > 0);
  const waterDays = stats.days.filter((d) => d.water_ml > 0);
  const waterGoal = stats.water_target_ml && stats.water_target_ml / 1000;
  const isSteps = metric === "steps";
  const daily = stats.days.map((d) => ({ day: d.day, value: isSteps ? d.steps : d.water_ml / 1000 }));
  const points = weeklyMode ? weekly(daily) : daily;
  const has = (isSteps ? stepDays : waterDays).length > 0;
  const liters = (v: number) => `${decimal(v)} ${tr("л", "L")}`;
  const goal: Goal | undefined = isSteps
    ? { value: STEP_GOAL, kind: "target", label: tr(`цель ${round(STEP_GOAL)}`, `goal ${round(STEP_GOAL)}`) }
    : waterGoal
      ? { value: waterGoal, kind: "target", label: tr(`норма ${liters(waterGoal)}`, `target ${liters(waterGoal)}`) }
      : undefined;

  return (
    <section className="stats-section order-activity">
      <h2>{tr("Активность", "Activity")}</h2>
      <div className="metric-tiles" role="tablist" aria-label={tr("Показатель", "Metric")}>
        <MetricTile
          tone="act-steps"
          label={tr("Шаги", "Steps")}
          value={stepDays.length ? round(mean(stepDays.map((d) => d.steps))) : "—"}
          sub={tr(`в день · цель ${round(STEP_GOAL)}`, `a day · goal ${round(STEP_GOAL)}`)}
          selected={isSteps}
          onSelect={() => setMetric("steps")}
        />
        <MetricTile
          tone="act-water"
          label={tr("Вода", "Water")}
          value={waterDays.length ? liters(mean(waterDays.map((d) => d.water_ml)) / 1000) : "—"}
          sub={waterGoal ? tr(`в день · норма ${liters(waterGoal)}`, `a day · target ${liters(waterGoal)}`) : tr("в день", "a day")}
          selected={!isSteps}
          onSelect={() => setMetric("water")}
        />
      </div>
      <section className="card">
        {has ? (
          <BarChart
            key={`${metric}-${weeklyMode}`}
            tone={`act-${metric}`}
            points={points}
            period={weeklyMode ? "week" : "day"}
            format={isSteps ? (v) => round(v) : (v) => decimal(v)}
            unit={isSteps ? (v) => count(Math.round(v), ["шаг", "шага", "шагов"], ["step", "steps"]) : tr("л", "L")}
            goal={goal}
            legend={
              goal
                ? targetLegend(
                    isSteps ? tr("цель выполнена", "goal met") : tr("норма выполнена", "target met"),
                    isSteps ? tr("меньше цели", "below goal") : tr("меньше нормы", "below target"),
                  )
                : undefined
            }
            label={isSteps ? tr("Шаги по дням", "Steps per day") : tr("Вода по дням", "Water per day")}
          />
        ) : (
          <p className="muted">
            {isSteps
              ? tr("Шаги за этот период не записаны. Их можно ввести на главной.", "No steps logged in this period. Add them on the home screen.")
              : tr("Вода за этот период не записана. Её можно отметить на главной.", "No water logged in this period. Add it on the home screen.")}
          </p>
        )}
      </section>
      <Link to="/analytics" className="card nav-card sand">
        <strong>{tr("Аналитика тренировок", "Workout analytics")}</strong>
        <span className="muted small">{tr("Объём, рекорды, нагрузка на мышцы", "Volume, records, muscle load")}</span>
      </Link>
    </section>
  );
}

/* Shared */

function Kpi({
  label,
  value,
  unit,
  sub,
  tone,
  action,
}: {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  tone?: "good" | "bad";
  action?: ReactNode;
}) {
  return (
    <div className="card kpi">
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        {action}
      </div>
      <span className={tone ? `kpi-value ${tone}` : "kpi-value"}>
        {value}
        {unit && <span className="kpi-unit"> {unit}</span>}
      </span>
      {sub && <span className="kpi-sub">{sub}</span>}
    </div>
  );
}

function MetricTile({
  label,
  value,
  sub,
  tone,
  warn = false,
  selected,
  onSelect,
}: {
  label: string;
  value: string;
  sub?: string;
  tone: string;
  warn?: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button role="tab" aria-selected={selected} className={`metric-tile ${tone}`} onClick={onSelect}>
      <span className="metric-label">
        <span className="metric-dot" aria-hidden />
        {label}
      </span>
      <span className={warn ? "metric-value warn" : "metric-value"}>{value}</span>
      {sub && <span className="metric-sub">{sub}</span>}
    </button>
  );
}
