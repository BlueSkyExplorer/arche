import { Node, mergeAttributes, type NodeViewProps } from "@tiptap/core";
import { NodeViewWrapper, ReactNodeViewRenderer } from "@tiptap/react";
import { createElement } from "react";

function AnswerSpaceView({ node, updateAttributes, selected }: NodeViewProps) {
  const lines = Number(node.attrs.lines);
  return createElement(NodeViewWrapper, { className: `question-answer-space ${selected ? "ring-2 ring-ring" : ""}` },
    createElement("span", null, `答題位置 ${lines} lines`),
    createElement("label", { className: "ml-auto flex items-center gap-2 text-xs" }, "行數",
      createElement("input", { "aria-label": "Answer-space lines", className: "w-16 rounded border bg-background px-2 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", type: "number", min: 0, step: 1, value: lines, onChange: (event: React.ChangeEvent<HTMLInputElement>) => updateAttributes({ lines: Math.max(0, Math.trunc(event.currentTarget.valueAsNumber || 0)) }) }),
    ),
  );
}

export const AnswerSpaceNode = Node.create({
  name: "answerSpace",
  group: "block",
  atom: true,
  selectable: true,
  addAttributes() { return { lines: { default: 3 } }; },
  parseHTML() { return [{ tag: "div[data-answer-space]" }]; },
  renderHTML({ HTMLAttributes }) { return ["div", mergeAttributes(HTMLAttributes, { "data-answer-space": "", class: "question-answer-space" }), `答題位置 ${HTMLAttributes.lines} lines`]; },
  addNodeView() { return ReactNodeViewRenderer(AnswerSpaceView); },
});
