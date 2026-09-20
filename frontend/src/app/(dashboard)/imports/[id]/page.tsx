import ReviewPage from "@/features/imports/review-page";
import { getSession } from "@/lib/auth/session";

export default async function ImportReviewRoute({ params }: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return null;
  const { id } = await params;
  return <ReviewPage token={session.token} importId={id} />;
}
