import type {
  AdminAction,
  AppError,
  Analytics,
  Broadcast,
  CatalogDetail,
  CatalogItem,
  Count,
  Dashboard,
  Day,
  Exercise,
  FeatureFlag,
  Health,
  Meal,
  MealHistoryItem,
  Me,
  Plan,
  Prefs,
  Progress,
  Promo,
  Referral,
  Referrer,
  Stats,
  SupportMessage,
  Template,
  UserDetail,
  UserPage,
  WeightPoint,
  Workout,
  WorkoutSummary,
} from "../src/api/types";

const isoDay = (offset = 0) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const at = (offset = 0) => `${isoDay(offset)}T09:30:00Z`;
const lastDays = (n: number) => Array.from({ length: n }, (_, i) => isoDay(i - n + 1));

const target = { kcal: 2200, protein: 150, fat: 70, carbs: 230 };

export const me: Me = {
  id: 1,
  username: "smoke",
  first_name: "Smoke",
  profile_complete: true,
  sex: "m",
  age: 30,
  height_cm: 180,
  goal: "maintain",
  weight_kg: 78.5,
  timezone: "Europe/Moscow",
  language: "ru",
  trial_ends_at: at(5),
  subscription_until: null,
  has_access: true,
  status: "trial",
  access_until: at(5),
  is_admin: true,
  activity_adjust: true,
  adaptive_target: false,
  remind_meals: true,
  remind_weight: false,
  photo_eval_consent: false,
  photo_storage: true,
  adaptive: {
    ready: false,
    logged_days: 4,
    weigh_ins: 2,
    span_days: 6,
    need_logged_days: 10,
    need_weigh_ins: 4,
    need_span_days: 14,
    window_days: 21,
    tdee: null,
    formula_tdee: 2400,
  },
  base_target: target,
  features: { photo: true, text: true, voice: true, barcode: true, reminders: true, payments: true },
  analyses_left: 3,
  free_history_days: 7,
};

const bench: Exercise = {
  id: 1,
  name: "Жим штанги лёжа",
  catalog_id: "Barbell_Bench_Press_-_Medium_Grip",
  group: "chest",
  cardio: false,
  primary: ["chest"],
  secondary: ["shoulders", "triceps"],
  sets: 12,
  last_day: isoDay(-2),
};
const run: Exercise = {
  id: 2,
  name: "Бег",
  catalog_id: null,
  group: "cardio",
  cardio: true,
  primary: [],
  secondary: [],
  sets: 3,
  last_day: isoDay(-1),
};

const meal: Meal = {
  id: 1,
  day: isoDay(),
  created_at: at(),
  source: "photo",
  title: "Омлет с овощами",
  scale: 1,
  items: [
    { id: 1, name: "Яйца", grams: 150, kcal: 215, protein: 19, fat: 15, carbs: 1 },
    { id: 2, name: "Помидоры", grams: 80, kcal: 14, protein: 1, fat: 0, carbs: 3 },
  ],
  totals: { kcal: 229, protein: 20, fat: 15, carbs: 4 },
  photo_url: null,
};

const set = (id: number, workout_id: number, weight_kg: number, reps: number) => ({
  id,
  workout_id,
  exercise_id: bench.id,
  exercise: bench.name,
  day: isoDay(),
  weight_kg,
  reps,
  duration_s: null,
});

export const day: Day = {
  day: isoDay(),
  eaten: meal.totals,
  target,
  target_source: "formula",
  adaptive_paused: false,
  steps: 6400,
  water_ml: 750,
  water_target_ml: 2500,
  activity_kcal: 120,
  weight_kg: 78.5,
  meals: [meal],
  sets: [set(1, 1, 60, 10)],
};

export const mealHistory: MealHistoryItem[] = [
  { meal_id: 1, title: meal.title, source: "photo", times: 4, last_eaten: at(-1), totals: meal.totals },
];

export const weights: WeightPoint[] = lastDays(10).map((d, i) => ({ day: d, weight_kg: 79 - i * 0.1 }));

export const stats: Stats = {
  days: lastDays(7).map((d, i) => ({
    day: d,
    eaten: { kcal: 1900 + i * 40, protein: 120 + i, fat: 60, carbs: 200 },
    steps: 5000 + i * 300,
    water_ml: 1500,
    sets: i % 2 ? 12 : 0,
  })),
  target,
  water_target_ml: 2400,
  limited: false,
};

