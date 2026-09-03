# Repository Agent Instructions

## Product

Build the teacher exam-paper formatting service defined in `PRODUCT.md`.
`MVP.md` is the scope boundary. `ARCHITECTURE.md` is the technical source of truth.
Read all three before making cross-cutting changes.

## Priority

1. User's current instruction.
2. More specific nested `AGENTS.md` for the directory being changed.
3. This file.
4. `MVP.md` for scope.
5. `ARCHITECTURE.md` for implementation direction.
6. `PRODUCT.md` for product intent.

If documents conflict, do not silently choose a new product direction. Make the smallest safe change and surface the conflict.

## Repository Shape

```text
/                    product docs + repo-wide rules
/frontend            Next.js/TypeScript application
/backend             FastAPI/Python API + document renderer
```

Do not move document-rendering logic into the frontend.
Do not move UI/business presentation logic into the backend.

## Working Method

- Inspect existing files, manifests, tests, and nearby code before editing.
- Prefer the smallest change that completes the requested behavior.
- Do not add features listed as out of scope in `MVP.md` unless explicitly requested.
- Preserve existing conventions when they are already established.
- Update documentation when a real command, architecture decision, or constraint changes.
- Never invent successful test results; report what actually ran.

## Product Safety Rules

- Preserve teacher-authored question wording by default.
- AI assistance must be reviewable and must not be required for deterministic export.
- Every private business object must be workspace-scoped.
- Never expose service keys, tokens, private storage URLs, or user document content in logs.
- Reject macro-enabled Office documents in the MVP.
- Browser preview is approximate; do not claim pixel-perfect Microsoft Word parity.

## Engineering Rules

- Prefer boring, maintainable code over abstractions created for hypothetical scale.
- No microservices, Kubernetes, Redis, or queue system for MVP without measured need.
- Validate data at API/domain boundaries.
- Keep content representation separate from formatting rules.
- Rendering must be deterministic and testable without an LLM.
- Add or update tests for changed behavior, especially document rendering and authorization.
- Do not edit generated files manually when a generator/source exists.

## Commands

Frontend commands are defined in `frontend/AGENTS.md`.
Backend commands are defined in `backend/AGENTS.md`.

Before running a command, confirm the relevant manifest/config exists. If the real repo command differs from the docs, use the real command and update the docs.

## Definition of Done

A change is complete when:

- the requested behavior works;
- relevant lint/type/test checks pass or failures are reported;
- workspace authorization remains correct;
- teacher content is not silently altered;
- MVP scope is not expanded accidentally;
- affected docs are updated when behavior or commands changed.
