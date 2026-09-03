# Papers

Feature-local UI and state for paper assembly and export.

The builder displays the backend detail response's `display_number` when present.
Immediately after a local reorder, it falls back to
`src/lib/validation/numbering.ts`, which mirrors the constrained template styles.
The backend remains authoritative for exported numbering and pagination.
