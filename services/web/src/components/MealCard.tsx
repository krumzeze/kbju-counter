import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Meal } from "../api/types";
import { round } from "../lib/format";
import { locale, tr } from "../lib/i18n";
import { useInvalidate } from "../lib/queries";
import { Art } from "./Art";
import { Icon } from "./Icon";

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
  const time = new Date(meal.created_at).toLocaleTimeString(locale(), {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <details className="card meal" open={defaultOpen}>
      <summary>
        <span className="meal-icon" aria-hidden>
          <Art
            name={meal.source === "photo" ? "meal-photo" : "meal-text"}
            fallback={meal.source === "photo" ? "🥗" : "🍳"}
          />
        </span>
        <span className="meal-title">
          <strong>{meal.title}</strong>
          <span>
            <span className="meal-kcal">
              {round(meal.totals.kcal)} {tr("ккал", "kcal")}
            </span>
            <span className="muted">
              {" "}
              · {time} · {tr("Б", "P")} {round(meal.totals.protein)} · {tr("Ж", "F")}{" "}
              {round(meal.totals.fat)} · {tr("У", "C")} {round(meal.totals.carbs)}
            </span>
          </span>
        </span>
        <span className="meal-chevron">
          <Icon name="chevron" />
        </span>
      </summary>

      <ul className="meal-items">
        {meal.items.map((item) => (
          <li key={item.id}>
            <span>{item.name}</span>
            <span className="muted">
              {round(item.grams * meal.scale)} {tr("г", "g")} · {round(item.kcal * meal.scale)}{" "}
              {tr("ккал", "kcal")}
            </span>
          </li>
        ))}
      </ul>

      <div className="meal-actions">
        <div className="stepper" role="group" aria-label={tr("Размер порции", "Portion size")}>
          <button
            disabled={busy || meal.scale <= STEP}
            onClick={() => scale.mutate(meal.scale - STEP)}
            aria-label={tr("Уменьшить порцию", "Smaller portion")}
          >
            −
          </button>
          <span>×{meal.scale.toFixed(2)}</span>
          <button
            disabled={busy || meal.scale >= 5}
            onClick={() => scale.mutate(meal.scale + STEP)}
            aria-label={tr("Увеличить порцию", "Larger portion")}
          >
            +
          </button>
        </div>
        <button className="btn-ghost danger" disabled={busy} onClick={() => remove.mutate()}>
          {tr("Удалить", "Delete")}
        </button>
      </div>
    </details>
  );
}
