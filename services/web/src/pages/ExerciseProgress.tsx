import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import type { ProgressPoint } from "../api/types";
import { BarChart } from "../components/BarChart";
import { LineChart } from "../components/LineChart";
import { ErrorState, Spinner } from "../components/States";
import { formatSet, kg } from "../lib/catalog";
import { dayLabel } from "../lib/format";
import { tr } from "../lib/i18n";
import { useProgress } from "../lib/queries";

type Metric = "e1rm" | "weight" | "volume" | "reps";

export function ExerciseProgress() {
  const id = Number(useParams().id);
  const { data, isPending, error, refetch } = useProgress(id);
  const [metric, setMetric] = useState<Metric>("e1rm");

  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  const { exercise, points, records } = data;
  const cardio = exercise.cardio;
  const weighted = !cardio && points.some((p) => p.top_weight_kg > 0);

  return (
    <div className="page">
      <div>
        <h1 className="capitalize">{exercise.name}</h1>
        {exercise.catalog_id && (
          <Link to={`/catalog/${encodeURIComponent(exercise.catalog_id)}`} className="btn-ghost inline">
            {tr("Техника выполнения", "How to do it")} →
          </Link>
        )}
      </div>

      {points.length === 0 ? (
        <p className="empty">{tr("Записей пока нет.", "No entries yet.")}</p>
      ) : (
        <>
          <section className="kpis">
            {cardio ? (
              <>
                <Kpi label={tr("Самая долгая", "Longest")} value={`${Math.round(records.duration_s / 60)}`} sub={tr("минут", "minutes")} />
                <Kpi
                  label={tr("Всего", "Total")}
                  value={`${Math.round(points.reduce((a, p) => a + p.duration_s, 0) / 60)}`}
                  sub={tr("минут", "minutes")}
                />
              </>
            ) : weighted ? (
              <>
                <Kpi label={tr("Рекорд 1ПМ", "Best 1RM")} value={records.e1rm.toFixed(1)} sub={tr("кг, расчётный", "kg, estimated")} />
                <Kpi label={tr("Макс. вес", "Top weight")} value={String(records.weight_kg)} sub={tr("кг", "kg")} />
                <Kpi label={tr("Лучший объём", "Best volume")} value={kg(records.volume_kg)} sub={tr("за тренировку", "per session")} />
                <Change points={points} />
              </>
            ) : (
              <Kpi label={tr("Макс. повторов", "Most reps")} value={String(records.reps)} sub={tr("в подходе", "in a set")} />
            )}
            <Kpi label={tr("Тренировок", "Sessions")} value={String(points.length)} sub={tr("в истории", "in history")} />
          </section>

          <section className="card">
            {weighted && (
              <div className="segmented compact" role="tablist">
                {(
                  [
                    ["e1rm", tr("1ПМ", "1RM")],
                    ["weight", tr("Вес", "Weight")],
                    ["volume", tr("Объём", "Volume")],
                    ["reps", tr("Повторы", "Reps")],
                  ] as [Metric, string][]
                ).map(([m, label]) => (
                  <button key={m} role="tab" aria-selected={metric === m} onClick={() => setMetric(m)}>
                    {label}
                  </button>
                ))}
              </div>
            )}
            <ProgressChart points={points} metric={cardio ? "duration" : weighted ? metric : "reps"} />
          </section>

          <section>
            <h2>{tr("История", "History")}</h2>
            <div className="stack">
              {[...points].reverse().map((p) => (
                <div key={p.day} className="card history-row">
                  <strong className="capitalize">{dayLabel(p.day)}</strong>
                  <span className="set-chips">
                    {p.items.map((s, i) => (
                      <span key={i} className="set-chip">
                        {formatSet(s)}
                      </span>
                    ))}
                  </span>
                  {weighted && (
                    <span className="muted small">
                      {tr("1ПМ", "1RM")} ≈ {p.e1rm.toFixed(1)} · {kg(p.volume_kg)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
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

function Change({ points }: { points: ProgressPoint[] }) {
  const delta = points[points.length - 1].e1rm - points[0].e1rm;
  return (
    <div className="card kpi">
      <span className="kpi-label">{tr("Изменение 1ПМ", "1RM change")}</span>
      <span className={`kpi-value ${delta >= 0 ? "positive" : "negative"}`}>
        {delta >= 0 ? "+" : ""}
        {delta.toFixed(1)}
      </span>
      <span className="kpi-sub">{tr("кг за период", "kg over the period")}</span>
    </div>
  );
}

function ProgressChart({ points, metric }: { points: ProgressPoint[]; metric: Metric | "duration" }) {
  const unit = tr("кг", "kg");
  switch (metric) {
    case "e1rm":
      return <LineChart points={points.map((p) => ({ day: p.day, value: p.e1rm }))} unit={unit} />;
    case "weight":
      return <LineChart points={points.map((p) => ({ day: p.day, value: p.top_weight_kg }))} unit={unit} />;
    case "volume":
      return (
        <BarChart
          points={points.map((p) => ({ day: p.day, value: p.volume_kg }))}
          format={kg}
          label={tr("Объём", "Volume")}
        />
      );
    case "reps":
      return (
        <BarChart
          points={points.map((p) => ({ day: p.day, value: p.reps }))}
          format={(n) => `${Math.round(n)}`}
          label={tr("Повторы", "Reps")}
        />
      );
    case "duration":
      return (
        <BarChart
          points={points.map((p) => ({ day: p.day, value: Math.round(p.duration_s / 60) }))}
          format={(n) => `${Math.round(n)} ${tr("мин", "min")}`}
          label={tr("Минуты", "Minutes")}
        />
      );
  }
}
