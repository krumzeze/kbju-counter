import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Stats as StatsData, WeightPoint } from "../api/types";
import { Art } from "../components/Art";
import { BarChart } from "../components/BarChart";
import { LineChart } from "../components/LineChart";
import { PremiumNote } from "../components/PremiumNote";
import { ErrorState, Spinner } from "../components/States";
import { count, round, shiftDay, todayIso } from "../lib/format";
import { tr } from "../lib/i18n";
import { useInvalidate, useStats, useWeights } from "../lib/queries";
import { haptic } from "../lib/telegram";

const PERIODS = [7, 30, 90] as const;
type Period = (typeof PERIODS)[number];
const ON_TARGET = 0.1;

export function Stats() {
  const [period, setPeriod] = useState<Period>(30);
  const stats = useStats(period);
  const weights = useWeights();

  return (
    <div className="page">
      <h1>{tr("Статистика", "Stats")}</h1>
      <div className="segmented compact" role="tablist">
        {PERIODS.map((p) => (
          <button key={p} role="tab" aria-selected={period === p} onClick={() => setPeriod(p)}>
            {p} {count(p, ["день", "дня", "дней"], ["day", "days"])}
          </button>
        ))}
      </div>
      {stats.data?.limited && <PremiumNote />}

      <WeightSection points={weights.data} from={shiftDay(todayIso(), 1 - period)} />

      {stats.isPending ? (
        <Spinner />
      ) : stats.error ? (
        <ErrorState message={errorMessage(stats.error)} onRetry={() => stats.refetch()} />
      ) : (
        <>
          <NutritionSection stats={stats.data} />
          <ActivitySection stats={stats.data} />
        </>
      )}
    </div>
  );
}

function WeightSection({ points, from }: { points: WeightPoint[] | undefined; from: string }) {
  const [value, setValue] = useState("");
  const invalidate = useInvalidate();
  const save = useMutation({
    mutationFn: (kg: number) => api.saveWeight(kg),
    onSuccess: async () => {
      haptic("success");
      setValue("");
      await invalidate("weights", "day", "me", "stats");
    },
  });
  const kg = Number(value.replace(",", "."));
  const valid = kg >= 30 && kg <= 300;
  const inPeriod = (points ?? []).filter((p) => p.day >= from);
  const last = points?.at(-1);

  return (
    <section className="stats-section">
      <h2>{tr("Вес", "Weight")}</h2>
      <form
        className="card inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) save.mutate(kg);
        }}
      >
        <input
          className="input"
          inputMode="decimal"
          placeholder={tr("Вес сегодня, кг", "Today's weight, kg")}
          value={value}
          onChange={(e) => setValue(e.target.value.replace(/[^\d.,]/g, ""))}
        />
        <button className="btn btn-primary" disabled={!valid || save.isPending}>
          {tr("Записать", "Log")}
        </button>
      </form>
      {save.isError && <p className="error">{errorMessage(save.error)}</p>}
      <p className="muted small">
        {tr(
          "Взвешивайся утром натощак, так цифры сравнимы между собой.",
          "Weigh yourself in the morning before eating so the numbers are comparable.",
        )}
      </p>

      {!points ? null : !last ? (
        <div className="empty">
          <Art name="empty-weight" />
          <p>
            {tr(
              "Записей пока нет. Запиши первый вес, и здесь появится график.",
              "No entries yet. Log your first weight and a chart will appear here.",
            )}
          </p>
        </div>
      ) : (
        <>
          <section className="tiles">
            <div className="tile-card tone-sage short">
              <h3>{tr("Сейчас", "Now")}</h3>
              <div>
                <strong>{last.weight_kg.toFixed(1)}</strong>
                <span className="unit">{tr("кг", "kg")}</span>
              </div>
            </div>
            <div className="tile-card tone-blush short">
              <h3>{tr("За период", "This period")}</h3>
              <div>
                <strong>{inPeriod.length > 1 ? signed(last.weight_kg - inPeriod[0].weight_kg) : "—"}</strong>
                <span className="unit">{tr("кг", "kg")}</span>
              </div>
            </div>
          </section>
          {inPeriod.length > 1 && (
            <section className="card">
              <LineChart points={inPeriod.map((p) => ({ day: p.day, value: p.weight_kg }))} unit={tr("кг", "kg")} />
            </section>
          )}
        </>
      )}
    </section>
  );
}

