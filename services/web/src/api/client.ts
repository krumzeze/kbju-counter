import type {
  AiChatDetail,
  AiChatList,
  AiReply,
  AdminRecipe,
  Recipe,
  RecipeCard,
  RecipeDiaryInput,
  RecipeFilter,
  RecipeInput,
  RecipeItem,
  RecipeScope,
  RecipeStatus,
  AdminAction,
  AppError,
  Barcode,
  Analytics,
  CatalogDetail,
  CatalogItem,
  Exercise,
  ExerciseRef,
  FeatureFlag,
  FeatureKey,
  Health,
  MuscleGroup,
  Plan,
  SetValues,
  Settings,
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
  SupportMessage,
  Referrer,
  Segment,
  UserDetail,
  UserFilter,
  UserPage,
  UserPatch,
  UserSort,
  Stats,
  WeightPoint,
  WorkoutSet,
} from "./types";
import { type Lang, tr } from "../lib/i18n";

// deepcode ignore HardcodedNonCryptoSecret: localStorage key name, not a secret
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
  updateSettings: (body: Settings) => request<Me>("PATCH", "/me/settings", body),
  sendDayCard: () => request<void>("POST", "/me/day-card"),

  aiChats: () => request<AiChatList>("GET", "/assistant/chats"),
  aiChat: (id: number) => request<AiChatDetail>("GET", `/assistant/chats/${id}`),
  aiStart: (text: string) => request<AiReply>("POST", "/assistant/chats", { text }),
  aiSend: (id: number, text: string) => request<AiReply>("POST", `/assistant/chats/${id}/messages`, { text }),
  aiDelete: (id: number) => request<void>("DELETE", `/assistant/chats/${id}`),

  day: (day?: string) => request<Day>("GET", day ? `/day?day=${day}` : "/day"),
  mealFromText: (text: string) => request<Meal>("POST", "/meals/text", { text }),
  mealFromPhoto: (photo: Blob, note: string) => {
    const form = new FormData();
    form.append("photo", photo, "meal.jpg");
    if (note) form.append("note", note);
    return request<Meal>("POST", "/meals/photo", form);
  },
  scaleMeal: (id: number, scale: number) => request<Meal>("PATCH", `/meals/${id}`, { scale }),
  refineMeal: (id: number, text: string) => request<Meal>("POST", `/meals/${id}/refine`, { text }),
  answerMeal: (id: number, text: string) => request<Meal>("POST", `/meals/${id}/answer`, { text }),
  dismissQuestion: (id: number) => request<Meal>("DELETE", `/meals/${id}/question`),
  deleteMeal: (id: number) => request<void>("DELETE", `/meals/${id}`),
  mealManual: (body: ManualMealInput) => request<Meal>("POST", "/meals/manual", body),
  barcode: (code: string) => request<Barcode>("GET", `/barcode/${code}`),
  barcodeFromPhoto: (photo: Blob) => {
    const form = new FormData();
    form.append("photo", photo, "barcode.jpg");
    return request<Barcode>("POST", "/barcode/photo", form);
  },
  mealHistory: (sort: "frequent" | "recent") =>
    request<MealHistoryItem[]>("GET", `/meals/history?sort=${sort}`),
  repeatMeal: (id: number) => request<Meal>("POST", `/meals/${id}/repeat`),

  recipes: (scope: RecipeScope, q: string, filters: RecipeFilter[]) => {
    const params = new URLSearchParams({ scope });
    if (q.trim()) params.set("q", q.trim());
    filters.forEach((f) => params.append("filters", f));
    return request<RecipeCard[]>("GET", `/recipes?${params}`);
  },
  recipeSuggestions: () => request<RecipeCard[]>("GET", "/recipes/suggestions"),
  recipe: (id: number) => request<Recipe>("GET", `/recipes/${id}`),
  createRecipe: (body: RecipeInput) => request<Recipe>("POST", "/recipes", body),
  updateRecipe: (id: number, body: RecipeInput) => request<Recipe>("PUT", `/recipes/${id}`, body),
  deleteRecipe: (id: number) => request<void>("DELETE", `/recipes/${id}`),
  forkRecipe: (id: number) => request<Recipe>("POST", `/recipes/${id}/fork`),
  cookRecipe: (id: number) => request<void>("POST", `/recipes/${id}/cook`),
  favoriteRecipe: (id: number, on: boolean) =>
    request<void>(on ? "PUT" : "DELETE", `/recipes/${id}/favorite`),
  rateRecipe: (id: number, stars: number) => request<Recipe>("PUT", `/recipes/${id}/rating`, { stars }),
  recipeToDiary: (id: number, body: RecipeDiaryInput) => request<Meal>("POST", `/recipes/${id}/diary`, body),
  publishRecipe: (id: number, author_name: string) =>
    request<Recipe>("POST", `/recipes/${id}/publish`, { author_name }),
  uploadRecipePhoto: (photo: Blob) => {
    const form = new FormData();
    form.append("photo", photo, "recipe.jpg");
    return request<{ photo: string; photo_url: string | null }>("POST", "/recipes/photos", form);
  },
  parseIngredients: (text: string) => request<RecipeItem[]>("POST", "/recipes/ingredients", { text }),
  resizeMealItem: (mealId: number, itemId: number, grams: number) =>
    request<Meal>("PATCH", `/meals/${mealId}/items/${itemId}`, { grams }),
  deleteMealItem: (mealId: number, itemId: number) =>
    request<Meal>("DELETE", `/meals/${mealId}/items/${itemId}`),

  weights: () => request<WeightPoint[]>("GET", "/weights"),
  stats: (days: number) => request<Stats>("GET", `/stats?days=${days}`),
  addWater: (delta_ml: number, day: string) =>
    request<{ water_ml: number }>("POST", `/water/today?day=${day}`, { delta_ml }),
  saveWeight: (weight_kg: number) => request<void>("PUT", "/weights/today", { weight_kg }),
  saveSteps: (steps: number, day: string) => request<void>("PUT", `/steps/today?day=${day}`, { steps }),

  catalog: () => request<CatalogItem[]>("GET", "/catalog"),
  catalogItem: (id: string) => request<CatalogDetail>("GET", `/catalog/${encodeURIComponent(id)}`),
  exercises: () => request<Exercise[]>("GET", "/exercises"),
  createExercise: (body: {
    name: string;
    group: MuscleGroup | null;
    cardio: boolean;
    primary: string[];
    secondary: string[];
  }) => request<Exercise>("POST", "/exercises", body),
  setExerciseMuscles: (id: number, primary: string[], secondary: string[]) =>
    request<Exercise>("PUT", `/exercises/${id}/muscles`, { primary, secondary }),
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
  support: () => request<SupportMessage[]>("GET", "/support"),
  sendSupport: (text: string) => request<SupportMessage>("POST", "/support", { text }),
  starsInvoice: (days: number) => request<{ link: string }>("POST", `/payments/stars/${days}`),
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
  features: () => request<FeatureFlag[]>("GET", "/admin/features"),
  setFeature: (key: FeatureKey, enabled: boolean) =>
    request<FeatureFlag[]>("PUT", `/admin/features/${key}`, { enabled }),
  health: () => request<Health>("GET", "/admin/health"),
  errors: () => request<AppError[]>("GET", "/admin/errors"),
  adminRecipes: (status: RecipeStatus) => request<AdminRecipe[]>("GET", `/admin/recipes?status=${status}`),
  approveRecipe: (id: number) => request<Recipe>("POST", `/admin/recipes/${id}/approve`),
  rejectRecipe: (id: number, reason: string) =>
    request<Recipe>("POST", `/admin/recipes/${id}/reject`, { reason }),
  resolveErrors: (fingerprint?: string) =>
    request<void>("DELETE", fingerprint ? `/admin/errors?fingerprint=${fingerprint}` : "/admin/errors"),
};

