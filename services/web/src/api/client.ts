import type {
  AdminAction,
  Analytics,
  CatalogDetail,
  CatalogItem,
  Exercise,
  ExerciseRef,
  MuscleGroup,
  Plan,
  SetValues,
  Template,
  TemplateInput,
  Workout,
  WorkoutSummary,
  Broadcast,
  Count,
  Dashboard,
  Day,
  ManualMealInput,
  Meal,
  MealHistoryItem,
  Me,
  Prefs,
  ProfileInput,
  Progress,
  Promo,
  PromoInput,
  Referral,
  Referrer,
  Segment,
  UserDetail,
  UserFilter,
  UserPage,
  UserPatch,
  UserSort,
  WeightPoint,
  WorkoutSet,
} from "./types";
import { type Lang, tr } from "../lib/i18n";

const TOKEN_KEY = "belok.token";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }
}

let token: string | null = readToken();
let onUnauthorized: () => void = () => {};

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(value: string | null) {
  token = value;
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage can be unavailable in private mode; the in-memory token still works
  }
}

export const hasToken = () => token !== null;

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const response = await fetch(`/api${path}`, { method, headers, body: payload });
  if (response.status === 401) {
    setToken(null);
    onUnauthorized();
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      // non-JSON error body
    }
    throw new ApiError(response.status, detail);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  config: () => request<{ bot_username: string | null }>("GET", "/config"),
  authWebApp: (initData: string) =>
    request<{ token: string }>("POST", "/auth/webapp", { init_data: initData }),
  authWidget: (data: Record<string, string | number>) =>
    request<{ token: string }>("POST", "/auth/widget", data),

  me: () => request<Me>("GET", "/me"),
  saveProfile: (body: ProfileInput) => request<Me>("PUT", "/me/profile", body),
  setLanguage: (language: Lang) => request<Me>("PUT", "/me/language", { language }),

  day: (day?: string) => request<Day>("GET", day ? `/day?day=${day}` : "/day"),
  mealFromText: (text: string) => request<Meal>("POST", "/meals/text", { text }),
  mealFromPhoto: (photo: Blob, note: string) => {
    const form = new FormData();
    form.append("photo", photo, "meal.jpg");
    if (note) form.append("note", note);
    return request<Meal>("POST", "/meals/photo", form);
  },
  scaleMeal: (id: number, scale: number) => request<Meal>("PATCH", `/meals/${id}`, { scale }),
  deleteMeal: (id: number) => request<void>("DELETE", `/meals/${id}`),
  mealManual: (body: ManualMealInput) => request<Meal>("POST", "/meals/manual", body),
  mealHistory: (sort: "frequent" | "recent") =>
    request<MealHistoryItem[]>("GET", `/meals/history?sort=${sort}`),
  repeatMeal: (id: number) => request<Meal>("POST", `/meals/${id}/repeat`),
  resizeMealItem: (mealId: number, itemId: number, grams: number) =>
    request<Meal>("PATCH", `/meals/${mealId}/items/${itemId}`, { grams }),
  deleteMealItem: (mealId: number, itemId: number) =>
    request<Meal>("DELETE", `/meals/${mealId}/items/${itemId}`),

  weights: () => request<WeightPoint[]>("GET", "/weights"),
  saveWeight: (weight_kg: number) => request<void>("PUT", "/weights/today", { weight_kg }),
  saveSteps: (steps: number) => request<void>("PUT", "/steps/today", { steps }),

  catalog: () => request<CatalogItem[]>("GET", "/catalog"),
  catalogItem: (id: string) => request<CatalogDetail>("GET", `/catalog/${encodeURIComponent(id)}`),
  exercises: () => request<Exercise[]>("GET", "/exercises"),
  createExercise: (name: string, group: MuscleGroup | null, cardio: boolean) =>
    request<Exercise>("POST", "/exercises", { name, group, cardio }),
  resolveExercise: (ref: ExerciseRef) => request<Exercise>("POST", "/exercises/resolve", ref),
  progress: (exerciseId: number) => request<Progress>("GET", `/exercises/${exerciseId}/progress`),
  analytics: () => request<Analytics>("GET", "/analytics"),

  workouts: (beforeId?: number) =>
    request<WorkoutSummary[]>("GET", beforeId ? `/workouts?before_id=${beforeId}` : "/workouts"),
  activeWorkout: () => request<Workout | null>("GET", "/workouts/active"),
  workout: (id: number) => request<Workout>("GET", `/workouts/${id}`),
  startWorkout: (templateId?: number, fromWorkoutId?: number) =>
    request<Workout>("POST", "/workouts", {
      template_id: templateId ?? null,
      from_workout_id: fromWorkoutId ?? null,
    }),
  patchWorkout: (id: number, body: { title?: string | null; finished?: boolean }) =>
    request<Workout>("PATCH", `/workouts/${id}`, body),
  deleteWorkout: (id: number) => request<void>("DELETE", `/workouts/${id}`),
  addWorkoutExercise: (id: number, ref: ExerciseRef, sets = 3) =>
    request<Workout>("POST", `/workouts/${id}/exercises`, { ...ref, sets }),
  removeWorkoutExercise: (id: number, exerciseId: number) =>
    request<Workout>("DELETE", `/workouts/${id}/exercises/${exerciseId}`),
  addSet: (workoutId: number, exerciseId: number, values: SetValues) =>
    request<WorkoutSet & { record: boolean }>("POST", `/workouts/${workoutId}/sets`, {
      exercise_id: exerciseId,
      ...values,
    }),
  patchSet: (id: number, values: SetValues) => request<WorkoutSet>("PATCH", `/sets/${id}`, values),
  deleteSet: (id: number) => request<void>("DELETE", `/sets/${id}`),

  templates: () => request<Template[]>("GET", "/templates"),
  createTemplate: (body: TemplateInput) => request<Template>("POST", "/templates", body),
  updateTemplate: (id: number, body: TemplateInput) =>
    request<Template>("PUT", `/templates/${id}`, body),
  deleteTemplate: (id: number) => request<void>("DELETE", `/templates/${id}`),

  plans: () => request<Plan[]>("GET", "/payments/plans"),
  redeemPromo: (code: string) =>
    request<{ days: number; access_until: string }>("POST", "/me/promo", { code }),
  referral: () => request<Referral>("GET", "/me/referral"),
};

