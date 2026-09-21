import { apiFetch } from "./client";
import type { TemplateFormValues } from "@/lib/validation/template";

type RoleStyle = {
  latin_font?: string | null;
  east_asia_font?: string | null;
  size_pt?: number | null;
  bold?: boolean | null;
  alignment?: "left" | "center" | "right" | "justify" | null;
  spacing_before_pt?: number | null;
  spacing_after_pt?: number | null;
  indentation_mm?: number | null;
};

export type TemplateProfile = {
  id: string; name: string; version: number; school_name: string; logo_asset_id: string | null; is_active: boolean;
  page_config_json: { size: TemplateFormValues["pageSize"]; margin_top_mm: number; margin_right_mm: number; margin_bottom_mm: number; margin_left_mm: number };
  typography_config_json: { chinese_font: string; latin_font: string; base_font_size_pt: number; line_spacing: number };
  header_config_json: { text: string }; footer_config_json: { text: string; page_numbering: boolean };
  numbering_config_json: { question_style: TemplateFormValues["questionNumberStyle"]; sub_question_style: TemplateFormValues["subQuestionStyle"]; sub_sub_question_style: TemplateFormValues["subSubQuestionStyle"] };
  section_style_config_json: { spacing_before_pt: number; spacing_after_pt: number };
  question_style_config_json: { spacing_before_pt: number; spacing_after_pt: number; marks_display: TemplateFormValues["marksDisplayStyle"]; marks_format: string; default_answer_lines: number };
  answer_sheet_layout_json: {
    metadata_lines: string[];
    mcq_columns: 1 | 2 | 3;
    mcq_borders: boolean;
    mcq_question_width_mm: number;
    mcq_answer_width_mm: number;
    mcq_alignment: "left" | "center" | "right";
    mcq_font_size_pt: number;
    mcq_row_height_mm: number;
    hierarchy_indent_mm: number;
    show_parent_totals: boolean;
    image_max_width_mm: number;
    answer_table_borders: boolean;
    answer_table_alignment: "left" | "center" | "right";
    answer_table_font_size_pt: number;
    repeat_table_header: boolean;
  };
  role_styles: Partial<Record<"Normal" | "PaperTitle" | "PaperMetadata" | "SectionHeading" | "QuestionBody" | "QuestionSubpart" | "QuestionMarks" | "AnswerSpace", RoleStyle>>;
};

const unwrap = <T,>(response: T[] | { items: T[] }) => Array.isArray(response) ? response : response.items;
export async function listTemplates(token: string) { return unwrap(await apiFetch<TemplateProfile[] | { items: TemplateProfile[] }>("/api/v1/templates", token)); }
export function getTemplate(token: string, id: string) { return apiFetch<TemplateProfile>(`/api/v1/templates/${encodeURIComponent(id)}`, token); }
export type TemplateFormSource = Pick<
  TemplateProfile,
  | "name" | "school_name" | "logo_asset_id" | "is_active"
  | "page_config_json" | "typography_config_json" | "header_config_json"
  | "footer_config_json" | "numbering_config_json" | "question_style_config_json"
  | "answer_sheet_layout_json" | "role_styles"
>;

export function templateToForm(t: TemplateFormSource): TemplateFormValues {
  const sectionHeading = t.role_styles?.SectionHeading;
  return {
    name: t.name, schoolName: t.school_name, logoAssetId: t.logo_asset_id, isActive: t.is_active,
    pageSize: t.page_config_json.size, marginTop: t.page_config_json.margin_top_mm, marginRight: t.page_config_json.margin_right_mm, marginBottom: t.page_config_json.margin_bottom_mm, marginLeft: t.page_config_json.margin_left_mm,
    chineseFont: t.typography_config_json.chinese_font, latinFont: t.typography_config_json.latin_font, baseFontSize: t.typography_config_json.base_font_size_pt, lineSpacing: t.typography_config_json.line_spacing,
    headerText: t.header_config_json.text, footerText: t.footer_config_json.text, pageNumbers: t.footer_config_json.page_numbering,
    sectionFontSize: sectionHeading?.size_pt ?? 14, sectionBold: sectionHeading?.bold ?? true, sectionAlignment: sectionHeading?.alignment === "justify" ? "left" : (sectionHeading?.alignment ?? "left"),
    questionNumberStyle: t.numbering_config_json.question_style, subQuestionStyle: t.numbering_config_json.sub_question_style, subSubQuestionStyle: t.numbering_config_json.sub_sub_question_style, marksDisplayStyle: t.question_style_config_json.marks_display,
    marksFormat: t.question_style_config_json.marks_format, spacingBeforeQuestion: t.question_style_config_json.spacing_before_pt, spacingAfterQuestion: t.question_style_config_json.spacing_after_pt, answerSpaceLines: t.question_style_config_json.default_answer_lines,
    metadataLinesText: t.answer_sheet_layout_json.metadata_lines.join("\n"),
    mcqColumns: t.answer_sheet_layout_json.mcq_columns,
    mcqBorders: t.answer_sheet_layout_json.mcq_borders,
    mcqQuestionWidth: t.answer_sheet_layout_json.mcq_question_width_mm,
    mcqAnswerWidth: t.answer_sheet_layout_json.mcq_answer_width_mm,
    mcqAlignment: t.answer_sheet_layout_json.mcq_alignment,
    mcqFontSize: t.answer_sheet_layout_json.mcq_font_size_pt,
    mcqRowHeight: t.answer_sheet_layout_json.mcq_row_height_mm,
    hierarchyIndent: t.answer_sheet_layout_json.hierarchy_indent_mm,
    showParentTotals: t.answer_sheet_layout_json.show_parent_totals,
    imageMaxWidth: t.answer_sheet_layout_json.image_max_width_mm,
    answerTableBorders: t.answer_sheet_layout_json.answer_table_borders,
    answerTableAlignment: t.answer_sheet_layout_json.answer_table_alignment,
    answerTableFontSize: t.answer_sheet_layout_json.answer_table_font_size_pt,
    repeatTableHeader: t.answer_sheet_layout_json.repeat_table_header,
  };
}

