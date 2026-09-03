import PapersPage from "@/features/papers/page";
import { getSession } from "@/lib/auth/session";
export default async function PapersRoute() { const session = await getSession(); if (!session) return null; return <PapersPage token={session.token} />; }
