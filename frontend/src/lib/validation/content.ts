import { z } from "zod";

// TODO(M4b): generate from backend content.schema.json
const markSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("bold") }).strict(),
  z.object({ type: z.literal("italic") }).strict(),
  z.object({ type: z.literal("underline") }).strict(),
  z.object({ type: z.literal("subscript") }).strict(),
  z.object({ type: z.literal("superscript") }).strict(),
  z.object({
    type: z.literal("link"),
    attrs: z.object({
      href: z.string(),
      title: z.string().nullable().optional(),
      target: z.string().nullable().optional(),
      rel: z.string().nullable().optional(),
    }).strict(),
  }).strict(),
]);

const leafMarksSchema = z.union([z.number().min(0), z.string().min(1), z.null()]).optional();

export type ContentNode = {
  type: string;
  attrs?: Record<string, unknown>;
  content?: ContentNode[];
  text?: string;
  marks?: z.infer<typeof markSchema>[];
};
export type QuestionContent = { type: "doc"; marks?: string | number | null; content: ContentNode[] };

const textNode = z.object({ type: z.literal("text"), text: z.string(), marks: z.array(markSchema).optional() }).strict();
const hardBreakNode = z.object({ type: z.literal("hardBreak") }).strict();
const imageNode = z.object({
  type: z.literal("image"),
  attrs: z.object({ assetId: z.string().uuid(), alt: z.string().optional(), widthMm: z.number().positive().optional() }).strict(),
}).strict();
const answerSpaceNode = z.object({
  type: z.literal("answerSpace"),
  attrs: z.union([
    z.object({ lines: z.number().int().min(1) }).strict(),
    z.object({ blankHeightMm: z.number().min(1) }).strict(),
  ]),
}).strict();

const inlineNodeSchema: z.ZodType<ContentNode, ContentNode> = z.lazy(() => z.union([textNode, hardBreakNode]));
const blockNodeSchema: z.ZodType<ContentNode, ContentNode> = z.lazy(() => z.union([
  z.object({ type: z.literal("paragraph"), content: z.array(inlineNodeSchema).optional() }).strict(),
  z.object({ type: z.literal("heading"), attrs: z.object({ level: z.union([z.literal(1), z.literal(2), z.literal(3)]) }).strict(), content: z.array(inlineNodeSchema).optional() }).strict(),
  z.object({ type: z.literal("bulletList"), content: z.array(listItemSchema).min(1) }).strict(),
  z.object({ type: z.literal("orderedList"), content: z.array(listItemSchema).min(1) }).strict(),
  tableSchema,
  imageNode,
  z.object({
    type: z.literal("subQuestion"),
    attrs: z.object({
      label: z.string().min(1).nullable().optional(),
      marks: leafMarksSchema,
    }).strict().optional(),
    content: z.array(blockNodeSchema).min(1),
  }).strict(),
  answerSpaceNode,
]));

const listItemSchema: z.ZodType<ContentNode, ContentNode> = z.lazy(() => z.object({
  type: z.literal("listItem"),
  content: z.tuple([z.object({ type: z.literal("paragraph"), content: z.array(inlineNodeSchema).optional() }).strict()]).rest(blockNodeSchema),
}).strict());
const tableCellSchema: z.ZodType<ContentNode, ContentNode> = z.lazy(() => z.object({ type: z.literal("tableCell"), content: z.array(blockNodeSchema).min(1) }).strict());
const tableRowSchema: z.ZodType<ContentNode, ContentNode> = z.lazy(() => z.object({ type: z.literal("tableRow"), content: z.array(tableCellSchema).min(1) }).strict());
const tableSchema: z.ZodType<ContentNode, ContentNode> = z.lazy(() => z.object({ type: z.literal("table"), content: z.array(tableRowSchema).min(1) }).strict());

export const contentSchema: z.ZodType<QuestionContent, QuestionContent> = z.object({ type: z.literal("doc"), marks: leafMarksSchema, content: z.array(blockNodeSchema) }).strict();

export function isValidContent(json: unknown): json is QuestionContent {
  return contentSchema.safeParse(json).success;
}

export function normalizeContentForWire(content: QuestionContent): QuestionContent {
  const normalize = (node: ContentNode): ContentNode => {
    const attrs = node.attrs ? { ...node.attrs } : undefined;
    if (node.type === "image" && attrs?.alt === null) delete attrs.alt;
    // Strip only null/undefined marks — a real 0 is authoritative and must be kept.
    if (attrs && attrs.marks == null) delete attrs.marks;
    return {
      ...node,
      ...(attrs ? { attrs } : {}),
      ...(node.content ? { content: node.content.map(normalize) } : {}),
    };
  };
  return {
    type: "doc",
    ...(content.marks == null ? {} : { marks: content.marks }),
    content: content.content.map(normalize),
  };
}

export function hasSubQuestions(content: QuestionContent): boolean {
  return content.content.some((n) => n.type === "subQuestion");
}

function numberOf(raw: unknown): number {
  if (raw == null) return 0;
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

export function leafMarksTotal(content: QuestionContent): number {
  const sumSubs = (nodes: ContentNode[]): number =>
    nodes
      .filter((n) => n.type === "subQuestion")
      .reduce((acc, sub) => {
        const nested = (sub.content ?? []).some((n) => n.type === "subQuestion");
        return nested ? acc + sumSubs(sub.content ?? []) : acc + numberOf(sub.attrs?.marks);
      }, 0);
  if (hasSubQuestions(content)) return sumSubs(content.content);
  return numberOf(content.marks);
}
