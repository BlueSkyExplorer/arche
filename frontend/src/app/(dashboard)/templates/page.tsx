import TemplatesPage from "@/features/templates/page";
import { getSession } from "@/lib/auth/session";
export default async function TemplatesRoute() { const session = await getSession(); if (!session) return null; return <TemplatesPage token={session.token} />; }
