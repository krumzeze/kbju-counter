import type { Page } from "@playwright/test";
import * as f from "./fixtures";

type Handler = (url: URL) => unknown;

const routes: [string, RegExp, Handler][] = [
  ["GET", /^\/config$/, () => ({ bot_username: "belok_bot" })],
  ["GET", /^\/me$/, () => f.me],
  ["GET", /^\/me\/referral$/, () => f.referral],
  ["GET", /^\/day$/, () => f.day],
  ["GET", /^\/meals\/history$/, () => f.mealHistory],
  ["GET", /^\/weights$/, () => f.weights],
  ["GET", /^\/stats$/, () => f.stats],
  ["GET", /^\/catalog$/, () => f.catalog],
  ["GET", /^\/catalog\/[^/]+$/, () => f.catalogItem],
  ["GET", /^\/exercises$/, () => f.exercises],
  ["GET", /^\/exercises\/\d+\/progress$/, () => f.progress],
  ["GET", /^\/analytics$/, () => f.analytics],
  ["GET", /^\/workouts$/, (url) => (url.searchParams.has("before_id") ? [] : f.workouts)],
  ["GET", /^\/workouts\/active$/, () => f.activeWorkout],
  ["GET", /^\/workouts\/2$/, () => f.finishedWorkout],
  ["GET", /^\/workouts\/\d+$/, () => f.activeWorkout],
  ["GET", /^\/templates$/, () => f.templates],
  ["GET", /^\/payments\/plans$/, () => f.plans],
  ["GET", /^\/support$/, () => f.support],
  ["GET", /^\/recipes$/, () => [f.recipeCard]],
  ["GET", /^\/recipes\/suggestions$/, () => [f.recipeCard]],
  ["GET", /^\/recipes\/\d+$/, () => f.recipe],
  ["GET", /^\/admin\/recipes$/, () => [f.adminRecipe]],
  ["GET", /^\/admin\/dashboard$/, () => f.dashboard],
  ["GET", /^\/admin\/users$/, () => f.users],
  ["GET", /^\/admin\/users\/\d+$/, () => f.userDetail],
  ["GET", /^\/admin\/promos$/, () => f.promos],
  ["GET", /^\/admin\/segments$/, () => f.segments],
  ["GET", /^\/admin\/broadcasts$/, () => f.broadcasts],
  ["GET", /^\/admin\/referrals$/, () => f.referrers],
  ["GET", /^\/admin\/actions$/, (url) => (Number(url.searchParams.get("offset")) > 0 ? [] : f.actions)],
  ["GET", /^\/admin\/prefs$/, () => f.prefs],
  ["GET", /^\/admin\/features$/, () => f.features],
  ["GET", /^\/admin\/health$/, () => f.health],
  ["GET", /^\/admin\/errors$/, () => f.appErrors],
];

export interface MockOptions {
  me?: Partial<typeof f.me>;
}

export async function mockApi(page: Page, problems: string[], options: MockOptions = {}) {
  const me = { ...f.me, ...options.me };

  await page.route(
    (url) => url.hostname !== "localhost",
    (route) => route.fulfill({ status: 200, body: "" }),
  );

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, "");

    if (path === "/client-errors") {
      problems.push(`client error report: ${request.postData()}`);
      return route.fulfill({ status: 204 });
    }
    const match = routes.find(([method, re]) => method === request.method() && re.test(path));
    if (!match) {
      problems.push(`unmocked API call: ${request.method()} ${path}`);
      return route.fulfill({ status: 404, json: { detail: "not_found" } });
    }
    return route.fulfill({ json: path === "/me" ? me : match[2](url) });
  });
}
