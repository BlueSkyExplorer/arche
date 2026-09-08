# Alignment — User's Two-Document Workflow vs. Current System

Date: 2026-09-08 · Repo: `/opt/data/projects/arche` @ `1ec3e50`

The user's expected workflow:

> 老師提供兩份資料: (1) 學校 Standard 出卷格式文件(含答題線等) (2) 整理好的題目集
> 系統把題目套用格式,輸出一份新卷。

This table maps each expectation to the current system behavior, citing the exact code.

## Expectation vs. Reality

| # | User expectation | Current behavior | Gap? | Evidence |
|---|---|---|---|---|
| 1 | 提供學校格式**文件**(上傳) | 格式只能**逐欄手動填寫**,不能上傳文件 | ❌ GAP | `backend/app/api/v1/routes/templates.py` — `POST /api/v1/templates` 只接受結構化 JSON(`TemplateProfileCreate`,`backend/app/schemas/template_profile.py`,schema `extra="forbid"`) |
| 2 | 格式文件含**頁面/字型/頁首頁尾/編號**等 | 這些欄位都存在,但全靠手動輸入 | ◑ 半 | `TemplateProfileCreate` 有 `page_config_json`(size/margins)、`typography_config_json`(字型/大小/行距)、`header/footer_config_json`、`numbering_config_json` — 欄位齊,缺「從文件自動填入」 |
| 3 | 格式文件含**答題線**設定 | `question_style_config_json.default_answer_lines` 存在,但只能手動設數字 | ◑ 半 | `backend/app/schemas/template_profile.py:60-63` `QuestionStyleConfig` |
| 4 | 提供整理好的題目集(一份) | 只能**逐題**建立:每題一個 POST | ❌ GAP | `backend/app/api/v1/routes/questions.py` `POST /api/v1/questions`(單題);無 bulk/ingest endpoint |
| 5 | 套用格式出**新卷** | ✅ 已實作且實測通過 | ✅ MATCH | `PUT /papers/{id}/sections/{sid}/questions` + `POST /papers/{id}/export?format=docx|pdf` → `GET /exports/{id}/download`;E2E 全通過(pytest 66 passed, PDF 32KB) |
| 6 | 題目**子題/分數**結構化 | 單題編輯器支援子題/分數(`DocNode` content_json),但無自動切分 | ◑ 半 | `backend/app/schemas/question.py`;`frontend/src/features/questions/editor/question-editor.tsx`(TipTap 單題編輯) |
| 7 | 教師內容**不被竄改** | ✅ 產品原則 1 + renderer 不碰 wording;輸出前需審查 | ✅ MATCH | `PRODUCT.md §5.1`、`MVP.md §7`、`AGENTS.md` |
| 8 | 上傳格式文件的方式 | 上傳基礎設施已存在(`POST /api/v1/assets`,multipart,workspace 私有),但未接到模板/題目流程 | ◑ 半 | `backend/app/api/v1/routes/assets.py:20-36` |
| 9 | 掃描 PDF/圖片 OCR | ❌ 目前**完全無 OCR**;且被 `MVP.md §6` 明列 out-of-scope | ❌ DEFERRED | `MVP.md §6`:"bulk PDF question extraction"、"OCR from scanned papers" |

## Scope boundary (explicit, per `MVP.md §6` + `ARCHITECTURE.md §16`)

- **In scope now (iteration 1):** 格式 DOCX → best-effort 映射模板草稿(教師審查後存);題目集貼文字 / **.docx 上傳** → 自動切分草稿(教師勾選後存)。純規則、確定性、無 LLM 依賴、教師可審查。
- **Deferred (later iteration):** PDF/圖片 OCR(題目集)、完美複製任意學校格式(`MVP.md §6`:「automatic cloning of arbitrary school DOCX/PDF formats」out of scope)。

## Decisions recorded

- **2026-09-08 (user):** 題目集迭代 1 = 貼文字 + .docx 上傳;PDF/圖片(OCR)之後再加。
- **2026-09-08 (plan):** 格式導入 = 「自動映射 + 教師審查」,不宣稱像素級複製。AI 輔助結構辨識 = 可選/env-flagged,預設純規則(YAGNI)。

## What is NOT a gap (matches today)

- 紙上組裝(sections/questions/順序)、總分計算、DOCX/PDF 匯出、workspace 私有、中文/英文混合、macro(.docm)拒絕 — 全部已符合且可驗證。

## Follow-up ideas (not planned, for future iterations)

- PDF/圖片題目抽取 + OCR(`MVP.md §6` 需先 scope change)。
- 完整匯入既有 DOCX 並推斷模板(`ARCHITECTURE.md §16 #3` — 本計畫做 **best-effort** 版本,不承諾完整)。
- AI 結構辨識輔助(env 旗標,可審查,非必要)。