const catalogBench: CatalogItem = {
  id: "Barbell_Bench_Press_-_Medium_Grip",
  name: "Жим штанги лёжа",
  group: "chest",
  primary: ["chest"],
  equipment: "barbell",
  cardio: false,
  images: 2,
};

export const catalog: CatalogItem[] = [
  catalogBench,
  {
    id: "Barbell_Squat",
    name: "Приседания со штангой",
    group: "legs",
    primary: ["quadriceps"],
    equipment: "barbell",
    cardio: false,
    images: 2,
  },
];

export const catalogItem: CatalogDetail = {
  ...catalogBench,
  name_en: "Barbell Bench Press - Medium Grip",
  secondary: ["shoulders", "triceps"],
  instructions: ["Lie back on a flat bench.", "Lower the bar to your chest.", "Press it back up."],
  level: "beginner",
  mechanic: "compound",
  force: "push",
  exercise_id: bench.id,
};

export const exercises: Exercise[] = [bench, run];

export const progress: Progress = {
  exercise: bench,
  points: lastDays(4).map((d, i) => ({
    workout_id: i + 1,
    day: d,
    top_weight_kg: 55 + i * 2.5,
    top_reps: 8,
    e1rm: 70 + i * 3,
    sets: 3,
    reps: 24,
    volume_kg: 1300 + i * 60,
    duration_s: 0,
    items: [{ weight_kg: 55 + i * 2.5, reps: 8, duration_s: null }],
  })),
  records: { e1rm: 79, weight_kg: 62.5, reps: 10, volume_kg: 1480, duration_s: 0 },
};

export const analytics: Analytics = {
  weeks: lastDays(4).map((d, i) => ({ start: d, workouts: 2 + i, sets: 20, volume_kg: 5000, cardio_min: 30 })),
  streak_weeks: 3,
  total_workouts: 14,
  muscles_week: { chest: 9, triceps: 6 },
  muscles_month: { chest: 30, quadriceps: 20 },
  groups_month: { chest: 30, legs: 20 },
  top: [{ exercise: bench, sets: 30, best_e1rm: 79 }],
};

export const activeWorkout: Workout = {
  id: 1,
  day: isoDay(),
  started_at: at(),
  finished_at: null,
  title: "Грудь",
  exercises: [
    {
      exercise: bench,
      planned_sets: 3,
      sets: [set(1, 1, 60, 10)],
      previous: [{ weight_kg: 57.5, reps: 10, duration_s: null }],
      previous_day: isoDay(-2),
      records: ["e1rm", "weight"],
    },
    { exercise: run, planned_sets: 1, sets: [], previous: [], previous_day: null, records: [] },
  ],
  sets: 1,
  volume_kg: 600,
  muscles: { chest: 1, shoulders: 0.5, triceps: 0.5 },
  compare: { id: 2, day: isoDay(-2), started_at: at(-2), finished_at: at(-2), sets: 8, volume_kg: 4200 },
};

export const finishedWorkout: Workout = { ...activeWorkout, id: 2, finished_at: at() };

export const workouts: WorkoutSummary[] = [
  {
    id: 2,
    day: isoDay(-2),
    started_at: at(-2),
    finished_at: at(-2),
    title: null,
    exercises: 2,
    sets: 8,
    volume_kg: 4200,
    names: [bench.name, run.name],
  },
];

export const templates: Template[] = [{ id: 1, name: "Грудь", items: [{ exercise: bench, sets: 3 }] }];

export const plans: Plan[] = [
  { provider: "stars", code: "stars-30", days: 30, link: null, web_link: null, amount: 250, currency: "XTR" },
];

export const support: SupportMessage[] = [
  { id: 1, created_at: at(-1), from_admin: false, text: "Привет" },
  { id: 2, created_at: at(-1), from_admin: true, text: "Здравствуйте!" },
];

export const referral: Referral = {
  link: "https://t.me/belok_bot?start=ref1",
  invited: 2,
  paid: 1,
  days: 7,
  trial_days: 7,
  reward_days: 7,
};

const brief = { id: 2, username: "user2", first_name: "Анна" };

