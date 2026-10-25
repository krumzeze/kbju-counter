import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Meal } from "../api/types";
import { MealCard } from "../components/MealCard";
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
        <h1>Готово</h1>
        <p className="muted">Если порция на фото больше или меньше, поправь её кнопками.</p>
        <MealCard meal={meal} defaultOpen />
        <div className="row">
          <button className="btn" onClick={reset}>
            Добавить ещё
          </button>
          <Link className="btn btn-primary" to="/">
            К итогам дня
          </Link>
        </div>
      </div>
    );
  }

  const canSubmit = mode === "photo" ? photo !== null : text.trim().length >= 2;

  return (
    <div className="page">
      <h1>Что съел?</h1>
      <div className="segmented" role="tablist">
        <button role="tab" aria-selected={mode === "photo"} onClick={() => setMode("photo")}>
          📸 Фото
        </button>
        <button role="tab" aria-selected={mode === "text"} onClick={() => setMode("text")}>
          ✍️ Текстом
        </button>
      </div>

      {mode === "photo" ? (
        <>
          <button className="dropzone" onClick={() => fileInput.current?.click()}>
            {preview ? (
              <img src={preview} alt="Фото блюда" />
            ) : (
              <span>
                <strong>Сфотографируй тарелку</strong>
                <span className="muted">или выбери фото из галереи</span>
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
            placeholder="Подсказка, например: рис 150 г, без масла"
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
          placeholder="2 яйца, тост с маслом, кофе с молоком"
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
        {analyze.isPending ? "Считаю КБЖУ…" : "Посчитать"}
      </button>
    </div>
  );
}
