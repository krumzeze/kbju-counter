import { Link } from "react-router-dom";
import type { SetValues, Workout, WorkoutExercise } from "../api/types";
import { BodyMap } from "../components/BodyMap";
import { ExerciseThumb } from "../components/ExerciseThumb";
import { Icon } from "../components/Icon";
import { duration, e1rm, formatSet, kg, setVolume } from "../lib/catalog";
import { count, dayLabel, shortDate } from "../lib/format";
import { locale, tr } from "../lib/i18n";

const MIN_TIMED_MS = 5 * 60000;

const elapsed = (from: string, to: string | null) => (to ? new Date(to).getTime() - new Date(from).getTime() : 0);

const RECORD_LABELS = {
  e1rm: () => tr("Рекорд 1ПМ", "1RM record"),
  weight: () => tr("Рекорд веса", "Weight record"),
  reps: () => tr("Рекорд повторов", "Reps record"),
};

function Delta({ value, unit }: { value: number; unit: string }) {
  const rounded = Math.round(value * 10) / 10;
  if (!rounded) return <span className="delta">{tr("без изменений", "no change")}</span>;
  return (
    <span className={rounded > 0 ? "delta positive" : "delta negative"}>
      {rounded > 0 ? "+" : "−"}
      {Math.abs(rounded).toLocaleString(locale())} {unit}
    </span>
  );
}

export function WorkoutSummary({ workout, onEdit }: { workout: Workout; onEdit: () => void }) {
  const { compare } = workout;
  const done = workout.exercises.filter((e) => e.sets.length > 0);
  const records = done.reduce((n, e) => n + e.records.length, 0);
  const time = elapsed(workout.started_at, workout.finished_at);
  const timeBefore = compare ? elapsed(compare.started_at, compare.finished_at) : 0;
  const peak = Math.max(1, ...Object.values(workout.muscles));
  const heat = Object.fromEntries(Object.entries(workout.muscles).map(([m, v]) => [m, v / peak]));

  return (
    <div className="page">
      <header className="session-head">
        <h1 className="capitalize">{workout.title || tr("Тренировка", "Workout")}</h1>
        <div className="session-stats">
          <span className="capitalize">{dayLabel(workout.day)}</span>
          {compare && (
            <Link to={`/workouts/${compare.id}`}>
              {tr("сравнение с", "compared with")} {shortDate(compare.day)}
            </Link>
          )}
        </div>
      </header>

      {records > 0 && (
        <div className="card record-banner">
          <strong>
            {records} {count(records, ["новый рекорд", "новых рекорда", "новых рекордов"], ["new record", "new records"])}
          </strong>
          <span className="small">
            {done
              .filter((e) => e.records.length > 0)
              .map((e) => e.exercise.name)
              .join(", ")}
          </span>
        </div>
      )}

      <section className="kpis">
        {time >= MIN_TIMED_MS && (
          <div className="card kpi">
            <span className="kpi-label">{tr("Длительность", "Duration")}</span>
            <span className="kpi-value small-value">{duration(workout.started_at, workout.finished_at)}</span>
            {timeBefore >= MIN_TIMED_MS && (
              <span className="kpi-sub">
                {tr("было", "was")} {duration(compare!.started_at, compare!.finished_at)}
              </span>
            )}
          </div>
        )}
        <div className="card kpi">
          <span className="kpi-label">{tr("Подходы", "Sets")}</span>
          <span className="kpi-value">{workout.sets}</span>
          {compare && (
            <span className="kpi-sub">
              <Delta value={workout.sets - compare.sets} unit="" />
            </span>
          )}
        </div>
        {workout.volume_kg > 0 && (
          <div className="card kpi">
            <span className="kpi-label">{tr("Тоннаж", "Volume")}</span>
            <span className="kpi-value small-value">{kg(workout.volume_kg)}</span>
            {compare && compare.volume_kg > 0 && (
              <span className="kpi-sub">
                <Delta value={workout.volume_kg - compare.volume_kg} unit={tr("кг", "kg")} />
              </span>
            )}
          </div>
        )}
      </section>

      {done.length === 0 && <p className="empty">{tr("В этой тренировке нет подходов.", "This workout has no sets.")}</p>}

      {done.map((entry) => (
        <ExerciseResult key={entry.exercise.id} entry={entry} />
      ))}

      {Object.keys(heat).length > 0 && (
        <section className="card">
          <h2>{tr("Что работало", "Muscles worked")}</h2>
          <BodyMap values={heat} className="large" />
        </section>
      )}

      <button className="btn btn-block" onClick={onEdit}>
        <Icon name="pen" size={18} />
        {tr("Изменить тренировку", "Edit workout")}
      </button>
    </div>
  );
}

