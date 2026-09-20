"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Save, Check, Trash2, Plus, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import {
  approveImport,
  getExamImport,
  saveReviewed,
  type ExamDocument,
  type ExamImportDetail,
  type QuestionNode,
} from "@/lib/api/exam-imports";
import AnswerSheetReview from "./answer-sheet-review";

type NodePath = number[]; // [sectionIndex, questionIndex, childIndex, ...]

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function getNode(doc: ExamDocument, path: NodePath): QuestionNode {
  const section = doc.sections[path[0]];
  let node = section.questions![path[1]];
  for (let i = 2; i < path.length; i++) node = node.children![path[i]];
  return node;
}

function setNode(doc: ExamDocument, path: NodePath, next: QuestionNode): ExamDocument {
  const copy = clone(doc);
  const section = copy.sections[path[0]];
  if (path.length === 2) {
    section.questions![path[1]] = next;
    return copy;
  }
  let parent = section.questions![path[1]];
  const chain: QuestionNode[] = [];
  for (let i = 2; i < path.length - 1; i++) {
    chain.push(parent);
    parent = parent.children![path[i]];
  }
  parent.children![path[path.length - 1]] = next;
  // reassemble ancestors immutably
  for (let i = chain.length - 1; i >= 0; i--) {
    const child = chain[i + 1] ?? parent;
    chain[i].children![path[i + 2]] = child;
  }
  section.questions![path[1]] = chain[0] ?? parent;
  return copy;
}

function listPaths(doc: ExamDocument): { path: NodePath; node: QuestionNode; depth: number }[] {
  const out: { path: NodePath; node: QuestionNode; depth: number }[] = [];
  doc.sections.forEach((section, si) => {
    (section.questions ?? []).forEach((q, qi) => {
      const walk = (node: QuestionNode, path: NodePath, depth: number) => {
        out.push({ path, node, depth });
        (node.children ?? []).forEach((c, ci) => walk(c, [...path, ci], depth + 1));
      };
      walk(q, [si, qi], 0);
    });
  });
  return out;
}

function label(node: QuestionNode, fallback: string): string {
  return node.label ?? fallback;
}

function contentPreview(node: QuestionNode): string {
  return (node.content ?? [])
    .map((b) => {
      if (b.kind === "image") return "[image]";
      if (b.kind === "table") return "[table]";
      if (b.kind === "equation") return `[equation ${b.text ?? ""}]`;
      return b.text ?? "";
    })
    .join(" ")
    .slice(0, 120);
}

function evidenceLine(node: QuestionNode): string {
  const s = node.source;
  if (!s?.block_id && !s?.page) return "";
  return `page ${s.page ?? "—"} · block ${s.block_id ?? "—"}`;
}

function SeverityBadge({ severity }: { severity: string }) {
  const cls =
    severity === "blocking"
      ? "bg-destructive text-destructive-foreground"
      : severity === "warning"
        ? "bg-amber-100 text-amber-800"
        : "bg-muted text-muted-foreground";
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}>{severity}</span>;
}

