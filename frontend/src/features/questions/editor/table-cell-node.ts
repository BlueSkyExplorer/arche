import { Node, mergeAttributes } from "@tiptap/core";

/** Table cell without ProseMirror's colspan/rowspan/colwidth attrs, which are not canonical. */
export const QuestionTableCell = Node.create({
  name: "tableCell",
  content: "block+",
  tableRole: "cell",
  isolating: true,
  parseHTML() { return [{ tag: "td" }]; },
  renderHTML({ HTMLAttributes }) { return ["td", mergeAttributes(HTMLAttributes), 0]; },
});
