import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { Meal, MealHistoryItem } from "../api/types";
import { round } from "../lib/format";
import { tr } from "../lib/i18n";
import { useInvalidate, useMealHistory } from "../lib/queries";
import { haptic } from "../lib/telegram";
import { Icon } from "./Icon";
import { MealIcon } from "./MealCard";
import { type Sort, SortChips } from "./SortChips";
import { Spinner } from "./States";

const MEAL_KEYS = ["day", "meal-history"];

const fields = () =>
  [
    { key: "kcal", label: tr("Ккал", "Kcal"), max: 900 },
    { key: "protein", label: tr("Белки, г", "Protein, g"), max: 100 },
    { key: "fat", label: tr("Жиры, г", "Fat, g"), max: 100 },
    { key: "carbs", label: tr("Углеводы, г", "Carbs, g"), max: 100 },
  ] as const;

type Per100 = Record<"kcal" | "protein" | "fat" | "carbs", string>;

const num = (v: string) => Number(v.replace(",", "."));
const clean = (v: string) => v.replace(/[^\d.,]/g, "");

export function ManualMeal({ onDone }: { onDone: (meal: Meal) => void }) {
  const [title, setTitle] = useState("");
  const [grams, setGrams] = useState("");
  const [per100, setPer100] = useState<Per100>({ kcal: "", protein: "", fat: "", carbs: "" });
  const invalidate = useInvalidate();
  const save = useMutation({
    mutationFn: () =>
      api.mealManual({
        title: title.trim(),
        grams: num(grams),
        kcal: num(per100.kcal),
        protein: num(per100.protein || "0"),
        fat: num(per100.fat || "0"),
        carbs: num(per100.carbs || "0"),
      }),
    onSuccess: async (meal) => {
      haptic("success");
      onDone(meal);
      await invalidate(...MEAL_KEYS);
    },
  });

  const g = num(grams);
  const valid =
    title.trim().length > 0 &&
    g >= 1 &&
    g <= 3000 &&
    per100.kcal !== "" &&
    fields().every((f) => {
      const v = num(per100[f.key] || "0");
      return Number.isFinite(v) && v >= 0 && v <= f.max;
    });
  const total = (key: keyof Per100) => (num(per100[key] || "0") * g) / 100;

  return (
    <form
      className="card form"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) save.mutate();
      }}
    >
      <label className="field">
        <span>{tr("Название", "Name")}</span>
        <input
          className="input"
          maxLength={255}
          placeholder={tr("Например: сырники мамины", "E.g. grandma's pancakes")}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>
      <label className="field">
        <span>{tr("Вес порции, г", "Portion weight, g")}</span>
        <input
          className="input"
          inputMode="decimal"
          placeholder="250"
          value={grams}
          onChange={(e) => setGrams(clean(e.target.value))}
        />
      </label>
      <div className="field">
        <span>{tr("На 100 г", "Per 100 g")}</span>
        <div className="fields-2">
          {fields().map((f) => (
            <label key={f.key} className="field">
              <span className="muted small">{f.label}</span>
              <input
                className="input"
                inputMode="decimal"
                placeholder="0"
                value={per100[f.key]}
                onChange={(e) => setPer100({ ...per100, [f.key]: clean(e.target.value) })}
              />
            </label>
          ))}
        </div>
      </div>
      {g > 0 && per100.kcal !== "" && (
        <p className="manual-total">
          {tr(`Итого на ${round(g)} г:`, `Total for ${round(g)} g:`)}{" "}
          <strong>
            {round(total("kcal"))} {tr("ккал", "kcal")}
          </strong>{" "}
          · {tr("Б", "P")} {round(total("protein"))} · {tr("Ж", "F")} {round(total("fat"))} ·{" "}
          {tr("У", "C")} {round(total("carbs"))}
        </p>
      )}
      {save.isError && <p className="error">{errorMessage(save.error)}</p>}
      <button className="btn btn-primary btn-block" disabled={!valid || save.isPending}>
        {tr("Добавить", "Add")}
      </button>
      <p className="muted small center">
        {tr(
          "Блюдо сохранится в истории, и в следующий раз его можно будет добавить в одно касание.",
          "The dish is saved to your history so next time you can add it in one tap.",
        )}
      </p>
    </form>
  );
}

export function MealHistory({ onDone }: { onDone: (meal: Meal) => void }) {
  const [sort, setSort] = useState<Sort>("frequent");
  const [query, setQuery] = useState("");
  const { data, isPending, error, refetch } = useMealHistory(sort);
  const invalidate = useInvalidate();
  const repeat = useMutation({
    mutationFn: (id: number) => api.repeatMeal(id),
    onSuccess: async (meal) => {
      haptic("success");
      onDone(meal);
      await invalidate(...MEAL_KEYS);
    },
  });
  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data ?? []).filter((m) => !q || m.title.toLowerCase().includes(q));
  }, [data, query]);

  if (isPending) return <Spinner />;
  if (error) {
    return (
      <div className="empty">
        <p>{errorMessage(error)}</p>
        <button className="btn" onClick={() => refetch()}>
          {tr("Повторить", "Retry")}
        </button>
      </div>
    );
  }
  if (!data.length) {
    return (
      <div className="empty">
        <p>
          {tr(
            "Здесь появится всё, что ты добавлял: фото, текст и свои блюда.",
            "Everything you log shows up here: photos, text and your own dishes.",
          )}
        </p>
      </div>
    );
  }

  return (
    <>
      <input
        className="input"
        type="search"
        placeholder={tr("Поиск по истории", "Search history")}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <SortChips value={sort} onChange={setSort} />
      {repeat.isError && <p className="error">{errorMessage(repeat.error)}</p>}
      {items.length === 0 ? (
        <p className="empty">{tr("Ничего не нашлось.", "Nothing found.")}</p>
      ) : (
        <ul className="history-meals">
          {items.map((m) => (
            <HistoryRow
              key={m.meal_id}
              meal={m}
              busy={repeat.isPending}
              onAdd={() => repeat.mutate(m.meal_id)}
            />
          ))}
        </ul>
      )}
    </>
  );
}

function HistoryRow({ meal, busy, onAdd }: { meal: MealHistoryItem; busy: boolean; onAdd: () => void }) {
  return (
    <li className="history-meal">
      <span className="meal-icon" aria-hidden>
        <MealIcon source={meal.source} />
      </span>
      <span className="meal-title">
        <strong>{meal.title}</strong>
        <span>
          {meal.times > 1 && <span className="times">×{meal.times} · </span>}
          <span className="meal-kcal">
            {round(meal.totals.kcal)} {tr("ккал", "kcal")}
          </span>
          <span className="muted">
            {" "}
            · {tr("Б", "P")} {round(meal.totals.protein)} · {tr("Ж", "F")} {round(meal.totals.fat)} ·{" "}
            {tr("У", "C")} {round(meal.totals.carbs)}
          </span>
        </span>
      </span>
      <button
        className="history-add"
        disabled={busy}
        onClick={onAdd}
        aria-label={tr(`Добавить: ${meal.title}`, `Add: ${meal.title}`)}
      >
        <Icon name="plus" size={22} />
      </button>
    </li>
  );
}
