import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Exercise, Template } from "../api/types";
import { ExercisePicker } from "../components/ExercisePicker";
import { ExerciseThumb } from "../components/ExerciseThumb";
import { ErrorState, Spinner } from "../components/States";
import { tr } from "../lib/i18n";
import { useInvalidate, useTemplates } from "../lib/queries";
import { confirmAction } from "../lib/telegram";

export function TemplateEdit() {
  const param = useParams().id;
  const templates = useTemplates();
  if (param === undefined) return <Editor />;
  if (templates.isPending) return <Spinner />;
  if (templates.error) return <ErrorState message={errorMessage(templates.error)} />;
  const template = templates.data.find((t) => t.id === Number(param));
  if (!template) return <ErrorState message={tr("Программа не найдена", "Routine not found")} />;
  return <Editor template={template} />;
}

interface Item {
  exercise: Exercise;
  sets: number;
}

function Editor({ template }: { template?: Template }) {
  const [name, setName] = useState(template?.name ?? "");
  const [items, setItems] = useState<Item[]>(template?.items ?? []);
  const [picking, setPicking] = useState(false);
  const navigate = useNavigate();
  const invalidate = useInvalidate();

  const resolve = useMutation({
    mutationFn: api.resolveExercise,
    onSuccess: (exercise) => {
      setPicking(false);
      if (!items.some((i) => i.exercise.id === exercise.id)) setItems([...items, { exercise, sets: 3 }]);
    },
  });

  const save = useMutation({
    mutationFn: () => {
      const body = {
        name: name.trim(),
        items: items.map((i) => ({ exercise_id: i.exercise.id, sets: i.sets })),
      };
      return template ? api.updateTemplate(template.id, body) : api.createTemplate(body);
    },
    onSuccess: async () => {
      await invalidate("templates");
      navigate("/workouts");
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteTemplate(template!.id),
    onSuccess: async () => {
      await invalidate("templates");
      navigate("/workouts");
    },
  });

  const move = (from: number, to: number) => {
    if (to < 0 || to >= items.length) return;
    const next = [...items];
    [next[from], next[to]] = [next[to], next[from]];
    setItems(next);
  };

  return (
    <div className="page">
      <h1>{template ? tr("Программа", "Routine") : tr("Новая программа", "New routine")}</h1>
      <label className="field">
        <span>{tr("Название", "Name")}</span>
        <input
          className="input"
          maxLength={64}
          placeholder={tr("Например, Грудь и трицепс", "e.g. Chest and triceps")}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>

      {items.length > 0 && (
        <ul className="card template-items">
          {items.map((item, i) => (
            <li key={item.exercise.id}>
              <ExerciseThumb catalogId={item.exercise.catalog_id} group={item.exercise.group} />
              <span className="capitalize template-item-name">{item.exercise.name}</span>
              <div className="stepper" aria-label={tr("Подходов", "Sets")}>
                <button
                  type="button"
                  onClick={() => setItems(items.map((x, j) => (j === i ? { ...x, sets: Math.max(1, x.sets - 1) } : x)))}
                  aria-label={tr("Меньше подходов", "Fewer sets")}
                >
                  −
                </button>
                <span>
                  {item.sets} {tr("подх.", "sets")}
                </span>
                <button
                  type="button"
                  onClick={() => setItems(items.map((x, j) => (j === i ? { ...x, sets: Math.min(20, x.sets + 1) } : x)))}
                  aria-label={tr("Больше подходов", "More sets")}
                >
                  +
                </button>
              </div>
              <div className="reorder">
                <button className="icon-btn" disabled={i === 0} onClick={() => move(i, i - 1)} aria-label={tr("Выше", "Up")}>
                  ↑
                </button>
                <button
                  className="icon-btn"
                  onClick={() => setItems(items.filter((_, j) => j !== i))}
                  aria-label={tr("Убрать", "Remove")}
                >
                  ×
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <button className="btn btn-block dashed" onClick={() => setPicking(true)} disabled={items.length >= 30}>
        ＋ {tr("Добавить упражнение", "Add exercise")}
      </button>
      {resolve.isError && <p className="error">{errorMessage(resolve.error)}</p>}
      {save.isError && <p className="error">{errorMessage(save.error)}</p>}

      <button
        className="btn btn-primary btn-block"
        disabled={!name.trim() || !items.length || save.isPending}
        onClick={() => save.mutate()}
      >
        {tr("Сохранить", "Save")}
      </button>
      {template && (
        <button
          className="btn-ghost danger"
          disabled={remove.isPending}
          onClick={async () => {
            if (await confirmAction(tr(`Удалить «${template.name}»?`, `Delete "${template.name}"?`))) remove.mutate();
          }}
        >
          {tr("Удалить программу", "Delete routine")}
        </button>
      )}

      {picking && (
        <ExercisePicker
          title={tr("Добавить упражнение", "Add exercise")}
          onPick={(ref) => resolve.mutate(ref)}
          onClose={() => setPicking(false)}
        />
      )}
    </div>
  );
}
