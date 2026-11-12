import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Macros, RecipeFilter, RecipeItem, RecipeScope, RecipeStatus } from "../api/types";
import { plural } from "./format";
import { tr } from "./i18n";

export const RECIPE_KEYS = ["recipes", "recipe", "recipe-suggestions"];

export const useRecipes = (scope: RecipeScope, q: string, filters: RecipeFilter[]) =>
  useQuery({
    queryKey: ["recipes", scope, q.trim(), [...filters].sort()],
    queryFn: () => api.recipes(scope, q, filters),
  });

export const useRecipe = (id: number) =>
  useQuery({ queryKey: ["recipe", id], queryFn: () => api.recipe(id), enabled: Number.isFinite(id) });

export const useRecipeSuggestions = () =>
  useQuery({ queryKey: ["recipe-suggestions"], queryFn: api.recipeSuggestions });

export function sumItems(items: RecipeItem[]): Macros {
  return items.reduce(
    (t, i) => ({
      kcal: t.kcal + i.kcal,
      protein: t.protein + i.protein,
      fat: t.fat + i.fat,
      carbs: t.carbs + i.carbs,
    }),
    { kcal: 0, protein: 0, fat: 0, carbs: 0 },
  );
}

export function scaleMacros(m: Macros, k: number): Macros {
  return { kcal: m.kcal * k, protein: m.protein * k, fat: m.fat * k, carbs: m.carbs * k };
}

export const statusLabel = (status: RecipeStatus) =>
  ({
    private: tr("Личный", "Private"),
    pending: tr("На модерации", "In review"),
    public: tr("В каталоге", "Published"),
    rejected: tr("Вернули на доработку", "Needs changes"),
  })[status];

export const portionsWord = (n: number) =>
  tr(plural(n, "порция", "порции", "порций"), n === 1 ? "serving" : "servings");
