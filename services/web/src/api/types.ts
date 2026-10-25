export type Sex = "m" | "f";
export type Goal = "lose" | "maintain" | "gain";

export interface Macros {
  kcal: number;
  protein: number;
  fat: number;
  carbs: number;
}

export interface MealItem extends Macros {
  id: number;
  name: string;
  grams: number;
}

export interface Meal {
  id: number;
  day: string;
  created_at: string;
  source: "photo" | "text";
  title: string;
  scale: number;
  items: MealItem[];
  totals: Macros;
}

export interface WorkoutSet {
  id: number;
  exercise: string;
  day: string;
  weight_kg: number;
  reps: number;
}

export interface Day {
  day: string;
  eaten: Macros;
  target: Macros | null;
  steps: number;
  steps_kcal: number;
  weight_kg: number | null;
  meals: Meal[];
  sets: WorkoutSet[];
}

export interface Me {
  id: number;
  username: string | null;
  profile_complete: boolean;
  sex: Sex | null;
  age: number | null;
  height_cm: number | null;
  goal: Goal | null;
  weight_kg: number | null;
  timezone: string;
  trial_ends_at: string;
  subscription_until: string | null;
  has_access: boolean;
  base_target: Macros | null;
}

export interface ProfileInput {
  sex: Sex;
  age: number;
  height_cm: number;
  weight_kg: number;
  goal: Goal;
  timezone?: string;
}

export interface WeightPoint {
  day: string;
  weight_kg: number;
}

export interface ProgressPoint {
  day: string;
  top_weight_kg: number;
  top_reps: number;
  e1rm: number;
  sets: number;
}

export interface Progress {
  exercise: string;
  points: ProgressPoint[];
}
