// Confidence as a percentage, derived from the rule the AI service already uses for its
// HIGH / MEDIUM / LOW label (_grade_confidence in ai-service explainer_pipeline.py). Nothing here is
// a new score: the answer percentage is the share of that rule's criteria the answer meets, and the
// evidence percentage is a passage's relevance score against the rule's strong-evidence threshold.
// Kept free of runtime imports so `node --test` can load it directly.
import type { QuestionAnswerResponse } from '../types';

/** STRONG_EVIDENCE_SCORE in ai-service/app/services/explainer_pipeline.py: the score that counts as strong evidence. */
export const STRONG_EVIDENCE_SCORE = 12;

/**
 * The answer percentage is kept between these bounds: no answer is shown as certain (100%) or as
 * having no support at all (0%). Evidence percentages per passage are not bounded.
 */
export const MIN_CONFIDENCE_PERCENT = 5;
export const MAX_CONFIDENCE_PERCENT = 98;

/** The share of criteria met, as a percentage within the displayed bounds. */
export function boundedPercent(met: number, total: number): number {
  const raw = total ? Math.round((met / total) * 100) : 0;
  return Math.min(MAX_CONFIDENCE_PERCENT, Math.max(MIN_CONFIDENCE_PERCENT, raw));
}

export interface ConfidenceCriterion {
  label: string;
  met: boolean;
}

export interface AnswerConfidence {
  percent: number;
  criteria: ConfidenceCriterion[];
}

/** Values read straight from the policy's own records (no evidence search, no language model). */
export function isRecordAnswer(result: Pick<QuestionAnswerResponse, 'retrieval'>): boolean {
  return result.retrieval?.answer_type === 'factual_lookup';
}

/** How strongly a passage supports the question: its relevance score against the strong-evidence threshold. */
export function evidencePercent(score?: number | null): number | null {
  if (score === null || score === undefined || Number.isNaN(score)) return null;
  return Math.round(Math.min(Math.max(score, 0) / STRONG_EVIDENCE_SCORE, 1) * 100);
}

/** Passages found by searching the policy wording; facts read from the records are not scored passages. */
export function searchedEvidence<T extends { scope?: string | null }>(evidence: T[]): T[] {
  return evidence.filter((e) => e.scope !== 'policy_record');
}

/** The strongest searched passage's evidence percentage, or null when nothing was searched. */
export function topEvidencePercent(result: Pick<QuestionAnswerResponse, 'evidence'>): number | null {
  const scores = searchedEvidence(result.evidence)
    .map((e) => e.relevance_score)
    .filter((s): s is number => typeof s === 'number');
  return scores.length ? evidencePercent(Math.max(...scores)) : null;
}

/** Criteria for values read straight from the records: found, checked, and each value cited to its record. */
function recordConfidence(result: QuestionAnswerResponse): AnswerConfidence {
  const criteria: ConfidenceCriterion[] = [
    { label: 'Value found in the policy records', met: result.evidence.length > 0 },
    { label: 'Record check passed', met: result.guardrail_status === 'passed' },
    { label: 'Every value cites its record', met: result.evidence.length > 0 && result.citations.length >= result.evidence.length },
  ];
  const met = criteria.filter((c) => c.met).length;
  return { percent: boundedPercent(met, criteria.length), criteria };
}

/**
 * The share of the confidence criteria this answer meets. For a generated answer these are the criteria
 * of the AI service's HIGH rule (HIGH means all of them; MEDIUM and LOW miss some); for values read from
 * the records, the record checks. Null for portfolio answers and older answers recorded without checks.
 */
export function answerConfidence(result: QuestionAnswerResponse): AnswerConfidence | null {
  if (result.answer_type === 'portfolio') return null;
  if (isRecordAnswer(result)) return recordConfidence(result);
  if (!result.guardrail_checks?.length) return null;
  const scores = searchedEvidence(result.evidence).map((e) => e.relevance_score ?? 0);
  const top = scores.length ? Math.max(...scores) : 0;
  const verified = result.citations.length;
  const inline = result.guardrail_checks.find((c) => c.name === 'inline_citations');
  const criteria: ConfidenceCriterion[] = [
    { label: 'Policy evidence found', met: result.evidence.length > 0 },
    { label: 'Guardrails passed', met: result.guardrail_status === 'passed' },
    { label: 'At least one citation verified', met: verified >= 1 },
    { label: 'Two or more citations verified', met: verified >= 2 },
    { label: 'Answer cites its evidence inline', met: inline?.status === 'passed' },
    { label: `Strongest evidence reaches the strong-evidence threshold (${STRONG_EVIDENCE_SCORE})`, met: top >= STRONG_EVIDENCE_SCORE },
  ];
  const met = criteria.filter((c) => c.met).length;
  return { percent: boundedPercent(met, criteria.length), criteria };
}

/** One line for a tooltip or screen reader: what the percentage is made of. */
export function confidenceExplanation(confidence: AnswerConfidence): string {
  const met = confidence.criteria.filter((c) => c.met).length;
  const missed = confidence.criteria.filter((c) => !c.met).map((c) => c.label.toLowerCase());
  return `${met} of ${confidence.criteria.length} confidence criteria met${missed.length ? `; missing: ${missed.join(', ')}` : ''}.`;
}
