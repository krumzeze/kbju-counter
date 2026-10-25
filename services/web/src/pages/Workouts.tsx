import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { WorkoutSet } from "../api/types";
import { Spinner } from "../components/States";
import { todayIso } from "../lib/format";
import { useDay, useExercises, useInvalidate } from "../lib/queries";
import { haptic } from "../lib/telegram";

interface Row {
  weight: string;
  reps: string;
}

const emptyRow = (prev?: Row): Row => (prev ? { ...prev } : { weight: "", reps: "" });

export function Workouts() {
  const day = useDay(todayIso());
  const exercises = useExercises();

  return (
    <div className="page">
      <h1>Тренировка</h1>
      <SetForm suggestions={exercises.data ?? []} />

      <section>
        <h2>Сегодня</h2>
        {day.isPending ? <Spinner /> : <TodaySets sets={day.data?.sets ?? []} />}
      </section>

      {exercises.data && exercises.data.length > 0 && (
        <section>
          <h2>Прогресс</h2>
          <div className="chips">
            {exercises.data.map((name) => (
              <Link key={name} className="chip" to={`/workouts/${encodeURIComponent(name)}`}>
                {name}
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function SetForm({ suggestions }: { suggestions: string[] }) {
  const [exercise, setExercise] = useState("");
  const [rows, setRows] = useState<Row[]>([emptyRow()]);
  const invalidate = useInvalidate();

  const sets = rows
    .map((r) => ({ weight_kg: Number(r.weight.replace(",", ".")), reps: Number(r.reps) }))
    .filter((s) => isValidSet(s.weight_kg, s.reps));

  const save = useMutation({
    mutationFn: () => api.addSets(exercise, sets),
    onSuccess: async () => {
      haptic("success");
      setRows([emptyRow()]);
      await invalidate("day", "exercises", "progress");
    },
  });

  const update = (i: number, patch: Partial<Row>) =>
    setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <form
      className="card form"
      onSubmit={(e) => {
        e.preventDefault();
        if (exercise.trim() && sets.length) save.mutate();
      }}
    >
      <label className="field">
        <span>Упражнение</span>
        <input
          className="input"
          list="exercise-list"
          placeholder="Жим лёжа"
          value={exercise}
          onChange={(e) => setExercise(e.target.value)}
          maxLength={128}
        />
        <datalist id="exercise-list">
          {suggestions.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
      </label>

      <div className="sets-grid">
        <span className="muted small">#</span>
        <span className="muted small">Вес, кг</span>
        <span className="muted small">Повторы</span>
        <span />
        {rows.map((row, i) => (
          <SetRow
            key={i}
            index={i}
            row={row}
            onChange={(patch) => update(i, patch)}
            onRemove={rows.length > 1 ? () => setRows(rows.filter((_, j) => j !== i)) : undefined}
          />
        ))}
      </div>

      <button
        type="button"
        className="btn-ghost"
        onClick={() => rows.length < 20 && setRows([...rows, emptyRow(rows[rows.length - 1])])}
      >
        ＋ Подход
      </button>

      {save.isError && <p className="error">{errorMessage(save.error)}</p>}
      <button
        className="btn btn-primary btn-block"
        disabled={!exercise.trim() || !sets.length || save.isPending}
      >
        Записать {sets.length > 0 ? `(${sets.length})` : ""}
      </button>
    </form>
  );
}

function isValidSet(weight: number, reps: number) {
  return Number.isFinite(weight) && weight >= 0 && weight <= 1000 && Number.isInteger(reps) && reps >= 1;
}

function SetRow({
  index,
  row,
  onChange,
  onRemove,
}: {
  index: number;
  row: Row;
  onChange: (patch: Partial<Row>) => void;
  onRemove?: () => void;
}) {
  return (
    <>
      <span className="set-index">{index + 1}</span>
      <input
        className="input"
        inputMode="decimal"
        placeholder="80"
        value={row.weight}
        onChange={(e) => onChange({ weight: e.target.value.replace(/[^\d.,]/g, "") })}
        aria-label={`Вес, подход ${index + 1}`}
      />
      <input
        className="input"
        inputMode="numeric"
        placeholder="8"
        value={row.reps}
        onChange={(e) => onChange({ reps: e.target.value.replace(/\D/g, "") })}
        aria-label={`Повторы, подход ${index + 1}`}
      />
      {onRemove ? (
        <button type="button" className="icon-btn" onClick={onRemove} aria-label="Убрать подход">
          ×
        </button>
      ) : (
        <span />
      )}
    </>
  );
}

function TodaySets({ sets }: { sets: WorkoutSet[] }) {
  const invalidate = useInvalidate();
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteSet(id),
    onSuccess: () => invalidate("day", "progress"),
  });

  if (sets.length === 0) return <p className="empty">Сегодня подходов ещё не было.</p>;

  const grouped = new Map<string, WorkoutSet[]>();
  for (const s of sets) grouped.set(s.exercise, [...(grouped.get(s.exercise) ?? []), s]);
  return (
    <div className="stack">
      {[...grouped].map(([name, items]) => (
        <div key={name} className="card">
          <Link to={`/workouts/${encodeURIComponent(name)}`} className="set-title">
            {name}
          </Link>
          <ul className="set-list">
            {items.map((s) => (
              <li key={s.id}>
                <span>
                  {s.weight_kg} кг × {s.reps}
                </span>
                <button
                  className="icon-btn"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(s.id)}
                  aria-label="Удалить подход"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
