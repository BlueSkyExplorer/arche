import { z } from "zod";

// TODO(M4b): generate from backend content.schema.json
const markSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("bold") }).strict(),
  z.object({ type: z.literal("italic") }).strict(),
  z.object({ type: z.literal("underline") }).strict(),
  z.object({ type: z.literal("subscript") }).strict(),
  z.object({ type: z.literal("superscript") }).strict(),
  z.object({ type: z.literal("link"), attrs: z.object({ href: z.string() }).strict() }).strict(),
]);

export type ContentNode = {
  type: string;
  attrs?: Record<string, unknown>;
  content?: ContentNode[];
  text?: string;
  marks?: z.infer<typeof markSchema>[];
};
export type QuestionContent = { type: "doc"; content: ContentNode[] };

const textNode = z.object({ type: z.literal("text"), text: z.string(), marks: z.array(markSchema).optional() }).strict();
const hardBreakNode = z.object({ type: z.literal("hardBreak") }).strict();
const imageNode = z.object({
  type: z.literal("image"),
  attrs: z.object({ assetId: z.string().uuid(), alt: z.string().optional(), widthMm: z.number().positive().optional() }).strict(),
}).strict();
const answerSpaceNode = z.object({
  type: z.literal("answerSpace"),
  attrs: z.object({ lines: z.number().int().min(0) }).strict(),
}).strict();

const inlineNodeSchema: z.ZodType<ContentNode, ContentNode> = z.lazy(() => z.union([textNode, hardBreakNode]));
const blockNodeSchema: z.ZodType<ContentNode, ContentNode> = z.lazy(() => z.union([
  z.object({ type: z.literal("paragraph"), content: z.array(inlineNodeSchema).optional() }).strict(),
  z.object({ type: z.literal("heading"), attrs: z.object({ level: z.union([z.literal(1), z.literal(2), z.literal(3)]) }).strict(), content: z.array(inlineNodeSchema).optional() }).strict(),
  z.object({ type: z.literal("bulletList"), content: z.array(listItemSchema).min(1) }).strict(),
  z.object({ type: z.literal("orderedList"), content: z.array(listItemSchema).min(1) }).strict(),
  tableSchema,
  imageNode,
  z.object({ type: z.literal("subQuestion"), attrs: z.object({ label: z.string() }).strict(), content: z.array(blockNodeSchema).min(1) }).strict(),
  answerSpaceNode,
]));

const listItemSchema: z.ZodType<ContentNode, ContentNode> = z.lazy(() => z.object({
  type: z.literal("listItem"),
  content: z.tuple([z.object({ type: z.literal("paragraph"), content: z.array(inlineNodeSchema).optional() }).strict()]).rest(blockNodeSchema),
}).strict());
const tableCellSchema: z.ZodType<ContentNode, ContentNode> = z.lazy(() => z.object({ type: z.literal("tableCell"), content: z.array(blockNodeSchema).min(1) }).strict());
const tableRowSchema: z.ZodType<ContentNode, ContentNode> = z.lazy(() => z.object({ type: z.literal("tableRow"), content: z.array(tableCellSchema).min(1) }).strict());
const tableSchema: z.ZodType<ContentNode, ContentNode> = z.lazy(() => z.object({ type: z.literal("table"), content: z.array(tableRowSchema).min(1) }).strict());

export const contentSchema: z.ZodType<QuestionContent, QuestionContent> = z.object({ type: z.literal("doc"), content: z.array(blockNodeSchema) }).strict();

export function isValidContent(json: unknown): json is QuestionContent {
  return contentSchema.safeParse(json).success;
}
