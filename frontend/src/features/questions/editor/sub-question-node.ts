import { Node, mergeAttributes } from "@tiptap/core";

export const SubQuestionNode = Node.create({
  name: "subQuestion",
  group: "block",
  content: "block+",
  defining: true,
  isolating: true,
  addAttributes() { return { label: { default: "(a)" } }; },
  parseHTML() { return [{ tag: "section[data-sub-question]" }]; },
  renderHTML({ HTMLAttributes }) {
    return ["section", mergeAttributes(HTMLAttributes, { "data-sub-question": "", class: "question-sub-question" }), ["span", { class: "question-sub-question-label", contenteditable: "false" }, String(HTMLAttributes.label)], ["div", { class: "question-sub-question-content" }, 0]];
  },
});
