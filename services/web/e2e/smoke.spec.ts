import { expect, type Page, test } from "@playwright/test";
import { type MockOptions, mockApi } from "./mockApi";

const SCREENS = [
  "/",
  "/add",
  "/workouts",
  "/workouts/1",
  "/workouts/2",
  "/catalog",
  "/catalog/Barbell_Bench_Press_-_Medium_Grip",
  "/exercises/1",
  "/analytics",
  "/templates/new",
  "/templates/1",
  "/stats",
  "/profile",
  "/premium",
  "/support",
  "/admin",
  "/admin/users",
  "/admin/users/2",
  "/admin/broadcasts",
  "/admin/promos",
  "/admin/referrals",
  "/admin/system",
  "/admin/log",
  "/admin/settings",
];

async function open(page: Page, path: string, options: MockOptions & { signedIn?: boolean } = {}) {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(`page error: ${error.message}`));
  page.on("console", (msg) => {
    if (msg.type() === "error" && !msg.text().startsWith("Failed to load resource")) {
      problems.push(`console error: ${msg.text()}`);
    }
  });
  await mockApi(page, problems, options);
  if (options.signedIn !== false) {
    await page.addInitScript(() => localStorage.setItem("belok.token", "smoke-token"));
  }

  await page.goto(path);
  await expect(page.locator(".spinner")).toHaveCount(0);
  await expect(page.locator(".state.crash")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(problems).toEqual([]);
}

for (const path of SCREENS) {
  test(`opens ${path}`, async ({ page }) => {
    await open(page, path);
    await expect(page.locator("#root")).not.toBeEmpty();
  });
}

test("shows login when signed out", async ({ page }) => {
  await open(page, "/", { signedIn: false });
  await expect(page.locator(".landing")).toBeVisible();
});

test("asks for language first", async ({ page }) => {
  await open(page, "/", { me: { language: null } });
});

test("starts onboarding with an incomplete profile", async ({ page }) => {
  await open(page, "/", { me: { profile_complete: false, is_admin: false } });
});

test("opens the protein calculator landing", async ({ page }) => {
  await open(page, "/kalkulyator-belka/", { signedIn: false });
  await expect(page.locator("h1")).toBeVisible();
});
