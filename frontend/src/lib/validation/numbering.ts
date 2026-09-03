export type QuestionNumberStyle = "arabic-dot" | "arabic-paren" | "upper-alpha" | "roman";

function roman(value: number): string {
  const entries: [number, string][] = [[1000,"M"],[900,"CM"],[500,"D"],[400,"CD"],[100,"C"],[90,"XC"],[50,"L"],[40,"XL"],[10,"X"],[9,"IX"],[5,"V"],[4,"IV"],[1,"I"]];
  let remaining = value; let result = "";
  for (const [number, glyph] of entries) while (remaining >= number) { result += glyph; remaining -= number; }
  return result;
}

/** Fallback only: the backend-provided display_number is authoritative when present. */
export function formatQuestionNumber(position: number, style: QuestionNumberStyle): string {
  if (style === "arabic-paren") return `(${position})`;
  if (style === "upper-alpha") return `${String.fromCharCode(64 + Math.max(1, Math.min(position, 26)))}.`;
  if (style === "roman") return `${roman(position)}.`;
  return `${position}.`;
}
