"use client";

import { useCallback, useEffect, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, Controller } from "react-hook-form";
import { z } from "zod";
import { Plus, Pencil, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { QuestionEditor } from "./editor/question-editor";
import { IngestPanel } from "./ingest-panel";
import { contentSchema, hasSubQuestions, isValidContent, leafMarksTotal, normalizeContentForWire, type QuestionContent } from "@/lib/validation/content";
import { ApiError } from "@/lib/api/client";
import { createQuestion, listQuestions, updateQuestion, type Question, type QuestionInput } from "@/lib/api/questions";

const formSchema = z.object({
  internalTitle: z.string().trim().min(1, "請輸入內部標題 / Internal title is required"),
  subject: z.string().trim().min(1, "請輸入科目 / Subject is required"),
  level: z.string().trim().min(1, "請輸入級別 / Level is required"),
  tagsText: z.string(), marks: z.number().positive("分數必須大於 0 / Marks must be greater than zero"),
  sourceNote: z.string(), status: z.enum(["draft", "ready"]), content: contentSchema,
});
type FormValues = z.infer<typeof formSchema>;
const EMPTY: QuestionContent = { type: "doc", content: [{ type: "paragraph" }] };
const defaults: FormValues = { internalTitle: "", subject: "", level: "", tagsText: "", marks: 1, sourceNote: "", status: "draft", content: EMPTY };

function errorMessage(error: unknown) { return error instanceof ApiError ? error.body.detail : "Unable to reach the question service. Please try again."; }

export default function QuestionsPage({ token }: { token: string }) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Question>();
  const [saveError, setSaveError] = useState<string>();
  const form = useForm<FormValues>({ resolver: zodResolver(formSchema), defaultValues: defaults });
  const load = useCallback(async () => { setLoading(true); setLoadError(undefined); try { setQuestions(await listQuestions(token)); } catch (error) { setLoadError(errorMessage(error)); } finally { setLoading(false); } }, [token]);
  useEffect(() => {
    let active = true;
    listQuestions(token).then((result) => { if (active) setQuestions(result); }).catch((error: unknown) => { if (active) setLoadError(errorMessage(error)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token]);

  const openCreate = () => { setEditing(undefined); setSaveError(undefined); form.reset(defaults); setDialogOpen(true); };
  const openEdit = (question: Question) => {
    setEditing(question);
    setSaveError(undefined);
    const editorContent = normalizeContentForWire(question.content_json);
    delete editorContent.marks; // doc-level mark lives in the form's marks field, not the editor
    form.reset({
      internalTitle: question.internal_title,
      subject: question.subject,
      level: question.level,
      tagsText: question.tags_json.join(", "),
      marks: Number(question.marks),
      sourceNote: question.source_note ?? "",
      status: question.status,
      content: editorContent,
    });
    setDialogOpen(true);
  };
  const submit = form.handleSubmit(async (values) => {
    setSaveError(undefined);
    if (!isValidContent(values.content)) {
      form.setError("content", { message: "Invalid question content / 題目內容格式不正確" });
      return;
    }
    const content = normalizeContentForWire(values.content);
    const multiPart = hasSubQuestions(content);
    if (multiPart) {
      delete content.marks; // multipart: root (doc) marks must be absent — non-leaf
    } else {
      content.marks = values.marks; // standalone: doc.marks is the authoritative leaf
    }
    const total = multiPart ? leafMarksTotal(content) : values.marks;
    const input: QuestionInput = {
      internalTitle: values.internalTitle,
      subject: values.subject,
      level: values.level,
      tags: values.tagsText.split(/[,，]/u).map((tag) => tag.trim()).filter(Boolean),
      marks: total, // legacy column mirror; removed in ticket 07
      sourceNote: values.sourceNote,
      status: values.status,
      content,
    };
    try { if (editing) await updateQuestion(token, editing.id, input); else await createQuestion(token, input); setDialogOpen(false); await load(); } catch (error) { setSaveError(errorMessage(error)); }
  });

  return <main className="mx-auto w-full max-w-6xl p-6">
    <div className="mb-6 flex items-start justify-between gap-4"><div><h1 className="text-2xl font-semibold">Question Library / 題目庫</h1><p className="mt-1 text-sm text-muted-foreground">建立及重用中英文題目。Create and reuse bilingual questions.</p></div><Button onClick={openCreate}><Plus className="size-4" />新增題目</Button></div>
    <IngestPanel token={token} onSaved={load} />
    {loading ? <div className="rounded-lg border p-8 text-center text-muted-foreground" role="status">Loading questions… / 正在載入…</div> : loadError ? <div role="alert" className="rounded-lg border border-destructive/40 p-6"><p className="text-destructive">{loadError}</p><Button variant="outline" className="mt-4" onClick={() => void load()}><RefreshCw className="size-4" />Retry / 重試</Button></div> : questions.length === 0 ? <div className="rounded-lg border border-dashed p-10 text-center"><h2 className="font-medium">No questions yet / 尚未有題目</h2><p className="mt-1 text-sm text-muted-foreground">Create your first reusable question.</p><Button className="mt-4" onClick={openCreate}>新增題目</Button></div> : <ul className="grid gap-3">{questions.map((question) => <li key={question.id} className="flex items-center justify-between gap-4 rounded-lg border bg-card p-4"><div className="min-w-0"><h2 className="truncate font-medium">{question.internal_title}</h2><p className="mt-1 text-sm text-muted-foreground">{question.subject} · {question.level} · {Number(question.marks)} marks · {question.status}</p>{question.tags_json.length > 0 && <p className="mt-2 text-sm">{question.tags_json.map((tag) => <span key={tag} className="mr-2 rounded-full bg-muted px-2 py-1">{tag}</span>)}</p>}</div><Button variant="outline" onClick={() => openEdit(question)} aria-label={`Edit ${question.internal_title}`}><Pencil className="size-4" />Edit</Button></li>)}</ul>}
    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}><DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto"><DialogHeader><DialogTitle>{editing ? "Edit question / 編輯題目" : "New question / 新增題目"}</DialogTitle><DialogDescription>題目內容只會在你按儲存後提交。Content is submitted only when you save.</DialogDescription></DialogHeader>
      <form onSubmit={submit} className="grid gap-5" noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Internal title / 內部標題" error={form.formState.errors.internalTitle?.message}><Input {...form.register("internalTitle")} /></Field>
          <Field label="Subject / 科目" error={form.formState.errors.subject?.message}><Input {...form.register("subject")} /></Field>
          <Field label="Level / 級別" error={form.formState.errors.level?.message}><Input {...form.register("level")} /></Field>
          <Field label="Marks / 分數" error={form.formState.errors.marks?.message}>
            <Input type="number" min="0.01" step="0.01" {...form.register("marks", { valueAsNumber: true })} />
            <span className="text-xs text-muted-foreground">多子題題目總分由各子題分數加總；此欄只影響無子題的題目。</span>
          </Field>
          <Field label="Tags / 標籤（逗號分隔）"><Input placeholder="代數, 因式分解" {...form.register("tagsText")} /></Field>
          <Field label="Status / 狀態"><select className="h-9 rounded-md border bg-background px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" {...form.register("status")}><option value="draft">Draft / 草稿</option><option value="ready">Ready / 就緒</option></select></Field>
          <Field label="Source note / 來源註記" className="sm:col-span-2"><Input {...form.register("sourceNote")} /></Field>
        </div>
        <div><Label className="mb-2 block">Question content / 題目內容</Label><Controller control={form.control} name="content" render={({ field }) => <QuestionEditor value={field.value} onChange={field.onChange} />} />{form.formState.errors.content && <p className="mt-1 text-sm text-destructive">Invalid question content / 題目內容格式不正確</p>}</div>
        {saveError && <p role="alert" className="text-sm text-destructive">{saveError}</p>}
        <DialogFooter><Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel / 取消</Button><Button type="submit" disabled={form.formState.isSubmitting}>{form.formState.isSubmitting ? "Saving…" : "Save / 儲存"}</Button></DialogFooter>
      </form>
    </DialogContent></Dialog></main>;
}

function Field({ label, error, className, children }: { label: string; error?: string; className?: string; children: React.ReactNode }) { return <div className={`grid gap-2 ${className ?? ""}`}><Label className="grid gap-2">{label}{children}</Label>{error && <p className="text-sm text-destructive">{error}</p>}</div>; }
