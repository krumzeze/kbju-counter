import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Meal } from "../api/types";
import { round } from "../lib/format";
import { useInvalidate } from "../lib/queries";

const STEP = 0.25;

export function MealCard({ meal, defaultOpen = false }: { meal: Meal; defaultOpen?: boolean }) {
  const invalidate = useInvalidate();
  const scale = useMutation({
    mutationFn: (value: number) => api.scaleMeal(meal.id, value),
    onSuccess: () => invalidate("day"),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteMeal(meal.id),
    onSuccess: () => invalidate("day"),
  });
  const busy = scale.isPending || remove.isPending;
  const time = new Date(meal.created_at).toLocaleTimeString("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <details className="card meal" open={defaultOpen}>
      <summary>
        <div className="meal-title">
          <span className="meal-icon" aria-hidden>
            {meal.source === "photo" ? "📸" : "✍️"}
          </span>
          <div>
            <strong>{meal.title}</strong>
            <span className="muted">
              {time} · Б {round(meal.totals.protein)} · Ж {round(meal.totals.fat)} · У{" "}
              {round(meal.totals.carbs)}
            </span>
          </div>
        </div>
        <span className="meal-kcal">{round(meal.totals.kcal)}</span>
      </summary>

      <ul className="meal-items">
        {meal.items.map((item) => (
          <li key={item.id}>
            <span>{item.name}</span>
            <span className="muted">
              {round(item.grams * meal.scale)} г · {round(item.kcal * meal.scale)} ккал
            </span>
          </li>
        ))}
      </ul>

      <div className="meal-actions">
        <div className="stepper" role="group" aria-label="Размер порции">
          <button
            disabled={busy || meal.scale <= STEP}
            onClick={() => scale.mutate(meal.scale - STEP)}
            aria-label="Уменьшить порцию"
          >
            −
          </button>
          <span>×{meal.scale.toFixed(2)}</span>
          <button
            disabled={busy || meal.scale >= 5}
            onClick={() => scale.mutate(meal.scale + STEP)}
            aria-label="Увеличить порцию"
          >
            +
          </button>
        </div>
        <button className="btn-ghost danger" disabled={busy} onClick={() => remove.mutate()}>
          Удалить
        </button>
      </div>
    </details>
  );
}
