import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { adminApi, errorMessage } from "../../api/client";
import type { AdminRecipe, RecipeStatus } from "../../api/types";
import { ErrorState, Spinner } from "../../components/States";
import { round } from "../../lib/format";
import { useAdminMutation } from "../../lib/adminQueries";

const TABS: { value: RecipeStatus; label: string }[] = [
  { value: "pending", label: "На проверке" },
  { value: "public", label: "В каталоге" },
  { value: "rejected", label: "Отклонённые" },
];

const REASONS = ["Неверные КБЖУ или граммы", "Чужое или плохое фото", "Нет понятных шагов", "Это не рецепт"];

export function Recipes() {
  const [tab, setTab] = useState<RecipeStatus>("pending");
  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["admin", "recipes", tab],
    queryFn: () => adminApi.adminRecipes(tab),
  });

  return (
    <div className="stack">
      <div className="section-head">
        <h2>Рецепты</h2>
        <Link to="/recipes/new" className="btn small">
          + В каталог
        </Link>
      </div>
      <p className="muted small">
        Свой рецепт админ публикует сразу: создай его, затем нажми «Опубликовать в каталоге».
      </p>
      <div className="segmented compact" role="tablist">
        {TABS.map((t) => (
          <button key={t.value} role="tab" aria-selected={tab === t.value} onClick={() => setTab(t.value)}>
            {t.label}
          </button>
        ))}
      </div>
      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : data.length === 0 ? (
        <p className="muted center">Пусто</p>
      ) : (
        data.map((r) => <ModerationCard key={r.id} recipe={r} />)
      )}
    </div>
  );
}

function ModerationCard({ recipe }: { recipe: AdminRecipe }) {
  const [reason, setReason] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const approve = useAdminMutation(() => adminApi.approveRecipe(recipe.id), "recipes");
  const reject = useAdminMutation((text: string) => adminApi.rejectRecipe(recipe.id, text), "recipes");
  const p = recipe.per_portion;

  return (
    <article className="card stack moderation-card">
      <div className="moderation-head">
        {recipe.photo_url ? <img className="recipe-thumb" src={recipe.photo_url} alt="" /> : <span className="recipe-thumb recipe-photo-empty" />}
        <span className="stack-tight">
          <Link to={`/recipes/${recipe.id}`}>
            <strong>{recipe.title}</strong>
          </Link>
          <span className="muted small">
            {recipe.author_name ?? "без имени"} ·{" "}
            <Link to={`/admin/users/${recipe.owner_id}`}>{recipe.owner_name ?? recipe.owner_id}</Link>
            {recipe.forked_from && <> · копия «{recipe.forked_from.title}»</>}
          </span>
          <span className="small">
            {round(p.kcal)} ккал · Б {round(p.protein)} · Ж {round(p.fat)} · У {round(p.carbs)} на порцию
          </span>
        </span>
      </div>
      <p className={recipe.warnings.length ? "moderation-check warn small" : "moderation-check small"}>
        {recipe.warnings.length
          ? `Проверь: ${recipe.warnings.join("; ")}`
          : `Автопроверка: цифры правдоподобны, ${round(recipe.raw_grams)} г сырых${
              recipe.cooked_grams ? `, ${round(recipe.cooked_grams)} г готового` : ""
            }`}
      </p>
      <details className="small">
        <summary>
          {recipe.items.length} продуктов и {recipe.steps.length} шагов
        </summary>
        <p className="muted">{recipe.items.map((i) => `${i.name} ${round(i.grams)} г`).join(", ")}</p>
        <ol>
          {recipe.steps.map((s, n) => (
            <li key={n}>{s.text}</li>
          ))}
        </ol>
      </details>
      {recipe.status === "rejected" && recipe.reject_reason && <p className="muted small">Причина: {recipe.reject_reason}</p>}

      {rejecting ? (
        <div className="stack">
          <div className="chips">
            {REASONS.map((r) => (
              <button key={r} className="chip filter-chip" aria-pressed={reason === r} onClick={() => setReason(r)}>
                {r}
              </button>
            ))}
          </div>
          <textarea
            className="input textarea"
            rows={2}
            maxLength={500}
            placeholder="Или своим текстом, бот перешлёт его автору"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className="sheet-actions">
            <button className="btn" onClick={() => setRejecting(false)}>
              Отмена
            </button>
            <button className="btn btn-danger" disabled={!reason.trim() || reject.isPending} onClick={() => reject.mutate(reason.trim())}>
              Вернуть автору
            </button>
          </div>
        </div>
      ) : (
        <div className="fields-2">
          {recipe.status !== "public" && (
            <button className="btn btn-accent" disabled={approve.isPending} onClick={() => approve.mutate(undefined)}>
              Опубликовать
            </button>
          )}
          {recipe.status !== "rejected" && (
            <button className="btn" onClick={() => setRejecting(true)}>
              {recipe.status === "public" ? "Снять с публикации" : "Вернуть автору"}
            </button>
          )}
        </div>
      )}
      {(approve.error || reject.error) && <p className="error">{errorMessage(approve.error ?? reject.error)}</p>}
    </article>
  );
}
