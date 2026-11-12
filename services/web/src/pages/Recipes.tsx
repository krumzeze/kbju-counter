import { useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/client";
import type { RecipeFilter, RecipeScope } from "../api/types";
import { Icon } from "../components/Icon";
import { RecipeRow } from "../components/RecipeCard";
import { ErrorState, Spinner } from "../components/States";
import { tr } from "../lib/i18n";
import { useRecipes } from "../lib/recipes";

const scopes = (): { value: RecipeScope; label: string }[] => [
  { value: "catalog", label: tr("Каталог", "Catalog") },
  { value: "mine", label: tr("Мои", "Mine") },
  { value: "favorites", label: tr("Избранное", "Favorites") },
];

const filterChips = (): { value: RecipeFilter; label: string }[] => [
  { value: "protein", label: tr("Много белка", "High protein") },
  { value: "light", label: tr("До 400 ккал", "Under 400 kcal") },
  { value: "fits", label: tr("Закроет остаток дня", "Fits what's left today") },
];

const SCOPE_KEY = "belok.recipes.scope";

function savedScope(): RecipeScope {
  try {
    const v = localStorage.getItem(SCOPE_KEY);
    return v === "mine" || v === "favorites" ? v : "catalog";
  } catch {
    return "catalog";
  }
}

export function Recipes() {
  const [scope, setScopeState] = useState<RecipeScope>(savedScope);
  const [q, setQ] = useState("");
  const [filters, setFilters] = useState<RecipeFilter[]>([]);
  const { data, isPending, error, refetch } = useRecipes(scope, q, filters);

  const setScope = (v: RecipeScope) => {
    setScopeState(v);
    try {
      localStorage.setItem(SCOPE_KEY, v);
    } catch {
      // the tab just won't be remembered
    }
  };
  const toggle = (f: RecipeFilter) =>
    setFilters(filters.includes(f) ? filters.filter((x) => x !== f) : [...filters, f]);

  return (
    <div className="page">
      <header className="recipes-head">
        <div>
          <p className="eyebrow">{tr("КБЖУ на порцию уже посчитаны", "Macros per serving included")}</p>
          <h1>{tr("Рецепты", "Recipes")}</h1>
        </div>
        <Link to="/recipes/new" className="icon-btn dark" aria-label={tr("Новый рецепт", "New recipe")}>
          <Icon name="plus" />
        </Link>
      </header>

      <div className="segmented" role="tablist">
        {scopes().map((s) => (
          <button key={s.value} role="tab" aria-selected={scope === s.value} onClick={() => setScope(s.value)}>
            {s.label}
          </button>
        ))}
      </div>

      <label className="search-field">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <input
          type="search"
          value={q}
          maxLength={100}
          onChange={(e) => setQ(e.target.value)}
          placeholder={tr("Сырники, паста, курица…", "Pancakes, pasta, chicken…")}
          aria-label={tr("Поиск рецептов", "Search recipes")}
        />
      </label>

      <div className="chips" role="group" aria-label={tr("Фильтры", "Filters")}>
        {filterChips().map((f) => (
          <button
            key={f.value}
            className="chip filter-chip"
            aria-pressed={filters.includes(f.value)}
            onClick={() => toggle(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : data.length === 0 ? (
        <EmptyRecipes scope={scope} searching={q.trim().length > 0 || filters.length > 0} />
      ) : (
        <div className="stack">
          {data.map((r) => (
            <RecipeRow key={r.id} recipe={r} />
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyRecipes({ scope, searching }: { scope: RecipeScope; searching: boolean }) {
  if (searching) {
    return <p className="muted center">{tr("Ничего не нашлось. Попробуй другие слова.", "Nothing found. Try other words.")}</p>;
  }
  if (scope === "mine") {
    return (
      <div className="card empty-recipes">
        <p>
          {tr(
            "Здесь будут твои рецепты: соберёшь блюдо из продуктов один раз, а потом будешь добавлять его порциями.",
            "Your recipes live here: put a dish together once, then log it by servings.",
          )}
        </p>
        <Link to="/recipes/new" className="btn btn-primary">
          {tr("Создать рецепт", "Create a recipe")}
        </Link>
      </div>
    );
  }
  if (scope === "favorites") {
    return (
      <p className="muted center">
        {tr("Нажми ♥ на странице рецепта, и он появится здесь.", "Tap ♥ on a recipe and it shows up here.")}
      </p>
    );
  }
  return <p className="muted center">{tr("Каталог пока пустой, скоро здесь появятся рецепты.", "The catalog is empty for now.")}</p>;
}
