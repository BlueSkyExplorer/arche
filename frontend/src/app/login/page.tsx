import { redirect } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getSession } from "@/lib/auth/session";

export default async function LoginPage() {
  if (await getSession()) redirect("/papers");
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <Card className="w-full max-w-md">
        <CardHeader><CardTitle>Developer sign in</CardTitle><CardDescription>開發登入：use any email and non-empty token. Supabase Auth will replace this stub.</CardDescription></CardHeader>
        <CardContent>
          <form action="/api/auth/session" method="post" className="space-y-5">
            <div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" name="email" type="email" autoComplete="email" required placeholder="teacher@school.edu.hk" /></div>
            <div className="space-y-2"><Label htmlFor="token">Development token</Label><Input id="token" name="token" type="password" autoComplete="off" required minLength={1} /></div>
            <Button className="w-full" type="submit">Sign in / 登入</Button>
          </form>
          <p className="mt-4 text-xs text-muted-foreground">Development only. Never paste a Supabase service-role key here.</p>
        </CardContent>
      </Card>
    </main>
  );
}
