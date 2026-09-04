# Frontend Agent Instructions

Extends the root `AGENTS.md`; these rules take precedence under `frontend/`.

## Responsibility

Own the teacher-facing web UI:
- authentication;
- template-profile editor;
- question library/editor;
- paper builder;
- approximate browser preview;
- export actions and error/status UI.

Do **not** implement DOCX/PDF rendering in the frontend.

## Stack

- Next.js App Router + React
- TypeScript strict mode
- Tailwind CSS + shadcn/ui
- TipTap/ProseMirror for rich question content
- React Hook Form + Zod

Do not replace core stack choices without an explicit architecture change.

## Structure

```text
src/
├── app/
├── components/       shared UI only
├── features/
│   ├── templates/
│   ├── questions/
│   └── papers/
└── lib/
    ├── api/
    ├── auth/
    └── validation/
```

Keep API/domain transformations out of large page components.

## UI Rules

- Optimize for completing a real paper, not showcasing AI.
- Never alter entered question content without explicit user acceptance.
- Show loading, empty, error, and retry states for remote operations.
- Never claim browser preview is identical to Microsoft Word.
- Support Chinese/English mixed text; do not assume ASCII-only input.
- Reordering paper questions must not mutate reusable source questions.
- Make destructive actions explicit and recoverable where practical.

## API / State Rules

- Backend OpenAPI is the API contract.
- Centralize HTTP code under `src/lib/api/`.
- Do not scatter raw `fetch` calls through components.
- Do not manually duplicate API types once generated OpenAPI types exist.
- Never expose backend service-role credentials to browser code.
- Prefer API server state as source of truth.
- Keep transient editor/reordering state local.
- Do not add global state tooling without a real cross-feature need.

## Testing

Prioritize:
- template-form validation;
- question editing/persistence;
- paper ordering;
- mark-total display;
- export error handling;
- one critical create-paper -> add-question -> export flow.

Do not use screenshot tests as the only evidence of document fidelity.

## Commands

Run from `frontend/` after `package.json` exists:

```bash
pnpm install
pnpm dev
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e
```

`package.json` scripts are authoritative. If they differ, update this file.

## Done Check

- Run relevant lint/type/tests and report failures.
- Verify Chinese and English input.
- Verify loading/error states.
- Confirm no backend document-rendering rules were duplicated.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
