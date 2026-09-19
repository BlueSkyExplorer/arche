"use client";

import { useState } from "react";
import { Check, Loader2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { QuestionIngestDraft } from "@/lib/api/questions";
import { batchSaveDrafts } from "@/lib/api/questions.batch";

function draftText(draft: QuestionIngestDraft): string {
  const out: string[] = [];
  const walk = (nodes: { type: string; content?: unknown[]; text?: string; attrs?: { label?: string } }[]) => {
    for (const n of nodes) {
      if (n.type === "text" && typeof n.text === "string") out.push(n.text);
      else if (n.type === "subQuestion" && n.attrs?.label) out.push(`${n.attrs.label} `);
      if (n.content) walk(n.content as never[]);
    }
  };
  walk(draft.content_json.content as never[]);
  return out.join("").trim() || "(empty / 空白)";
}

export function QuestionScan({
  token,
  drafts,
  onSaved,
}: {
  token: string;
  drafts: QuestionIngestDraft[];
  onSaved?: () => Promise<void>;
}) {
  const [subject, setSubject] = useState("");
  const [level, setLevel] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string>();
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState<Set<number>>(new Set());

  if (drafts.length === 0) return null;

  const remaining = drafts
    .map((d, i) => ({ draft: d, index: i }))
    .filter(({ index }) => !saved.has(index));

  const saveAll = async () => {
    if (!subject.trim() || !level.trim()) {
      setError("Subject and level are required / 請填寫科目與級別");
      return;
    }
    setSaving(true);
    setError(undefined);
    setMessage(undefined);
    const results = await batchSaveDrafts(
      token,
      remaining.map(({ draft }) => ({
        draft,
        override: { subject: "", level: "" },
        marks: Number(draft.marks ?? 0),
      })),
      { subject, level },
    );
    const okCount = results.filter((r) => r.ok).length;
    const indices = results
      .filter((r) => r.ok)
      .map((r) => remaining[r.index].index);
    setSaved((prev) => {
      const next = new Set(prev);
      for (const i of indices) next.add(i);
      return next;
    });
    setMessage(
      okCount === results.length
        ? `已存入 ${okCount} 题 / ${okCount} questions saved`
        : `成功 ${okCount} 题，失败 ${results.length - okCount} 题`,
    );
    setSaving(false);
    if (okCount > 0) await onSaved?.();
  };

  return (
    <section className="rounded-md border p-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-medium">Scanned questions / 掃描到的題目（{drafts.length}）</h3>
        {saved.size === drafts.length && (
          <span className="inline-flex items-center gap-1 text-sm text-green-600">
            <Check className="size-4" /> All saved / 全部已存
          </span>
        )}
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="grid gap-1">
          <Label htmlFor="qs-subject" className="text-xs text-muted-foreground">Subject / 科目</Label>
          <Input id="qs-subject" size={1} className="h-8" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Biology 生物" />
        </div>
        <div className="grid gap-1">
          <Label htmlFor="qs-level" className="text-xs text-muted-foreground">Level / 級別</Label>
          <Input id="qs-level" size={1} className="h-8" value={level} onChange={(e) => setLevel(e.target.value)} placeholder="Form 4 中四" />
        </div>
      </div>

      <div className="mt-2 max-h-64 space-y-1 overflow-y-auto">
        {drafts.map((d, i) => (
          <div key={i} className={`rounded border px-3 py-2 text-sm ${saved.has(i) ? "border-green-300 bg-green-50" : ""}`}>
            <span className="font-medium">{d.internal_title}</span>
            <span className="ml-2 text-muted-foreground">· {d.marks ?? "—"} marks</span>
            {saved.has(i) && <span className="ml-2 text-green-600">✓</span>}
            <span className="ml-2 block truncate text-muted-foreground">{draftText(d)}</span>
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-3">
        <Button type="button" size="sm" disabled={saving || remaining.length === 0} onClick={() => void saveAll()}>
          {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
          Save {remaining.length} to library / 存 {remaining.length} 題
        </Button>
        {message && <p className="text-sm text-muted-foreground">{message}</p>}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      </div>
    </section>
  );
}