import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorMessage } from "../api/client";
import type { Meal, MealItem } from "../api/types";
import { round } from "../lib/format";
import { locale, tr } from "../lib/i18n";
import { useInvalidate } from "../lib/queries";
import { confirmAction } from "../lib/telegram";
import { Art } from "./Art";
import { Icon } from "./Icon";

const STEP = 0.25;

interface Props {
  meal: Meal;
  defaultOpen?: boolean;
  onChange?: (meal: Meal) => void;
  onDelete?: () => void;
}

export function MealCard({ meal, defaultOpen = false, onChange, onDelete }: Props) {
  const invalidate = useInvalidate();
  const updated = async (m: Meal) => {
    onChange?.(m);
    await invalidate("day");
  };
  const scale = useMutation({
    mutationFn: (value: number) => api.scaleMeal(meal.id, value),
    onSuccess: updated,
  });
  const remove = useMutation({
    mutationFn: () => api.deleteMeal(meal.id),
    onSuccess: async () => {
      onDelete?.();
      await invalidate("day");
    },
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
          <MealIcon source={meal.source} />
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
          <ItemRow
            key={item.id}
            meal={meal}
            item={item}
            removable={meal.items.length > 1}
            onChange={updated}
          />
        ))}
      </ul>
      <p className="meal-hint">
        {tr("Нажми на граммы, чтобы поправить вес позиции", "Tap the grams to correct an item's weight")}
      </p>

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
        <button
          className="btn-ghost danger"
          disabled={busy}
          onClick={async () => {
            if (await confirmAction(tr("Удалить приём пищи?", "Delete this meal?"))) remove.mutate();
          }}
        >
          {tr("Удалить всё", "Delete all")}
        </button>
      </div>
    </details>
  );
}

function ItemRow({
  meal,
  item,
  removable,
  onChange,
}: {
  meal: Meal;
  item: MealItem;
  removable: boolean;
  onChange: (meal: Meal) => Promise<void>;
}) {
  const grams = Math.round(item.grams * meal.scale);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(grams));
  const resize = useMutation({
    mutationFn: (g: number) => api.resizeMealItem(meal.id, item.id, g),
    onSuccess: async (m) => {
      setEditing(false);
      await onChange(m);
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteMealItem(meal.id, item.id),
    onSuccess: onChange,
  });
  const error = resize.error ?? remove.error;

  if (editing) {
    const n = Number(value);
    const valid = Number.isFinite(n) && n >= 1 && n <= 3000;
    return (
      <li>
        <form
          className="item-edit"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid) resize.mutate(n);
          }}
        >
          <span className="item-name">{item.name}</span>
          <input
            className="input"
            inputMode="numeric"
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value.replace(/\D/g, ""))}
            aria-label={tr("Вес, г", "Weight, g")}
          />
          <span className="muted">{tr("г", "g")}</span>
          <button className="btn btn-primary small" disabled={!valid || resize.isPending}>
            OK
          </button>
        </form>
        {error && <p className="error small">{errorMessage(error)}</p>}
      </li>
    );
  }

  return (
    <li>
      <span className="item-name">{item.name}</span>
      <button
        className="item-grams"
        onClick={() => {
          setValue(String(grams));
          setEditing(true);
        }}
        aria-label={tr(`Изменить вес: ${item.name}`, `Edit weight: ${item.name}`)}
      >
        {grams} {tr("г", "g")}
      </button>
      <span className="muted item-kcal">
        {round(item.kcal * meal.scale)} {tr("ккал", "kcal")}
      </span>
      {removable && (
        <button
          className="item-remove"
          disabled={remove.isPending}
          onClick={() => remove.mutate()}
          aria-label={tr(`Убрать: ${item.name}`, `Remove: ${item.name}`)}
        >
          <Icon name="trash" size={18} />
        </button>
      )}
    </li>
  );
}

export function MealIcon({ source }: { source: Meal["source"] }) {
  return (
    <Art
      name={source === "photo" ? "meal-photo" : "meal-text"}
      fallback={source === "photo" ? "🥗" : "🍳"}
    />
  );
}
