import { cookies } from "next/headers";

export const SESSION_COOKIE_NAME = "arche_dev_session";
export type Session = { token: string; email: string };

export function serializeSession(session: Session): string {
  return Buffer.from(JSON.stringify(session), "utf8").toString("base64url");
}

export async function getSession(): Promise<Session | null> {
  const value = (await cookies()).get(SESSION_COOKIE_NAME)?.value;
  if (!value) return null;
  try {
    const parsed: unknown = JSON.parse(Buffer.from(value, "base64url").toString("utf8"));
    if (typeof parsed === "object" && parsed !== null && "token" in parsed && "email" in parsed && typeof parsed.token === "string" && typeof parsed.email === "string" && parsed.token && parsed.email) return { token: parsed.token, email: parsed.email };
  } catch { return null; }
  return null;
}
