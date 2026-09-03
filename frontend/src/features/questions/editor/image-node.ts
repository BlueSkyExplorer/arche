import { Node, mergeAttributes } from "@tiptap/core";

export const QuestionImageNode = Node.create({
  name: "image",
  group: "block",
  atom: true,
  draggable: true,
  addAttributes() {
    return { assetId: { default: null }, alt: { default: undefined }, widthMm: { default: undefined } };
  },
  parseHTML() { return [{ tag: "figure[data-asset-id]" }]; },
  renderHTML({ HTMLAttributes }) {
    const width = typeof HTMLAttributes.widthMm === "number" ? `width:${HTMLAttributes.widthMm}mm` : undefined;
    return ["figure", mergeAttributes({ "data-asset-id": HTMLAttributes.assetId, "aria-label": HTMLAttributes.alt || "Question image", class: "question-image", style: width }), `Image asset: ${HTMLAttributes.alt || HTMLAttributes.assetId}`];
  },
});
