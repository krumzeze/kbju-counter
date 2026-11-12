import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Me, Meal } from "../api/types";
import { Icon } from "../components/Icon";
import { MealCard } from "../components/MealCard";
import { ManualMeal, MealHistory } from "../components/MealSources";
import { RecipeQuickList } from "../components/RecipeQuickList";
import { tr } from "../lib/i18n";
import { prepareImage } from "../lib/image";
import { useInvalidate } from "../lib/queries";
import { haptic } from "../lib/telegram";

type Mode = "photo" | "text" | "manual" | "history" | "recipes";

const modes = (features: Me["features"]): { value: Mode; label: string }[] =>
  [
    { value: "photo" as const, label: tr("Фото", "Photo"), on: features.photo },
    { value: "text" as const, label: tr("Текст", "Text"), on: features.text },
    { value: "manual" as const, label: tr("Вручную", "Manual"), on: true },
    { value: "history" as const, label: tr("История", "History"), on: true },
    { value: "recipes" as const, label: tr("Рецепты", "Recipes"), on: true },
  ].filter((m) => m.on);

export function AddMeal({ me }: { me: Me }) {
  const available = modes(me.features);
  const [chosen, setMode] = useState<Mode>(available[0].value);
  const mode = available.some((m) => m.value === chosen) ? chosen : available[0].value;
  const [photo, setPhoto] = useState<Blob | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [text, setText] = useState("");
  const [meal, setMeal] = useState<Meal | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const invalidate = useInvalidate();

  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview]);

  const analyze = useMutation({
    mutationFn: () => (mode === "photo" ? api.mealFromPhoto(photo!, note) : api.mealFromText(text)),
    onSuccess: async (result) => {
      haptic("success");
      setMeal(result);
      await invalidate("day", "meal-history", "me");
    },
    onError: () => {
      haptic("error");
      void invalidate("me");
    },
  });

  async function onFile(file: File | undefined) {
    if (!file) return;
    const blob = await prepareImage(file);
    setPhoto(blob);
    setPreview(URL.createObjectURL(blob));
    analyze.reset();
  }

  function reset() {
    setMeal(null);
    setPhoto(null);
    setPreview(null);
    setNote("");
    setText("");
    analyze.reset();
  }

  if (meal) {
    return (
      <div className="page">
        <div className="done-head">
          <div className="done-text">
            <h1>{tr("Готово", "Done")}</h1>
            <p className="muted">
              {tr(
                "Если порция больше или меньше, поправь граммы или размер порции.",
                "If the portion is bigger or smaller, adjust the grams or the portion size.",
              )}
            </p>
          </div>
        </div>
        <MealCard meal={meal} defaultOpen onChange={setMeal} onDelete={reset} />
        <div className="row">
          <button className="btn" onClick={reset}>
            {tr("Добавить ещё", "Add another")}
          </button>
          <Link className="btn btn-primary" to="/">
            {tr("К итогам дня", "Back to today")}
          </Link>
        </div>
      </div>
    );
  }

  const canSubmit = mode === "photo" ? photo !== null : text.trim().length >= 2;

  return (
    <div className="page">
      <h1>{tr("Что съел?", "What did you eat?")}</h1>
      <div className={available.length > 4 ? "segmented compact" : "segmented"} role="tablist">
        {available.map((m) => (
          <button key={m.value} role="tab" aria-selected={mode === m.value} onClick={() => setMode(m.value)}>
            {m.label}
          </button>
        ))}
      </div>

      {mode === "manual" ? (
        <ManualMeal onDone={setMeal} barcode={me.features.barcode} />
      ) : mode === "history" ? (
        <MealHistory onDone={setMeal} />
      ) : mode === "recipes" ? (
        <RecipeQuickList />
      ) : mode === "photo" ? (
        <>
          <button className="dropzone" onClick={() => fileInput.current?.click()}>
            {preview ? (
              <img src={preview} alt={tr("Фото блюда", "Meal photo")} />
            ) : (
              <span className="dropzone-empty">
                <span className="dropzone-icon">
                  <Icon name="camera" size={30} />
                </span>
                <span className="dropzone-text">
                  <strong>{tr("Сфотографируй тарелку", "Take a photo of your plate")}</strong>
                  <span className="muted">{tr("или выбери фото из галереи", "or pick one from your gallery")}</span>
                </span>
              </span>
            )}
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(e) => onFile(e.target.files?.[0])}
          />
          <input
            className="input"
            placeholder={tr("Подсказка, например: рис 150 г, без масла", "Hint, e.g. rice 150 g, no oil")}
            maxLength={200}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </>
      ) : (
        <textarea
          className="input"
          rows={4}
          maxLength={500}
          placeholder={tr("2 яйца, тост с маслом, кофе с молоком", "2 eggs, buttered toast, coffee with milk")}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      )}
      {mode === "text" && me.features.voice && (
        <p className="muted small">
          {tr(
            "Можно и голосом: отправь боту голосовое сообщение, и он сам всё запишет.",
            "You can also use your voice: send the bot a voice message and it'll log it for you.",
          )}
        </p>
      )}

      {(mode === "photo" || mode === "text") && (
        <>
          {analyze.isError && <p className="error">{errorMessage(analyze.error)}</p>}
          {!me.has_access && me.analyses_left > 0 && (
            <p className="muted small center">
              {tr(
                `Бесплатных распознаваний сегодня: ${me.analyses_left}`,
                `Free recognitions left today: ${me.analyses_left}`,
              )}
            </p>
          )}
          {!me.has_access && me.analyses_left === 0 ? (
            <Link to="/premium" className="btn btn-primary btn-block">
              {tr("Больше распознаваний в Premium", "More recognitions with Premium")}
            </Link>
          ) : (
            <button
              className="btn btn-primary btn-block"
              disabled={!canSubmit || analyze.isPending}
              onClick={() => analyze.mutate()}
            >
              {analyze.isPending ? tr("Считаю КБЖУ…", "Counting…") : tr("Посчитать", "Analyze")}
            </button>
          )}
        </>
      )}
    </div>
  );
}
