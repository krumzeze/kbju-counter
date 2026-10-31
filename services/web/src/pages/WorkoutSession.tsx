import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { ExerciseRef, SetValues, Workout, WorkoutExercise, WorkoutSet } from "../api/types";
import { ExercisePicker } from "../components/ExercisePicker";
import { ExerciseThumb } from "../components/ExerciseThumb";
import { RestBar, useRestTimer } from "../components/RestTimer";
import { ErrorState, Spinner } from "../components/States";
import { duration, formatSet, kg } from "../lib/catalog";
import { count, dayLabel, shortDate } from "../lib/format";
import { tr } from "../lib/i18n";
import { useInvalidate, useWorkout, WORKOUT_KEYS } from "../lib/queries";
import { confirmAction, haptic } from "../lib/telegram";

interface Draft {
  weight: string;
  reps: string;
  minutes: string;
}

const toDraft = (s?: SetValues): Draft => ({
  weight: s?.weight_kg ? String(s.weight_kg) : "",
  reps: s?.reps ? String(s.reps) : "",
  minutes: s?.duration_s ? String(Math.round(s.duration_s / 60)) : "",
});

function toValues(d: Draft, cardio: boolean): SetValues | null {
  const weight = d.weight ? Number(d.weight.replace(",", ".")) : 0;
  if (!Number.isFinite(weight) || weight < 0 || weight > 1000) return null;
  if (cardio) {
    const minutes = Number(d.minutes);
    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 360) return null;
    return { weight_kg: weight, reps: null, duration_s: minutes * 60 };
  }
  const reps = Number(d.reps);
  if (!Number.isInteger(reps) || reps < 1 || reps > 1000) return null;
  return { weight_kg: weight, reps, duration_s: null };
}

function useNow(intervalMs: number) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

