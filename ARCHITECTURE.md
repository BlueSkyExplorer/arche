# ARCHITECTURE.md

## 1. Architecture Goal

Build the MVP as a small, maintainable web application with a deterministic document-rendering backend.

The architecture should optimize for:

- correctness of question content;
- repeatable school formatting;
- editable DOCX output;
- Chinese/English support;
- simple deployment;
- clear boundaries for later OCR/AI expansion.

Do not optimize prematurely for school-wide scale, microservices, or complex distributed processing.

## 2. Proposed Stack

### Frontend

- Next.js with App Router
- React
- TypeScript in strict mode
- Tailwind CSS
- shadcn/ui for accessible UI primitives
- TipTap/ProseMirror for structured rich-text question editing
- React Hook Form + Zod for forms and client-side validation

### Backend

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic
- PostgreSQL

Python is preferred for the document service because the ecosystem for DOCX/PDF/document parsing and future OCR/AI work is stronger and easier to extend.

### Authentication / Storage

MVP default:

- Supabase Auth for authentication;
- PostgreSQL as the application database;
- Supabase Storage or another S3-compatible object store for logos, question images, and exports.

Keep storage access behind a small adapter so the provider can be changed later.

### Document Processing

- `python-docx` for DOCX construction and low-level document control;
- direct OOXML helpers only where `python-docx` does not expose required features;
- LibreOffice headless in the backend container for best-effort DOCX -> PDF conversion;
- open-source CJK fonts installed in the backend image for predictable server-side rendering.

Do not use an LLM to decide final layout.

## 3. High-Level System

```text
Browser
   |
   v
Next.js frontend
   |
   | HTTPS / JSON
   v
FastAPI backend
   |---------------------> PostgreSQL
   |                         metadata + structured content
   |
   |---------------------> Object storage
   |                         logos + images + exports
   |
   v
Document renderer
   |-- structured paper + template profile
   |-- python-docx / OOXML
   v
DOCX
   |
   +--> optional LibreOffice conversion --> PDF
```

## 4. Repository Layout

```text
repo/
├── PRODUCT.md
├── MVP.md
├── ARCHITECTURE.md
├── AGENTS.md
├── frontend/
│   ├── AGENTS.md
│   ├── package.json
│   └── src/
│       ├── app/
│       ├── components/
│       ├── features/
│       └── lib/
└── backend/
    ├── AGENTS.md
    ├── pyproject.toml
    ├── app/
    │   ├── main.py
    │   ├── api/
    │   ├── core/
    │   ├── models/
    │   ├── schemas/
    │   ├── services/
    │   └── document/
    ├── migrations/
    └── tests/
```

## 5. Domain Model

### Workspace

```text
id
name
owner_user_id
created_at
updated_at
```

All other business objects must carry `workspace_id`.

### TemplateProfile

```text
id
workspace_id
name
version
school_name
logo_asset_id
page_config_json
typography_config_json
header_config_json
footer_config_json
numbering_config_json
section_style_config_json
question_style_config_json
is_active
created_at
updated_at
```

Store constrained style settings as validated JSON objects rather than arbitrary CSS or raw OOXML.

### Question

```text
id
workspace_id
internal_title
subject
level
tags_json
source_note
content_json
marks
status
created_at
updated_at
```

`content_json` is the canonical rich-text representation. It should be compatible with the editor schema and contain references to separately stored assets.

### Asset

```text
id
workspace_id
kind
storage_key
mime_type
size_bytes
width
height
created_at
```

### Paper

```text
id
workspace_id
template_profile_id
title
subject
level
paper_date
duration_minutes
instructions_json
status
created_at
updated_at
```

### PaperSection

```text
id
paper_id
title
instructions_json
position
```

### PaperQuestion

```text
id
paper_section_id
question_id
position
marks_override
settings_json
```

### Export

```text
id
workspace_id
paper_id
template_version
format
status
storage_key
error_message
created_at
```

## 6. API Boundaries

