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

## Implementation status (2026-09-10)

Both bridges are now usable end-to-end from the UI:

- **Backend (`9112502`)** — `POST /api/v1/templates/import` (DOCX → template draft, no persist) and `POST /api/v1/questions/ingest` (text/docx → question drafts, no persist), both covered by `test_template_import.py` / `test_question_ingest.py`.
- **Frontend** — template import wizard (`frontend/src/features/templates/import-wizard.tsx`) with a review banner wired into the existing template dialog, and a bulk question ingest panel (`frontend/src/features/questions/ingest-panel.tsx`) wired into the question library. The ingest panel collects Subject/Level (required before saving) and saves only accepted drafts.
- **E2E** — `frontend/tests/e2e/import-ingest-flow.spec.ts` covers "import a format DOCX → review → save a template" and "paste a mixed EN/中文 question set → review drafts → save N questions".
- **C7 AI-assisted structure suggestion remains deferred** (open question — the deterministic happy path is complete without it; `MVP.md §5` treats AI as optional and non-blocking).

## Real school file (2026-09-10)

The user provided a real school exam (余振強紀念中學 中四生物科 參考答案) as a **legacy `.doc`** (not `.docx`). This drove iteration 2:

- **`.doc` support** — `backend/app/services/doc_convert.py` converts `.doc → .docx` via the existing headless LibreOffice (`LIBREOFFICE_BIN`), so both `POST /templates/import` and `POST /questions/ingest` now accept `.doc` **and** `.docx` (still rejecting `.docm`). Covered by `test_doc_convert.py` + endpoint cases.
- **Real format conventions captured** (deterministic, no LLM): Chinese marks `（X分）` → `marks_format: "（{marks}分）"` + `marks_display: "right"`; `Q1.`/`Q1` question numbering; two-level sub-question `(a)` → `(i)` via a new `sub_sub_question_style` (default `"roman"`) wired through the renderer; question ingest splits `Q1.`/`第N題` questions, skips 甲部/乙部 section headers, and nests `(i)(ii)` under `(a)(b)(c)`.

**Known limitation (important):** the real school file lays its header, `Q` numbering, and marks out inside **tables**, while the importer scans **plain paragraphs**. For that specific file the importer therefore does **not** auto-detect `school_name`, `Q1.` numbering, or Chinese marks (it defaults `school_name="Imported school"`, `question_style="1."`, `marks_format="({marks} marks)"`), and `ingest` returns 0 drafts from the table-based answer key. The answer-key table layout is content, not a reusable paragraph-format template. This is a heuristic limitation, not a bug — the question-paper (non-answer) file is the right input for the "parse questions" half.

Section labels 甲部/乙部 remain **paper-level** section titles (typed by the teacher in the paper builder) — no auto-section-numbering was added (YAGNI).