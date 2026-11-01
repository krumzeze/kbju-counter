import { useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/client";
import type { MuscleGroup } from "../api/types";
import { BarChart } from "../components/BarChart";
import { BodyMap } from "../components/BodyMap";
import { ExerciseThumb } from "../components/ExerciseThumb";
import { ErrorState, Spinner } from "../components/States";
import { GROUPS, compact, groupLabel, kg } from "../lib/catalog";
import { count } from "../lib/format";
import { tr } from "../lib/i18n";
import { useAnalytics, useExercises } from "../lib/queries";

type Series = "workouts" | "volume" | "sets";

export function Analytics() {
  const { data, isPending, error, refetch } = useAnalytics();
  const exercises = useExercises();
  const [series, setSeries] = useState<Series>("workouts");
  const [period, setPeriod] = useState<"week" | "month">("week");

  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  if (data.total_workouts === 0) {
    return (
      <div className="page">
        <h1>{tr("Аналитика", "Analytics")}</h1>
        <p className="empty">
          {tr(
            "Здесь появятся графики, рекорды и карта нагрузки на мышцы после первой тренировки.",
            "Charts, records and a muscle load map will appear here after your first workout.",
          )}
        </p>
      </div>
    );
  }

  const week = data.weeks[data.weeks.length - 1];
  const muscles = period === "week" ? data.muscles_week : data.muscles_month;
  const peak = Math.max(1, ...Object.values(muscles));
  const heat = Object.fromEntries(Object.entries(muscles).map(([m, v]) => [m, v / peak]));
  const groupMax = Math.max(1, ...Object.values(data.groups_month));
  const value = (w: (typeof data.weeks)[number]) =>
    series === "workouts" ? w.workouts : series === "volume" ? w.volume_kg : w.sets;

  return (
    <div className="page wide">
      <h1>{tr("Аналитика", "Analytics")}</h1>

      <section className="kpis">
        <div className="card kpi">
          <span className="kpi-label">{tr("Всего тренировок", "Total workouts")}</span>
          <span className="kpi-value">{data.total_workouts}</span>
        </div>
        <div className="card kpi">
          <span className="kpi-label">{tr("Серия", "Streak")}</span>
          <span className="kpi-value">{data.streak_weeks}</span>
          <span className="kpi-sub">
            {count(data.streak_weeks, ["неделя подряд", "недели подряд", "недель подряд"], ["week in a row", "weeks in a row"])}
          </span>
        </div>
        <div className="card kpi">
          <span className="kpi-label">{tr("Эта неделя", "This week")}</span>
          <span className="kpi-value">{week.workouts}</span>
          <span className="kpi-sub">
            {week.sets} {count(week.sets, ["подход", "подхода", "подходов"], ["set", "sets"])} · {compact(week.volume_kg)}{" "}
            {tr("кг", "kg")}
          </span>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>{tr("По неделям", "Weekly")}</h2>
        </div>
        <div className="segmented compact" role="tablist">
          {(
            [
              ["workouts", tr("Тренировки", "Workouts")],
              ["sets", tr("Подходы", "Sets")],
              ["volume", tr("Тоннаж", "Volume")],
            ] as [Series, string][]
          ).map(([s, label]) => (
            <button key={s} role="tab" aria-selected={series === s} onClick={() => setSeries(s)}>
              {label}
            </button>
          ))}
        </div>
        <BarChart
          points={data.weeks.map((w) => ({ day: w.start, value: value(w) }))}
          format={series === "volume" ? kg : (n) => String(Math.round(n))}
          label={tr("По неделям", "Weekly")}
        />
      </section>

      <section className="card">
        <div className="card-head">
          <h2>{tr("Нагрузка на мышцы", "Muscle load")}</h2>
        </div>
        <div className="segmented compact" role="tablist">
          <button role="tab" aria-selected={period === "week"} onClick={() => setPeriod("week")}>
            {tr("Эта неделя", "This week")}
          </button>
          <button role="tab" aria-selected={period === "month"} onClick={() => setPeriod("month")}>
            {tr("30 дней", "30 days")}
          </button>
        </div>
        <BodyMap values={heat} className="large" />
        {Object.keys(muscles).length === 0 && (
          <p className="muted small center">{tr("За этот период подходов нет.", "No sets in this period.")}</p>
        )}
      </section>

      {Object.keys(data.groups_month).length > 0 && (
        <section className="card">
          <h2>{tr("Подходы по группам за 30 дней", "Sets per muscle group, 30 days")}</h2>
          <ul className="hbars">
            {GROUPS.filter((g) => data.groups_month[g]).map((g: MuscleGroup) => (
              <li key={g}>
                <div className="hbar-head">
                  <span>{groupLabel(g)}</span>
                  <span>{data.groups_month[g]}</span>
                </div>
                <div className="hbar-track">
                  <div className="hbar-fill accent" style={{ width: `${(data.groups_month[g] / groupMax) * 100}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.top.length > 0 && (
        <section>
          <h2>{tr("Чаще всего", "Most trained")}</h2>
          <ExerciseList
            items={data.top.map((t) => ({
              ...t.exercise,
              note:
                t.best_e1rm > 0
                  ? `${t.sets} ${count(t.sets, ["подход", "подхода", "подходов"], ["set", "sets"])} · ${tr("1ПМ", "1RM")} ${t.best_e1rm}`
                  : `${t.sets} ${count(t.sets, ["подход", "подхода", "подходов"], ["set", "sets"])}`,
            }))}
          />
        </section>
      )}

      {exercises.data && exercises.data.some((e) => e.sets > 0) && (
        <section>
          <h2>{tr("Все мои упражнения", "All my exercises")}</h2>
          <ExerciseList
            items={exercises.data
              .filter((e) => e.sets > 0)
              .map((e) => ({ ...e, note: `${e.sets} ${count(e.sets, ["подход", "подхода", "подходов"], ["set", "sets"])}` }))}
          />
        </section>
      )}
    </div>
  );
}

function ExerciseList({
  items,
}: {
  items: { id: number; name: string; catalog_id: string | null; group: MuscleGroup | null; note: string }[];
}) {
  return (
    <ul className="pick-list card">
      {items.map((e) => (
        <li key={e.id}>
          <Link to={`/exercises/${e.id}`}>
            <ExerciseThumb catalogId={e.catalog_id} group={e.group} />
            <span>
              <strong className="capitalize">{e.name}</strong>
              <span className="muted small">{e.note}</span>
            </span>
            <span className="chevron" aria-hidden>
              ›
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