export default function ReviewPage({ token, importId }: { token: string; importId: string }) {
  const router = useRouter();
  const [detail, setDetail] = useState<ExamImportDetail | null>(null);
  const [reviewed, setReviewed] = useState<ExamDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [notice, setNotice] = useState<string>();

  useEffect(() => {
    let active = true;
    getExamImport(token, importId)
      .then((d) => {
        if (!active) return;
        setDetail(d);
        setReviewed(d.reviewed_document_json ? clone(d.reviewed_document_json) : null);
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof ApiError ? e.body.detail : "Unable to load import.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, importId]);

  function patchNode(path: NodePath, patch: Partial<QuestionNode>) {
    setReviewed((doc) => (doc ? setNode(doc, path, { ...getNode(doc, path), ...patch }) : doc));
  }

  function removeNode(path: NodePath) {
    if (path.length < 2) return;
    const parentPath = path.slice(0, -1);
    const index = path[path.length - 1];
    setReviewed((doc) => {
      if (!doc) return doc;
      const copy = clone(doc);
      const parent = getNode(copy, parentPath);
      parent.children!.splice(index, 1);
      return copy;
    });
  }

  function addChild(path: NodePath) {
    setReviewed((doc) => {
      if (!doc) return doc;
      const copy = clone(doc);
      const node = getNode(copy, path);
      node.children = node.children ?? [];
      node.children.push({ label: null, own_marks: null, content: [], children: [] });
      return copy;
    });
  }

  function moveNode(path: NodePath, newParentPath: NodePath | null) {
    setReviewed((doc) => {
      if (!doc) return doc;
      const copy = clone(doc);
      const node = getNode(copy, path);
      // remove from old parent
      const oldParentPath = path.slice(0, -1);
      const oldIndex = path[path.length - 1];
      getNode(copy, oldParentPath).children!.splice(oldIndex, 1);
      // insert into new parent (or root)
      if (newParentPath === null) {
        copy.sections[path[0]].questions!.push(node);
      } else {
        const parent = getNode(copy, newParentPath);
        parent.children = parent.children ?? [];
        parent.children.push(node);
      }
      return copy;
    });
  }

  async function onSave() {
    if (!reviewed) return;
    setSaving(true);
    setNotice(undefined);
    try {
      const updated = await saveReviewed(token, importId, reviewed);
      setDetail(updated);
      setReviewed(clone(updated.reviewed_document_json!));
      setNotice("Saved / 已儲存");
    } catch (e) {
      setError(e instanceof ApiError ? e.body.detail : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function onApprove() {
    setApproving(true);
    setNotice(undefined);
    try {
      await approveImport(token, importId);
      router.push("/imports");
    } catch (e) {
      setError(e instanceof ApiError ? e.body.detail : "Approve failed.");
      setApproving(false);
    }
  }

  if (loading) {
    return <main className="mx-auto max-w-6xl p-6 text-muted-foreground">Loading… / 載入中</main>;
  }
  if (error && !detail) {
    return <main className="mx-auto max-w-6xl p-6"><p className="text-destructive">{error}</p><Link href="/imports" className="text-sm underline">← Back to imports</Link></main>;
  }
  if (detail && detail.import_type === "answer_sheet") {
    return <AnswerSheetReview token={token} importId={importId} detail={detail} />;
  }
  if (!detail || !reviewed) return null;

  const issues = detail.validation_json?.issues ?? [];
  const flat = listPaths(reviewed);
  const extractorLabel = detail.extractor_name === "llm" ? "AI (LLM)" : "Rule-based";

  return (
    <main className="mx-auto w-full max-w-6xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <Link href="/imports" className="text-sm text-muted-foreground underline">← Imports / 匯入列表</Link>
          <h1 className="text-xl font-semibold">{detail.source_filename}</h1>
          <p className="text-sm text-muted-foreground">
            Status: {detail.status} · Extractor: {extractorLabel}
            {detail.fallback_occurred ? " · ⚠ Fallback occurred" : ""}
            {detail.model ? ` · ${detail.model}` : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void onSave()} disabled={saving}>
            <Save className="size-4" /> {saving ? "Saving…" : "Save / 儲存"}
          </Button>
          <Button onClick={() => void onApprove()} disabled={approving || detail.status === "completed"}>
            <Check className="size-4" /> {approving ? "Importing…" : "Approve & Import / 批准並匯入"}
          </Button>
        </div>
      </div>

      {notice && <p className="mb-3 rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p>}
      {error && <p className="mb-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Extracted questions / 提取的題目</h2>
          {flat.length === 0 ? (
            <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">No questions extracted.</div>
          ) : (
            <div className="space-y-3">
              {reviewed.sections.map((section, si) =>
                (section.questions ?? []).map((q, qi) => (
                  <NodeCard
                    key={`${si}/${qi}`}
                    node={q}
                    path={[si, qi]}
                    flat={flat}
                    onPatch={patchNode}
                    onRemove={removeNode}
                    onAddChild={addChild}
                    onMove={moveNode}
                  />
                )),
              )}
            </div>
          )}
        </section>

        <aside className="space-y-4">
          <section className="rounded-lg border bg-card p-4">
            <h2 className="mb-2 text-sm font-semibold">Validation issues / 驗證問題</h2>
            {issues.length === 0 ? (
              <p className="text-sm text-muted-foreground">No issues.</p>
            ) : (
              <ul className="space-y-2">
                {issues.map((issue, i) => (
                  <li key={i} className="text-sm">
                    <SeverityBadge severity={issue.severity} />{" "}
                    <span className="font-medium">{issue.code}</span>{" "}
                    <span className="text-muted-foreground">{issue.message}</span>
                    {issue.location && <span className="block text-xs text-muted-foreground">at {issue.location}</span>}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-lg border bg-card p-4">
            <h2 className="mb-2 text-sm font-semibold">How to review / 審閱方式</h2>
            <p className="text-sm text-muted-foreground">
              修改題號、分數或結構後按「Save」。確認無誤後按「Approve & Import」將題目建立到 Question Library。
              Unknown marks 會保持為空（不會變成 0），需要你填上或在 Approve 時保留待審。
            </p>
          </section>
        </aside>
      </div>
    </main>
  );
}

function NodeCard({
  node,
  path,
  flat,
  onPatch,
  onRemove,
  onAddChild,
  onMove,
}: {
  node: QuestionNode;
  path: NodePath;
  flat: { path: NodePath; node: QuestionNode; depth: number }[];
  onPatch: (path: NodePath, patch: Partial<QuestionNode>) => void;
  onRemove: (path: NodePath) => void;
  onAddChild: (path: NodePath) => void;
  onMove: (path: NodePath, parent: NodePath | null) => void;
}) {
  const depth = path.length - 2;
  const isDescendant = (p: NodePath) => p.length > path.length && p.slice(0, path.length).every((v, i) => v === path[i]);
  const parentOptions = flat.filter((f) => !isDescendant(f.path) && f.path.join("/") !== path.join("/"));
  const currentParent = path.length > 2 ? path.slice(0, -1).join("/") : "";

  return (
    <div className="rounded-lg border bg-card p-3" style={{ marginLeft: depth * 16 }}>
      <div className="flex items-start gap-2">
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{path.map((p, i) => (i === 1 ? "" : "")).join("")}</span>
            <Input
              aria-label="label"
              className="h-8 w-28 font-medium"
              value={node.label ?? ""}
              placeholder="label"
              onChange={(e) => onPatch(path, { label: e.target.value || null })}
            />
            <div className="flex items-center gap-1 text-sm text-muted-foreground">
              marks
              <Input
                aria-label="marks"
                type="number"
                step="0.5"
                min="0"
                className="h-8 w-20"
                value={node.own_marks ?? ""}
                placeholder="?"
                onChange={(e) =>
                  onPatch(path, { own_marks: e.target.value === "" ? null : e.target.value })
                }
              />
            </div>
          </div>
          {contentPreview(node) && (
            <p className="text-sm text-muted-foreground">{contentPreview(node)}</p>
          )}
          {evidenceLine(node) && (
            <p className="text-xs text-muted-foreground">
              {evidenceLine(node)}
              {node.source?.source_text ? ` · “${node.source.source_text.slice(0, 60)}”` : ""}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <select
            className="h-8 rounded-md border bg-background px-2 text-xs"
            value={currentParent}
            onChange={(e) => onMove(path, e.target.value === "" ? null : e.target.value.split("/").map(Number))}
          >
            <option value="">root</option>
            {parentOptions.map((f) => (
              <option key={f.path.join("/")} value={f.path.join("/")}>
                {"· ".repeat(f.depth) + label(f.node, "?")}
              </option>
            ))}
          </select>
          <Button size="icon" variant="ghost" aria-label="add child" onClick={() => onAddChild(path)}>
            <Plus className="size-4" />
          </Button>
          <Button size="icon" variant="ghost" aria-label="delete" onClick={() => onRemove(path)}>
            <Trash2 className="size-4" />
          </Button>
          {(node.children?.length ?? 0) > 0 && <ChevronRight className="size-4 text-muted-foreground" />}
        </div>
      </div>

      {(node.children ?? []).map((child, ci) => (
        <NodeCard
          key={ci}
          node={child}
          path={[...path, ci]}
          flat={flat}
          onPatch={onPatch}
          onRemove={onRemove}
          onAddChild={onAddChild}
          onMove={onMove}
        />
      ))}
    </div>
  );
}
