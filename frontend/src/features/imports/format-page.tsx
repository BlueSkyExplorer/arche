"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, FileDown, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { leafMarks, totalsMismatch } from "@/lib/answer-sheet";
import { canExportAnswerSheet, metadataComplete } from "@/lib/answer-sheet-format";
import {
  downloadAnswerSheetExport,
  exportAnswerSheet,
  previewAnswerSheet,
  type AnswerSheetPreview,
  type DocumentMetadata,
} from "@/lib/api/answer-sheet-exports";
import { ApiError } from "@/lib/api/client";
import { getExamImport, type AnsNode, type AnsSheet, type ExamImportDetail } from "@/lib/api/exam-imports";
import { listTemplates, type TemplateProfile } from "@/lib/api/templates";
import { AuthenticatedImportImage } from "./authenticated-import-image";

const EMPTY_METADATA: DocumentMetadata = {
  school_name: "",
  academic_year: "",
  exam_name: "",
  level: "",
  subject: "",
  document_type: "參考答案",
};

const FIELD_LABELS: Record<keyof DocumentMetadata, string> = {
  school_name: "School name / 學校名稱",
  academic_year: "Academic year / 學年",
  exam_name: "Exam name / 考試名稱",
  level: "Level / 級別",
  subject: "Subject / 科目",
  document_type: "Document type / 文件類型",
};

function message(error: unknown): string {
  return error instanceof ApiError ? error.body.detail : "Unable to format answer sheet.";
}