function NutritionSection({ stats }: { stats: StatsData }) {
  const logged = stats.days.filter((d) => d.eaten.kcal > 0);
  const target = stats.target;
  const avg = (pick: (d: StatsData["days"][number]) => number) =>
    logged.length ? logged.reduce((s, d) => s + pick(d), 0) / logged.length : 0;
  const kcal = avg((d) => d.eaten.kcal);
  const onTarget = target
    ? logged.filter((d) => Math.abs(d.eaten.kcal - target.kcal) <= target.kcal * ON_TARGET).length
    : null;

  return (
    <section className="stats-section">
      <h2>{tr("Питание", "Nutrition")}</h2>
      {logged.length === 0 ? (
        <p className="muted">{tr("За этот период еды не записано.", "No food logged in this period.")}</p>
      ) : (
        <>
          <section className="kpis">
            <Kpi
              label={tr("Калорий в день", "Calories a day")}
              value={round(kcal)}
              sub={target ? tr(`цель ${round(target.kcal)}`, `target ${round(target.kcal)}`) : undefined}
            />
            <Kpi
              label={tr("Белка в день", "Protein a day")}
              value={`${round(avg((d) => d.eaten.protein))} ${tr("г", "g")}`}
              sub={target ? tr(`цель ${round(target.protein)} г`, `target ${round(target.protein)} g`) : undefined}
            />
            <Kpi
              label={tr("Дней с записями", "Days logged")}
              value={`${logged.length}/${stats.days.length}`}
              sub={
                onTarget !== null
                  ? tr(`${onTarget} в пределах цели ±10%`, `${onTarget} within ±10% of target`)
                  : undefined
              }
            />
          </section>
          <section className="card">
            <BarChart
              points={stats.days.map((d) => ({ day: d.day, value: d.eaten.kcal }))}
              format={(n) => round(n)}
              label={tr("Калории по дням", "Calories per day")}
            />
            <p className="muted small">
              {tr("Средний БЖУ", "Average macros")}: {round(avg((d) => d.eaten.protein))} /{" "}
              {round(avg((d) => d.eaten.fat))} / {round(avg((d) => d.eaten.carbs))} {tr("г", "g")}
            </p>
          </section>
        </>
      )}
    </section>
  );
}

function ActivitySection({ stats }: { stats: StatsData }) {
  const n = stats.days.length;
  const stepDays = stats.days.filter((d) => d.steps > 0);
  const waterDays = stats.days.filter((d) => d.water_ml > 0);
  const workoutDays = stats.days.filter((d) => d.sets > 0).length;
  const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

  return (
    <section className="stats-section">
      <h2>{tr("Активность", "Activity")}</h2>
      <section className="kpis">
        <Kpi
          label={tr("Шагов в день", "Steps a day")}
          value={stepDays.length ? round(mean(stepDays.map((d) => d.steps))) : "—"}
        />
        <Kpi
          label={tr("Воды в день", "Water a day")}
          value={waterDays.length ? `${(mean(waterDays.map((d) => d.water_ml)) / 1000).toFixed(1)} ${tr("л", "L")}` : "—"}
        />
        <Kpi
          label={tr("Дней с тренировкой", "Workout days")}
          value={`${workoutDays}/${n}`}
        />
      </section>
      {stepDays.length > 0 && (
        <section className="card">
          <BarChart
            points={stats.days.map((d) => ({ day: d.day, value: d.steps }))}
            format={(v) => round(v)}
            label={tr("Шаги по дням", "Steps per day")}
          />
        </section>
      )}
      <Link to="/analytics" className="card nav-card sand">
        <strong>{tr("Аналитика тренировок", "Workout analytics")}</strong>
        <span className="muted small">{tr("Объём, рекорды, нагрузка на мышцы", "Volume, records, muscle load")}</span>
      </Link>
    </section>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      {sub && <span className="kpi-sub">{sub}</span>}
    </div>
  );
}

const signed = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(1)}`;
