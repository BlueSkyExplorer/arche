"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FileUp, RefreshCw, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { createExamImport, listExamImports, type ExamImportSummary } from "@/lib/api/exam-imports";
import { canFormatAnswerSheet } from "@/lib/answer-sheet-format";

const STATUS_LABEL: Record<string, string> = {
  uploaded: "Uploaded / 已上傳",
  parsing: "Parsing / 解析中",
  extracting: "Extracting / 提取中",
  needs_review: "Needs Review / 待審閱",
  ready: "Ready / 就緒",
  materializing: "Importing / 匯入中",
  completed: "Completed / 已完成",
  failed: "Failed / 失敗",
};

function issueCount(imp: ExamImportSummary): number {
  return imp.validation_json?.issues?.length ?? 0;
}

function statusColor(status: string): string {
  if (status === "completed") return "text-emerald-600";
  if (status === "failed") return "text-destructive";
  if (status === "needs_review") return "text-amber-600";
  return "text-muted-foreground";
}

export default function ImportsPage({ token }: { token: string }) {
  const [imports, setImports] = useState<ExamImportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string>();
  const [importType, setImportType] = useState<"question_paper" | "answer_sheet">("question_paper");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(undefined);
    try {
      setImports(await listExamImports(token));
    } catch (e) {
      setError(e instanceof ApiError ? e.body.detail : "Unable to load imports.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    let active = true;
    listExamImports(token)
      .then((result) => {
        if (active) setImports(result);
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof ApiError ? e.body.detail : "Unable to load imports.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  async function onUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(undefined);
    try {
      await createExamImport(token, file, importType);
      if (fileRef.current) fileRef.current.value = "";
      await load();
    } catch (e) {
      setUploadError(e instanceof ApiError ? e.body.detail : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-6xl p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Exam Imports / 試卷匯入</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Upload a paper to auto-extract questions, marks and structure, then review and import.
        </p>
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-3 rounded-lg border bg-card p-4">
        <div className="flex items-center gap-2 text-sm">
          <label className="flex items-center gap-1">
            <input
              type="radio"
              name="import_type"
              value="question_paper"
              checked={importType === "question_paper"}
              onChange={() => setImportType("question_paper")}
            />
            Question Paper / 試卷
          </label>
          <label className="flex items-center gap-1">
            <input
              type="radio"
              name="import_type"
              value="answer_sheet"
              checked={importType === "answer_sheet"}
              onChange={() => setImportType("answer_sheet")}
            />
            Answer Sheet / 答案卷
          </label>
        </div>
        <input ref={fileRef} type="file" accept=".docx,.pdf,.doc" className="text-sm" />
        <Button onClick={onUpload} disabled={uploading}>
          <FileUp className="size-4" />
          {uploading ? "Importing…" : "Import / 匯入"}
        </Button>
        {uploadError && <p className="text-sm text-destructive">{uploadError}</p>}
      </div>

      {loading ? (
        <div className="rounded-lg border p-8 text-center text-muted-foreground">Loading… / 載入中</div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/40 p-6">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" className="mt-4" onClick={() => void load()}>
            <RefreshCw className="size-4" /> Retry
          </Button>
        </div>
      ) : imports.length === 0 ? (
        <div className="rounded-lg border border-dashed p-10 text-center text-muted-foreground">
          No imports yet. Upload a .docx or .pdf to get started.
        </div>
      ) : (
        <ul className="grid gap-3">
          {imports.map((imp) => (
            <li key={imp.id} className="flex items-center justify-between gap-4 rounded-lg border bg-card p-4">
              <div className="min-w-0">
                <h2 className="truncate font-medium">{imp.source_filename}</h2>
                <p className="mt-1 text-sm">
                  <span className={statusColor(imp.status)}>{STATUS_LABEL[imp.status] ?? imp.status}</span>
                  <span className="text-muted-foreground">
                    {" · "}
                    {imp.import_type === "answer_sheet"
                      ? "Answer Sheet / 答案卷"
                      : imp.extractor_name === "llm"
                        ? "AI"
                        : "Rule-based"}
                    {imp.fallback_occurred ? " (fallback)" : ""}
                  </span>
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {imp.import_type === "answer_sheet"
                    ? `${imp.current_warning_count} current warning${imp.current_warning_count === 1 ? "" : "s"} · ${imp.original_warning_count} original`
                    : `${issueCount(imp)} issue${issueCount(imp) === 1 ? "" : "s"}`}
                  {imp.failure_message ? ` · ${imp.failure_message}` : ""}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {imp.status === "needs_review" || imp.status === "ready" || imp.status === "completed" ? (
                  <Button asChild variant="outline">
                    <Link href={`/imports/${imp.id}`}>
                      <Eye className="size-4" /> Review
                    </Link>
                  </Button>
                ) : (
                  <Button asChild variant="outline">
                    <Link href={`/imports/${imp.id}`}>View</Link>
                  </Button>
                )}
                {canFormatAnswerSheet(imp) && (
                  <Button asChild>
                    <Link href={`/imports/${imp.id}/format`}>Format / 套用格式</Link>
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
