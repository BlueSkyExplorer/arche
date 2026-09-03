import QuestionsPage from "@/features/questions/page";
import { getSession } from "@/lib/auth/session";

export default async function QuestionsRoute() {
  // The dashboard layout has already redirected unauthenticated requests.
  const session = await getSession();
  if (!session) return null;
  return <QuestionsPage token={session.token} />;
}
