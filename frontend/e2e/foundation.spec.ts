import { expect, test } from "@playwright/test";

test.describe("UI foundation", () => {
  test("home page renders hero and primary actions", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Buy, sell & share with neighbors");
    await expect(page.getByRole("link", { name: /Snap & sell/ })).toBeVisible();
    await expect(page.getByRole("link", { name: "Browse listings" })).toBeVisible();
  });

  test("language toggle switches UI to Telugu and persists", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "తెలుగు" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("పొరుగువారితో కొనండి, అమ్మండి, పంచుకోండి");
    await expect(page.locator("html")).toHaveAttribute("lang", "te");

    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "te");

    await page.getByRole("button", { name: "EN" }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
  });

  test("Telugu is chosen from Accept-Language on first visit", async ({ browser }) => {
    const ctx = await browser.newContext({ locale: "te-IN" });
    const page = await ctx.newPage();
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("lang", "te");
    await ctx.close();
  });

  test("browse page has search and listing-type filters", async ({ page }) => {
    await page.goto("/listings?listing_type=free");
    await expect(page.getByRole("heading", { name: "Browse listings" })).toBeVisible();
    await expect(page.getByRole("searchbox").or(page.getByPlaceholder("Search listings"))).toBeVisible();
    await expect(page.getByRole("link", { name: "Free", exact: true })).toHaveAttribute("aria-current", "page");
  });

  test("account page requires sign-in", async ({ page }) => {
    await page.goto("/account");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: "Sign in to Community Connect" })).toBeVisible();
  });

  test("unknown routes show a friendly 404", async ({ page }) => {
    const res = await page.goto("/does-not-exist");
    expect(res?.status()).toBe(404);
    await expect(page.getByText("Page not found")).toBeVisible();
  });
});
