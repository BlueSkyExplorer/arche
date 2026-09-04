import { apiDownload, apiFetch } from "./client";
import type { Question } from "./questions";
import type { QuestionNumberStyle } from "@/lib/validation/numbering";

export type PaperSummary = { id: string; title: string; subject: string; level: string; paper_date: string | null; duration_minutes: number | null; template_profile_id: string; status?: string };
export type PaperQuestion = { id?: string; question_id: string; position: number; marks_override: number | string | null; display_number?: string; question: Question };
export type PaperSection = { id: string; title: string; position: number; instructions_json?: unknown; questions: PaperQuestion[] };
export type PaperDetail = PaperSummary & { instructions_json: string | { text: string }[] | null; sections: PaperSection[]; template_profile?: { id: string; name: string; typography_config_json?: Record<string, unknown>; numbering_config_json?: { question_style?: QuestionNumberStyle }; question_style_config_json?: Record<string, unknown> } };
export type PaperInput = { title: string; subject: string; level: string; paperDate: string; durationMinutes: number; instructions: string; templateProfileId: string };
export type ExportRecord = { id: string; status: "pending" | "processing" | "succeeded" | "failed"; format: "docx" | "pdf"; error_message?: string | null };

const unwrap = <T,>(response: T[] | { items: T[] }) => Array.isArray(response) ? response : response.items;
const payload = (v: Partial<PaperInput>) => ({ ...(v.title !== undefined && { title: v.title }), ...(v.subject !== undefined && { subject: v.subject }), ...(v.level !== undefined && { level: v.level }), ...(v.paperDate !== undefined && { paper_date: v.paperDate || null }), ...(v.durationMinutes !== undefined && { duration_minutes: v.durationMinutes }), ...(v.instructions !== undefined && { instructions_json: v.instructions.trim() ? [{ text: v.instructions }] : [] }), ...(v.templateProfileId !== undefined && { template_profile_id: v.templateProfileId }) });
export async function listPapers(token: string) { return unwrap(await apiFetch<PaperSummary[] | { items: PaperSummary[] }>("/api/v1/papers", token)); }
export function getPaper(token: string, id: string) { return apiFetch<PaperDetail>(`/api/v1/papers/${encodeURIComponent(id)}`, token); }
export function createPaper(token: string, input: PaperInput) { return apiFetch<PaperSummary>("/api/v1/papers", token, { method: "POST", body: JSON.stringify(payload(input)) }); }
export function updatePaper(token: string, id: string, input: Partial<PaperInput>) { return apiFetch<PaperDetail>(`/api/v1/papers/${encodeURIComponent(id)}`, token, { method: "PATCH", body: JSON.stringify(payload(input)) }); }
export function addSection(token: string, paperId: string, title: string, position?: number) { return apiFetch<PaperSection>(`/api/v1/papers/${encodeURIComponent(paperId)}/sections`, token, { method: "POST", body: JSON.stringify({ title, ...(position !== undefined && { position }) }) }); }
export function updateSection(token: string, paperId: string, sectionId: string, input: { title?: string; position?: number }) { return apiFetch<PaperSection>(`/api/v1/papers/${encodeURIComponent(paperId)}/sections/${encodeURIComponent(sectionId)}`, token, { method: "PATCH", body: JSON.stringify(input) }); }
export function deleteSection(token: string, paperId: string, sectionId: string) { return apiFetch<void>(`/api/v1/papers/${encodeURIComponent(paperId)}/sections/${encodeURIComponent(sectionId)}`, token, { method: "DELETE" }); }
export function putSectionQuestions(token: string, paperId: string, sectionId: string, questions: { question_id: string; marks_override?: number | null }[]) { return apiFetch<PaperSection>(`/api/v1/papers/${encodeURIComponent(paperId)}/sections/${encodeURIComponent(sectionId)}/questions`, token, { method: "PUT", body: JSON.stringify(questions) }); }
export function createExport(token: string, paperId: string, format: "docx" | "pdf") { return apiFetch<ExportRecord>(`/api/v1/papers/${encodeURIComponent(paperId)}/export?format=${format}`, token, { method: "POST" }); }
export function getExport(token: string, id: string) { return apiFetch<ExportRecord>(`/api/v1/exports/${encodeURIComponent(id)}`, token); }
export function downloadExport(token: string, id: string) { return apiDownload(`/api/v1/exports/${encodeURIComponent(id)}/download`, token); }
