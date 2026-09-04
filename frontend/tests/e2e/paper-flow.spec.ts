import { expect, test } from "@playwright/test";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";

const API_URL = "http://localhost:8000";
const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
const templateName = `E2E ${suffix} Template`;
const schoolName = `E2E ${suffix} School`;
const firstQuestion = `E2E ${suffix} Quadratic`;
const secondQuestion = `E2E ${suffix} Linear`;
const paperTitle = `E2E ${suffix} Paper`;
const sectionTitle = "Section A 甲部";
const stem = "解方程 Solve: x² − 5x + 6 = 0，求兩根 find both roots。";

test.describe.serial("critical paper flow", () => {
  test("create a template and question, build and reorder a paper, export and reopen it", async ({ page, context }) => {
    await page.goto("/templates");
    await page.getByRole("button", { name: "New / 新增" }).click();
    let dialog = page.locator('[role="dialog"]').last();
    await dialog.getByLabel("Template name / 範本名稱").fill(templateName);
    await dialog.getByLabel("School name / 學校名稱").fill(schoolName);
    await dialog.getByRole("button", { name: "Save / 儲存" }).click();
    await expect(page.getByText(templateName, { exact: true })).toBeVisible();
    await expect(page.getByText(schoolName)).toBeVisible();

    await page.goto("/questions");
    await page.getByRole("button", { name: "新增題目" }).first().click();
    dialog = page.locator('[role="dialog"]').last();
    await dialog.getByLabel("Internal title / 內部標題").fill(firstQuestion);
    await dialog.getByLabel("Subject / 科目").fill("Mathematics 數學");
    await dialog.getByLabel("Level / 級別").fill("Form 2 中二");
    await dialog.getByLabel("Marks / 分數").fill("10");
    await dialog.getByLabel("Tags / 標籤（逗號分隔）").fill("algebra, 代數");
    const bold = dialog.getByRole("button", { name: "Bold / 粗體" });
    await bold.click();
    await expect(bold).toHaveAttribute("aria-pressed", "true");
    const editor = dialog.locator('[aria-label="Question content / 題目內容"]');
    await editor.click();
    await page.keyboard.type(stem);
    await dialog.getByRole("button", { name: "Save / 儲存" }).click();
    await expect(page.getByRole("heading", { name: firstQuestion })).toBeVisible();
    await expect(page.getByText(/Mathematics 數學 · Form 2 中二 · 10 marks/).first()).toBeVisible();

    await page.goto("/papers");
    await page.getByRole("button", { name: "Create / 建立" }).click();
    dialog = page.locator('[role="dialog"]').last();
    await dialog.getByLabel("Title / 標題").fill(paperTitle);
    await dialog.getByLabel("Subject / 科目").fill("Mathematics 數學");
    await dialog.getByLabel("Level / 班級").fill("Form 2 中二");
    await dialog.getByLabel("Duration (minutes) / 時間").fill("60");
    await dialog.getByLabel("Template / 範本").selectOption({ label: `${templateName} (v1)` });
    await dialog.getByRole("button", { name: "Create / 建立" }).click();
    await expect(page).toHaveURL(/\/papers\/[0-9a-f-]+$/);
    await expect(page.getByRole("heading", { name: paperTitle })).toBeVisible();

    page.once("dialog", async nativeDialog => {
      expect(nativeDialog.type()).toBe("prompt");
      await nativeDialog.accept(sectionTitle);
    });
    await page.getByRole("button", { name: "Add section" }).click();
    await expect(page.getByText(sectionTitle, { exact: true })).toBeVisible();

    await addQuestionFromLibrary(page, firstQuestion);
    let section = page.locator('[data-slot="card"]').filter({ has: page.getByText(sectionTitle, { exact: true }) });
    await expect(questionRow(section, firstQuestion).locator("b")).toHaveText("1.");
    await expect(questionRow(section, firstQuestion)).toContainText("Library marks / 題庫分數: 10");
    await expect(page.getByText("Total / 總分:").locator("..")) .toContainText("10");

    // The login response stores the submitted bearer token in an httpOnly session
    // cookie. Playwright can inspect that cookie from the browser context; decoding
    // it keeps this setup request tied to the token produced by the real login flow.
    const cookie = (await context.cookies()).find(item => item.name === "arche_dev_session");
    expect(cookie).toBeTruthy();
    const session = JSON.parse(Buffer.from(cookie!.value, "base64url").toString("utf8")) as { token: string };
    const seeded = await context.request.post(`${API_URL}/api/v1/questions`, {
      headers: { Authorization: `Bearer ${session.token}` },
      data: {
        internal_title: secondQuestion,
        subject: "Mathematics 數學",
        level: "Form 2 中二",
        tags_json: ["algebra", "代數"],
        source_note: "Playwright setup convenience",
        content_json: { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "Solve x + 1 = 2." }] }] },
        marks: 5,
        status: "ready",
      },
    });
    expect(seeded.ok()).toBeTruthy();

    // Reload refreshes the page's question-library query after the permitted API seed.
    await page.reload();
    await expect(page.getByText(sectionTitle, { exact: true })).toBeVisible();
    await addQuestionFromLibrary(page, secondQuestion);
    section = page.locator('[data-slot="card"]').filter({ has: page.getByText(sectionTitle, { exact: true }) });
    await expect(page.getByText("Total / 總分:").locator("..")) .toContainText("15");
    await questionRow(section, secondQuestion).getByRole("button", { name: "Move question up" }).click();
    await expect(questionRow(section, secondQuestion).locator("b")).toHaveText("1.");
    await expect(questionRow(section, firstQuestion).locator("b")).toHaveText("2.");

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export DOCX" }).click();
    const download = await downloadPromise;
    const artifacts = path.resolve("tests/e2e/artifacts");
    await mkdir(artifacts, { recursive: true });
    const artifact = path.join(artifacts, `${paperTitle}.docx`);
    await download.saveAs(artifact);
    const bytes = await readFile(artifact);
    expect(bytes.length).toBeGreaterThan(4);
    expect([...bytes.subarray(0, 4)]).toEqual([0x50, 0x4b, 0x03, 0x04]);
    await expect(page.getByText("DOCX ready / 已下載")).toBeVisible();

    await page.reload();
    await expect(page.getByText(sectionTitle, { exact: true })).toBeVisible();
    section = page.locator('[data-slot="card"]').filter({ has: page.getByText(sectionTitle, { exact: true }) });
    await expect(questionRow(section, secondQuestion).locator("b")).toHaveText("1.");
    await expect(questionRow(section, firstQuestion).locator("b")).toHaveText("2.");
    await expect(page.getByText("Total / 總分:").locator("..")) .toContainText("15");
  });
});

async function addQuestionFromLibrary(page: import("@playwright/test").Page, title: string) {
  await page.getByRole("button", { name: "Add from library / 從題庫加入" }).click();
  const dialog = page.locator('[role="dialog"]').last();
  await dialog.getByPlaceholder("搜尋 Search: 幾何 / Geometry").fill(title);
  await dialog.getByLabel(new RegExp(title)).check();
  await dialog.getByRole("button", { name: "Append 1 / 加入" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText(title)).toBeVisible();
}

function questionRow(section: import("@playwright/test").Locator, title: string) {
  return section.locator("div.grid").filter({ hasText: title });
}
