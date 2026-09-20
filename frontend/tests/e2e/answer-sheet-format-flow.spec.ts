import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";

// Full smoke: template import (format only) → answer-sheet import → review →
// approve → completed → format → preview → export DOCX. Drives the real UI and
// complements the deterministic render/export checks in the backend suite.

const API_URL = "http://localhost:8000";
const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
const templateName = `E2E AS Template ${suffix}`;
const asFileName = `ans-${suffix}.docx`;

const formatFixture = path.resolve("../backend/tests/fixtures/school_format.docx");
const answerSheetFixture = path.resolve("../backend/tests/fixtures/answer_sheet.docx");

test.describe.serial("answer-sheet format + export smoke", () => {
  test("template → answer sheet → review → approve → format → preview → export DOCX", async ({ page, context }) => {
    // 1. Import a format template (Format template only is the default mode).
    await page.goto("/templates");
    await expect(page.getByLabel("Format template only / 只匯入格式")).toBeChecked();
    await page.getByLabel("Import DOCX file").setInputFiles(formatFixture);
    const templateDialog = page.locator('[role="dialog"]').last();
    await expect(templateDialog.getByText(/已從 DOCX 匯入/)).toBeVisible();
    await templateDialog.getByLabel("Template name / 範本名稱").fill(templateName);
    await templateDialog.getByRole("button", { name: "Save / 儲存" }).click();
    await expect(page.getByText(templateName, { exact: true })).toBeVisible();

    // 2. Upload the answer sheet (deterministic fixture: MCQ 30 + Q1..Q9, 50 vs 51).
    await page.goto("/imports");
    await page.getByLabel("Answer Sheet / 答案卷").check();
    await page.locator('input[type="file"]').setInputFiles({
      name: asFileName,
      mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      buffer: await readFile(answerSheetFixture),
    });
    await page.getByRole("button", { name: /Import \/ 匯入/ }).click();
    const card = page.locator("li").filter({ hasText: asFileName });
    await expect(card).toBeVisible();
    await expect(card.getByText(/待審閱|Needs Review/)).toBeVisible();

    // 3. Review and approve → navigate back to /imports.
    await card.getByRole("link", { name: /Review/ }).click();
    await expect(page).toHaveURL(/\/imports\/[0-9a-f-]+$/);
    await expect(page.getByText(/多項選擇題/)).toBeVisible();
    await page.getByRole("button", { name: /Approve Import \/ 批准匯入/ }).click();
    await expect(page).toHaveURL(/\/imports$/);

    // 4. The completed card shows preserved warnings and a Format / 套用格式 button;
    //    the review page is now read-only.
    const completed = page.locator("li").filter({ hasText: asFileName });
    await expect(completed.getByText(/Completed \/ 已完成/)).toBeVisible();
    await expect(completed.getByText(/\d+ current warning/)).toBeVisible();
    await completed.getByRole("link", { name: /Review/ }).click();
    await expect(page).toHaveURL(/\/imports\/[0-9a-f-]+$/);
    await expect(page.getByText(/Completed answer sheets are read-only/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Save / 儲存" })).toBeDisabled();

    // 5. Open the Format page for the completed answer sheet.
    await page.goto("/imports");
    const formatCard = page.locator("li").filter({ hasText: asFileName });
    await formatCard.getByRole("link", { name: /Format \/ 套用格式/ }).click();
    await expect(page).toHaveURL(/\/imports\/[0-9a-f-]+\/format$/);
    const importId = page.url().split("/").slice(-2, -1)[0];

    // 6. Select the imported template and fill every metadata field.
    await page.getByLabel("Template profile / 格式範本").selectOption({ label: `${templateName} (v1)` });
    await page.getByLabel("School name / 學校名稱").fill("余振強紀念中學");
    await page.getByLabel("Academic year / 學年").fill("2024-2025");
    await page.getByLabel("Exam name / 考試名稱").fill("下學期考試");
    await page.getByLabel("Level / 級別").fill("中四級");
    await page.getByLabel("Subject / 科目").fill("生物科");
    await page.getByLabel("Document type / 文件類型").fill("參考答案");

    // 6. Generate preview → render validation is valid; content is shown.
    await page.getByRole("button", { name: /Generate Preview \/ 產生預覽/ }).click();
    await expect(page.getByText(/Render validation: valid/)).toBeVisible();
    await expect(page.getByText("風媒花的適應特徵")).toBeVisible();
    await expect(page.getByText(/MCQ 30/)).toBeVisible();
    await expect(page.getByText(/images 1/)).toBeVisible();

    // 7. Export DOCX and verify the downloaded package.
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: /Export DOCX/ }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.docx$/);
    const artifact = path.resolve("tests/e2e/artifacts", `answer-sheet-${suffix}.docx`);
    await download.saveAs(artifact);
    const bytes = await readFile(artifact);
    expect(bytes.length).toBeGreaterThan(1024);
    expect([...bytes.subarray(0, 4)]).toEqual([0x50, 0x4b, 0x03, 0x04]); // PK\x03\x04
    // lossless image: a media part and the relationships file exist in the package.
    expect(bytes.includes(Buffer.from("word/media/"))).toBe(true);
    expect(bytes.includes(Buffer.from("word/_rels/document.xml.rels"))).toBe(true);

    // 8. Backend audit: completed import retains its warnings (approval != warning-free).
    const cookie = (await context.cookies()).find(item => item.name === "arche_dev_session");
    expect(cookie).toBeTruthy();
    const session = JSON.parse(Buffer.from(cookie!.value, "base64url").toString("utf8")) as { token: string };
    const detail = await context.request.get(`${API_URL}/api/v1/exam-imports/${importId}`, {
      headers: { Authorization: `Bearer ${session.token}` },
    });
    expect(detail.ok()).toBeTruthy();
    expect(await detail.json()).toMatchObject({
      import_type: "answer_sheet",
      status: "completed",
    });
  });
});