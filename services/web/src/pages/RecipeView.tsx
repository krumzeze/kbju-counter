import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Recipe } from "../api/types";
import { Icon } from "../components/Icon";
import { RecipeDiarySheet } from "../components/RecipeDiarySheet";
import { ErrorState, Spinner } from "../components/States";
import { count, decimal, round, todayIso } from "../lib/format";
import { tr } from "../lib/i18n";
import { useDay, useInvalidate, useMe } from "../lib/queries";
import { RECIPE_KEYS, portionsWord, scaleMacros, statusLabel, useRecipe } from "../lib/recipes";
import { confirmAction, haptic } from "../lib/telegram";

export function RecipeView() {
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const { data, isPending, error, refetch } = useRecipe(id);
  const navigate = useNavigate();
  const adding = params.get("add") === "1";
  const setAdding = (on: boolean) => setParams(on ? { add: "1" } : {}, { replace: true });

  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;
  return (
    <>
      <RecipeBody recipe={data} onAdd={() => setAdding(true)} />
      {adding && (
        <RecipeDiarySheet
          recipe={data}
          onClose={() => setAdding(false)}
          onDone={() => navigate("/", { replace: true })}
        />
      )}
    </>
  );
}

function RecipeBody({ recipe, onAdd }: { recipe: Recipe; onAdd: () => void }) {
  const [per100, setPer100] = useState(false);
  const navigate = useNavigate();
  const invalidate = useInvalidate();
  const today = useDay(todayIso());
  const { data: me } = useMe();

  const favorite = useMutation({
    mutationFn: () => api.favoriteRecipe(recipe.id, !recipe.is_favorite),
    onSuccess: () => {
      haptic("success");
      return invalidate(...RECIPE_KEYS);
    },
  });
  const fork = useMutation({
    mutationFn: () => api.forkRecipe(recipe.id),
    onSuccess: async (copy) => {
      await invalidate(...RECIPE_KEYS);
      navigate(`/recipes/${copy.id}/edit`);
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteRecipe(recipe.id),
    onSuccess: async () => {
      await invalidate(...RECIPE_KEYS);
      navigate("/recipes", { replace: true });
    },
  });
  const cook = useMutation({
    mutationFn: () => api.cookRecipe(recipe.id),
    onSuccess: () => haptic("success"),
    onError: () => haptic("error"),
  });
  const rate = useMutation({
    mutationFn: (stars: number) => api.rateRecipe(recipe.id, stars),
    onSuccess: () => {
      haptic("success");
      return invalidate(...RECIPE_KEYS);
    },
  });

  const weight = recipe.cooked_grams ?? recipe.raw_grams;
  const shown = per100 && weight > 0 ? scaleMacros(recipe.totals, 100 / weight) : recipe.per_portion;
  const target = today.data?.target;
  const left = target && today.data ? target.kcal - today.data.eaten.kcal - recipe.per_portion.kcal : null;
  const leftProtein =
    target && today.data ? target.protein - today.data.eaten.protein - recipe.per_portion.protein : null;
  const edit = () => (recipe.is_mine ? navigate(`/recipes/${recipe.id}/edit`) : fork.mutate());

  return (
    <div className="page recipe-page">
      <div className="recipe-hero">
        {recipe.photo_url ? (
          <img src={recipe.photo_url} alt="" />
        ) : (
          <span className="recipe-photo-empty" aria-hidden>
            <Icon name="book" size={40} />
          </span>
        )}
        {(recipe.status === "public" || recipe.is_mine) && (
          <button
            className={recipe.is_favorite ? "fav-btn on" : "fav-btn"}
            aria-pressed={recipe.is_favorite}
            aria-label={tr("В избранное", "Favorite")}
            disabled={favorite.isPending}
            onClick={() => favorite.mutate()}
          >
            <Icon name="heart" />
          </button>
        )}
      </div>

      <header className="stack-tight">
        <h1 className="recipe-title">{recipe.title}</h1>
        <p className="muted small">
          {recipe.author_name && (
            <>
              {tr("Автор:", "By")} {recipe.author_name} ·{" "}
            </>
          )}
          {recipe.portions} {portionsWord(recipe.portions)}
        </p>
        {recipe.status === "public" && (recipe.ratings > 0 || recipe.favorites > 0 || recipe.cooked > 0) && (
          <p className="recipe-meta muted small">
            {recipe.rating !== null && (
              <span>
                ★ {decimal(recipe.rating)} · {recipe.ratings} {count(recipe.ratings, ["оценка", "оценки", "оценок"], ["rating", "ratings"])}
              </span>
            )}
            {recipe.favorites > 0 && (
              <span>
                {tr("в избранном у", "favorited by")} {recipe.favorites}
              </span>
            )}
            {recipe.cooked > 0 && (
              <span>
                {tr("готовили", "cooked")} {recipe.cooked} {count(recipe.cooked, ["раз", "раза", "раз"], ["time", "times"])}
              </span>
            )}
          </p>
        )}
      </header>

      {recipe.forked_from && (
        <p className="card recipe-note accent">
          {tr("Это твоя версия рецепта", "Your version of")}{" "}
          <Link to={`/recipes/${recipe.forked_from.id}`}>«{recipe.forked_from.title}»</Link>.{" "}
          {tr("Оригинал не меняется.", "The original stays as is.")}
        </p>
      )}
      {recipe.is_mine && recipe.status !== "public" && (
        <div className={`card recipe-note ${recipe.status}`}>
          <strong>{statusLabel(recipe.status)}</strong>
          {recipe.status === "rejected" && recipe.reject_reason && <p>{recipe.reject_reason}</p>}
          {recipe.status === "pending" && (
            <p className="small">{tr("Бот напишет, когда модератор проверит рецепт.", "The bot will message you after review.")}</p>
          )}
          {(recipe.status === "private" || recipe.status === "rejected") && (
            <Link to={`/recipes/${recipe.id}/publish`} className="btn small">
              {tr("Опубликовать в каталоге", "Publish to the catalog")}
            </Link>
          )}
        </div>
      )}

      <section className="card hero recipe-macros-card">
        <div className="recipe-macros-head">
          <span>
            <b className="recipe-kcal-big">{round(shown.kcal)}</b>{" "}
            <span className="hero-muted">{per100 ? tr("ккал в 100 г", "kcal per 100 g") : tr("ккал на порцию", "kcal per serving")}</span>
          </span>
          <span className="segmented mini" role="tablist">
            <button role="tab" aria-selected={!per100} onClick={() => setPer100(false)}>
              {tr("порция", "serving")}
            </button>
            <button role="tab" aria-selected={per100} onClick={() => setPer100(true)}>
              100 {tr("г", "g")}
            </button>
          </span>
        </div>
        <div className="recipe-macro-grid">
          <span>
            <span className="hero-muted">{tr("Белки", "Protein")}</span>
            <b>
              {round(shown.protein)} {tr("г", "g")}
            </b>
          </span>
          <span>
            <span className="hero-muted">{tr("Жиры", "Fat")}</span>
            <b>
              {round(shown.fat)} {tr("г", "g")}
            </b>
          </span>
          <span>
            <span className="hero-muted">{tr("Углеводы", "Carbs")}</span>
            <b>
              {round(shown.carbs)} {tr("г", "g")}
            </b>
          </span>
        </div>
        {left !== null && leftProtein !== null && (
          <p className="hero-muted small">
            {left >= 0
              ? tr(
                  `После порции до нормы останется ${round(left)} ккал и ${round(Math.max(0, leftProtein))} г белка`,
                  `After a serving you'll have ${round(left)} kcal and ${round(Math.max(0, leftProtein))} g protein left`,
                )
              : tr(`Порция выйдет за норму на ${round(-left)} ккал`, `A serving goes ${round(-left)} kcal over target`)}
          </p>
        )}
      </section>

      <div className="recipe-actions">
        <button className="btn btn-accent" onClick={onAdd}>
          {tr("Добавить в дневник", "Add to diary")}
        </button>
        <button className="btn" disabled={fork.isPending} onClick={edit}>
          {tr("Изменить", "Edit")}
        </button>
      </div>
      {fork.isError && <p className="error">{errorMessage(fork.error)}</p>}
      {me?.features.widgets && (
        <div className="stack-tight">
          <button className="btn btn-block" disabled={cook.isPending || cook.isSuccess} onClick={() => cook.mutate()}>
            <Icon name="list" size={20} />
            {cook.isSuccess ? tr("Рецепт в чате с ботом", "Sent to the bot chat") : tr("Готовить по шагам в Telegram", "Cook step by step in Telegram")}
          </button>
          {cook.isError ? (
            <p className="error small">{errorMessage(cook.error)}</p>
          ) : (
            <p className="muted small center">
              {tr(
                "Бот пришлёт рецепт с чек-листом шагов, а в конце блюдо можно сразу добавить в дневник.",
                "The bot sends a step checklist, and at the end you can log the dish right there.",
              )}
            </p>
          )}
        </div>
      )}

      <section className="card">
        <div className="section-head">
          <h2>{tr("Ингредиенты", "Ingredients")}</h2>
          <span className="muted small">
            {tr("в сыром виде, на", "raw, for")} {recipe.portions} {portionsWord(recipe.portions)}
          </span>
        </div>
        <ul className="ingredient-list">
          {recipe.items.map((i, n) => (
            <li key={n}>
              <span>{i.name}</span>
              <span className="muted">
                {round(i.grams)} {tr("г", "g")}
              </span>
            </li>
          ))}
          {recipe.cooked_grams && (
            <li className="small">
              <span className="muted">{tr("Вес готового блюда", "Cooked weight")}</span>
              <b>
                {round(recipe.cooked_grams)} {tr("г", "g")}
              </b>
            </li>
          )}
        </ul>
      </section>

      {recipe.steps.length > 0 && (
        <section className="card">
          <h2>{tr("Как готовить", "Method")}</h2>
          <ol className="recipe-steps">
            {recipe.steps.map((s, n) => (
              <li key={n}>
                <b className="step-num">{n + 1}</b>
                <span className="stack-tight">
                  <span className="pre-wrap">{s.text}</span>
                  {s.photo_url && <img className="step-photo" src={s.photo_url} alt="" loading="lazy" />}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {recipe.status === "public" && !recipe.is_mine && (
        <section className="card rate-row">
          <span>{recipe.my_rating ? tr("Твоя оценка", "Your rating") : tr("Оцени рецепт", "Rate this recipe")}</span>
          {recipe.can_rate ? (
            <span className="stars">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  className={(recipe.my_rating ?? 0) >= n ? "on" : ""}
                  aria-label={`${n}`}
                  disabled={rate.isPending}
                  onClick={() => rate.mutate(n)}
                >
                  ★
                </button>
              ))}
            </span>
          ) : (
            <span className="muted small">{tr("после того, как добавишь в дневник", "after you log it")}</span>
          )}
        </section>
      )}

      {recipe.is_mine && (
        <button
          className="btn-ghost danger"
          disabled={remove.isPending}
          onClick={async () => {
            if (await confirmAction(tr("Удалить рецепт? Записи в дневнике останутся.", "Delete the recipe? Diary entries stay."))) {
              remove.mutate();
            }
          }}
        >
          <Icon name="trash" size={18} />
          {tr("Удалить рецепт", "Delete recipe")}
        </button>
      )}
    </div>
  );
}