export default function AnswerSheetFormatPage({ token, importId }: { token: string; importId: string }) {
  const [detail, setDetail] = useState<ExamImportDetail>();
  const [templates, setTemplates] = useState<TemplateProfile[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [metadata, setMetadata] = useState<DocumentMetadata>(EMPTY_METADATA);
  const [preview, setPreview] = useState<AnswerSheetPreview>();
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    let active = true;
    Promise.all([getExamImport(token, importId), listTemplates(token)])
      .then(([loadedImport, loadedTemplates]) => {
        if (!active) return;
        setDetail(loadedImport);
        setTemplates(loadedTemplates);
        if (loadedTemplates[0]) {
          setTemplateId(loadedTemplates[0].id);
          setMetadata((current) => ({ ...current, school_name: loadedTemplates[0].school_name }));
        }
      })
      .catch((caught: unknown) => {
        if (active) setError(message(caught));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, importId]);

  function selectTemplate(nextId: string) {
    setTemplateId(nextId);
    setPreview(undefined);
    const selected = templates.find((template) => template.id === nextId);
    if (selected) setMetadata((current) => ({ ...current, school_name: selected.school_name }));
  }

  async function generatePreview() {
    if (!templateId || !metadataComplete(metadata)) {
      setError("Select a template and complete every metadata field.");
      return;
    }
    setGenerating(true);
    setError(undefined);
    try {
      setPreview(await previewAnswerSheet(token, importId, templateId, metadata));
    } catch (caught) {
      setError(message(caught));
    } finally {
      setGenerating(false);
    }
  }

  async function downloadDocx() {
    if (!canExportAnswerSheet(preview?.record ?? null)) return;
    setExporting(true);
    setError(undefined);
    try {
      const record = await exportAnswerSheet(token, importId, templateId, metadata);
      if (record.status !== "succeeded") throw new Error(record.error_message ?? "Export blocked");
      const blob = await downloadAnswerSheetExport(token, record.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${detail?.source_filename.replace(/\.[^.]+$/, "") || "answer-sheet"}.docx`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : message(caught));
    } finally {
      setExporting(false);
    }
  }

  if (loading) return <main className="mx-auto max-w-6xl p-6 text-muted-foreground">Loading…</main>;
  if (!detail) return <main className="mx-auto max-w-6xl p-6 text-destructive">{error}</main>;
  if (detail.import_type !== "answer_sheet" || detail.status !== "completed") {
    return (
      <main className="mx-auto max-w-6xl p-6">
        <p className="text-destructive">Formatting is available only after an answer sheet is completed.</p>
        <Link href={`/imports/${importId}`} className="text-sm underline">Back to review</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 p-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href={`/imports/${importId}`} className="text-sm text-muted-foreground underline">← Review / 審閱</Link>
          <h1 className="text-2xl font-semibold">Format answer sheet / 套用答案卷格式</h1>
          <p className="text-sm text-muted-foreground">{detail.source_filename} · {detail.status}</p>
        </div>
        <Button
          onClick={() => void downloadDocx()}
          disabled={!canExportAnswerSheet(preview?.record ?? null) || exporting}
        >
          <FileDown className="size-4" /> {exporting ? "Exporting…" : "Export DOCX"}
        </Button>
      </header>

      <section className="rounded-lg border bg-card p-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <label className="grid gap-1 text-sm">
            Template profile / 格式範本
            <select
              aria-label="Template profile / 格式範本"
              className="h-9 rounded-md border bg-background px-3"
              value={templateId}
              onChange={(event) => selectTemplate(event.target.value)}
            >
              <option value="">Select…</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>{template.name} (v{template.version})</option>
              ))}
            </select>
          </label>
          {(Object.keys(FIELD_LABELS) as (keyof DocumentMetadata)[]).map((field) => (
            <label key={field} className="grid gap-1 text-sm">
              {FIELD_LABELS[field]}
              <Input
                aria-label={FIELD_LABELS[field]}
                value={metadata[field]}
                onChange={(event) => {
                  setMetadata((current) => ({ ...current, [field]: event.target.value }));
                  setPreview(undefined);
                }}
              />
            </label>
          ))}
        </div>
        <Button className="mt-4" onClick={() => void generatePreview()} disabled={generating || templates.length === 0}>
          <RefreshCw className="size-4" /> {generating ? "Generating…" : "Generate Preview / 產生預覽"}
        </Button>
        {templates.length === 0 && <p className="mt-2 text-sm text-amber-700">Create a Template Profile first.</p>}
      </section>

      {error && <p role="alert" className="rounded border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      {preview && (
        <Preview
          token={token}
          importId={importId}
          sheet={preview.preview.answer_sheet}
          metadata={preview.preview.metadata}
          validation={preview.record.validation_json}
          template={templates.find((item) => item.id === templateId)}
        />
      )}
    </main>
  );
}

function substituteMetadata(value: string, metadata: DocumentMetadata): string {
  return value.replace(/{{\s*([a-z_]+)\s*}}/g, (match, key: keyof DocumentMetadata) => (
    key in metadata ? metadata[key] : match
  )).trim();
}

function Preview({ token, importId, sheet, metadata, validation, template }: {
  token: string;
  importId: string;
  sheet: AnsSheet;
  metadata: DocumentMetadata;
  validation: AnswerSheetPreview["record"]["validation_json"];
  template?: TemplateProfile;
}) {
  const page = template?.page_config_json;
  const typography = template?.typography_config_json;
  const layout = template?.answer_sheet_layout_json;
  const metadataLines = layout?.metadata_lines.map((line) => substituteMetadata(line, metadata))
    ?? [metadata.school_name, `${metadata.academic_year} ${metadata.exam_name}`, `${metadata.level} ${metadata.subject} (${metadata.document_type})`];
  const header = template ? substituteMetadata(template.header_config_json.text, metadata) : "";
  const footer = template ? substituteMetadata(template.footer_config_json.text, metadata) : "";
  const previewStyle = {
    fontFamily: typography ? `${typography.chinese_font}, ${typography.latin_font}, sans-serif` : undefined,
    fontSize: typography ? `${typography.base_font_size_pt}pt` : undefined,
    lineHeight: typography?.line_spacing,
    paddingTop: page ? `${page.margin_top_mm}mm` : undefined,
    paddingRight: page ? `${page.margin_right_mm}mm` : undefined,
    paddingBottom: page ? `${page.margin_bottom_mm}mm` : undefined,
    paddingLeft: page ? `${page.margin_left_mm}mm` : undefined,
  };
  return (
    <section className="space-y-4 rounded-lg border bg-white text-black shadow-sm" style={previewStyle}>
      <p className="text-xs text-gray-500">Approximate browser preview; validate the generated DOCX in Word.</p>
      {header && <p className="border-b pb-2 text-center text-sm text-gray-600">Header: {header}</p>}
      <header className="text-center">
        {metadataLines.map((line, index) => index === 0
          ? <h2 key={index} className="text-xl font-bold">{line}</h2>
          : <p key={index}>{line}</p>)}
      </header>
      <ValidationPanel validation={validation} />
      {sheet.sections.map((section, sectionIndex) => {
        const heading = template?.role_styles.SectionHeading;
        return (
        <section key={sectionIndex} className="space-y-2">
          <h3
            className="font-bold"
            style={{
              fontSize: heading?.size_pt ? `${heading.size_pt}pt` : undefined,
              fontWeight: heading?.bold === false ? "normal" : undefined,
              textAlign: heading?.alignment && heading.alignment !== "justify" ? heading.alignment : undefined,
            }}
          >{section.title}</h3>
          <p className={totalsMismatch(section) ? "text-amber-700" : "text-gray-600"}>
            Declared {section.declared_total ?? "—"} / Computed {section.computed_total ?? "—"}
            {totalsMismatch(section) ? " · mismatch preserved" : ""}
          </p>
          {section.mcq && (
            <div
              className={`${layout?.mcq_borders === false ? "" : "border"} grid gap-x-8 p-2 text-sm`}
              style={{
                gridTemplateColumns: `repeat(${layout?.mcq_columns ?? 2}, minmax(0, 1fr))`,
                fontSize: layout?.mcq_font_size_pt ? `${layout.mcq_font_size_pt}pt` : undefined,
                textAlign: layout?.mcq_alignment,
              }}
            >
              {section.mcq.map(([number, answer]) => <span key={number}>{number}. {answer}</span>)}
            </div>
          )}
          {(section.questions ?? []).map((node, index) => (
            <PreviewNode key={index} node={node} depth={0} token={token} importId={importId} layout={layout} />
          ))}
        </section>
      )})}
      {footer && <p className="border-t pt-2 text-center text-sm text-gray-600">Footer: {footer}{template?.footer_config_json.page_numbering ? " · Page #" : ""}</p>}
    </section>
  );
}

function PreviewNode({ node, depth, token, importId, layout }: { node: AnsNode; depth: number; token: string; importId: string; layout?: TemplateProfile["answer_sheet_layout_json"] }) {
  const leaf = !node.children?.length;
  return (
    <div className="space-y-1" style={{ marginLeft: `${depth * (layout?.hierarchy_indent_mm ?? 7)}mm` }}>
      <p className="font-medium">{node.label ?? "?"} · {leaf ? (node.marks ?? "?") : (leafMarks(node) ?? "?")} marks</p>
      {(node.answer_content?.length ? node.answer_content : (node.answer ?? []).map((text) => ({ kind: "paragraph" as const, text }))).map((content, index) => {
        if (content.kind === "paragraph") return <p key={index} className="whitespace-pre-wrap text-sm">{content.text}</p>;
        if (content.kind === "table") return <table key={index} className="w-full border-collapse text-sm" style={{ textAlign: layout?.answer_table_alignment, fontSize: layout?.answer_table_font_size_pt ? `${layout.answer_table_font_size_pt}pt` : undefined }}><tbody>{content.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td className={layout?.answer_table_borders === false ? "p-1" : "border p-1"} key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table>;
        if (content.kind === "image") return <AuthenticatedImportImage key={index} token={token} importId={importId} localId={content.local_id} className="max-h-72 max-w-full" style={{ maxWidth: `${layout?.image_max_width_mm ?? 120}mm` }} />;
        return <p key={index} className="text-destructive">Unsupported: {content.reason}</p>;
      })}
      {(node.children ?? []).map((child, index) => <PreviewNode key={index} node={child} depth={depth + 1} token={token} importId={importId} layout={layout} />)}
    </div>
  );
}

function ValidationPanel({ validation }: { validation: AnswerSheetPreview["record"]["validation_json"] }) {
  return (
    <aside className={`rounded border p-3 text-sm ${validation.valid ? "border-emerald-400" : "border-destructive"}`}>
      <p className="font-medium">Render validation: {validation.valid ? "valid" : `${validation.blocking_count} blocking issue(s)`}</p>
      <p>MCQ {validation.stats.mcq_items} · leaves {validation.stats.leaves} · tables {validation.stats.tables} · images {validation.stats.images}</p>
      <ul>{validation.issues.map((issue, index) => <li key={index} className={issue.severity === "blocking" ? "text-destructive" : "text-amber-700"}><AlertTriangle className="mr-1 inline size-3" />[{issue.code}] {issue.message} · {issue.path}</li>)}</ul>
    </aside>
  );
}
