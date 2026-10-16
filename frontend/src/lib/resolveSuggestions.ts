// What the Needs attention Resolve box shows, decided in a fixed order, and where a suggestion goes.
// Pure (type-only imports) so `node --test` can load it; ResolveBox renders exactly what this returns.
import type { AttentionAnalysis, AttentionCandidate, AttentionItem } from '../types';

/** The number of suggestions shown whenever suggestions are appropriate. */
export const SUGGESTION_COUNT = 2;

export type ResolveMode =
  | 'customer_not_found' // the customer asked about is not on file: no suggestions, verify the customer
  | 'policy_context_missing' // no verified policy: no suggestions, identify the policy
  | 'not_ready' // not analysed yet, or the analysis failed: no suggestions, offer Analyze now
  | 'out_of_scope' // not an insurance question: no suggestions
  | 'suggestions' // exactly two suggestions in the verified policy context
  | 'no_alternative'; // analysed, but not two usable suggestions: none shown

export interface ResolveView {
  mode: ResolveMode;
  heading: string | null;
  candidates: AttentionCandidate[];
}

const HEADINGS: Record<string, string> = {
  typo: 'WRONG WORDING · TRY THESE',
  vague_wording: 'WRONG WORDING · TRY THESE',
  definition: 'TRY THESE INSTEAD',
  coverage_no_evidence: 'ASK THIS INSTEAD',
  missing_form_or_edition: 'ASK THIS INSTEAD',
};

/**
 * The decision order: the flag reason and customer verification first, then the policy context,
 * and only then the stored suggestions, which are shown only when there are exactly two.
 */
export function resolveView(item: AttentionItem, analysis: AttentionAnalysis | null | undefined): ResolveView {
  const none = (mode: ResolveMode, heading: string | null = null): ResolveView => ({ mode, heading, candidates: [] });
  if (item.reason === 'customer_not_found' || analysis?.type === 'customer_not_found') return none('customer_not_found');
  if (!item.policy_id || analysis?.type === 'policy_context_missing') return none('policy_context_missing');
  if (!analysis || analysis.status !== 'ready') return none('not_ready');
  if (analysis.category === 'out_of_scope' || analysis.type === 'out_of_scope') return none('out_of_scope', 'NO EVIDENCE CAN EXIST');
  const candidates = analysis.candidates ?? [];
  if (candidates.length !== SUGGESTION_COUNT) return none('no_alternative');
  return { mode: 'suggestions', heading: HEADINGS[analysis.type ?? ''] ?? 'TRY THESE', candidates };
}

/**
 * Where a suggestion (or an edited question) is asked: a NEW conversation of the employee who clicked,
 * with the item's verified policy. Never the original asker's conversation, which belongs to them.
 */
export function suggestionNavigation(
  item: AttentionItem,
  question: string
): { path: string; state: { initialQuestion: string; policyId?: string } } {
  return {
    path: '/app/explainer/new',
    state: { initialQuestion: question, ...(item.policy_id ? { policyId: item.policy_id } : {}) },
  };
}
