import { z } from "zod";

const boundedNumber = (min: number, max: number, message: string) => z.number().min(min, message).max(max, message);

export const templateFormSchema = z.object({
  name: z.string().trim().min(1, "請輸入範本名稱 / Template name is required"),
  schoolName: z.string().trim().min(1, "請輸入學校名稱 / School name is required"),
  logoAssetId: z.string().nullable().optional(),
  isActive: z.boolean(),
  pageSize: z.enum(["A4", "Letter"]),
  marginTop: boundedNumber(5, 50, "Margins must be 5–50 mm"),
  marginRight: boundedNumber(5, 50, "Margins must be 5–50 mm"),
  marginBottom: boundedNumber(5, 50, "Margins must be 5–50 mm"),
  marginLeft: boundedNumber(5, 50, "Margins must be 5–50 mm"),
  chineseFont: z.string().trim().min(1, "Chinese font is required"),
  latinFont: z.string().trim().min(1, "Latin font is required"),
  baseFontSize: boundedNumber(8, 36, "Font size must be 8–36 pt"),
  lineSpacing: boundedNumber(1, 3, "Line spacing must be 1–3"),
  headerText: z.string(), footerText: z.string(), pageNumbers: z.boolean(),
  sectionFontSize: boundedNumber(8, 36, "Font size must be 8–36 pt"),
  sectionBold: z.boolean(), sectionAlignment: z.enum(["left", "center", "right"]),
  questionNumberStyle: z.enum(["1", "1.", "(1)", "Q1", "Q1.", "arabic-dot", "lower-alpha", "upper-alpha", "roman"]),
  subQuestionStyle: z.enum(["a", "a.", "(a)", "arabic-dot", "lower-alpha", "upper-alpha", "roman"]),
  subSubQuestionStyle: z.enum(["a", "a.", "(a)", "arabic-dot", "lower-alpha", "upper-alpha", "roman"]),
  marksDisplayStyle: z.enum(["inline", "right", "below"]),
  marksFormat: z.string().refine(value => value.includes("{marks}"), "Marks format must include {marks}"),
  spacingBeforeQuestion: boundedNumber(0, 50, "Spacing must be 0–50 pt"),
  spacingAfterQuestion: boundedNumber(0, 50, "Spacing must be 0–50 pt"),
  answerSpaceLines: z.number().int().min(0).max(20),
});
export type TemplateFormValues = z.infer<typeof templateFormSchema>;

export const templateDefaults: TemplateFormValues = {
  name: "", schoolName: "", logoAssetId: null, isActive: true, pageSize: "A4",
  marginTop: 20, marginRight: 20, marginBottom: 20, marginLeft: 20,
  chineseFont: "Noto Sans CJK TC", latinFont: "Arial", baseFontSize: 12, lineSpacing: 1.5,
  headerText: "", footerText: "", pageNumbers: true, sectionFontSize: 14,
  sectionBold: true, sectionAlignment: "left", questionNumberStyle: "arabic-dot",
  subQuestionStyle: "lower-alpha", subSubQuestionStyle: "roman", marksDisplayStyle: "right", marksFormat: "({marks} marks)",
  spacingBeforeQuestion: 2, spacingAfterQuestion: 2, answerSpaceLines: 3,
};