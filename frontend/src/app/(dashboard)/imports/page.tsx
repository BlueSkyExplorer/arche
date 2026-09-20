import ImportsPage from "@/features/imports/page";
import { getSession } from "@/lib/auth/session";

export default async function ImportsRoute() {
  const session = await getSession();
  if (!session) return null;
  return <ImportsPage token={session.token} />;
}
