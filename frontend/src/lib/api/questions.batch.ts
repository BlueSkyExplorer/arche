import { createQuestion, type QuestionIngestDraft } from "./questions";
import { ApiError } from "./client";
import {
  type DraftOverride,
  type SharedDefaults,
  type DraftSaveResult,
  resolveEffective,
  buildDraftPayload,
  sharedDefaultsSchema,
} from "@/lib/validation/ingest-batch";

export type { DraftSaveResult, DraftOverride, SharedDefaults };

/**
 * Save selected drafts one-by-one using the existing createQuestion API.
 * Returns per-draft results so the caller can show partial success / errors.
 * Successful items are NOT re-sent on retry — the caller removes them.
 */
export async function batchSaveDrafts(
  token: string,
  drafts: { draft: QuestionIngestDraft; override: DraftOverride }[],
  shared: SharedDefaults,
): Promise<DraftSaveResult[]> {
  // Validate shared defaults up-front
  const parsed = sharedDefaultsSchema.safeParse(shared);
  if (!parsed.success) {
    const msg = parsed.error.issues.map((i) => i.message).join("; ");
    return drafts.map((_, i) => ({ ok: false as const, index: i, error: msg }));
  }

  const results: DraftSaveResult[] = [];

  for (let i = 0; i < drafts.length; i++) {
    const { draft, override } = drafts[i];
    const effective = resolveEffective(parsed.data, override);
    const payload = buildDraftPayload(draft, effective);

    try {
      await createQuestion(token, payload);
      results.push({ ok: true, index: i });
    } catch (e: unknown) {
      const error =
        e instanceof ApiError
          ? e.body.detail
          : e instanceof Error
            ? e.message
            : "Unknown error / 未知錯誤";
      results.push({ ok: false, index: i, error });
    }
  }

  return results;
}
