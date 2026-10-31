import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { MuscleGroup } from "../api/types";
import { BodyMap } from "../components/BodyMap";
import { ExerciseThumb } from "../components/ExerciseThumb";
import { ErrorState, Spinner } from "../components/States";
import { equipmentLabel, groupLabel, imageUrl, levelLabel, muscleLabel } from "../lib/catalog";
import { tr } from "../lib/i18n";
import { useActiveWorkout, useCatalogItem, useInvalidate, WORKOUT_KEYS } from "../lib/queries";
import { haptic } from "../lib/telegram";

export function ExerciseInfo() {
  const id = decodeURIComponent(useParams().id ?? "");
  const { data, isPending, error, refetch } = useCatalogItem(id);
  const active = useActiveWorkout();
  const navigate = useNavigate();
  const invalidate = useInvalidate();

  const add = useMutation({
    mutationFn: async () => {
      const workout = active.data ?? (await api.startWorkout());
      return api.addWorkoutExercise(workout.id, { catalog_id: id });
    },
    onSuccess: async (w) => {
      haptic("success");
      await invalidate(...WORKOUT_KEYS);
      navigate(`/workouts/${w.id}`);
    },
  });

  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  const muscles = {
    ...Object.fromEntries(data.secondary.map((m) => [m, 0.35])),
    ...Object.fromEntries(data.primary.map((m) => [m, 1])),
    ...(data.cardio ? { heart: 1 } : {}),
  };

  return (
    <div className="page">
      <Frames id={data.id} count={data.images} group={data.group} />
      <div>
        <h1 className="capitalize">{data.name}</h1>
        {data.name_en !== data.name && <p className="muted small">{data.name_en}</p>}
      </div>
      <div className="chips">
        <Link to={`/catalog?group=${data.group}`} className="chip">
          {groupLabel(data.group)}
        </Link>
        <Link to={`/catalog?equipment=${encodeURIComponent(data.equipment)}`} className="chip">
          {equipmentLabel(data.equipment)}
        </Link>
        <span className="chip muted">{levelLabel(data.level)}</span>
      </div>

      <div className="actions-row">
        <button className="btn btn-primary" disabled={add.isPending || active.isPending} onClick={() => add.mutate()}>
          ＋ {active.data ? tr("В текущую тренировку", "Add to workout") : tr("Начать с него", "Start workout")}
        </button>
        {data.exercise_id && (
          <Link to={`/exercises/${data.exercise_id}`} className="btn">
            {tr("Мой прогресс", "My progress")}
          </Link>
        )}
      </div>
      {add.isError && <p className="error">{errorMessage(add.error)}</p>}

      <section className="card muscles-card">
        <BodyMap values={muscles} />
        <dl className="muscle-legend">
          <dt>
            <i className="swatch strong" /> {tr("Основные", "Primary")}
          </dt>
          <dd>{data.primary.map(muscleLabel).join(", ") || "—"}</dd>
          {data.secondary.length > 0 && (
            <>
              <dt>
                <i className="swatch" /> {tr("Вспомогательные", "Secondary")}
              </dt>
              <dd>{data.secondary.map(muscleLabel).join(", ")}</dd>
            </>
          )}
        </dl>
      </section>

      <section className="card">
        <h2>{tr("Техника выполнения", "How to do it")}</h2>
        <ol className="steps">
          {data.instructions.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
      </section>
    </div>
  );
}

function Frames({ id, count, group }: { id: string; count: number; group: MuscleGroup }) {
  const [frame, setFrame] = useState(0);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (count < 2) return;
    const t = setInterval(() => setFrame((f) => (f + 1) % count), 1100);
    return () => clearInterval(t);
  }, [count]);

  if (failed) {
    return <ExerciseThumb catalogId={null} group={group} className="hero-frames" />;
  }
  return (
    <div className="hero-frames">
      {Array.from({ length: count }, (_, i) => (
        <img
          key={i}
          src={imageUrl(id, i)}
          alt=""
          className={i === frame ? "shown" : undefined}
          onError={() => setFailed(true)}
        />
      ))}
    </div>
  );
}
