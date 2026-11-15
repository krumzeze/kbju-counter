import { expect, test } from "@playwright/test";
import { TOURS } from "../src/lib/tours";
import { mockApi } from "./mockApi";

const paths = [...new Set(TOURS.map((t) => t.path))];

for (const path of paths) {
  test(`every tutorial step on ${path} finds its target`, async ({ page }) => {
    const tours = TOURS.filter((t) => t.path === path);
    const seen = TOURS.filter((t) => t.path !== path).map((t) => t.id);
    const marked: string[][] = [];
    await mockApi(page, [], { me: { tour_seen: seen } });
    await page.route("**/api/me/tour", async (route) => {
      marked.push(route.request().postDataJSON().ids);
      await route.fulfill({ status: 500, json: { detail: "ignored" } });
    });
    await page.addInitScript(() => localStorage.setItem("belok.token", "smoke-token"));
    await page.goto(path);

    const steps = tours.flatMap((t) => t.steps);
    const card = page.locator(".tour-card");
    await expect(card.locator(".tour-count")).toHaveText(`1 / ${steps.length}`);
    for (const [i, step] of steps.entries()) {
      await expect(card.locator("h3")).toHaveText(step.title[0]);
      await card.getByRole("button", { name: i + 1 === steps.length ? "Понятно" : "Далее" }).click();
    }
    await expect(page.locator(".tour")).toHaveCount(0);
    expect(marked).toEqual([tours.map((t) => t.id)]);
  });
}
