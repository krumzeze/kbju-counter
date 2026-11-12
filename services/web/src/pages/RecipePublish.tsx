import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Me, Recipe } from "../api/types";
import { ErrorState, Spinner } from "../components/States";
import { tr } from "../lib/i18n";
import { useInvalidate } from "../lib/queries";
import { RECIPE_KEYS, useRecipe } from "../lib/recipes";
import { haptic } from "../lib/telegram";

export function RecipePublish({ me }: { me: Me }) {
  const recipe = useRecipe(Number(useParams().id));
  if (recipe.isPending) return <Spinner />;
  if (recipe.error) return <ErrorState message={errorMessage(recipe.error)} onRetry={() => recipe.refetch()} />;
  return <PublishForm me={me} recipe={recipe.data} />;
}

function PublishForm({ me, recipe }: { me: Me; recipe: Recipe }) {
  const navigate = useNavigate();
  const invalidate = useInvalidate();
  const [name, setName] = useState(recipe.author_name ?? me.first_name ?? "");
  const publish = useMutation({
    mutationFn: () => api.publishRecipe(recipe.id, name.trim()),
    onSuccess: async () => {
      haptic("success");
      await invalidate(...RECIPE_KEYS);
      navigate(`/recipes/${recipe.id}`, { replace: true });
    },
    onError: () => haptic("error"),
  });

  const checks = [
    { ok: recipe.items.length > 0, label: tr("Название и продукты", "Name and ingredients") },
    { ok: recipe.steps.length > 0, label: tr("Шаги приготовления", "Cooking steps") },
    { ok: !!recipe.photo, label: tr("Фото блюда", "Dish photo") },
  ];
  const ready = checks.every((c) => c.ok) && name.trim().length > 0;

  return (
    <div className="page">
      <h1>{tr("Публикация", "Publish")}</h1>
      <p className="muted">
        {me.is_admin
          ? tr("Ты админ, рецепт сразу появится в каталоге.", "You're an admin, the recipe goes straight to the catalog.")
          : tr(
              "Чтобы рецептом могли пользоваться другие, нужны фото, шаги и имя автора. Перед публикацией его проверит модератор.",
              "To share a recipe it needs a photo, steps and an author name. A moderator checks it first.",
            )}
      </p>

      <section className="card stack">
        <strong>{recipe.title}</strong>
        <ul className="checklist">
          {checks.map((c) => (
            <li key={c.label} className={c.ok ? "ok" : "missing"}>
              {c.ok ? "✓" : "•"} {c.label}
            </li>
          ))}
        </ul>
        {!checks.every((c) => c.ok) && (
          <Link to={`/recipes/${recipe.id}/edit`} className="btn">
            {tr("Дополнить рецепт", "Complete the recipe")}
          </Link>
        )}
      </section>

      <label className="field">
        <span>{tr("Имя автора в каталоге", "Author name in the catalog")}</span>
        <input className="input" maxLength={64} value={name} onChange={(e) => setName(e.target.value)} />
        <span className="muted small">
          {tr("Взяли имя из Telegram, можно поменять. Ник в Telegram не показываем.", "Taken from Telegram, you can change it. We never show your username.")}
        </span>
      </label>

      {publish.isError && <p className="error">{errorMessage(publish.error)}</p>}
      <button className="btn btn-accent btn-cta" disabled={!ready || publish.isPending} onClick={() => publish.mutate()}>
        {me.is_admin ? tr("Опубликовать", "Publish") : tr("Отправить на модерацию", "Send for review")}
      </button>
      {!me.is_admin && (
        <p className="card hero small">
          {tr(
            "После отправки рецепт остаётся у тебя в «Моих», и его можно добавлять в дневник как обычно. Бот напишет, когда его опубликуют или если нужно что-то поправить.",
            "Meanwhile the recipe stays in “Mine” and you can log it as usual. The bot will message you once it's published or needs changes.",
          )}
        </p>
      )}
    </div>
  );
}
