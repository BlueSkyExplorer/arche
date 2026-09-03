import Link from "next/link";
import { FileText } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-20">
      <div className="max-w-2xl space-y-6">
        <div className="flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground"><FileText /></div>
        <p className="text-sm font-medium text-primary">Arche Paper Studio · 試卷工作室</p>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-6xl">Spend less time formatting exam papers.</h1>
        <p className="text-lg leading-8 text-muted-foreground">Build reusable school formats, questions, and papers while keeping every teacher-authored word intact. 支援中文及 English 混合內容。</p>
        <Button asChild size="lg"><Link href="/login">Sign in to continue</Link></Button>
      </div>
    </main>
  );
}