const messages = (): Record<string, string> => ({
  daily_limit: tr("На сегодня лимит распознаваний исчерпан", "You've hit today's analysis limit"),
  widget_unavailable: tr(
    "Не получилось отправить рецепт в чат, попробуй позже",
    "Couldn't send the recipe to the chat, try later",
  ),
  recipe_not_found: tr("Рецепт не найден или его скрыли", "Recipe not found or hidden"),
  no_photo: tr("Добавь фото блюда", "Add a photo of the dish"),
  no_steps: tr("Опиши хотя бы один шаг", "Describe at least one step"),
  no_items: tr("Добавь хотя бы один продукт", "Add at least one ingredient"),
  cook_first: tr("Оценить можно после того, как добавишь блюдо в дневник", "You can rate it after logging it"),
  invalid_photo: tr("Это фото нельзя использовать", "This photo can't be used"),
  photos_unavailable: tr("Загрузка фото сейчас недоступна", "Photo upload is unavailable right now"),
  invalid_amount: tr("Проверь количество", "Check the amount"),
  invalid_items: tr("Оставь хотя бы один продукт", "Keep at least one ingredient"),
  day_card_unavailable: tr(
    "Не получилось отправить карточку, попробуй позже",
    "Couldn't send the card, try again later",
  ),
  premium_required: tr(
    "Бесплатные распознавания на сегодня закончились. Больше в Premium",
    "You've used today's free recognitions. Get more with Premium",
  ),
  invoice_failed: tr("Не удалось создать счёт, попробуй ещё раз", "Couldn't create the invoice, please try again"),
  too_many_messages: tr("Слишком много сообщений за сутки, подожди немного", "Too many messages today, please wait a little"),
  empty_message: tr("Напиши сообщение", "Write a message"),
  no_question: tr("Этот вопрос уже закрыт", "This question is already closed"),
  too_fast: tr("Слишком быстро, подожди минутку", "Too fast, wait a minute"),
  assistant_busy: tr(
    "Ассистент сейчас перегружен, попробуй позже",
    "The assistant is overloaded right now, try later",
  ),
  assistant_failed: tr(
    "Ассистент не ответил, попробуй ещё раз",
    "The assistant didn't answer, please try again",
  ),
  chat_not_found: tr("Чат не найден", "Chat not found"),
  plan_not_found: tr("Такого тарифа больше нет", "This plan is no longer available"),
  payments_disabled: tr("Оплата временно недоступна", "Payments are temporarily unavailable"),
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
  feature_disabled: tr(
    "Эта функция временно недоступна, попробуй позже",
    "This feature is temporarily unavailable, please try later",
  ),
  adaptive_not_ready: tr(
    "Пока мало данных для расчёта по фактическому расходу",
    "Not enough data yet to use your real expenditure",
  ),
  no_barcode: tr(
    "Не вижу штрихкод. Сфотографируй его ближе и ровнее или введи цифры",
    "Can't find a barcode. Take a closer, straighter photo or type the digits",
  ),
  invalid_barcode: tr("Штрихкод состоит из 8–14 цифр", "A barcode has 8 to 14 digits"),
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

export function reportClientError(message: string, stack?: string) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const body = JSON.stringify({
    message: message.slice(0, 500),
    stack: stack?.slice(0, 8000) ?? null,
    path: location.pathname.slice(0, 256),
  });
  return fetch("/api/client-errors", { method: "POST", headers, body, keepalive: true }).catch(() => {});
}
