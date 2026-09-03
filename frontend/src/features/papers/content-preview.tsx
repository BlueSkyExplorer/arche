import type { ContentNode, QuestionContent } from "@/lib/validation/content";

export function ContentPreview({ content }: { content: QuestionContent }) { return <>{content.content.map((node, i) => <Node key={i} node={node} />)}</>; }
function Node({ node }: { node: ContentNode }) {
  const children = node.content?.map((child, i) => <Node key={i} node={child} />);
  if (node.type === "text") { let value: React.ReactNode = node.text; for (const mark of node.marks ?? []) { if (mark.type === "bold") value=<strong>{value}</strong>; if(mark.type==="italic")value=<em>{value}</em>; if(mark.type==="underline")value=<u>{value}</u>; if(mark.type==="subscript")value=<sub>{value}</sub>; if(mark.type==="superscript")value=<sup>{value}</sup>; } return value; }
  if (node.type === "paragraph") return <p>{children ?? <br />}</p>;
  if (node.type === "heading") return <h3 className="font-semibold">{children}</h3>;
  if (node.type === "bulletList") return <ul className="list-disc pl-6">{children}</ul>;
  if (node.type === "orderedList") return <ol className="list-decimal pl-6">{children}</ol>;
  if (node.type === "listItem") return <li>{children}</li>;
  if (node.type === "table") return <table className="w-full border-collapse"><tbody>{children}</tbody></table>;
  if (node.type === "tableRow") return <tr>{children}</tr>;
  if (node.type === "tableCell") return <td className="border p-2">{children}</td>;
  if (node.type === "subQuestion") return <div className="flex gap-2"><b>{String(node.attrs?.label ?? "")}</b><div>{children}</div></div>;
  if (node.type === "answerSpace") return <div className="my-2 space-y-3">{Array.from({length:Number(node.attrs?.lines ?? 0)},(_,i)=><div key={i} className="border-b" />)}</div>;
  if (node.type === "image") return <div className="rounded border bg-muted p-3 text-center text-xs">Image / 圖片 ({String(node.attrs?.alt ?? node.attrs?.assetId ?? "asset")})</div>;
  if (node.type === "hardBreak") return <br />;
  return <>{children}</>;
}
