import AnswerSheetFormatPage from "@/features/imports/format-page";
import { getSession } from "@/lib/auth/session";

export default async function ImportFormatRoute({ params }: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return null;
  const { id } = await params;
  return <AnswerSheetFormatPage token={session.token} importId={id} />;
}
