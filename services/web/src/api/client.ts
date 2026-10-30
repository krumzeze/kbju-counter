import type {
  AdminAction,
  Broadcast,
  Count,
  Dashboard,
  Day,
  Meal,
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

  weights: () => request<WeightPoint[]>("GET", "/weights"),
  saveWeight: (weight_kg: number) => request<void>("PUT", "/weights/today", { weight_kg }),
  saveSteps: (steps: number) => request<void>("PUT", "/steps/today", { steps }),

  exercises: () => request<string[]>("GET", "/exercises"),
  addSets: (exercise: string, sets: { weight_kg: number; reps: number }[]) =>
    request<WorkoutSet[]>("POST", "/workouts", { exercise, sets }),
  deleteSet: (id: number) => request<void>("DELETE", `/sets/${id}`),
  progress: (exercise: string) =>
    request<Progress>("GET", `/progress?exercise=${encodeURIComponent(exercise)}`),

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

const MESSAGES: Record<string, string> = {
  daily_limit: "На сегодня лимит распознаваний исчерпан",
  analysis_failed: "Не получилось посчитать, попробуй ещё раз чуть позже",
  no_food: "Не вижу здесь еды. Попробуй другое фото или опиши текстом",
  image_too_large: "Фото слишком большое",
  unsupported_image: "Поддерживаются JPEG, PNG и WebP",
  not_found: "Не найдено",
  expired: "Срок действия промокода истёк",
  exhausted: "Промокод уже использовали максимальное число раз",
  already_used: "Ты уже активировал этот промокод",
  new_users_only: "Этот промокод только для новых пользователей",
  too_many_attempts: "Слишком много попыток, попробуй через час",
  admin_only: "Только для админов",
  blocked: "Доступ ограничен",
  cannot_change_self: "Нельзя заблокировать, удалить или разжаловать себя",
  cannot_block_admin: "Сначала сними с пользователя права админа",
  code_taken: "Такой промокод уже есть",
  invalid_message: "Telegram не принял сообщение, проверь HTML-разметку",
  telegram_unavailable: "Telegram недоступен, попробуй позже",
  invalid_state: "Рассылка уже запущена или завершена",
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return MESSAGES[error.detail] ?? "Что-то пошло не так";
  return "Нет связи с сервером";
}
