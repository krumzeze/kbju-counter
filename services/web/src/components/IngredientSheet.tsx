import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorMessage } from "../api/client";
import type { Barcode, Me, RecipeItem } from "../api/types";
import { round } from "../lib/format";
import { tr } from "../lib/i18n";
import { haptic } from "../lib/telegram";
import { BarcodeScan } from "./MealSources";

type Mode = "text" | "barcode" | "manual";
type Per100 = Record<"kcal" | "protein" | "fat" | "carbs", string>;

const num = (v: string) => Number(v.replace(",", "."));
const clean = (v: string) => v.replace(/[^\d.,]/g, "");
const EMPTY: Per100 = { kcal: "", protein: "", fat: "", carbs: "" };

export function IngredientSheet({
  features,
  onAdd,
  onClose,
}: {
  features: Me["features"];
  onAdd: (items: RecipeItem[]) => void;
  onClose: () => void;
}) {
  const modes = [
    features.text && { value: "text" as const, label: tr("Текстом", "Text") },
    features.barcode && { value: "barcode" as const, label: tr("Штрихкод", "Barcode") },
    { value: "manual" as const, label: tr("Вручную", "Manual") },
  ].filter(Boolean) as { value: Mode; label: string }[];
  const [mode, setMode] = useState<Mode>(modes[0].value);

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" role="dialog" aria-label={tr("Добавить продукты", "Add ingredients")} onClick={(e) => e.stopPropagation()}>
        <div className="sheet-head">
          <h2>{tr("Добавить продукты", "Add ingredients")}</h2>
          <button className="icon-btn" onClick={onClose} aria-label={tr("Закрыть", "Close")}>
            ×
          </button>
        </div>
        <div className="segmented" role="tablist">
          {modes.map((m) => (
            <button key={m.value} role="tab" aria-selected={mode === m.value} onClick={() => setMode(m.value)}>
              {m.label}
            </button>
          ))}
        </div>
        <div className="sheet-body stack">
          {mode === "text" ? <FromText onAdd={onAdd} /> : <PerHundred scan={mode === "barcode"} onAdd={onAdd} key={mode} />}
        </div>
      </div>
    </div>
  );
}

function FromText({ onAdd }: { onAdd: (items: RecipeItem[]) => void }) {
  const [text, setText] = useState("");
  const parse = useMutation({
    mutationFn: () => api.parseIngredients(text),
    onSuccess: () => haptic("success"),
    onError: () => haptic("error"),
  });
  const items = parse.data;

  return (
    <>
      <label className="field">
        <span className="muted small">
          {tr(
            "Перечисли продукты и граммы в сыром виде, через запятую или с новой строки.",
            "List ingredients with raw weights, comma or line separated.",
          )}
        </span>
        <textarea
          className="input textarea"
          rows={4}
          maxLength={2000}
          value={text}
          placeholder={tr("куриное филе 600 г, булгур 200 г, кабачок 300 г", "chicken breast 600 g, bulgur 200 g")}
          onChange={(e) => setText(e.target.value)}
        />
      </label>
      {!items && (
        <button className="btn btn-primary btn-block" disabled={text.trim().length < 2 || parse.isPending} onClick={() => parse.mutate()}>
          {parse.isPending ? tr("Считаю…", "Calculating…") : tr("Посчитать КБЖУ", "Calculate macros")}
        </button>
      )}
      {parse.isError && <p className="error">{errorMessage(parse.error)}</p>}
      {items && (
        <>
          <ul className="ingredient-list">
            {items.map((i, n) => (
              <li key={n}>
                <span>
                  {i.name}
                  <span className="muted small block">
                    {round(i.kcal)} {tr("ккал", "kcal")} · {tr("Б", "P")} {round(i.protein)} · {tr("Ж", "F")} {round(i.fat)} ·{" "}
                    {tr("У", "C")} {round(i.carbs)}
                  </span>
                </span>
                <span className="muted">
                  {round(i.grams)} {tr("г", "g")}
                </span>
              </li>
            ))}
          </ul>
          <div className="sheet-actions">
            <button className="btn" onClick={() => parse.reset()}>
              {tr("Исправить", "Edit")}
            </button>
            <button className="btn btn-primary" onClick={() => onAdd(items)}>
              {tr("Добавить", "Add")} {items.length}
            </button>
          </div>
        </>
      )}
    </>
  );
}

function PerHundred({ scan, onAdd }: { scan: boolean; onAdd: (items: RecipeItem[]) => void }) {
  const [name, setName] = useState("");
  const [grams, setGrams] = useState("");
  const [per100, setPer100] = useState<Per100>(EMPTY);

  function fill(result: Barcode) {
    const p = result.product;
    if (!p) return;
    const fmt = (v: number) => String(Math.round(v * 10) / 10);
    setName(p.name);
    setPer100({ kcal: fmt(p.kcal), protein: fmt(p.protein), fat: fmt(p.fat), carbs: fmt(p.carbs) });
  }

  const g = num(grams);
  const value = (k: keyof Per100) => num(per100[k] || "0");
  const valid =
    name.trim().length > 0 &&
    g > 0 &&
    g <= 10000 &&
    per100.kcal !== "" &&
    value("kcal") <= 900 &&
    (["protein", "fat", "carbs"] as const).every((k) => value(k) >= 0 && value(k) <= 100);
  const item = (): RecipeItem => ({
    name: name.trim(),
    grams: g,
    kcal: (value("kcal") * g) / 100,
    protein: (value("protein") * g) / 100,
    fat: (value("fat") * g) / 100,
    carbs: (value("carbs") * g) / 100,
  });
  const fields = [
    { key: "kcal" as const, label: tr("Ккал", "Kcal") },
    { key: "protein" as const, label: tr("Белки, г", "Protein, g") },
    { key: "fat" as const, label: tr("Жиры, г", "Fat, g") },
    { key: "carbs" as const, label: tr("Углеводы, г", "Carbs, g") },
  ];

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onAdd([item()]);
      }}
    >
      {scan && <BarcodeScan onResult={fill} />}
      <label className="field">
        <span>{tr("Продукт", "Ingredient")}</span>
        <input className="input" maxLength={255} value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="field">
        <span>{tr("Вес в сыром виде, г", "Raw weight, g")}</span>
        <input className="input" inputMode="decimal" value={grams} onChange={(e) => setGrams(clean(e.target.value))} />
      </label>
      <div className="field">
        <span>{tr("На 100 г", "Per 100 g")}</span>
        <div className="fields-2">
          {fields.map((f) => (
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
      <button className="btn btn-primary btn-block" disabled={!valid}>
        {tr("Добавить", "Add")}
      </button>
    </form>
  );
}
