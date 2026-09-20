"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Save, Check, AlertTriangle, ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import {
  approveImport,
  saveReviewed,
  type AnsNode,
  type AnsSection,
  type AnsSheet,
  type ExamImportDetail,
} from "@/lib/api/exam-imports";
import { leafMarks, totalsMismatch } from "@/lib/answer-sheet";
import { answerSheetReviewReadOnly } from "@/lib/answer-sheet-format";
import { AuthenticatedImportImage } from "./authenticated-import-image";

type NodePath = number[]; // [sectionIndex, questionIndex, childIndex, ...]

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function getNode(sheet: AnsSheet, path: NodePath): AnsNode {
  const section = sheet.sections[path[0]];
  let node = section.questions![path[1]];
  for (let i = 2; i < path.length; i++) node = node.children![path[i]];
  return node;
}

function setNode(sheet: AnsSheet, path: NodePath, next: AnsNode): AnsSheet {
  const copy = clone(sheet);
  const section = copy.sections[path[0]];
  if (path.length === 2) {
    section.questions![path[1]] = next;
    return copy;
  }
  let parent = section.questions![path[1]];
  for (let i = 2; i < path.length - 1; i++) parent = parent.children![path[i]];
  parent.children![path[path.length - 1]] = next;
  return copy;
}

