"use client";

import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { importTemplate, templateDraftToForm, type TemplateImportResult } from "@/lib/api/templates";
import type { TemplateFormValues } from "@/lib/validation/template";

export function ImportWizard({
  token,
  onImported,
}: {
  token: string;
  onImported: (values: TemplateFormValues, draft: TemplateImportResult) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const pick = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    setError(undefined);
    try {
      const draft = await importTemplate(token, file);
      onImported(templateDraftToForm(draft), draft);
    } catch (e) {
      setError(e instanceof ApiError ? e.body.detail : "Import failed / 匯入失敗");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".docx"
        aria-label="Import DOCX file"
        className="hidden"
        onChange={(e) => void pick(e.target.files?.[0])}
      />
      <Button type="button" variant="outline" disabled={busy} onClick={() => inputRef.current?.click()}>
        <Upload className="size-4" />
        {busy ? "Importing… / 匯入中…" : "Import DOCX / 匯入格式"}
      </Button>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </>
  );
}
