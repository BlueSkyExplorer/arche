"use client";

import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { importTemplate, templateDraftToForm, type TemplateImportResult } from "@/lib/api/templates";
import { ingestQuestions, type QuestionIngestDraft } from "@/lib/api/questions";
import type { TemplateFormValues } from "@/lib/validation/template";

export function ImportWizard({
  token,
  onImported,
}: {
  token: string;
  onImported: (
    values: TemplateFormValues,
    draft: TemplateImportResult,
    questions: QuestionIngestDraft[],
    scannedQuestions: boolean,
  ) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [mode, setMode] = useState<"format_only" | "format_and_questions">("format_only");

  const pick = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    setError(undefined);
    try {
      const draft = await importTemplate(token, file);
      let questions: QuestionIngestDraft[] = [];
      if (mode === "format_and_questions") {
        // A question scan failure must not block the format import.
        try {
          questions = await ingestQuestions(token, { file });
        } catch {
          questions = [];
        }
      }
      onImported(templateDraftToForm(draft), draft, questions, mode === "format_and_questions");
    } catch (e) {
      setError(e instanceof ApiError ? e.body.detail : "Import failed / 匯入失敗");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <>
      <fieldset className="flex items-center gap-3 text-sm">
        <legend className="sr-only">Template import mode</legend>
        <label className="flex items-center gap-1">
          <input
            type="radio"
            name="template_import_mode"
            checked={mode === "format_only"}
            onChange={() => setMode("format_only")}
          />
          Format template only / 只匯入格式
        </label>
        <label className="flex items-center gap-1">
          <input
            type="radio"
            name="template_import_mode"
            checked={mode === "format_and_questions"}
            onChange={() => setMode("format_and_questions")}
          />
          Format + scan questions / 格式及題目
        </label>
      </fieldset>
      <input
        ref={inputRef}
        type="file"
        accept=".doc,.docx"
        aria-label="Import DOCX file"
        className="hidden"
        onChange={(e) => void pick(e.target.files?.[0])}
      />
      <Button type="button" variant="outline" disabled={busy} onClick={() => inputRef.current?.click()}>
        <Upload className="size-4" />
        {busy ? "Importing… / 匯入中…" : "Import Word / 匯入格式"}
      </Button>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </>
  );
}
