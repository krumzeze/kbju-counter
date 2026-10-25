import type {
  Day,
  Meal,
  Me,
  ProfileInput,
  Progress,
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
};

const MESSAGES: Record<string, string> = {
  daily_limit: "На сегодня лимит распознаваний исчерпан",
  analysis_failed: "Не получилось посчитать, попробуй ещё раз чуть позже",
  no_food: "Не вижу здесь еды. Попробуй другое фото или опиши текстом",
  image_too_large: "Фото слишком большое",
  unsupported_image: "Поддерживаются JPEG, PNG и WebP",
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return MESSAGES[error.detail] ?? "Что-то пошло не так";
  return "Нет связи с сервером";
}
