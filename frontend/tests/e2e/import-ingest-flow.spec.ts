import { expect, test } from "@playwright/test";
import path from "node:path";

const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
const templateName = `Imported ${suffix}`;
const fixturePath = path.resolve("../backend/tests/fixtures/school_format.docx");

test.describe.serial("two-document import + ingest", () => {
  test("import a format DOCX into a template, review and save", async ({ page }) => {
    await page.goto("/templates");
    await page.getByLabel("Import DOCX file").setInputFiles(fixturePath);

    // Review banner appears; mapped values land in the form.
    const dialog = page.locator('[role="dialog"]').last();
    await expect(dialog.getByText(/已從 DOCX 匯入/)).toBeVisible();
    await expect(dialog.getByLabel("School name / 學校名稱")).toHaveValue("ST. MARY'S COLLEGE");
    await expect(dialog.getByLabel("Chinese font / 中文字體")).toHaveValue("Noto Sans CJK");

    // Teacher supplies the template name, then saves.
    await dialog.getByLabel("Template name / 範本名稱").fill(templateName);
    await dialog.getByRole("button", { name: "Save / 儲存" }).click();

    await expect(page.getByText(templateName, { exact: true })).toBeVisible();
    await expect(page.getByText("ST. MARY'S COLLEGE").first()).toBeVisible();
  });

  test("paste a question set, review drafts, save selected", async ({ page }) => {
    await page.goto("/questions");
    await page.getByLabel("Paste question set / 貼上題目集").fill(
      "1. Solve 2 + 2. (2 marks)\n\na) 2\nb) 4\n\n2. 計算 12 × 4。 （2分）",
    );
    await page.getByLabel("Subject / 科目").fill("Mathematics 數學");
    await page.getByLabel("Level / 級別").fill("Form 2 中二");
    await page.getByRole("button", { name: /Parse text/ }).click();

    await expect(page.getByText(/2 drafts/)).toBeVisible();
    await expect(page.locator("p.font-medium", { hasText: "Solve 2 + 2" })).toBeVisible();
    await expect(page.locator("p.font-medium", { hasText: "計算 12 × 4" })).toBeVisible();

    await page.getByRole("button", { name: /Save 2/ }).click();
    await expect(page.getByText(/Saved 2 question/)).toBeVisible();

    // Saved questions appear in the library list below.
    await expect(page.getByRole("heading", { name: /Solve 2 \+ 2/ }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: /計算 12 × 4/ }).first()).toBeVisible();
  });
});
