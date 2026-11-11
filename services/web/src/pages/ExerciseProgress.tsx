import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Exercise, ProgressPoint } from "../api/types";
import { BarChart } from "../components/BarChart";
import { BodyMap } from "../components/BodyMap";
import { type MuscleChoice, MuscleEditor, muscleValues } from "../components/MuscleEditor";
import { LineChart } from "../components/LineChart";
import { ErrorState, Spinner } from "../components/States";
import { formatSet, kg, muscleLabel } from "../lib/catalog";
import { count, dayLabel, shortDate } from "../lib/format";
import { tr } from "../lib/i18n";
import { useInvalidate, useProgress } from "../lib/queries";
import { PremiumNote } from "../components/PremiumNote";

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

      <PremiumNote />
      {!exercise.catalog_id && !cardio && <Muscles exercise={exercise} />}
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
            {weighted && metric === "e1rm" && (
              <p className="muted small">
                {tr(
                  "1ПМ: расчётный вес, который ты поднял бы на один повтор. Считается по лучшему подходу тренировки.",
                  "1RM: the estimated weight you could lift for one rep, based on the best set of the session.",
                )}
              </p>
            )}
          </section>

          {!cardio && points.length > 1 && <RecentSessions points={points.slice(-RECENT)} weighted={weighted} />}

          <section>
            <h2>{tr("История", "History")}</h2>
            <div className="stack">
              {[...points].reverse().map((p) => (
                <Link key={p.workout_id} to={`/workouts/${p.workout_id}`} className="card history-row">
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
                </Link>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

const RECENT = 4;

/** Set-by-set bars for the latest sessions, newest first, on one shared scale. */
function RecentSessions({ points, weighted }: { points: ProgressPoint[]; weighted: boolean }) {
  const size = (s: ProgressPoint["items"][number]) => (weighted ? s.weight_kg : (s.reps ?? 0));
  const peak = Math.max(1, ...points.flatMap((p) => p.items.map(size)));
  return (
    <section className="card">
      <h2>{tr("Последние сессии", "Recent sessions")}</h2>
      <p className="muted small">
        {weighted
          ? tr("Столбик: вес в подходе, под ним повторы.", "Bar: weight of the set, reps below it.")
          : tr("Столбик: повторы в подходе.", "Bar: reps in the set.")}
      </p>
      <div className="sessions">
        {[...points].reverse().map((p, i, list) => {
          const before = list[i + 1];
          const delta = before ? p.e1rm - before.e1rm : 0;
          return (
            <Link key={p.workout_id} to={`/workouts/${p.workout_id}`} className="session-row">
              <span className="session-day">
                <strong>{shortDate(p.day)}</strong>
                {weighted && before && Math.abs(delta) >= 0.05 && (
                  <span className={delta > 0 ? "small positive" : "small negative"}>
                    {delta > 0 ? "+" : "−"}
                    {Math.abs(delta).toFixed(1)}
                  </span>
                )}
              </span>
              <span className="session-bars">
                {p.items.map((s, j) => (
                  <span key={j} className="session-bar">
                    <span className="session-top">{weighted ? s.weight_kg : s.reps}</span>
                    <span className="session-fill" style={{ height: `calc((100% - 34px) * ${(size(s) / peak).toFixed(3)})` }} />
                    {weighted && <span className="session-reps">{s.reps}</span>}
                  </span>
                ))}
              </span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

function Muscles({ exercise }: { exercise: Exercise }) {
  const [draft, setDraft] = useState<MuscleChoice | null>(null);
  const invalidate = useInvalidate();
  const save = useMutation({
    mutationFn: (v: MuscleChoice) => api.setExerciseMuscles(exercise.id, v.primary, v.secondary),
    onSuccess: async () => {
      await invalidate("progress", "exercises", "analytics", "workout");
      setDraft(null);
    },
  });
  const empty = exercise.primary.length + exercise.secondary.length === 0;

  return (
    <section className="card muscles-card">
      <div className="card-head">
        <h2>{tr("Мышцы", "Muscles")}</h2>
        {!draft && (
          <button className="btn-ghost" onClick={() => setDraft({ primary: exercise.primary, secondary: exercise.secondary })}>
            {empty ? tr("Указать", "Set") : tr("Изменить", "Edit")}
          </button>
        )}
      </div>
      {draft ? (
        <>
          <MuscleEditor value={draft} onChange={setDraft} />
          {save.isError && <p className="error">{errorMessage(save.error)}</p>}
          <div className="sheet-actions">
            <button className="btn" onClick={() => setDraft(null)}>
              {tr("Отмена", "Cancel")}
            </button>
            <button className="btn btn-primary" disabled={save.isPending} onClick={() => save.mutate(draft)}>
              {tr("Сохранить", "Save")}
            </button>
          </div>
        </>
      ) : empty ? (
        <p className="muted small">
          {tr(
            "Укажи, какие мышцы работают, и упражнение появится на карте нагрузки в аналитике.",
            "Set the muscles this exercise works and it will show up on the muscle load map.",
          )}
        </p>
      ) : (
        <>
          <BodyMap values={muscleValues(exercise)} />
          <p className="small center">
            {exercise.primary.map(muscleLabel).join(", ")}
            {exercise.secondary.length > 0 && (
              <span className="muted">
                {exercise.primary.length > 0 && " · "}
                {exercise.secondary.map(muscleLabel).join(", ")}
              </span>
            )}
          </p>
        </>
      )}
    </section>
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
          unit={(n) => count(n, ["повтор", "повтора", "повторов"], ["rep", "reps"])}
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
