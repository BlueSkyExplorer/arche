import PaperBuilder from "@/features/papers/detail-page";
import { getSession } from "@/lib/auth/session";
export default async function PaperRoute({ params }: { params: Promise<{ id: string }> }) { const session = await getSession(); if (!session) return null; const { id } = await params; return <PaperBuilder token={session.token} paperId={id} />; }
