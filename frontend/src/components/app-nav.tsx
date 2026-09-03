import Link from "next/link";
import { FileText } from "lucide-react";

const links = [{ href: "/templates", label: "Templates" }, { href: "/questions", label: "Questions" }, { href: "/papers", label: "Papers" }];

export function AppNav({ email }: { email: string }) {
  return <header className="border-b bg-card"><div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-6"><Link href="/papers" className="flex items-center gap-2 font-semibold"><FileText className="size-5 text-primary" /><span>Arche</span></Link><nav aria-label="Primary" className="flex flex-1 items-center gap-1">{links.map((link) => <Link key={link.href} href={link.href} className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground">{link.label}</Link>)}</nav><span className="hidden text-sm text-muted-foreground sm:block">{email}</span></div></header>;
}