export interface UserQuery {
  q: string;
  filter: UserFilter;
  sort: UserSort;
  desc: boolean;
  offset: number;
  limit: number;
}

export const adminApi = {
  dashboard: () => request<Dashboard>("GET", "/admin/dashboard"),
  users: (query: UserQuery) => {
    const params = new URLSearchParams({
      filter: query.filter,
      sort: query.sort,
      desc: String(query.desc),
      offset: String(query.offset),
      limit: String(query.limit),
    });
    if (query.q.trim()) params.set("q", query.q.trim());
    return request<UserPage>("GET", `/admin/users?${params}`);
  },
  user: (id: number) => request<UserDetail>("GET", `/admin/users/${id}`),
  patchUser: (id: number, body: UserPatch) => request<UserDetail>("PATCH", `/admin/users/${id}`, body),
  grant: (id: number, days: number) =>
    request<UserDetail>("POST", `/admin/users/${id}/grant`, { days }),
  revoke: (id: number) => request<UserDetail>("POST", `/admin/users/${id}/revoke`),
  message: (id: number, text: string) =>
    request<void>("POST", `/admin/users/${id}/message`, { text }),
  deleteUser: (id: number) => request<void>("DELETE", `/admin/users/${id}`),

  promos: () => request<Promo[]>("GET", "/admin/promos"),
  createPromo: (body: PromoInput) => request<Promo>("POST", "/admin/promos", body),
  patchPromo: (id: number, body: { active?: boolean }) =>
    request<Promo>("PATCH", `/admin/promos/${id}`, body),

  segments: () => request<Count[]>("GET", "/admin/segments"),
  broadcasts: () => request<Broadcast[]>("GET", "/admin/broadcasts"),
  createBroadcast: (text: string, segment: Segment) =>
    request<Broadcast>("POST", "/admin/broadcasts", { text, segment }),
  sendBroadcast: (id: number) => request<Broadcast>("POST", `/admin/broadcasts/${id}/send`),
  cancelBroadcast: (id: number) => request<Broadcast>("POST", `/admin/broadcasts/${id}/cancel`),

  referrals: () => request<Referrer[]>("GET", "/admin/referrals"),
  actions: (offset: number) => request<AdminAction[]>("GET", `/admin/actions?offset=${offset}`),
  prefs: () => request<Prefs>("GET", "/admin/prefs"),
  savePrefs: (body: Partial<Prefs>) => request<Prefs>("PUT", "/admin/prefs", body),
};

const messages = (): Record<string, string> => ({
  daily_limit: tr("На сегодня лимит распознаваний исчерпан", "You've hit today's analysis limit"),
  analysis_failed: tr(
    "Не получилось посчитать, попробуй ещё раз чуть позже",
    "Couldn't analyze that, please try again a bit later",
  ),
  no_food: tr(
    "Не вижу здесь еды. Попробуй другое фото или опиши текстом",
    "I don't see any food here. Try another photo or describe it",
  ),
  image_too_large: tr("Фото слишком большое", "The photo is too large"),
  unsupported_image: tr("Поддерживаются JPEG, PNG и WebP", "Only JPEG, PNG and WebP are supported"),
  not_found: tr("Не найдено", "Not found"),
  expired: tr("Срок действия промокода истёк", "This promo code has expired"),
  exhausted: tr(
    "Промокод уже использовали максимальное число раз",
    "This promo code has reached its usage limit",
  ),
  already_used: tr("Ты уже активировал этот промокод", "You've already redeemed this promo code"),
  new_users_only: tr(
    "Этот промокод только для новых пользователей",
    "This promo code is for new users only",
  ),
  too_many_attempts: tr(
    "Слишком много попыток, попробуй через час",
    "Too many attempts, try again in an hour",
  ),
  blocked: tr("Доступ ограничен", "Access restricted"),
  admin_only: "Только для админов",
  cannot_change_self: "Нельзя заблокировать, удалить или разжаловать себя",
  cannot_block_admin: "Сначала сними с пользователя права админа",
  code_taken: "Такой промокод уже есть",
  invalid_message: "Telegram не принял сообщение, проверь HTML-разметку",
  telegram_unavailable: "Telegram недоступен, попробуй позже",
  invalid_state: "Рассылка уже запущена или завершена",
});

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return messages()[error.detail] ?? tr("Что-то пошло не так", "Something went wrong");
  }
  return tr("Нет связи с сервером", "Can't reach the server");
}