export default function AnswerSheetReview({
  token,
  importId,
  detail,
}: {
  token: string;
  importId: string;
  detail: ExamImportDetail;
}) {
  const router = useRouter();
  const [sheet, setSheet] = useState<AnsSheet | null>(
    detail.reviewed_answer_sheet_json ? clone(detail.reviewed_answer_sheet_json) : null,
  );
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [notice, setNotice] = useState<string>();
  const [error, setError] = useState<string>();

  function patchNode(path: NodePath, patch: Partial<AnsNode>) {
    setSheet((s) => (s ? setNode(s, path, { ...getNode(s, path), ...patch }) : s));
  }

  async function onSave() {
    if (!sheet) return;
    setSaving(true);
    setNotice(undefined);
    setError(undefined);
    try {
      await saveReviewed(token, importId, sheet);
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
    setError(undefined);
    try {
      await approveImport(token, importId);
      router.push("/imports");
    } catch (e) {
      setError(e instanceof ApiError ? e.body.detail : "Approve failed.");
      setApproving(false);
    }
  }

  if (!sheet) return null;
  const isCompleted = answerSheetReviewReadOnly(detail.status);

  return (
    <main className="mx-auto w-full max-w-6xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <Link href="/imports" className="text-sm text-muted-foreground underline">
            ← Imports / 匯入列表
          </Link>
          <h1 className="text-xl font-semibold">{detail.source_filename}</h1>
          <p className="text-sm text-muted-foreground">
            Status: {detail.status} · Type: Answer Sheet / 答案卷 · Extractor: deterministic
          </p>
        </div>
        <div className="flex gap-2">
          {isCompleted && (
            <Button asChild>
              <Link href={`/imports/${importId}/format`}>Format / 套用格式</Link>
            </Button>
          )}
          <Button variant="outline" onClick={() => void onSave()} disabled={saving || isCompleted}>
            <Save className="size-4" /> {saving ? "Saving…" : "Save / 儲存"}
          </Button>
          <Button onClick={() => void onApprove()} disabled={approving || isCompleted}>
            <Check className="size-4" /> {approving ? "Importing…" : "Approve Import / 批准匯入"}
          </Button>
        </div>
      </div>

      {notice && (
        <p className="mb-3 rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {notice}
        </p>
      )}
      {isCompleted && (
        <p className="mb-3 rounded border bg-muted px-3 py-2 text-sm">
          Completed answer sheets are read-only. Approval records durable completion; no Question
          Library questions were created. / 已完成的答案卷只供檢視。
        </p>
      )}
      {error && (
        <p className="mb-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {(sheet.asset_refs ?? []).length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {(sheet.asset_refs ?? []).map((ref) => (
            <AuthenticatedImportImage
              key={ref.local_id}
              token={token}
              importId={importId}
              localId={ref.local_id}
              className="max-h-24 rounded border"
            />
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
        <section className="space-y-5">
          {sheet.sections.map((section, si) => (
            <SectionView key={si} section={section} sectionIndex={si} onPatch={patchNode} readOnly={isCompleted} token={token} importId={importId} />
          ))}
        </section>

        <aside className="space-y-4">
          <WarningsPanel sheet={sheet} />
          <section className="rounded-lg border bg-card p-4">
            <h2 className="mb-2 text-sm font-semibold">How to review / 審閱方式</h2>
            <p className="text-sm text-muted-foreground">
              檢查題號階層、答案與分數；修正 marks 或答案後按「Save」。警告不阻擋 Approve，但請確認
              declared total 與 computed total 的差異後再批准。
            </p>
          </section>
        </aside>
      </div>
    </main>
  );
}

function SectionView({
  section,
  sectionIndex,
  onPatch,
  readOnly,
  token,
  importId,
}: {
  section: AnsSection;
  sectionIndex: number;
  onPatch: (path: NodePath, patch: Partial<AnsNode>) => void;
  readOnly: boolean;
  token: string;
  importId: string;
}) {
  const declared = section.declared_total;
  const computed = section.computed_total;
  const mismatch = totalsMismatch(section);

  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="text-base font-semibold">{section.title}</h2>
      <p className="mb-1 text-sm text-muted-foreground">
        Declared total: {declared ?? "—"} · Computed total: {computed ?? "—"}
        {mismatch && (
          <span className="ml-2 inline-flex items-center gap-1 text-amber-700">
            <AlertTriangle className="size-4" /> Declared total does not match extracted leaf marks.
          </span>
        )}
      </p>

      {section.mcq && section.mcq.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium uppercase text-muted-foreground">
            多項選擇 (MCQ) {section.mcq.length} 題
          </p>
          <p className="text-sm">{section.mcq.map(([n, a]) => `${n}.${a}`).join("  ")}</p>
        </div>
      )}

      {section.standalone_non_text && (
        <p className="mb-2 flex items-center gap-1 text-sm text-amber-700">
          <ImageIcon className="size-4" /> Section contains detached image content (manual review).
        </p>
      )}

      <div className="mt-3 space-y-2">
        {(section.questions ?? []).map((q, qi) => (
          <QuestionNodeView
            key={qi}
            node={q}
            path={[sectionIndex, qi]}
            onPatch={onPatch}
            readOnly={readOnly}
            token={token}
            importId={importId}
          />
        ))}
      </div>
    </section>
  );
}

function QuestionNodeView({
  node,
  path,
  onPatch,
  readOnly,
  token,
  importId,
}: {
  node: AnsNode;
  path: NodePath;
  onPatch: (path: NodePath, patch: Partial<AnsNode>) => void;
  readOnly: boolean;
  token: string;
  importId: string;
}) {
  const depth = path.length - 2;
  const isLeaf = !node.children || node.children.length === 0;

  return (
    <div className="rounded-md border bg-background/50 p-2" style={{ marginLeft: depth * 16 }}>
      <div className="flex items-center gap-2">
        <span className="font-medium">{node.label ?? "?"}</span>
        {node.has_non_text_content && (
          <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800">
            <ImageIcon className="size-3" /> Non-text / diagram content detected. Manual review required.
          </span>
        )}
        {isLeaf ? (
          <div className="ml-auto flex items-center gap-1 text-sm">
            Marks
            <Input
              aria-label="marks"
              type="number"
              step="0.5"
              min="0"
              className="h-7 w-20"
              value={node.marks ?? ""}
              placeholder="?"
              disabled={readOnly}
              onChange={(e) =>
                onPatch(path, { marks: e.target.value === "" ? null : e.target.value })
              }
            />
          </div>
        ) : (
          <span className="ml-auto text-sm text-muted-foreground">
            = {leafMarks(node) ?? "?"}分
          </span>
        )}
      </div>

      {isLeaf && (node.answer ?? []).length > 0 && (
        <textarea
          aria-label="answer"
          className="mt-1 min-h-16 w-full rounded-md border bg-background p-2 text-sm"
          value={(node.answer ?? []).join("\n")}
          disabled={readOnly}
          onChange={(e) => {
            const lines = e.target.value.split("\n");
            const nonParagraph = (node.answer_content ?? []).filter(
              (content) => content.kind !== "paragraph",
            );
            onPatch(path, {
              answer: lines,
              answer_content: [
                ...lines.filter(Boolean).map((text) => ({ kind: "paragraph" as const, text })),
                ...nonParagraph,
              ],
            });
          }}
        />
      )}

      {(node.answer_content ?? []).map((content, index) => {
        if (content.kind === "table") {
          return (
            <table key={index} className="mt-2 w-full border-collapse text-sm">
              <tbody>
                {content.rows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex} className="border p-1">{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          );
        }
        if (content.kind === "image") {
          return <AuthenticatedImportImage key={index} token={token} importId={importId} localId={content.local_id} className="mt-2 max-h-64 rounded border" />;
        }
        if (content.kind === "unsupported") {
          return <p key={index} className="mt-1 text-sm text-destructive">Unsupported content: {content.reason}</p>;
        }
        return null;
      })}

      {(node.children ?? []).map((child, ci) => (
        <QuestionNodeView key={ci} node={child} path={[...path, ci]} onPatch={onPatch} readOnly={readOnly} token={token} importId={importId} />
      ))}
    </div>
  );
}

function WarningsPanel({ sheet }: { sheet: AnsSheet }) {
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="mb-2 text-sm font-semibold">Warnings / 驗證問題</h2>
      {sheet.warnings.length === 0 ? (
        <p className="text-sm text-muted-foreground">No warnings.</p>
      ) : (
        <ul className="space-y-2">
          {sheet.warnings.map((w, i) => (
            <li key={i} className="text-sm">
              <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800">
                <AlertTriangle className="size-3" /> {w.code}
              </span>{" "}
              <span className="text-muted-foreground">{w.message}</span>
              {w.section && <span className="block text-xs text-muted-foreground">in {w.section}</span>}
              {w.declared != null && w.computed != null && (
                <span className="block text-xs text-muted-foreground">
                  declared {w.declared} / computed {w.computed}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
