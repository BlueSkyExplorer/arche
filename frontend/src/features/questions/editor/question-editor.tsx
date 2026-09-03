"use client";

import { useEffect } from "react";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import Subscript from "@tiptap/extension-subscript";
import Superscript from "@tiptap/extension-superscript";
import Link from "@tiptap/extension-link";
import Table from "@tiptap/extension-table";
import TableRow from "@tiptap/extension-table-row";
import BulletList from "@tiptap/extension-bullet-list";
import OrderedList from "@tiptap/extension-ordered-list";
import ListItem from "@tiptap/extension-list-item";
import Placeholder from "@tiptap/extension-placeholder";
import { Bold, Italic, Underline as UnderlineIcon, Subscript as SubscriptIcon, Superscript as SuperscriptIcon, List, ListOrdered, Table2, ImageIcon, Split, Rows3 } from "lucide-react";
import { AnswerSpaceNode } from "./answer-space-node";
import { QuestionImageNode } from "./image-node";
import { SubQuestionNode } from "./sub-question-node";
import { QuestionTableCell } from "./table-cell-node";
import type { QuestionContent } from "@/lib/validation/content";

const EMPTY_CONTENT: QuestionContent = { type: "doc", content: [{ type: "paragraph" }] };

function cleanPastedHtml(html: string) {
  // Preserve semantic structure for ProseMirror, while dropping source-app styles.
  // Plain-text paste stays untouched, including mixed Chinese/English input.
  const document = new DOMParser().parseFromString(html, "text/html");
  document.body.querySelectorAll("*").forEach((element) => {
    const href = element.tagName === "A" ? element.getAttribute("href") : null;
    for (const attribute of Array.from(element.attributes)) element.removeAttribute(attribute.name);
    if (href) element.setAttribute("href", href);
  });
  return document.body.innerHTML;
}

type Props = { value: QuestionContent; onChange: (value: QuestionContent) => void; onReady?: (editor: Editor) => void; disabled?: boolean };

export function QuestionEditor({ value, onChange, onReady, disabled = false }: Props) {
  const editor = useEditor({
    immediatelyRender: false,
    editable: !disabled,
    content: value ?? EMPTY_CONTENT,
    extensions: [
      StarterKit.configure({ blockquote: false, bulletList: false, orderedList: false, listItem: false, code: false, codeBlock: false, strike: false, horizontalRule: false, heading: { levels: [1, 2, 3] } }),
      BulletList, OrderedList.extend({ addAttributes: () => ({}) }), ListItem,
      Underline, Subscript, Superscript, Link.configure({ openOnClick: false }),
      Table.configure({ resizable: false }), TableRow, QuestionTableCell,
      QuestionImageNode, SubQuestionNode, AnswerSpaceNode,
      Placeholder.configure({ placeholder: "輸入題目… Type a question…" }),
    ],
    editorProps: { attributes: { class: "question-editor-content", "aria-label": "Question content / 題目內容" }, transformPastedHTML: cleanPastedHtml },
    onUpdate: ({ editor: current }) => onChange(current.getJSON() as QuestionContent),
    onCreate: ({ editor: current }) => onReady?.(current),
  });

  useEffect(() => { editor?.setEditable(!disabled); }, [disabled, editor]);
  useEffect(() => {
    if (editor && JSON.stringify(editor.getJSON()) !== JSON.stringify(value)) editor.commands.setContent(value, false);
  }, [editor, value]);
  if (!editor) return <div className="min-h-44 animate-pulse rounded-md border bg-muted" aria-label="Loading editor" />;

  const askLink = () => { const href = window.prompt("Link URL"); if (href !== null) editor.chain().focus().extendMarkRange("link").setLink({ href }).run(); };
  const addImage = () => { const assetId = window.prompt("Asset UUID"); if (assetId) editor.chain().focus().insertContent({ type: "image", attrs: { assetId } }).run(); };
  const addSubQuestion = () => { const label = window.prompt("Sub-question label", "(a)"); if (label !== null) editor.chain().focus().insertContent({ type: "subQuestion", attrs: { label }, content: [{ type: "paragraph" }] }).run(); };
  const items = [
    ["Bold / 粗體", Bold, () => editor.chain().focus().toggleBold().run(), editor.isActive("bold")],
    ["Italic / 斜體", Italic, () => editor.chain().focus().toggleItalic().run(), editor.isActive("italic")],
    ["Underline / 底線", UnderlineIcon, () => editor.chain().focus().toggleUnderline().run(), editor.isActive("underline")],
    ["Subscript / 下標", SubscriptIcon, () => editor.chain().focus().toggleSubscript().run(), editor.isActive("subscript")],
    ["Superscript / 上標", SuperscriptIcon, () => editor.chain().focus().toggleSuperscript().run(), editor.isActive("superscript")],
    ["Bulleted list", List, () => editor.chain().focus().toggleBulletList().run(), editor.isActive("bulletList")],
    ["Numbered list", ListOrdered, () => editor.chain().focus().toggleOrderedList().run(), editor.isActive("orderedList")],
    ["Insert table", Table2, () => editor.chain().focus().insertTable({ rows: 2, cols: 2 }).run(), false],
    ["Insert image", ImageIcon, addImage, false], ["Insert sub-question", Split, addSubQuestion, false],
    ["Insert answer space", Rows3, () => editor.chain().focus().insertContent({ type: "answerSpace", attrs: { lines: 3 } }).run(), false],
  ] as const;
  return <div className="overflow-hidden rounded-md border bg-background focus-within:ring-2 focus-within:ring-ring">
    <div role="toolbar" aria-label="Question formatting" className="flex flex-wrap gap-1 border-b bg-muted/50 p-2">
      {items.map(([label, Icon, action, active]) => <button key={label} type="button" title={label} aria-label={label} aria-pressed={active} disabled={disabled} onClick={action} className={`rounded p-2 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${active ? "bg-accent text-primary" : ""}`}><Icon className="size-4" /></button>)}
      <button type="button" onClick={askLink} disabled={disabled} className="rounded px-2 text-xs hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Link</button>
    </div>
    <EditorContent editor={editor} />
  </div>;
}