Use REST/JSON for the MVP.

Representative endpoints:

```text
GET    /api/v1/templates
POST   /api/v1/templates
GET    /api/v1/templates/{id}
PATCH  /api/v1/templates/{id}
POST   /api/v1/templates/import

GET    /api/v1/questions
POST   /api/v1/questions
GET    /api/v1/questions/{id}
PATCH  /api/v1/questions/{id}
DELETE /api/v1/questions/{id}
POST   /api/v1/questions/ingest

GET    /api/v1/papers
POST   /api/v1/papers
GET    /api/v1/papers/{id}
PATCH  /api/v1/papers/{id}
POST   /api/v1/papers/{id}/sections
POST   /api/v1/papers/{id}/export?format=docx
POST   /api/v1/papers/{id}/export?format=pdf

POST   /api/v1/exam-imports/{id}/answer-sheet-preview
POST   /api/v1/exam-imports/{id}/answer-sheet-exports
GET    /api/v1/answer-sheet-exports/{id}
GET    /api/v1/answer-sheet-exports/{id}/download

POST   /api/v1/assets
GET    /api/v1/exports/{id}
```

API schemas are owned by the backend OpenAPI definition. Frontend API types should be generated from OpenAPI once the API stabilizes instead of being manually duplicated.

## 7. Rich-Text Canonical Format

Do not store question content as HTML alone and do not store raw DOCX XML as the source of truth.

Use a structured ProseMirror/TipTap-compatible JSON tree for supported blocks such as:

- paragraph;
- heading where allowed;
- text with marks;
- bullet/ordered list;
- table;
- image reference;
- explicit sub-question block;
- answer-space block.

The frontend edits this structure. The backend validates it and maps it to DOCX elements.

This separates content from school formatting and makes template reuse possible.

## 8. Rendering Pipeline

```text
Paper ID
  -> load paper + sections + ordered questions
  -> authorize workspace access
  -> validate content schema
  -> calculate numbering and total marks
  -> load immutable template-profile version
  -> build normalized render tree
  -> map render tree to DOCX styles/elements
  -> attach header/footer/logo/page settings
  -> save DOCX
  -> store export record/file
  -> optionally convert DOCX to PDF
```

### Important rule

Question content and layout are separate layers:

```text
Question content = what the teacher wrote
Template profile = how the school wants it displayed
Renderer = deterministic mapping between them
```

## 9. DOCX Strategy

Generate DOCX from a controlled renderer rather than trying to modify arbitrary uploaded Word files.

The renderer should define named internal styles such as:

```text
PaperTitle
PaperMetadata
SectionHeading
QuestionBody
QuestionSubpart
QuestionMarks
AnswerSpace
```

The selected `TemplateProfile` maps those semantic roles to font, size, spacing, alignment, indentation, and numbering rules.

Use XML-level helpers only when necessary for:

- page numbering fields;
- section/page settings not exposed by `python-docx`;
- advanced numbering definitions;
- controlled header/footer fields.

Keep these helpers isolated under `backend/app/document/ooxml/` and test them with fixtures.

Uploaded source documents are accepted as `.docx` or legacy `.doc`; `.doc` files are first converted to `.docx` by headless LibreOffice (`app/services/doc_convert.py`, reusing the `LIBREOFFICE_BIN` setting and the same invocation shape as PDF conversion). Macro-enabled `.docm` is rejected.

Completed answer sheets use a parallel domain entry point but the same renderer,
OOXML, storage, template-validation, and authorization infrastructure. Their
semantic source is the reviewed AnsSheet snapshot, not Question Library or
Paper. See ADR-0010.

### Legacy `.doc` diagram dependency (answer sheets)

Answer-sheet images are preserved losslessly, never OCR'd:

- A `.docx` with relationship-backed inline images needs no extra runtime — the
  DOCX parser captures them via existing `asset_manifest`/`cell_assets` paths.
