import { NextResponse } from "next/server";
import { z } from "zod";
import { SESSION_COOKIE_NAME, serializeSession } from "@/lib/auth/session";

const loginSchema = z.object({ email: z.string().trim().email(), token: z.string().trim().min(1) });

// TODO(M1 auth): Replace this development-only token handoff with Supabase Auth.
export async function POST(request: Request) {
  const formData = await request.formData();
  const result = loginSchema.safeParse({ email: formData.get("email"), token: formData.get("token") });
  if (!result.success) {
    return NextResponse.json({ detail: "A valid email and non-empty token are required." }, { status: 400 });
  }
  const url = new URL(request.url);
  // Behind a reverse proxy (Cloudflare tunnel), request.url uses the server's
  // own hostname (localhost). Prefer forwarded headers so the redirect keeps
  // the browser on the public origin.
  const fwdProto = request.headers.get("x-forwarded-proto");
  const fwdHost = request.headers.get("x-forwarded-host");
  const origin =
    fwdProto && fwdHost ? `${fwdProto}://${fwdHost}` : url.origin;
  const response = NextResponse.redirect(new URL("/papers", origin), 303);
  response.cookies.set(SESSION_COOKIE_NAME, serializeSession(result.data), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 8,
  });
  return response;
}
