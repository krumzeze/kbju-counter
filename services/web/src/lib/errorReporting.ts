import { reportClientError } from "../api/client";

const MAX_REPORTS = 5;
const IGNORED = [/^Script error\.?$/, /ResizeObserver loop/];
const reported = new Set<string>();

export function report(error: unknown, extra?: string) {
  const err = error instanceof Error ? error : new Error(String(error));
  const message = `${err.name}: ${err.message}`;
  if (IGNORED.some((re) => re.test(err.message)) || reported.has(message) || reported.size >= MAX_REPORTS) return;
  reported.add(message);
  void reportClientError(message, [err.stack, extra].filter(Boolean).join("\n\n"));
}

export function installGlobalHandlers() {
  window.addEventListener("error", (e) => report(e.error ?? e.message));
  window.addEventListener("unhandledrejection", (e) => report(e.reason));
}
