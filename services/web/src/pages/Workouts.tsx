import { useMutation } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Workout, WorkoutSummary } from "../api/types";
import { Art } from "../components/Art";
import { Icon } from "../components/Icon";
import { Spinner } from "../components/States";
import { compact, duration, kg } from "../lib/catalog";
import { count, dayLabel } from "../lib/format";
import { tr } from "../lib/i18n";
import {
  useActiveWorkout,
  useAnalytics,
  useInvalidate,
  useTemplates,
  useWorkouts,
} from "../lib/queries";

export function Workouts() {
  const active = useActiveWorkout();
  const navigate = useNavigate();
  const invalidate = useInvalidate();

  const start = useMutation({
    mutationFn: (templateId?: number) => api.startWorkout(templateId),
    onSuccess: async (w) => {
      await invalidate("workout", "workouts");
      navigate(`/workouts/${w.id}`);
    },
  });

  return (
    <div className="page">
      <h1>{tr("Зал", "Gym")}</h1>

      {active.isPending ? (
        <Spinner />
      ) : active.data ? (
        <ActiveCard workout={active.data} />
      ) : (
        <button
          className="btn btn-primary btn-block"
          disabled={start.isPending}
          onClick={() => start.mutate(undefined)}
        >
          <Icon name="play" size={18} />
          {tr("Начать тренировку", "Start workout")}
        </button>
      )}
      {start.isError && <p className="error">{errorMessage(start.error)}</p>}

      <WeekCard />

      <div className="nav-cards">
        <Link to="/catalog" className="card sage nav-card">
          <span className="nav-card-icon" aria-hidden>
            <Icon name="list" />
          </span>
          <strong>{tr("Упражнения", "Exercises")}</strong>
          <span className="muted small">{tr("Техника и мышцы", "Technique and muscles")}</span>
        </Link>
        <Link to="/analytics" className="card sand nav-card">
          <span className="nav-card-icon" aria-hidden>
            <Icon name="chart" />
          </span>
          <strong>{tr("Аналитика", "Analytics")}</strong>
          <span className="muted small">{tr("Прогресс и рекорды", "Progress and records")}</span>
        </Link>
      </div>

      <Templates
        disabled={!!active.data || start.isPending}
        onStart={(id) => start.mutate(id)}
      />

      <History />
    </div>
  );
}

function ActiveCard({ workout }: { workout: Workout }) {
  return (
    <Link to={`/workouts/${workout.id}`} className="card active-workout">
      <span className="pulse" aria-hidden />
      <div>
        <strong>{workout.title || tr("Тренировка идёт", "Workout in progress")}</strong>
        <span className="muted small">
          {duration(workout.started_at)} · {workout.sets}{" "}
          {count(workout.sets, ["подход", "подхода", "подходов"], ["set", "sets"])}
        </span>
      </div>
      <span className="btn btn-primary small">{tr("Продолжить", "Continue")}</span>
    </Link>
  );
}

function WeekCard() {
  const { data } = useAnalytics();
  if (!data) return null;
  const week = data.weeks[data.weeks.length - 1];
  return (
    <section className="stats-row three">
      <div className="card peach stat">
        <span className="small">{tr("Неделя", "This week")}</span>
        <strong>{week.workouts}</strong>
        <span className="muted small">
          {count(week.workouts, ["тренировка", "тренировки", "тренировок"], ["workout", "workouts"])}
        </span>
      </div>
      <div className="card sage stat">
        <span className="small">{tr("Тоннаж", "Volume")}</span>
        <strong>{compact(week.volume_kg)}</strong>
        <span className="muted small">{tr("кг за неделю", "kg this week")}</span>
      </div>
      <div className="card blush stat">
        <span className="small">{tr("Серия", "Streak")}</span>
        <strong>{data.streak_weeks}</strong>
        <span className="muted small">
          {count(data.streak_weeks, ["неделя", "недели", "недель"], ["week", "weeks"])}
        </span>
      </div>
    </section>
  );
}

function Templates({ disabled, onStart }: { disabled: boolean; onStart: (id: number) => void }) {
  const { data } = useTemplates();
  return (
    <section>
      <div className="card-head">
        <h2>{tr("Мои программы", "My routines")}</h2>
        <Link to="/templates/new" className="btn-ghost">
          <Icon name="plus" size={18} />
          {tr("Создать", "New")}
        </Link>
      </div>
      {!data?.length ? (
        <div className="empty small">
          <Art name="empty-routines" />
          <p>
            {tr(
              "Собери программу, например «Грудь и трицепс», и запускай тренировку в одно касание.",
              'Build a routine such as "Chest and triceps" and start a workout in one tap.',
            )}
          </p>
        </div>
      ) : (
        <div className="template-list">
          {data.map((t) => (
            <div key={t.id} className="card template">
              <Link to={`/templates/${t.id}`} className="template-body">
                <strong>{t.name}</strong>
                <span className="muted small">
                  {t.items.map((i) => i.exercise.name).join(", ") || tr("Пусто", "Empty")}
                </span>
              </Link>
              <button
                className="btn btn-primary small"
                disabled={disabled}
                onClick={() => onStart(t.id)}
                aria-label={tr(`Начать: ${t.name}`, `Start: ${t.name}`)}
              >
                <Icon name="play" size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function History() {
  const { data, isPending } = useWorkouts();
  if (isPending) return null;
  const done = (data ?? []).filter((w) => w.finished_at && w.sets > 0);
  if (!done.length) return null;
  return (
    <section>
      <h2>{tr("История", "History")}</h2>
      <div className="stack">
        {done.map((w) => (
          <HistoryItem key={w.id} workout={w} />
        ))}
      </div>
    </section>
  );
}

function HistoryItem({ workout: w }: { workout: WorkoutSummary }) {
  return (
    <Link to={`/workouts/${w.id}`} className="card history-item">
      <div className="history-head">
        <strong className="capitalize">{w.title || dayLabel(w.day)}</strong>
        <span className="muted small">{w.title ? dayLabel(w.day) : duration(w.started_at, w.finished_at)}</span>
      </div>
      <span className="muted small clamp">{w.names.join(" · ")}</span>
      <span className="history-stats small">
        <span>
          {w.exercises} {count(w.exercises, ["упражнение", "упражнения", "упражнений"], ["exercise", "exercises"])}
        </span>
        <span>
          {w.sets} {count(w.sets, ["подход", "подхода", "подходов"], ["set", "sets"])}
        </span>
        {w.volume_kg > 0 && <span>{kg(w.volume_kg)}</span>}
      </span>
    </Link>
  );
}