const best = (sets: SetValues[]) => sets.reduce((a, b) => (e1rm(b) > e1rm(a) ? b : a));
const total = (sets: SetValues[], f: (s: SetValues) => number) => sets.reduce((n, s) => n + f(s), 0);

function ExerciseResult({ entry }: { entry: WorkoutExercise }) {
  const { exercise, sets, previous } = entry;
  const weighted = sets.some((s) => s.weight_kg > 0);

  return (
    <section className="card result">
      <div className="exercise-head">
        <ExerciseThumb catalogId={exercise.catalog_id} group={exercise.group} />
        <div className="exercise-title">
          <Link to={`/exercises/${exercise.id}`} className="capitalize">
            {exercise.name}
          </Link>
          {entry.records.length > 0 && (
            <span className="badges">
              {entry.records.map((r) => (
                <span key={r} className="badge record">
                  {RECORD_LABELS[r]()}
                </span>
              ))}
            </span>
          )}
        </div>
      </div>

      <span className="set-chips">
        {sets.map((s) => (
          <span key={s.id} className="set-chip">
            {formatSet(s)}
          </span>
        ))}
      </span>

      {previous.length === 0 ? (
        <span className="muted small">{tr("Первый раз, сравнивать пока не с чем.", "First time, nothing to compare with yet.")}</span>
      ) : (
        <dl className="compare">
          {exercise.cardio ? (
            <Row
              label={tr("Время", "Time")}
              before={`${Math.round(total(previous, (s) => s.duration_s ?? 0) / 60)}`}
              now={`${Math.round(total(sets, (s) => s.duration_s ?? 0) / 60)} ${tr("мин", "min")}`}
              delta={(total(sets, (s) => s.duration_s ?? 0) - total(previous, (s) => s.duration_s ?? 0)) / 60}
              unit={tr("мин", "min")}
            />
          ) : weighted ? (
            <>
              <Row
                label={tr("Лучший подход", "Best set")}
                before={formatSet(best(previous))}
                now={formatSet(best(sets))}
                delta={e1rm(best(sets)) - e1rm(best(previous))}
                unit={tr("кг 1ПМ", "kg 1RM")}
              />
              <Row
                label={tr("Объём", "Volume")}
                before={Math.round(total(previous, setVolume)).toLocaleString(locale())}
                now={kg(total(sets, setVolume))}
                delta={total(sets, setVolume) - total(previous, setVolume)}
                unit={tr("кг", "kg")}
              />
            </>
          ) : (
            <Row
              label={tr("Повторы", "Reps")}
              before={String(total(previous, (s) => s.reps ?? 0))}
              now={String(total(sets, (s) => s.reps ?? 0))}
              delta={total(sets, (s) => s.reps ?? 0) - total(previous, (s) => s.reps ?? 0)}
              unit=""
            />
          )}
          {entry.previous_day && (
            <span className="muted small compare-note">
              {tr("Прошлый раз", "Last time")} {shortDate(entry.previous_day)}: {previous.map(formatSet).join(" · ")}
            </span>
          )}
        </dl>
      )}
    </section>
  );
}

function Row({
  label,
  before,
  now,
  delta,
  unit,
}: {
  label: string;
  before: string;
  now: string;
  delta: number;
  unit: string;
}) {
  return (
    <>
      <dt className="muted small">{label}</dt>
      <dd>
        <span className="muted">{before}</span> → <strong>{now}</strong>
      </dd>
      <dd className="small">
        <Delta value={delta} unit={unit} />
      </dd>
    </>
  );
}
