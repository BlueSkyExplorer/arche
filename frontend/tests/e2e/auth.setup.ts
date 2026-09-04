import { expect, test as setup } from "@playwright/test";
import { mkdir } from "node:fs/promises";

const authFile = "tests/e2e/.auth/user.json";

setup("sign in with the development stub", async ({ page }) => {
  await mkdir("tests/e2e/.auth", { recursive: true });
  await page.goto("/login");
  await page.getByLabel("Email").fill("demo@example.com");
  await page.getByLabel("Development token").fill("e2e-browser-token");
  await page.getByRole("button", { name: "Sign in / 登入" }).click();
  await expect(page).toHaveURL(/\/papers$/);
  await expect(page.getByRole("heading", { name: "Papers / 試卷" })).toBeVisible();
  await page.context().storageState({ path: authFile });
});
