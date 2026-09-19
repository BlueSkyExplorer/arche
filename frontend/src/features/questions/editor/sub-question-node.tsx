import { Node, mergeAttributes } from "@tiptap/core";
import { NodeViewContent, NodeViewWrapper, ReactNodeViewRenderer, type NodeViewProps } from "@tiptap/react";

const SubQuestionView = ({ node, updateAttributes }: NodeViewProps) => {
  const marks = node.attrs.marks as number | string | null | undefined;
  let hasNestedSub = false;
  node.content.forEach((child) => {
    if (child.type.name === "subQuestion") hasNestedSub = true;
  });

  return (
    <NodeViewWrapper className="question-sub-question">
      <div className="question-sub-question-label-row" contentEditable={false}>
        <span className="question-sub-question-label">{String(node.attrs.label ?? "")}</span>
        {!hasNestedSub && (
          <input
            type="number"
            min="0"
            step="0.01"
            className="question-sub-question-marks"
            value={marks ?? ""}
            placeholder="分數"
            aria-label={`Marks for ${String(node.attrs.label ?? "sub-question")}`}
            onChange={(e) => updateAttributes({ marks: e.target.value === "" ? null : Number(e.target.value) })}
          />
        )}
      </div>
      <NodeViewContent className="question-sub-question-content" />
    </NodeViewWrapper>
  );
};

export const SubQuestionNode = Node.create({
  name: "subQuestion",
  group: "block",
  content: "block+",
  defining: true,
  isolating: true,
  addAttributes() {
    return { label: { default: "(a)" }, marks: { default: null } };
  },
  parseHTML() { return [{ tag: "section[data-sub-question]" }]; },
  renderHTML({ HTMLAttributes }) {
    return ["section", mergeAttributes(HTMLAttributes, { "data-sub-question": "", class: "question-sub-question" }), ["span", { class: "question-sub-question-label", contenteditable: "false" }, String(HTMLAttributes.label)], ["div", { class: "question-sub-question-content" }, 0]];
  },
  addNodeView() { return ReactNodeViewRenderer(SubQuestionView); },
});