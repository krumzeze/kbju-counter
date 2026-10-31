import type { Lang } from "../lib/i18n";

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
  workout_id: number;
  exercise_id: number;
  exercise: string;
  day: string;
  weight_kg: number;
  reps: number | null;
  duration_s: number | null;
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
  language: Lang | null;
  trial_ends_at: string;
  subscription_until: string | null;
  has_access: boolean;
  status: AccessStatus;
  access_until: string;
  is_admin: boolean;
  base_target: Macros | null;
}

export type AccessStatus = "trial" | "active" | "lifetime" | "expired";

export interface Referral {
  link: string | null;
  invited: number;
  paid: number;
  days: number;
  trial_days: number;
  reward_days: number;
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

export type MuscleGroup =
  | "delts"
  | "chest"
  | "arms"
  | "abs"
  | "back"
  | "legs"
  | "glutes"
  | "calves"
  | "cardio";

export interface CatalogItem {
  id: string;
  name: string;
  group: MuscleGroup;
  primary: string[];
  equipment: string;
  cardio: boolean;
  images: number;
}

export interface CatalogDetail extends CatalogItem {
  name_en: string;
  secondary: string[];
  instructions: string[];
  level: string;
  mechanic: string | null;
  force: string | null;
  exercise_id: number | null;
}

export interface Exercise {
  id: number;
  name: string;
  catalog_id: string | null;
  group: MuscleGroup | null;
  cardio: boolean;
  sets: number;
  last_day: string | null;
}

export type ExerciseRef = { exercise_id: number } | { catalog_id: string };

export interface SetValues {
  weight_kg: number;
  reps: number | null;
  duration_s: number | null;
}

export interface WorkoutExercise {
  exercise: Exercise;
  planned_sets: number;
  sets: WorkoutSet[];
  previous: SetValues[];
  previous_day: string | null;
}

export interface Workout {
  id: number;
  day: string;
  started_at: string;
  finished_at: string | null;
  title: string | null;
  exercises: WorkoutExercise[];
  sets: number;
  volume_kg: number;
}

export interface WorkoutSummary {
  id: number;
  day: string;
  started_at: string;
  finished_at: string | null;
  title: string | null;
  exercises: number;
  sets: number;
  volume_kg: number;
  names: string[];
}

export interface Template {
  id: number;
  name: string;
  items: { exercise: Exercise; sets: number }[];
}

export interface TemplateInput {
  name: string;
  items?: (ExerciseRef & { sets: number })[];
  workout_id?: number;
}

export interface ProgressPoint {
  day: string;
  top_weight_kg: number;
  top_reps: number | null;
  e1rm: number;
  sets: number;
  reps: number;
  volume_kg: number;
  duration_s: number;
  items: SetValues[];
}

export interface Progress {
  exercise: Exercise;
  points: ProgressPoint[];
  records: { e1rm: number; weight_kg: number; reps: number; volume_kg: number; duration_s: number };
}

export interface Analytics {
  weeks: { start: string; workouts: number; sets: number; volume_kg: number; cardio_min: number }[];
  streak_weeks: number;
  total_workouts: number;
  muscles_week: Record<string, number>;
  muscles_month: Record<string, number>;
  groups_month: Record<string, number>;
  top: { exercise: Exercise; sets: number; best_e1rm: number }[];
}

export interface Count {
  key: string;
  count: number;
}

export interface DayPoint {
  day: string;
  new_users: number;
  active_users: number;
  analyses: number;
  errors: number;
  cost_usd: number;
}

export interface Dashboard {
  users_total: number;
  new_today: number;
  new_7d: number;
  new_30d: number;
  dau: number;
  wau: number;
  mau: number;
  statuses: Record<AccessStatus, number>;
  blocked: number;
  bot_blocked: number;
  funnel: Count[];
  cost_today: number;
  cost_month: number;
  cost_forecast: number;
  avg_cost: number | null;
  requests_24h: number;
  error_rate_24h: number | null;
  no_food_rate_24h: number | null;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  referred_users: number;
  referral_rewards: number;
  promo_redemptions_30d: number;
  sources: Count[];
  series: DayPoint[];
}

export interface UserBrief {
  id: number;
  username: string | null;
  first_name: string | null;
}

export interface UserRow extends UserBrief {
  created_at: string;
  last_seen_at: string | null;
  status: AccessStatus;
  access_until: string;
  analyses: number;
  cost_usd: number;
  is_admin: boolean;
  is_blocked: boolean;
  bot_blocked: boolean;
}

export interface UserPage {
  items: UserRow[];
  total: number;
}

export type UserFilter = "all" | "trial" | "active" | "expired" | "blocked" | "inactive" | "admins";
export type UserSort = "created_at" | "last_seen_at" | "analyses" | "cost" | "access_until";

export interface ActivityDay {
  day: string;
  meals: number;
  sets: number;
  steps: number;
  analyses: number;
}

export interface LlmCall {
  created_at: string;
  kind: string;
  model: string;
  ok: boolean;
  no_food: boolean;
  cost_usd: number | null;
  latency_ms: number;
}

export interface AdminAction {
  id: number;
  created_at: string;
  action: string;
  admin: UserBrief | null;
  target: UserBrief | null;
  target_user_id: number | null;
  details: Record<string, unknown> | null;
}

export interface UserDetail extends UserRow {
  source: string | null;
  timezone: string;
  sex: Sex | null;
  age: number | null;
  height_cm: number | null;
  goal: Goal | null;
  weight_kg: number | null;
  trial_ends_at: string;
  subscription_until: string | null;
  lifetime_access: boolean;
  daily_limit: number | null;
  llm_errors: number;
  llm_requests: number;
  referred_by: UserBrief | null;
  invited: number;
  invited_paid: number;
  referral_days: number;
  activity: ActivityDay[];
  meals: Meal[];
  llm: LlmCall[];
  redemptions: { code: string; days: number; created_at: string }[];
  actions: AdminAction[];
}

export interface UserPatch {
  is_blocked?: boolean;
  is_admin?: boolean;
  lifetime_access?: boolean;
  daily_limit?: number | null;
}

export interface Promo {
  id: number;
  code: string;
  days: number;
  max_activations: number | null;
  activations: number;
  expires_at: string | null;
  new_users_only: boolean;
  active: boolean;
  note: string | null;
  created_at: string;
  retained: number;
  link: string | null;
}

export interface PromoInput {
  code?: string;
  days: number;
  max_activations?: number | null;
  expires_at?: string | null;
  new_users_only: boolean;
  note?: string;
}

export type Segment = "all" | "trial" | "active" | "expired" | "inactive";

export interface Broadcast {
  id: number;
  created_at: string;
  text: string;
  segment: Segment;
  status: "draft" | "sending" | "done" | "cancelled";
  total: number;
  sent: number;
  failed: number;
  blocked: number;
  started_at: string | null;
  finished_at: string | null;
}

export interface Referrer extends UserBrief {
  invited: number;
  paid: number;
  days: number;
}

export interface Prefs {
  new_users: boolean;
  errors: boolean;
  daily: boolean;
}
