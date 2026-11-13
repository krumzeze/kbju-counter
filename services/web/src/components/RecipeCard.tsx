import { Link } from "react-router-dom";
import type { RecipeCard } from "../api/types";
import { count, decimal, round } from "../lib/format";
import { tr } from "../lib/i18n";
import { statusLabel } from "../lib/recipes";
import { Icon } from "./Icon";

function Photo({ url, className }: { url: string | null; className: string }) {
  return url ? (
    <img className={className} src={url} alt="" loading="lazy" />
  ) : (
    <span className={`${className} recipe-photo-empty`} aria-hidden>
      <Icon name="book" size={26} />
    </span>
  );
}

export function RecipeRow({ recipe }: { recipe: RecipeCard }) {
  const p = recipe.per_portion;
  return (
    <Link to={`/recipes/${recipe.id}`} className="card recipe-row">
      <Photo url={recipe.photo_url} className="recipe-thumb" />
      <span className="recipe-row-body">
        <strong className="recipe-row-title">{recipe.title}</strong>
        <span className="recipe-kcal">
          <b>{round(p.kcal)}</b> <span className="muted">{tr("ккал на порцию", "kcal per serving")}</span>
        </span>
        <span className="recipe-macros small">
          <span>
            <b className="c-protein">{tr("Б", "P")}</b> {round(p.protein)}
          </span>
          <span>
            <b className="c-fat">{tr("Ж", "F")}</b> {round(p.fat)}
          </span>
          <span>
            <b className="c-carbs">{tr("У", "C")}</b> {round(p.carbs)}
          </span>
        </span>
        <span className="recipe-meta muted small">
          {recipe.is_mine && recipe.status !== "public" ? (
            <span className={`recipe-status ${recipe.status}`}>{statusLabel(recipe.status)}</span>
          ) : (
            <>
              {recipe.rating !== null && <span>★ {decimal(recipe.rating)}</span>}
              {recipe.cooked > 0 && (
                <span>
                  {tr("готовили", "cooked")} {round(recipe.cooked)}{" "}
                  {count(recipe.cooked, ["раз", "раза", "раз"], ["time", "times"])}
                </span>
              )}
              {recipe.is_favorite && <span>♥</span>}
            </>
          )}
        </span>
      </span>
    </Link>
  );
}

export function RecipeTile({ recipe, caption }: { recipe: RecipeCard; caption?: string }) {
  return (
    <Link to={`/recipes/${recipe.id}`} className="card recipe-tile">
      <Photo url={recipe.photo_url} className="recipe-tile-photo" />
      <strong className="recipe-tile-title">{recipe.title}</strong>
      <span className="muted small">
        {round(recipe.per_portion.kcal)} {tr("ккал", "kcal")} · {tr("Б", "P")} {round(recipe.per_portion.protein)}
      </span>
      {caption && <span className="recipe-tile-caption small">{caption}</span>}
    </Link>
  );
}
