import { z } from "zod";
import type { QuestionIngestDraft } from "@/lib/api/questions";
import { normalizeContentForWire } from "@/lib/validation/content";

// ---------------------------------------------------------------------------
// Zod schemas
// ---------------------------------------------------------------------------

/** Per-draft individual override fields (empty string = no override). */
export const draftOverrideSchema = z.object({
  subject: z.string(),
  level: z.string(),
});
export type DraftOverride = z.infer<typeof draftOverrideSchema>;

/** Shared defaults applied to all selected drafts. */
export const sharedDefaultsSchema = z.object({
  subject: z.string().min(1, "Subject is required / 科目必填"),
  level: z.string().min(1, "Level is required / 級別必填"),
});
export type SharedDefaults = z.infer<typeof sharedDefaultsSchema>;

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

/**
 * Resolve the effective subject/level for a single draft.
 * Priority: individual non-empty value > shared value.
 */
export function resolveEffective(
  shared: SharedDefaults,
  override: DraftOverride,
): { subject: string; level: string } {
  return {
    subject: override.subject.trim() || shared.subject.trim(),
    level: override.level.trim() || shared.level.trim(),
  };
}

/** Result of a single draft save attempt. */
export type DraftSaveResult =
  | { ok: true; index: number }
  | { ok: false; index: number; error: string };

/**
 * Build a createQuestion-compatible payload from a draft + resolved metadata.
 * Returns the input object expected by `createQuestion`.
 */
export function buildDraftPayload(
  draft: QuestionIngestDraft,
  effective: { subject: string; level: string },
) {
  return {
    internalTitle: draft.internal_title,
    subject: effective.subject,
    level: effective.level,
    tags: draft.tags_json,
    sourceNote: draft.source_note ?? undefined,
    content: normalizeContentForWire(draft.content_json),
    marks: Number(draft.marks),
    status: draft.status,
  };
}