export function templatePayload(v: TemplateFormValues) { return {
  name: v.name, school_name: v.schoolName, logo_asset_id: v.logoAssetId || null, is_active: v.isActive,
  page_config_json: { size: v.pageSize, margin_top_mm: v.marginTop, margin_right_mm: v.marginRight, margin_bottom_mm: v.marginBottom, margin_left_mm: v.marginLeft },
  typography_config_json: { chinese_font: v.chineseFont, latin_font: v.latinFont, base_font_size_pt: v.baseFontSize, line_spacing: v.lineSpacing },
  header_config_json: { text: v.headerText }, footer_config_json: { text: v.footerText, page_numbering: v.pageNumbers },
  numbering_config_json: { question_style: v.questionNumberStyle, sub_question_style: v.subQuestionStyle, sub_sub_question_style: v.subSubQuestionStyle },
  section_style_config_json: { spacing_before_pt: 0, spacing_after_pt: 0 },
  question_style_config_json: { spacing_before_pt: v.spacingBeforeQuestion, spacing_after_pt: v.spacingAfterQuestion, marks_display: v.marksDisplayStyle, marks_format: v.marksFormat, default_answer_lines: v.answerSpaceLines },
  answer_sheet_layout_json: {
    metadata_lines: v.metadataLinesText.split("\n").map(line => line.trim()).filter(Boolean),
    mcq_columns: v.mcqColumns,
    mcq_borders: v.mcqBorders,
    mcq_question_width_mm: v.mcqQuestionWidth,
    mcq_answer_width_mm: v.mcqAnswerWidth,
    mcq_alignment: v.mcqAlignment,
    mcq_font_size_pt: v.mcqFontSize,
    mcq_row_height_mm: v.mcqRowHeight,
    hierarchy_indent_mm: v.hierarchyIndent,
    show_parent_totals: v.showParentTotals,
    image_max_width_mm: v.imageMaxWidth,
    answer_table_borders: v.answerTableBorders,
    answer_table_alignment: v.answerTableAlignment,
    answer_table_font_size_pt: v.answerTableFontSize,
    repeat_table_header: v.repeatTableHeader,
  },
  role_styles: { SectionHeading: { size_pt: v.sectionFontSize, bold: v.sectionBold, alignment: v.sectionAlignment } },
}; }
export function createTemplate(token: string, v: TemplateFormValues) { return apiFetch<TemplateProfile>("/api/v1/templates", token, { method: "POST", body: JSON.stringify(templatePayload(v)) }); }
export function updateTemplate(token: string, id: string, v: TemplateFormValues) { return apiFetch<TemplateProfile>(`/api/v1/templates/${encodeURIComponent(id)}`, token, { method: "PATCH", body: JSON.stringify(templatePayload(v)) }); }
export function uploadLogo(token: string, file: File) { const body = new FormData(); body.set("kind", "logo"); body.set("file", file); return apiFetch<{ id: string }>("/api/v1/assets", token, { method: "POST", body }); }

export type TemplateImportResult = {
  profile: TemplateFormSource;
  confidence: Record<string, number>;
  unmapped: string[];
  detected_fields: Record<string, { value?: string | null; candidate?: string | null; confidence: number; review_required: boolean; source?: string | null }>;
  evidence: Record<string, { location: string; text: string }[]>;
  defaults_used: string[];
};

export function importTemplate(token: string, file: File): Promise<TemplateImportResult> {
  const body = new FormData();
  body.set("file", file);
  return apiFetch<TemplateImportResult>("/api/v1/templates/import", token, { method: "POST", body });
}

export function templateDraftToForm(draft: TemplateImportResult): TemplateFormValues {
  return templateToForm(draft.profile);
}
