"use client";

import { useRef, useState } from "react";
import { Upload, Wand2, CheckSquare, Square, Save, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import {
  createQuestion,
  ingestQuestions,
  type QuestionIngestDraft,
} from "@/lib/api/questions";
import {
  batchSaveDrafts,
  type DraftOverride,
  type DraftSaveResult,
} from "@/lib/api/questions.batch";
import type { QuestionContent } from "@/lib/validation/content";
import {
  resolveEffective,
  buildDraftPayload,
  sharedDefaultsSchema,
} from "@/lib/validation/ingest-batch";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DraftEntry = {
  draft: QuestionIngestDraft;
  selected: boolean;
  /** Per-draft individual subject/level overrides (empty = no override). */
  override: DraftOverride;
  /** Error from last save attempt. Cleared on next attempt. */
  saveError?: string;
  /** True after this draft was successfully saved. */
  saved?: boolean;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function draftText(content: QuestionContent): string {
  const out: string[] = [];
  const walk = (
    nodes: {
      type: string;
      content?: unknown[];
      text?: string;
      attrs?: { label?: string };
    }[],
  ) => {
    for (const n of nodes) {
      if (n.type === "text" && typeof n.text === "string") out.push(n.text);
      else if (n.type === "subQuestion" && n.attrs?.label)
        out.push(`${n.attrs.label} `);
      if (n.content) walk(n.content as never[]);
    }
  };
  walk(content.content as never[]);
  return out.join("").trim() || "(empty / 空白)";
}

const EMPTY_OVERRIDE: DraftOverride = { subject: "", level: "" };

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function IngestPanel({
  token,
  onSaved,
}: {
  token: string;
  onSaved: () => Promise<void>;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [sharedSubject, setSharedSubject] = useState("");
  const [sharedLevel, setSharedLevel] = useState("");
  const [drafts, setDrafts] = useState<DraftEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [batchResult, setBatchResult] = useState<{
    succeeded: number;
    failed: number;
  }>();

  // ----- Parse helpers -----

  const err = (e: unknown, fallback: string) =>
    setError(e instanceof ApiError ? e.body.detail : fallback);

  const parse = async (file?: File) => {
    setBusy(true);
    setError(undefined);
    setBatchResult(undefined);
    try {
      const source = file ? { file } : { text };
      const result = await ingestQuestions(token, source);
      setDrafts(
        result.map((draft) => ({
          draft,
          selected: true,
          override: { ...EMPTY_OVERRIDE },
        })),
      );
      if (result.length === 0)
        setError("No questions detected / 未偵測到題目");
    } catch (e) {
      err(e, "Parse failed / 解析失敗");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  // ----- Selection helpers -----

  const allSelected =
    drafts.length > 0 && drafts.every((d) => d.selected && !d.saved);
  const selectableCount = drafts.filter((d) => !d.saved).length;

  const toggleAll = () => {
    const next = !allSelected;
    setDrafts((ds) =>
      ds.map((d) => (d.saved ? d : { ...d, selected: next })),
    );
  };

  // ----- Individual save (preserved from original) -----

  const saveOne = async (index: number) => {
    const entry = drafts[index];
    if (entry.saved) return;

    const effective = resolveEffective(
      { subject: sharedSubject, level: sharedLevel },
      entry.override,
    );

    // Validate shared + override resolution
    const parsed = sharedDefaultsSchema.safeParse({
      subject: effective.subject,
      level: effective.level,
    });
    if (!parsed.success) {
      const msg = parsed.error.issues.map((i) => i.message).join("; ");
      setDrafts((ds) =>
        ds.map((d, i) => (i === index ? { ...d, saveError: msg } : d)),
      );
      return;
    }

    setDrafts((ds) =>
      ds.map((d, i) => (i === index ? { ...d, saveError: undefined } : d)),
    );
    try {
      await createQuestion(
        token,
        buildDraftPayload(entry.draft, effective),
      );
      setDrafts((ds) =>
        ds.map((d, i) => (i === index ? { ...d, saved: true } : d)),
      );
      await onSaved();
    } catch (e: unknown) {
      const msg =
        e instanceof ApiError
          ? e.body.detail
          : e instanceof Error
            ? e.message
            : "Save failed / 儲存失敗";
      setDrafts((ds) =>
        ds.map((d, i) => (i === index ? { ...d, saveError: msg } : d)),
      );
    }
  };

  // ----- Batch save -----

  const batchSave = async () => {
    const selected = drafts.filter((d) => d.selected && !d.saved);
    if (selected.length === 0) return;

    setSaving(true);
    setError(undefined);
    setBatchResult(undefined);

    // Clear per-draft errors before attempting
    setDrafts((ds) =>
      ds.map((d) => (d.selected && !d.saved ? { ...d, saveError: undefined } : d)),
    );

    try {
      const results: DraftSaveResult[] = await batchSaveDrafts(
        token,
        selected.map((d) => ({ draft: d.draft, override: d.override })),
        { subject: sharedSubject, level: sharedLevel },
      );

      let succeeded = 0;
      let failed = 0;

      // Map results back to original indices
      setDrafts((ds) => {
        const next = [...ds];
        // selected[] maps to the original index — we need to find them
        const selectedIndices = ds
          .map((d, i) => (d.selected && !d.saved ? i : -1))
          .filter((i) => i >= 0);

        for (const r of results) {
          const origIdx = selectedIndices[r.index];
          if (origIdx === undefined) continue;
          if (r.ok) {
            next[origIdx] = { ...next[origIdx], saved: true, saveError: undefined };
            succeeded++;
          } else {
            next[origIdx] = { ...next[origIdx], saveError: r.error };
            failed++;
          }
        }
        return next;
      });

      setBatchResult({ succeeded, failed });
      if (succeeded > 0) await onSaved();
    } catch (e) {
      err(e, "Batch save failed / 批次儲存失敗");
    } finally {
      setSaving(false);
    }
  };

  // ----- Derived state -----

  const selectedCount = drafts.filter((d) => d.selected && !d.saved).length;
  const savedCount = drafts.filter((d) => d.saved).length;
  const remainingDrafts = drafts.filter((d) => !d.saved);

  // ----- Render -----

  return (
    <section className="rounded-lg border bg-card p-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-medium">Bulk import / 批量匯入題目</h2>
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".docx"
            aria-label="Import questions DOCX"
            className="hidden"
            onChange={(e) => void parse(e.target.files?.[0])}
          />
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
          >
            <Upload className="size-4" />
            Upload DOCX / 上傳
          </Button>
          <Button
            type="button"
            disabled={busy || !text.trim()}
            onClick={() => void parse()}
          >
            <Wand2 className="size-4" />
            {busy ? "Parsing… / 解析中…" : "Parse text / 解析文字"}
          </Button>
        </div>
      </div>

      {/* Input area */}
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <div className="grid gap-2 sm:col-span-3">
          <Label htmlFor="ingest-text">Paste question set / 貼上題目集</Label>
          <textarea
            id="ingest-text"
            className="min-h-28 rounded-md border bg-background px-3 py-2 font-mono text-sm"
            placeholder={
              "1. Solve 2 + 2. (2 marks)\n\na) 2\nb) 4\n\n2. 計算 12 × 4。 （2分）"
            }
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
      </div>

      {/* Shared metadata — shown when drafts exist */}
      {drafts.length > 0 && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="shared-subject">
              Shared subject / 共用科目
              <span className="ml-1 text-xs text-muted-foreground">
                (個別科目非空時優先)
              </span>
            </Label>
            <Input
              id="shared-subject"
              value={sharedSubject}
              onChange={(e) => setSharedSubject(e.target.value)}
              placeholder="Mathematics 數學"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="shared-level">
              Shared level / 共用級別
              <span className="ml-1 text-xs text-muted-foreground">
                (個別級別非空時優先)
              </span>
            </Label>
            <Input
              id="shared-level"
              value={sharedLevel}
              onChange={(e) => setSharedLevel(e.target.value)}
              placeholder="Form 2 中二"
            />
          </div>
        </div>
      )}

      {/* Draft list */}
      {drafts.length > 0 && (
        <div className="mt-4 space-y-2">
          {/* Toolbar */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {drafts.length} drafts / 草稿
              {savedCount > 0 && ` · ${savedCount} saved / 已存`}
              {selectedCount > 0 &&
                ` · ${selectedCount} selected / 已選`}
            </p>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={toggleAll}
                disabled={selectableCount === 0}
              >
                {allSelected ? (
                  <>
                    <CheckSquare className="size-4" />
                    Deselect all / 取消全選
                  </>
                ) : (
                  <>
                    <Square className="size-4" />
                    Select all / 全選
                  </>
                )}
              </Button>
              <Button
                type="button"
                disabled={saving || selectedCount === 0}
                onClick={() => void batchSave()}
              >
                {saving ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Saving… / 儲存中…
                  </>
                ) : (
                  <>
                    <Save className="size-4" />
                    Save {selectedCount} selected / 儲存 {selectedCount} 題
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Draft cards */}
          {remainingDrafts.map((entry) => {
            const origIdx = drafts.indexOf(entry);
            return (
              <div
                key={origIdx}
                className={`rounded-md border p-3 ${entry.selected ? "border-primary/40 bg-primary/5" : ""} ${entry.saveError ? "border-destructive/40" : ""}`}
              >
                {/* Row 1: checkbox + title + individual save */}
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    className="mt-1 size-4"
                    checked={entry.selected}
                    onChange={() =>
                      setDrafts((ds) =>
                        ds.map((d, j) =>
                          j === origIdx ? { ...d, selected: !d.selected } : d,
                        ),
                      )
                    }
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      {entry.draft.internal_title}{" "}
                      <span className="text-muted-foreground">
                        · {String(entry.draft.marks)} marks
                      </span>
                    </p>
                    <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                      {draftText(entry.draft.content_json)}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={saving}
                    onClick={() => void saveOne(origIdx)}
                  >
                    <Save className="size-3" />
                    Save / 存
                  </Button>
                </div>

                {/* Row 2: individual subject/level overrides */}
                <div className="mt-2 ml-7 grid gap-2 sm:grid-cols-2">
                  <div className="grid gap-1">
                    <Label
                      htmlFor={`override-subject-${origIdx}`}
                      className="text-xs text-muted-foreground"
                    >
                      Override subject / 覆寫科目
                    </Label>
                    <Input
                      id={`override-subject-${origIdx}`}
                      size={1}
                      className="h-7 text-sm"
                      value={entry.override.subject}
                      placeholder={sharedSubject || "Subject / 科目"}
                      onChange={(e) =>
                        setDrafts((ds) =>
                          ds.map((d, j) =>
                            j === origIdx
                              ? {
                                  ...d,
                                  override: {
                                    ...d.override,
                                    subject: e.target.value,
                                  },
                                }
                              : d,
                          ),
                        )
                      }
                    />
                  </div>
                  <div className="grid gap-1">
                    <Label
                      htmlFor={`override-level-${origIdx}`}
                      className="text-xs text-muted-foreground"
                    >
                      Override level / 覆寫級別
                    </Label>
                    <Input
                      id={`override-level-${origIdx}`}
                      size={1}
                      className="h-7 text-sm"
                      value={entry.override.level}
                      placeholder={sharedLevel || "Level / 級別"}
                      onChange={(e) =>
                        setDrafts((ds) =>
                          ds.map((d, j) =>
                            j === origIdx
                              ? {
                                  ...d,
                                  override: {
                                    ...d.override,
                                    level: e.target.value,
                                  },
                                }
                              : d,
                          ),
                        )
                      }
                    />
                  </div>
                </div>

                {/* Per-draft error */}
                {entry.saveError && (
                  <p
                    role="alert"
                    className="ml-7 mt-1 text-sm text-destructive"
                  >
                    {entry.saveError}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Batch result summary */}
      {batchResult && (
        <p className="mt-3 text-sm">
          <span className="text-emerald-600">
            Saved {batchResult.succeeded} / 已存 {batchResult.succeeded} 題
          </span>
          {batchResult.failed > 0 && (
            <span className="ml-3 text-destructive">
              Failed {batchResult.failed} / 失敗 {batchResult.failed} 題
            </span>
          )}
        </p>
      )}

      {/* Top-level error */}
      {error && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {error}
        </p>
      )}
    </section>
  );
}
