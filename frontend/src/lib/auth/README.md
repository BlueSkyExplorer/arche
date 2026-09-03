# Authentication
Server-side session access; the development stub will be replaced by Supabase Auth.

The development session remains an `HttpOnly` `arche_dev_session` cookie containing
the base64url-encoded `{ token, email }` JSON payload. Server pages may pass the
token to client features that need to call the backend; client modules must not
import `session.ts` because it depends on `next/headers`.
