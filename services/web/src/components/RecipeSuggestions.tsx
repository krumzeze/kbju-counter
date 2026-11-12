import { Link } from "react-router-dom";
import type { Day } from "../api/types";
import { round } from "../lib/format";
import { tr } from "../lib/i18n";
import { useRecipeSuggestions } from "../lib/recipes";
import { RecipeTile } from "./RecipeCard";

export function RecipeSuggestions({ day }: { day: Day }) {
  const { data } = useRecipeSuggestions();
  if (!data?.length || !day.target) return null;
  const kcal = day.target.kcal - day.eaten.kcal;
  const protein = Math.max(0, day.target.protein - day.eaten.protein);
  return (
    <section className="recipe-suggestions">
      <div className="section-head">
        <h2>{tr("Что приготовить", "What to cook")}</h2>
        <Link to="/recipes" className="link-strong">
          {tr("Все рецепты", "All recipes")} →
        </Link>
      </div>
      <p className="muted small">
        {tr(
          `Закроют остаток: ${round(kcal)} ккал и ${round(protein)} г белка`,
          `Fit what's left: ${round(kcal)} kcal and ${round(protein)} g protein`,
        )}
      </p>
      <div className="scroll-x recipe-tiles">
        {data.map((r) => (
          <RecipeTile key={r.id} recipe={r} />
        ))}
      </div>
    </section>
  );
}
