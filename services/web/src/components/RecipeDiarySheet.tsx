import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorMessage } from "../api/client";
import type { Recipe } from "../api/types";
import { decimal, round } from "../lib/format";
import { tr } from "../lib/i18n";
import { useInvalidate } from "../lib/queries";
import { RECIPE_KEYS, portionsWord } from "../lib/recipes";
import { haptic } from "../lib/telegram";

type Mode = "portions" | "grams";

const itemStep = (g: number) => (g >= 100 ? 50 : 10);

export function RecipeDiarySheet({ recipe, onClose, onDone }: { recipe: Recipe; onClose: () => void; onDone: () => void }) {
  const [mode, setMode] = useState<Mode>("portions");
  const [portions, setPortions] = useState(1);
  const [grams, setGrams] = useState<number | null>(null);
  const [cooked, setCooked] = useState<number | null>(null);
  const [items, setItems] = useState(recipe.items.map((i) => ({ grams: i.grams, on: true })));
  const invalidate = useInvalidate();

  const raw = items.reduce((s, i) => s + (i.on ? i.grams : 0), 0);
  const cookedDefault =
    recipe.cooked_grams && recipe.raw_grams ? (recipe.cooked_grams * raw) / recipe.raw_grams : raw;
  const cookedValue = Math.max(1, Math.round(cooked ?? cookedDefault));
  const gramsValue = grams ?? Math.max(10, Math.round(cookedValue / recipe.portions / 10) * 10);
  const share = mode === "portions" ? portions / recipe.portions : gramsValue / cookedValue;
  const total = recipe.items.reduce(
    (t, item, n) => {
      const it = items[n];
      if (!it.on || item.grams <= 0) return t;
      const k = (it.grams / item.grams) * share;
      return {
        kcal: t.kcal + item.kcal * k,
        protein: t.protein + item.protein * k,
        fat: t.fat + item.fat * k,
        carbs: t.carbs + item.carbs * k,
      };
    },
    { kcal: 0, protein: 0, fat: 0, carbs: 0 },
  );

  const save = useMutation({
    mutationFn: () =>
      api.recipeToDiary(recipe.id, {
        mode,
        items: items.map((i) => (i.on ? i.grams : 0)),
        ...(mode === "portions" ? { portions } : { grams: gramsValue, cooked_grams: cookedValue }),
      }),
    onSuccess: async () => {
      haptic("success");
      await invalidate("day", "meal-history", "stats", ...RECIPE_KEYS);
      onDone();
    },
    onError: () => haptic("error"),
  });

  const setItem = (n: number, patch: Partial<{ grams: number; on: boolean }>) =>
    setItems(items.map((it, i) => (i === n ? { ...it, ...patch } : it)));
  const anyOn = items.some((i) => i.on);

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" role="dialog" aria-label={tr("Сколько добавить?", "How much to log?")} onClick={(e) => e.stopPropagation()}>
        <div className="sheet-head">
          <div>
            <h2>{tr("Сколько добавить?", "How much to log?")}</h2>
            <p className="muted small">{recipe.title}</p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label={tr("Закрыть", "Close")}>
            ×
          </button>
        </div>
        <div className="sheet-body stack">
          <div className="segmented" role="tablist">
            <button role="tab" aria-selected={mode === "portions"} onClick={() => setMode("portions")}>
              {tr("Порциями", "Servings")}
            </button>
            <button role="tab" aria-selected={mode === "grams"} onClick={() => setMode("grams")}>
              {tr("В граммах", "Grams")}
            </button>
          </div>

          {mode === "portions" ? (
            <div className="big-stepper">
              <button aria-label={tr("Меньше", "Less")} onClick={() => setPortions(Math.max(0.5, portions - 0.5))}>
                −
              </button>
              <span>
                <b>{decimal(portions, portions % 1 ? 1 : 0)}</b>
                <span className="muted small">
                  {tr("из", "of")} {recipe.portions} {portionsWord(recipe.portions)}
                </span>
              </span>
              <button aria-label={tr("Больше", "More")} onClick={() => setPortions(Math.min(50, portions + 0.5))}>
                +
              </button>
            </div>
          ) : (
            <>
              <div className="big-stepper">
                <button aria-label={tr("Меньше", "Less")} onClick={() => setGrams(Math.max(10, gramsValue - 10))}>
                  −
                </button>
                <span>
                  <b>
                    {round(gramsValue)} {tr("г", "g")}
                  </b>
                  <span className="muted small">{tr("готового блюда", "of the cooked dish")}</span>
                </span>
                <button aria-label={tr("Больше", "More")} onClick={() => setGrams(gramsValue + 10)}>
                  +
                </button>
              </div>
              <div className="cooked-row">
                <span>
                  {tr("Вес готового блюда", "Cooked weight")}
                  <span className="muted small">
                    {tr("по сырым продуктам", "raw ingredients")} {round(raw)} {tr("г", "g")}
                  </span>
                </span>
                <span className="mini-stepper">
                  <button aria-label={tr("Меньше", "Less")} onClick={() => setCooked(Math.max(10, cookedValue - 50))}>
                    −
                  </button>
                  <b>
                    {round(cookedValue)} {tr("г", "g")}
                  </b>
                  <button aria-label={tr("Больше", "More")} onClick={() => setCooked(cookedValue + 50)}>
                    +
                  </button>
                </span>
              </div>
            </>
          )}

          <p className="muted small">{tr("Состав в этот раз, на всё блюдо", "Ingredients this time, whole dish")}</p>
          <div className="diary-items">
            {recipe.items.map((item, n) => (
              <div key={n} className={items[n].on ? "diary-item" : "diary-item off"}>
                <button
                  className="check"
                  aria-pressed={items[n].on}
                  aria-label={items[n].on ? tr("Убрать", "Remove") : tr("Вернуть", "Bring back")}
                  onClick={() => setItem(n, { on: !items[n].on })}
                >
                  {items[n].on ? "✓" : ""}
                </button>
                <span className="diary-item-name">{item.name}</span>
                <span className="mini-stepper">
                  <button
                    aria-label={tr("Меньше", "Less")}
                    onClick={() => setItem(n, { grams: Math.max(5, items[n].grams - itemStep(items[n].grams - 1)) })}
                  >
                    −
                  </button>
                  <b>
                    {round(items[n].grams)} {tr("г", "g")}
                  </b>
                  <button
                    aria-label={tr("Больше", "More")}
                    onClick={() => setItem(n, { grams: items[n].grams + itemStep(items[n].grams) })}
                  >
                    +
                  </button>
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="diary-total">
          <span>
            <b>{round(total.kcal)}</b> {tr("ккал", "kcal")}
          </span>
          <span className="small">
            {tr("Б", "P")} {round(total.protein)} · {tr("Ж", "F")} {round(total.fat)} · {tr("У", "C")} {round(total.carbs)}
          </span>
        </div>
        {save.isError && <p className="error">{errorMessage(save.error)}</p>}
        <button className="btn btn-accent btn-cta" disabled={!anyOn || save.isPending} onClick={() => save.mutate()}>
          {tr("Добавить в дневник", "Add to diary")}
        </button>
        <p className="muted small center">
          {tr(
            "Запишется отдельным приёмом: правки рецепта потом не изменят этот день",
            "Logged as its own meal: later recipe edits won't change this day",
          )}
        </p>
      </div>
    </div>
  );
}
