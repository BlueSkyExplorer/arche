# Backend Agent Instructions

Extends the root `AGENTS.md`; these rules take precedence under `backend/`.

## Responsibility

Own:
- authenticated REST API;
- workspace authorization;
- template/question/paper persistence;
- asset metadata/private storage access;
- numbering and mark calculations;
- deterministic DOCX rendering;
- best-effort PDF conversion.

## Stack

- Python 3.12+
- FastAPI + Pydantic
- SQLAlchemy 2 + Alembic + PostgreSQL
- `python-docx` + isolated OOXML helpers
- LibreOffice headless for DOCX -> PDF

No Redis, task queue, or rendering microservice in MVP without measured need.

## Structure

```text
app/
├── api/          thin request/response layer
├── core/         config, auth, infrastructure
├── models/       persistence models
├── schemas/      Pydantic schemas
├── services/     application/domain operations
└── document/
    ├── renderer/
    └── ooxml/    low-level Word XML helpers only
```

Do not put document generation inside API routes.

## Domain Rules

- Enforce workspace authorization on every private read/write.
- Never trust caller-supplied `workspace_id` without verification.
- Canonical question content is structured JSON, not raw DOCX XML.
- Renderer must never change question wording.
- Numbering, marks, and layout come from explicit data/template rules.
- PDF is derived from DOCX; PDF failure must not invalidate DOCX export.

## Renderer Rules

- Rendering must be deterministic and testable without an LLM.
- Separate semantic roles from concrete Word styling.
- Keep OOXML manipulation inside `app/document/ooxml/`.
- Add fixture/golden tests for numbering, spacing, images, tables, headers, footers, or page settings when touched.
- Reject `.docm` and macro-enabled Office formats in MVP paths.
- Apply timeouts and safe diagnostics around LibreOffice conversion.

## Database / Security

- Use Alembic migrations; never rewrite applied migration history.
- Store files in private object storage, not PostgreSQL blobs.
- Validate upload extension, MIME type, and size.
- Generate storage keys server-side; sanitize user filenames.
- Keep service-role secrets backend-only.
- Do not log question bodies, tokens, or private/signed URLs by default.
- Return controlled errors; do not leak stack traces to clients.

## Testing

Cover changed behavior for authorization, schema validation, numbering, total marks, renderer output, DOCX export, and PDF failure handling.

## Commands

Run from `backend/` after `pyproject.toml` exists:

```bash
uv sync
uv run fastapi dev app/main.py
uv run ruff check .
uv run mypy app
uv run pytest
```

`pyproject.toml` and CI are authoritative. If commands differ, update this file.

## Done Check

- Run relevant Ruff, mypy, and pytest checks; report failures.
- Confirm authorization for new endpoints/queries.
- Confirm renderer changes preserve source content.
- Confirm migrations are additive/reproducible.
- Report output-fidelity limitations instead of hiding them.
