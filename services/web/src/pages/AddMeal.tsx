import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Meal } from "../api/types";
import { Art } from "../components/Art";
import { Icon } from "../components/Icon";
import { MealCard } from "../components/MealCard";
import { tr } from "../lib/i18n";
import { prepareImage } from "../lib/image";
import { useInvalidate } from "../lib/queries";
import { haptic } from "../lib/telegram";

type Mode = "photo" | "text";

export function AddMeal() {
  const [mode, setMode] = useState<Mode>("photo");
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
      await invalidate("day");
    },
    onError: () => haptic("error"),
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
          <Art name="meal-done" />
          <div className="done-text">
            <h1>{tr("Готово", "Done")}</h1>
            <p className="muted">
              {tr(
                "Если порция больше или меньше, поправь её кнопками.",
                "If the portion is bigger or smaller, adjust it with the buttons.",
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
      <div className="segmented" role="tablist">
        <button role="tab" aria-selected={mode === "photo"} onClick={() => setMode("photo")}>
          <Icon name="camera" size={18} />
          {tr("Фото", "Photo")}
        </button>
        <button role="tab" aria-selected={mode === "text"} onClick={() => setMode("text")}>
          <Icon name="pen" size={18} />
          {tr("Текстом", "Text")}
        </button>
      </div>

      {mode === "photo" ? (
        <>
          <button className="dropzone" onClick={() => fileInput.current?.click()}>
            {preview ? (
              <img src={preview} alt={tr("Фото блюда", "Meal photo")} />
            ) : (
              <span className="dropzone-empty">
                <span className="dropzone-text">
                  <strong>{tr("Сфотографируй тарелку", "Take a photo of your plate")}</strong>
                  <span className="muted">{tr("или выбери фото из галереи", "or pick one from your gallery")}</span>
                </span>
                <Art
                  name="add-photo"
                  className="art add-art"
                  fallback={
                    <span className="dropzone-icon">
                      <Icon name="camera" size={32} />
                    </span>
                  }
                />
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

      {analyze.isError && <p className="error">{errorMessage(analyze.error)}</p>}

      <button
        className="btn btn-primary btn-block"
        disabled={!canSubmit || analyze.isPending}
        onClick={() => analyze.mutate()}
      >
        {analyze.isPending ? tr("Считаю КБЖУ…", "Counting…") : tr("Посчитать", "Analyze")}
      </button>
    </div>
  );
}
