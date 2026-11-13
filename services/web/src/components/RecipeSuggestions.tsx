import { Link } from "react-router-dom";
import type { Day, RecipeSuggestion } from "../api/types";
import { round } from "../lib/format";
import { tr } from "../lib/i18n";
import { useRecipeSuggestions } from "../lib/recipes";
import { RecipeTile } from "./RecipeCard";

export function RecipeSuggestions({ day }: { day: Day }) {
  const { data } = useRecipeSuggestions();
  if (!data?.length || !day.target) return null;
  const kcal = day.target.kcal - day.eaten.kcal;
  const missing = (key: "protein" | "fat" | "carbs") => Math.max(0, Math.round(day.target![key] - day.eaten[key]));
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
          `Осталось ${round(kcal)} ккал · не хватает Б ${missing("protein")} · Ж ${missing("fat")} · У ${missing("carbs")} г`,
          `${round(kcal)} kcal left · missing P ${missing("protein")} · F ${missing("fat")} · C ${missing("carbs")} g`,
        )}
      </p>
      <div className="scroll-x recipe-tiles">
        {data.map((r) => (
          <RecipeTile key={r.id} recipe={r} caption={coverCaption(r)} />
        ))}
      </div>
    </section>
  );
}

function coverCaption(recipe: RecipeSuggestion): string | undefined {
  const names = {
    protein: tr("белка", "of protein"),
    fat: tr("жиров", "of fat"),
    carbs: tr("углеводов", "of carbs"),
  };
  const best = (Object.entries(recipe.covers) as [keyof typeof names, number][]).sort(
    (a, b) => (b[0] === "protein" ? b[1] + 15 : b[1]) - (a[0] === "protein" ? a[1] + 15 : a[1]),
  )[0];
  if (!best || best[1] < 20) return undefined;
  return tr(`Закроет ${best[1]}% ${names[best[0]]}`, `Covers ${best[1]}% ${names[best[0]]}`);
}