export function WorkoutSession() {
  const id = Number(useParams().id);
  const { data, isPending, error, refetch } = useWorkout(id);
  const timer = useRestTimer();
  const [picking, setPicking] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const client = useQueryClient();
  const invalidate = useInvalidate();
  const navigate = useNavigate();

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2800);
    return () => clearTimeout(t);
  }, [toast]);

  const apply = async (w: Workout) => {
    client.setQueryData(["workout", id], w);
    await invalidate(...WORKOUT_KEYS);
  };

  const addExercise = useMutation({
    mutationFn: (ref: ExerciseRef) => api.addWorkoutExercise(id, ref),
    onSuccess: async (w) => {
      setPicking(false);
      await apply(w);
    },
  });
  const removeExercise = useMutation({
    mutationFn: (exerciseId: number) => api.removeWorkoutExercise(id, exerciseId),
    onSuccess: apply,
  });
  const finish = useMutation({
    mutationFn: () => api.patchWorkout(id, { finished: true }),
    onSuccess: async (w) => {
      haptic("success");
      timer.stop();
      await apply(w);
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteWorkout(id),
    onSuccess: async () => {
      await invalidate(...WORKOUT_KEYS);
      navigate("/workouts", { replace: true });
    },
  });

  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  const active = data.finished_at === null;
  const onLogged = async (record: boolean) => {
    haptic(record ? "success" : "warning");
    if (record) setToast(tr("Новый рекорд! 🏆", "New personal record! 🏆"));
    if (active) timer.start();
    await invalidate(...WORKOUT_KEYS);
  };

  return (
    <div className={timer.active ? "page with-rest" : "page"}>
      <SessionHeader workout={data} onRenamed={apply} />

      {data.exercises.length === 0 && (
        <p className="empty">
          {tr(
            "Добавь первое упражнение. Вес из прошлой тренировки подставится сам.",
            "Add your first exercise. Weights from last time are filled in for you.",
          )}
        </p>
      )}

      {data.exercises.map((entry) => (
        <ExerciseBlock
          key={entry.exercise.id}
          entry={entry}
          workoutId={id}
          onLogged={onLogged}
          onRemove={async () => {
            const ok =
              entry.sets.length === 0 ||
              (await confirmAction(tr("Убрать упражнение вместе с подходами?", "Remove the exercise and its sets?")));
            if (ok) removeExercise.mutate(entry.exercise.id);
          }}
        />
      ))}

      <button className="btn btn-block dashed" onClick={() => setPicking(true)}>
        ＋ {tr("Добавить упражнение", "Add exercise")}
      </button>
      {addExercise.isError && <p className="error">{errorMessage(addExercise.error)}</p>}

      {active ? (
        <button
          className="btn btn-primary btn-block"
          disabled={finish.isPending}
          onClick={async () => {
            if (data.sets > 0 || (await confirmAction(tr("Завершить без подходов?", "Finish without any sets?"))))
              finish.mutate();
          }}
        >
          ✓ {tr("Завершить тренировку", "Finish workout")}
        </button>
      ) : (
        data.exercises.length > 0 && <SaveAsTemplate workout={data} />
      )}

      <button
        className="btn-ghost danger"
        disabled={remove.isPending}
        onClick={async () => {
          if (await confirmAction(tr("Удалить тренировку целиком?", "Delete the whole workout?"))) remove.mutate();
        }}
      >
        {tr("Удалить тренировку", "Delete workout")}
      </button>

      {picking && (
        <ExercisePicker
          title={tr("Добавить упражнение", "Add exercise")}
          onPick={(ref) => addExercise.mutate(ref)}
          onClose={() => setPicking(false)}
        />
      )}
      <RestBar timer={timer} />
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}

function SessionHeader({ workout, onRenamed }: { workout: Workout; onRenamed: (w: Workout) => void }) {
  const active = workout.finished_at === null;
  useNow(active ? 30000 : 3600000);
  const [title, setTitle] = useState(workout.title ?? "");
  const rename = useMutation({
    mutationFn: (value: string) => api.patchWorkout(workout.id, { title: value || null }),
    onSuccess: onRenamed,
  });

  return (
    <header className="session-head">
      <input
        className="title-input"
        value={title}
        maxLength={64}
        placeholder={active ? tr("Тренировка", "Workout") : dayLabel(workout.day)}
        onChange={(e) => setTitle(e.target.value)}
        onBlur={() => title !== (workout.title ?? "") && rename.mutate(title.trim())}
        aria-label={tr("Название тренировки", "Workout name")}
      />
      <div className="session-stats">
        {active ? (
          <span className="live">
            <span className="pulse" aria-hidden />
            {duration(workout.started_at)}
          </span>
        ) : (
          <span>
            {dayLabel(workout.day)} · {duration(workout.started_at, workout.finished_at)}
          </span>
        )}
        <span>
          {workout.sets} {count(workout.sets, ["подход", "подхода", "подходов"], ["set", "sets"])}
        </span>
        {workout.volume_kg > 0 && <span>{kg(workout.volume_kg)}</span>}
      </div>
    </header>
  );
}

function ExerciseBlock({
  entry,
  workoutId,
  onLogged,
  onRemove,
}: {
  entry: WorkoutExercise;
  workoutId: number;
  onLogged: (record: boolean) => Promise<void>;
  onRemove: () => void;
}) {
  const { exercise, sets, previous } = entry;
  const cardio = exercise.cardio;
  const [drafts, setDrafts] = useState<Draft[]>(() => {
    const n = sets.length;
    const count = Math.max(entry.planned_sets - n, n === 0 ? 1 : 0);
    return Array.from({ length: count }, (_, i) =>
      toDraft(previous[n + i] ?? previous[previous.length - 1] ?? sets[n - 1]),
    );
  });
  const [editing, setEditing] = useState<number | null>(null);

  const log = useMutation({
    mutationFn: ({ values }: { index: number; values: SetValues }) =>
      api.addSet(workoutId, exercise.id, values),
    onSuccess: async (created, { index }) => {
      setDrafts((d) => d.filter((_, i) => i !== index));
      await onLogged(created.record);
    },
  });

  const addDraft = () => {
    const last = drafts[drafts.length - 1];
    setDrafts([...drafts, last ? { ...last } : toDraft(sets[sets.length - 1] ?? previous[0])]);
  };

  return (
    <section className="card exercise-block">
      <div className="exercise-head">
        <ExerciseThumb catalogId={exercise.catalog_id} group={exercise.group} />
        <div className="exercise-title">
          {exercise.catalog_id ? (
            <Link to={`/catalog/${encodeURIComponent(exercise.catalog_id)}`} className="capitalize">
              {exercise.name}
            </Link>
          ) : (
            <span className="capitalize">{exercise.name}</span>
          )}
          {previous.length > 0 && entry.previous_day && (
            <span className="muted small">
              {tr("Прошлый раз", "Last time")} {shortDate(entry.previous_day)}:{" "}
              {previous.map(formatSet).join(" · ")}
            </span>
          )}
        </div>
        <Link
          to={`/exercises/${exercise.id}`}
          className="icon-btn"
          aria-label={tr("Прогресс", "Progress")}
          title={tr("Прогресс", "Progress")}
        >
          ↗
        </Link>
        <button className="icon-btn" onClick={onRemove} aria-label={tr("Убрать упражнение", "Remove exercise")}>
          ×
        </button>
      </div>

      <div className={cardio ? "set-table cardio" : "set-table"}>
        <span className="muted small">#</span>
        {cardio ? (
          <span className="muted small">{tr("Минуты", "Minutes")}</span>
        ) : (
          <>
            <span className="muted small">{tr("Вес, кг", "Weight, kg")}</span>
            <span className="muted small">{tr("Повторы", "Reps")}</span>
          </>
        )}
        <span />

        {sets.map((s, i) =>
          editing === s.id ? (
            <EditRow key={s.id} index={i} set={s} cardio={cardio} onDone={() => setEditing(null)} />
          ) : (
            <LoggedRow key={s.id} index={i} set={s} cardio={cardio} onEdit={() => setEditing(s.id)} />
          ),
        )}

        {drafts.map((d, i) => (
          <SetInputs
            key={`d${i}`}
            index={sets.length + i}
            draft={d}
            cardio={cardio}
            hint={previous[sets.length + i]}
            busy={log.isPending}
            onChange={(patch) => setDrafts(drafts.map((x, j) => (j === i ? { ...x, ...patch } : x)))}
            onSubmit={(values) => log.mutate({ index: i, values })}
          />
        ))}
      </div>
      {log.isError && <p className="error small">{errorMessage(log.error)}</p>}
      <button className="btn-ghost" onClick={addDraft} disabled={sets.length + drafts.length >= 30}>
        ＋ {tr("Подход", "Set")}
      </button>
    </section>
  );
}

function LoggedRow({
  index,
  set,
  cardio,
  onEdit,
}: {
  index: number;
  set: WorkoutSet;
  cardio: boolean;
  onEdit: () => void;
}) {
  return (
    <>
      <span className="set-index done">{index + 1}</span>
      {cardio ? (
        <button className="set-value" onClick={onEdit}>
          {formatSet(set)}
        </button>
      ) : (
        <>
          <button className="set-value" onClick={onEdit}>
            {set.weight_kg || "—"}
          </button>
          <button className="set-value" onClick={onEdit}>
            {set.reps}
          </button>
        </>
      )}
      <span className="set-check done" aria-label={tr("Выполнен", "Done")}>
        ✓
      </span>
    </>
  );
}

function EditRow({
  index,
  set,
  cardio,
  onDone,
}: {
  index: number;
  set: WorkoutSet;
  cardio: boolean;
  onDone: () => void;
}) {
  const [draft, setDraft] = useState(toDraft(set));
  const invalidate = useInvalidate();
  const save = useMutation({
    mutationFn: (values: SetValues) => api.patchSet(set.id, values),
    onSuccess: async () => {
      await invalidate(...WORKOUT_KEYS);
      onDone();
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteSet(set.id),
    onSuccess: async () => {
      await invalidate(...WORKOUT_KEYS);
      onDone();
    },
  });
  return (
    <SetInputs
      index={index}
      draft={draft}
      cardio={cardio}
      busy={save.isPending || remove.isPending}
      onChange={(patch) => setDraft({ ...draft, ...patch })}
      onSubmit={(values) => save.mutate(values)}
      onRemove={() => remove.mutate()}
    />
  );
}

function SetInputs({
  index,
  draft,
  cardio,
  hint,
  busy,
  onChange,
  onSubmit,
  onRemove,
}: {
  index: number;
  draft: Draft;
  cardio: boolean;
  hint?: SetValues;
  busy: boolean;
  onChange: (patch: Partial<Draft>) => void;
  onSubmit: (values: SetValues) => void;
  onRemove?: () => void;
}) {
  const values = toValues(draft, cardio);
  return (
    <>
      {onRemove ? (
        <button
          type="button"
          className="set-index removable"
          onClick={onRemove}
          aria-label={tr(`Удалить подход ${index + 1}`, `Delete set ${index + 1}`)}
        >
          ×
        </button>
      ) : (
        <span className="set-index">{index + 1}</span>
      )}
      {cardio ? (
        <input
          className="input set-input"
          inputMode="numeric"
          placeholder={hint?.duration_s ? String(Math.round(hint.duration_s / 60)) : "20"}
          value={draft.minutes}
          onChange={(e) => onChange({ minutes: e.target.value.replace(/\D/g, "") })}
          aria-label={tr(`Минуты, подход ${index + 1}`, `Minutes, set ${index + 1}`)}
        />
      ) : (
        <>
          <input
            className="input set-input"
            inputMode="decimal"
            placeholder={hint ? String(hint.weight_kg || 0) : "0"}
            value={draft.weight}
            onChange={(e) => onChange({ weight: e.target.value.replace(/[^\d.,]/g, "") })}
            aria-label={tr(`Вес, подход ${index + 1}`, `Weight, set ${index + 1}`)}
          />
          <input
            className="input set-input"
            inputMode="numeric"
            placeholder={hint?.reps ? String(hint.reps) : "10"}
            value={draft.reps}
            onChange={(e) => onChange({ reps: e.target.value.replace(/\D/g, "") })}
            aria-label={tr(`Повторы, подход ${index + 1}`, `Reps, set ${index + 1}`)}
          />
        </>
      )}
      <button
        type="button"
        className="set-check"
        disabled={!values || busy}
        onClick={() => values && onSubmit(values)}
        aria-label={tr(`Записать подход ${index + 1}`, `Log set ${index + 1}`)}
      >
        ✓
      </button>
    </>
  );
}

function SaveAsTemplate({ workout }: { workout: Workout }) {
  const [name, setName] = useState<string | null>(null);
  const invalidate = useInvalidate();
  const save = useMutation({
    mutationFn: (value: string) => api.createTemplate({ name: value, workout_id: workout.id }),
    onSuccess: async () => {
      haptic("success");
      setName(null);
      await invalidate("templates");
    },
  });

  if (save.isSuccess && name === null) {
    return <p className="muted small center">{tr("Программа сохранена", "Routine saved")}</p>;
  }
  if (name === null) {
    return (
      <button className="btn btn-block" onClick={() => setName(workout.title ?? "")}>
        {tr("Сохранить как программу", "Save as routine")}
      </button>
    );
  }
  return (
    <form
      className="inline-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) save.mutate(name.trim());
      }}
    >
      <input
        className="input"
        autoFocus
        maxLength={64}
        placeholder={tr("Например, Грудь и трицепс", "e.g. Chest and triceps")}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <button className="btn btn-primary" disabled={!name.trim() || save.isPending}>
        {tr("Сохранить", "Save")}
      </button>
    </form>
  );
}
