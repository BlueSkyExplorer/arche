import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function PlaceholderPage({ title, description }: { title: string; description: string }) {
  return <section className="space-y-6"><div><h1 className="text-3xl font-semibold tracking-tight">{title}</h1><p className="mt-2 text-muted-foreground">{description}</p></div><Card><CardHeader><CardTitle>Coming in a later milestone</CardTitle><CardDescription>This route is ready for its feature implementation.</CardDescription></CardHeader><CardContent><p className="text-sm text-muted-foreground">Scaffold only — no backend data is requested yet. 暫未有內容。</p></CardContent></Card></section>;
}
