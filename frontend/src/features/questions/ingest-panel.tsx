"use client";

import { useRef, useState } from "react";
import { Upload, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import {
  createQuestion,
  ingestQuestions,
  type QuestionIngestDraft,
} from "@/lib/api/questions";
import { normalizeContentForWire, type QuestionContent } from "@/lib/validation/content";

type Draft = { draft: QuestionIngestDraft; accepted: boolean };

function draftText(content: QuestionContent): string {
  const out: string[] = [];
  const walk = (nodes: { type: string; content?: unknown[]; text?: string; attrs?: { label?: string } }[]) => {
    for (const n of nodes) {
      if (n.type === "text" && typeof n.text === "string") out.push(n.text);
      else if (n.type === "subQuestion" && n.attrs?.label) out.push(`${n.attrs.label} `);
      if (n.content) walk(n.content as never[]);
    }
  };
  walk(content.content as never[]);
  return out.join("").trim() || "(empty / 空白)";
}

export function IngestPanel({ token, onSaved }: { token: string; onSaved: () => Promise<void> }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [subject, setSubject] = useState("");
  const [level, setLevel] = useState("");
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [done, setDone] = useState<number>();

  const err = (e: unknown, fallback: string) => setError(e instanceof ApiError ? e.body.detail : fallback);

  const parse = async (file?: File) => {
    setBusy(true); setError(undefined); setDone(undefined);
    try {
      const source = file ? { file } : { text };
      const result = await ingestQuestions(token, source);
      setDrafts(result.map((draft) => ({ draft, accepted: true })));
      if (result.length === 0) setError("No questions detected / 未偵測到題目");
    } catch (e) {
      err(e, "Parse failed / 解析失敗");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const save = async () => {
    const accepted = drafts.filter((d) => d.accepted);
    if (!subject.trim() || !level.trim()) {
      setError("Subject and level are required before saving / 儲存前需填寫科目與級別");
      return;
    }
    setSaving(true); setError(undefined);
    try {
      let n = 0;
      for (const { draft } of accepted) {
        await createQuestion(token, {
          internalTitle: draft.internal_title,
          subject,
          level,
          tags: draft.tags_json,
          sourceNote: draft.source_note ?? undefined,
          content: normalizeContentForWire(draft.content_json),
          marks: Number(draft.marks),
          status: draft.status,
        });
        n += 1;
      }
      setDrafts([]); setDone(n);
      await onSaved();
    } catch (e) {
      err(e, "Save failed / 儲存失敗");
    } finally {
      setSaving(false);
    }
  };

  const acceptedCount = drafts.filter((d) => d.accepted).length;

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-medium">Bulk import / 批量匯入題目</h2>
        <div className="flex items-center gap-2">
          <input ref={fileRef} type="file" accept=".docx" aria-label="Import questions DOCX" className="hidden" onChange={(e) => void parse(e.target.files?.[0])} />
          <Button type="button" variant="outline" disabled={busy} onClick={() => fileRef.current?.click()}>
            <Upload className="size-4" />Upload DOCX / 上傳
          </Button>
          <Button type="button" disabled={busy || !text.trim()} onClick={() => void parse()}>
            <Wand2 className="size-4" />{busy ? "Parsing… / 解析中…" : "Parse text / 解析文字"}
          </Button>
        </div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <div className="grid gap-2 sm:col-span-3">
          <Label htmlFor="ingest-text">Paste question set / 貼上題目集</Label>
          <textarea
            id="ingest-text"
            className="min-h-28 rounded-md border bg-background px-3 py-2 font-mono text-sm"
            placeholder={"1. Solve 2 + 2. (2 marks)\n\na) 2\nb) 4\n\n2. 計算 12 × 4。 （2分）"}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="ingest-subject">Subject / 科目</Label>
          <Input id="ingest-subject" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Mathematics 數學" />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="ingest-level">Level / 級別</Label>
          <Input id="ingest-level" value={level} onChange={(e) => setLevel(e.target.value)} placeholder="Form 2 中二" />
        </div>
      </div>

      {drafts.length > 0 && (
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">{drafts.length} drafts / 草稿, {acceptedCount} selected / 已選</p>
            <div className="flex items-center gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setDrafts((d) => d.map((x) => ({ ...x, accepted: !x.accepted })))}>
                Toggle all / 全選
              </Button>
              <Button type="button" disabled={saving || acceptedCount === 0} onClick={() => void save()}>
                {saving ? "Saving… / 儲存中…" : `Save ${acceptedCount} / 儲存 ${acceptedCount} 題`}
              </Button>
            </div>
          </div>
          {drafts.map(({ draft, accepted }, i) => (
            <label key={i} className="flex items-start gap-3 rounded-md border p-3">
              <input type="checkbox" className="mt-1 size-4" checked={accepted} onChange={() => setDrafts((d) => d.map((x, j) => (j === i ? { ...x, accepted: !x.accepted } : x)))} />
              <div className="min-w-0">
                <p className="font-medium">{draft.internal_title} <span className="text-muted-foreground">· {String(draft.marks)} marks</span></p>
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">{draftText(draft.content_json)}</p>
              </div>
            </label>
          ))}
        </div>
      )}

      {done !== undefined && <p className="mt-3 text-sm text-emerald-600">Saved {done} question(s) / 已儲存 {done} 題</p>}
      {error && <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>}
    </section>
  );
}
