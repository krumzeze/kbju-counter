import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { CalorieRing } from "../components/CalorieRing";
import { MacroBars } from "../components/MacroBars";
import { MealCard } from "../components/MealCard";
import { ErrorState, Spinner } from "../components/States";
import { dayLabel, round, shiftDay, todayIso } from "../lib/format";
import { useDay, useInvalidate } from "../lib/queries";

export function Today() {
  const [day, setDay] = useState(todayIso());
  const { data, isPending, error, refetch } = useDay(day);
  const isToday = day === todayIso();

  return (
    <div className="page">
      <div className="day-switch">
        <button className="icon-btn" onClick={() => setDay(shiftDay(day, -1))} aria-label="Предыдущий день">
          ‹
        </button>
        <h1>{dayLabel(day)}</h1>
        <button
          className="icon-btn"
          onClick={() => setDay(shiftDay(day, 1))}
          disabled={isToday}
          aria-label="Следующий день"
        >
          ›
        </button>
      </div>

      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : (
        <>
          <section className="card summary">
            <CalorieRing eaten={data.eaten.kcal} target={data.target?.kcal ?? null} />
            <MacroBars eaten={data.eaten} target={data.target} />
          </section>

          {isToday && (
            <Link to="/add" className="btn btn-primary btn-block">
              ＋ Добавить еду
            </Link>
          )}

          <section className="stats-row">
            <StepsCard steps={data.steps} kcal={data.steps_kcal} editable={isToday} />
            <Link to="/workouts" className="card stat">
              <span className="muted">Подходов</span>
              <strong>{data.sets.length}</strong>
              <span className="muted small">
                {data.sets.length ? "в зале сегодня" : "записать тренировку"}
              </span>
            </Link>
          </section>

          <section>
            <h2>Приёмы пищи</h2>
            {data.meals.length === 0 ? (
              <p className="empty">
                Пока пусто. Сфотографируй тарелку или опиши, что съел, а я посчитаю КБЖУ.
              </p>
            ) : (
              <div className="stack">
                {[...data.meals].reverse().map((meal) => (
                  <MealCard key={meal.id} meal={meal} />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function StepsCard({ steps, kcal, editable }: { steps: number; kcal: number; editable: boolean }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(steps || ""));
  const invalidate = useInvalidate();
  const save = useMutation({
    mutationFn: (n: number) => api.saveSteps(n),
    onSuccess: async () => {
      await invalidate("day");
      setEditing(false);
    },
  });

  if (editing) {
    return (
      <form
        className="card stat"
        onSubmit={(e) => {
          e.preventDefault();
          const n = Number(value);
          if (Number.isInteger(n) && n >= 0 && n <= 100000) save.mutate(n);
        }}
      >
        <span className="muted">Шаги за день</span>
        <input
          className="input"
          inputMode="numeric"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value.replace(/\D/g, ""))}
        />
        <button className="btn btn-primary small" disabled={save.isPending}>
          Сохранить
        </button>
      </form>
    );
  }

  return (
    <button className="card stat" onClick={() => editable && setEditing(true)} disabled={!editable}>
      <span className="muted">Шаги</span>
      <strong>{round(steps)}</strong>
      <span className="muted small">{kcal > 0 ? `+${round(kcal)} ккал к норме` : "нажми, чтобы ввести"}</span>
    </button>
  );
}