- A legacy `.doc` whose diagrams arrive as grouped Word drawings after the
  LibreOffice conversion is rasterized to PNG through LibreOffice's UNO
  `GraphicExportFilter` (`app/services/docx_shapes.py`). This requires, in the
  backend container: `LIBREOFFICE_BIN` (soffice) **and**
  `LIBREOFFICE_PYTHON_BIN` pointing at the LibreOffice-bundled UNO-capable
  Python (e.g. `<lo>/program/python`). No OCR or interpretation is involved.
- If that runtime is absent or the drawing count is ambiguous, the import still
  succeeds but each unresolved drawing is recorded as an `UnsupportedAnswerContent`
  block, which **blocks export** with a `unsupported_answer_content` validation
  issue — a missing/ambiguous image is never silently dropped, and never
  replaced with inferred content.

## 10. PDF Strategy

PDF is derived output, not the canonical document.

```text
DOCX -> LibreOffice headless -> PDF
```

Rules:

- DOCX export must still succeed if PDF conversion fails.
- Apply a conversion timeout.
- Capture conversion logs.
- Do not accept macro-enabled documents.
- Install the expected server fonts explicitly.
- Treat pagination differences between Microsoft Word and LibreOffice as a known constraint.

## 11. AI Boundary

The AI layer is optional and replaceable.

A future `QuestionStructureService` may accept pasted text and return a proposed structured question. It must return data conforming to a strict schema.

```text
raw pasted content
   -> optional AI parser
   -> schema validation
   -> user review/edit
   -> saved canonical question
```

Never call an LLM during deterministic paper rendering.

Never let AI silently replace the user's original content.

## 12. Security and Privacy

- Validate authorization using `workspace_id` on every business operation.
- Never trust a frontend-supplied workspace ID without verifying membership/ownership.
- Use signed URLs or backend-mediated access for private files.
- Validate MIME type, extension, and size for uploads.
- Sanitize filenames and never use user filenames as storage paths directly.
- Reject executable/macro-enabled Office formats in the MVP.
- Keep service-role/API secrets on the backend only.
- Do not log question bodies, access tokens, or private file URLs by default.
- Apply rate limits to expensive export endpoints.

## 13. Testing Strategy

### Backend

- unit tests for numbering and mark calculation;
- unit tests for content-schema validation;
- authorization tests for workspace isolation;
- renderer tests for paragraphs, sub-parts, images, tables, headers/footers;
- golden/fixture-based DOCX tests for important output structure;
- API integration test for create paper -> export DOCX.

### Frontend

- component tests for template form and question editor behavior;
- builder tests for ordering and mark totals;
- one critical end-to-end flow: sign in -> create paper -> add question -> export.

Do not rely only on screenshot tests for document correctness.

## 14. Local Development

Expected services:

```text
frontend:  localhost:3000
backend:   localhost:8000
postgres:  local or managed development database
storage:   Supabase dev project or S3-compatible local/test bucket
```

Suggested commands after scaffolding:

```bash
# frontend
cd frontend
pnpm install
pnpm dev
pnpm lint
pnpm typecheck
pnpm test

# backend
cd backend
uv sync
uv run fastapi dev app/main.py
uv run ruff check .
uv run mypy app
uv run pytest
```

These commands become authoritative only after the corresponding manifests/configuration exist. If the implementation uses different commands, update all relevant `AGENTS.md` files immediately.

## 15. Deployment Shape

MVP deployment should remain simple:

```text
Next.js frontend -> managed web host
FastAPI + LibreOffice -> one Dockerized Linux service
PostgreSQL -> managed database
Object storage -> managed private bucket
```

Do not split the renderer into a separate microservice until workload or isolation needs justify it.

## 16. Evolution Path

Add capabilities in this order only when evidence justifies them:

1. improve DOCX fidelity;
2. improve template configuration UX;
3. import existing DOCX and infer a template profile;
4. OCR/PDF ingestion;
5. shared school/department workspaces;
6. semantic search;
7. AI question assistance;
8. asynchronous export workers if export load requires them.