export const dashboard: Dashboard = {
  users_total: 120,
  new_today: 3,
  new_7d: 20,
  new_30d: 60,
  dau: 15,
  wau: 50,
  mau: 90,
  statuses: { trial: 40, active: 10, lifetime: 2, expired: 68 },
  blocked: 1,
  bot_blocked: 4,
  funnel: [
    { key: "started", count: 120 },
    { key: "profile", count: 90 },
    { key: "meal", count: 70 },
  ],
  cost_today: 0.42,
  cost_month: 9.1,
  cost_forecast: 12.5,
  avg_cost: 0.004,
  requests_24h: 210,
  error_rate_24h: 0.01,
  no_food_rate_24h: 0.03,
  latency_p50_ms: 2400,
  latency_p95_ms: 6100,
  referred_users: 8,
  referral_rewards: 3,
  promo_redemptions_30d: 5,
  sources: [
    { key: "direct", count: 100, paid: 12 },
    { key: "catalog_alpha", count: 40, paid: 6 },
  ],
  series: lastDays(14).map((d, i) => ({
    day: d,
    new_users: i % 4,
    active_users: 10 + i,
    analyses: 20 + i,
    errors: i % 3 === 0 ? 1 : 0,
    cost_usd: 0.3,
  })),
};

const userRow = {
  ...brief,
  created_at: at(-20),
  last_seen_at: at(),
  status: "active" as const,
  access_until: at(10),
  analyses: 42,
  cost_usd: 0.18,
  is_admin: false,
  is_blocked: false,
  bot_blocked: false,
};

export const users: UserPage = { items: [userRow], total: 1 };

const action: AdminAction = {
  id: 1,
  created_at: at(-1),
  action: "grant",
  admin: { id: 1, username: "smoke", first_name: "Smoke" },
  target: brief,
  target_user_id: brief.id,
  details: { days: 30 },
};

export const userDetail: UserDetail = {
  ...userRow,
  source: "direct",
  timezone: "Europe/Moscow",
  sex: "f",
  age: 27,
  height_cm: 168,
  goal: "lose",
  weight_kg: 62,
  trial_ends_at: at(-13),
  subscription_until: at(10),
  lifetime_access: false,
  daily_limit: null,
  llm_errors: 1,
  llm_requests: 42,
  referred_by: null,
  invited: 0,
  invited_paid: 0,
  referral_days: 0,
  activity: lastDays(7).map((d) => ({ day: d, meals: 3, sets: 0, steps: 4000, analyses: 2 })),
  meals: [meal],
  llm: [
    {
      created_at: at(),
      kind: "photo",
      model: "claude-haiku-5-5",
      ok: true,
      no_food: false,
      cost_usd: 0.004,
      latency_ms: 2300,
    },
  ],
  redemptions: [{ code: "WELCOME", days: 7, created_at: at(-15) }],
  actions: [action],
};

export const promos: Promo[] = [
  {
    id: 1,
    code: "WELCOME",
    days: 7,
    max_activations: 100,
    activations: 5,
    expires_at: null,
    new_users_only: true,
    active: true,
    note: null,
    created_at: at(-30),
    retained: 2,
    link: "https://t.me/belok_bot?start=promo_WELCOME",
  },
];

export const segments: Count[] = [
  { key: "all", count: 120 },
  { key: "trial", count: 40 },
];

export const broadcasts: Broadcast[] = [
  {
    id: 1,
    created_at: at(-3),
    text: "<b>Новая версия</b>",
    segment: "all",
    status: "done",
    total: 120,
    sent: 115,
    failed: 1,
    blocked: 4,
    started_at: at(-3),
    finished_at: at(-3),
  },
];

export const referrers: Referrer[] = [{ ...brief, invited: 3, paid: 1, days: 7 }];

export const actions: AdminAction[] = [action];

export const prefs: Prefs = { new_users: true, payments: true, errors: true, daily: false };

export const features: FeatureFlag[] = (Object.keys(me.features) as FeatureFlag["key"][]).map((key) => ({
  key,
  enabled: true,
}));

export const health: Health = {
  checked_at: at(),
  checks: [
    { key: "db", status: "ok", detail: null, latency_ms: 3 },
    { key: "llm", status: "warn", detail: "slow", latency_ms: 4100 },
  ],
};

export const appErrors: AppError[] = [
  {
    fingerprint: "abc123",
    source: "api",
    message: "ValueError: boom",
    detail: "Traceback...",
    path: "/api/day",
    user_id: 2,
    count: 2,
    first_seen: at(-1),
    last_seen: at(),
  },
];
