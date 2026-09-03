# Arche frontend

Teacher-facing shell for the Arche exam-paper formatting service.

## Local development

Requires Node.js 20.9+ and pnpm.

```bash
pnpm install
pnpm dev
pnpm lint
pnpm typecheck
pnpm build
```

Copy `.env.example` to `.env.local` when the API runs somewhere other than the default `http://localhost:8000`.

## Development authentication

`/login` is deliberately a development-only authentication stub. It stores the submitted `{ token, email }` payload in an `HttpOnly`, `SameSite=Lax` cookie so browser JavaScript cannot read it. Dashboard server layouts require this cookie. Replace the stub with Supabase Auth before production (`TODO(M1 auth)`). Never enter a service-role key.
