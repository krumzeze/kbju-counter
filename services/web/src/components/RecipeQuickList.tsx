import { Link } from "react-router-dom";
import type { RecipeCard } from "../api/types";
import { round } from "../lib/format";
import { tr } from "../lib/i18n";
import { useRecipes } from "../lib/recipes";
import { Icon } from "./Icon";
import { Spinner } from "./States";

export function RecipeQuickList() {
  const mine = useRecipes("mine", "", []);
  const favorites = useRecipes("favorites", "", []);
  if (mine.isPending || favorites.isPending) return <Spinner />;
  const seen = new Set<number>();
  const rows: RecipeCard[] = [...(mine.data ?? []), ...(favorites.data ?? [])].filter((r) =>
    seen.has(r.id) ? false : (seen.add(r.id), true),
  );

  return (
    <div className="stack">
      {rows.length === 0 ? (
        <p className="muted small">
          {tr(
            "Здесь будут твои и избранные рецепты: добавлять их можно порциями или в граммах.",
            "Your own and favorite recipes show up here, ready to log by servings or grams.",
          )}
        </p>
      ) : (
        rows.map((r) => (
          <div key={r.id} className="card quick-recipe">
            <Link to={`/recipes/${r.id}`} className="quick-recipe-body">
              <strong>{r.title}</strong>
              <span className="muted small">
                {r.is_mine ? tr("мой", "mine") : `♥ ${tr("избранное", "favorite")}`} · {round(r.per_portion.kcal)}{" "}
                {tr("ккал на порцию", "kcal per serving")}
              </span>
            </Link>
            <Link to={`/recipes/${r.id}?add=1`} className="icon-btn accent" aria-label={tr("Добавить в дневник", "Add to diary")}>
              <Icon name="plus" />
            </Link>
          </div>
        ))
      )}
      <Link to="/recipes" className="btn btn-block">
        {tr("Открыть каталог рецептов", "Open the recipe catalog")}
      </Link>
    </div>
  );
}
