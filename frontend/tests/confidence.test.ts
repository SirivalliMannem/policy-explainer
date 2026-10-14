// Run with `npm test`. Confidence percentages derived from the AI service's existing confidence rule.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { answerConfidence, confidenceExplanation, evidencePercent, STRONG_EVIDENCE_SCORE } from '../src/lib/confidence.ts';
import type { QuestionAnswerResponse } from '../src/types/index.ts';

function answer(overrides: Partial<QuestionAnswerResponse> = {}): QuestionAnswerResponse {
  return {
    conversation_id: 'c', question_id: 'q', question: 'Q', answer: 'A [E1] [E2]', answer_type: 'policy_explanation',
    evidence: [
      { source_type: 'clause', source_id: 'a', content: 'x', relevance_score: 18 },
      { source_type: 'clause', source_id: 'b', content: 'y', relevance_score: 4 },
    ],
    citations: [{ source_id: 'a' }, { source_id: 'b' }],
    confidence: 'high', status: 'answered', suggested_questions: [], guardrail_status: 'passed',
    guardrail_checks: [
      { name: 'inline_citations', status: 'passed', detail: '' },
      { name: 'citations_verified', status: 'passed', detail: '' },
    ],
    outcome: 'answered', model_used: 'm', provider: 'p', is_fallback: false, retrieval: {}, timings_ms: {},
    ...overrides,
  };
}

test('evidence percentage is the score against the strong-evidence threshold, capped at 100', () => {
  assert.equal(STRONG_EVIDENCE_SCORE, 12);
  assert.equal(evidencePercent(12), 100);
  assert.equal(evidencePercent(48.5), 100);
  assert.equal(evidencePercent(6), 50);
  assert.equal(evidencePercent(3), 25);
  assert.equal(evidencePercent(0), 0);
  assert.equal(evidencePercent(null), null);
});

test('an answer meeting every HIGH criterion is 100%', () => {
  const c = answerConfidence(answer());
  assert.equal(c?.percent, 100);
  assert.equal(confidenceExplanation(c!), '6 of 6 confidence criteria met.');
});

test('MEDIUM: one citation and weak evidence miss two criteria', () => {
  const c = answerConfidence(answer({ confidence: 'medium', citations: [{ source_id: 'a' }], evidence: [{ source_type: 'clause', source_id: 'a', content: 'x', relevance_score: 5 }] }));
  assert.equal(c?.percent, 67);
  assert.match(confidenceExplanation(c!), /missing: two or more citations verified, strongest evidence reaches/);
});

test('LOW: a failed guardrail is listed as missed', () => {
  const c = answerConfidence(answer({ confidence: 'low', guardrail_status: 'flagged' }));
  assert.equal(c?.percent, 83);
  assert.match(confidenceExplanation(c!), /missing: guardrails passed/);
});

test('values read from the records: found, checked and cited is 100%', () => {
  const record = { retrieval: { answer_type: 'factual_lookup' }, evidence: [{ source_type: 'coverage', source_id: 'a', content: 'x', relevance_score: 1 }], citations: [{ source_id: 'a' }] };
  assert.equal(answerConfidence(answer(record))?.percent, 100);
  // Nothing found in the records: only the record check is met.
  const missing = answerConfidence(answer({ ...record, evidence: [], citations: [] }));
  assert.equal(missing?.percent, 33);
});

test('portfolio answers, and answers without recorded checks, have no graded percentage', () => {
  assert.equal(answerConfidence(answer({ answer_type: 'portfolio' })), null);
  assert.equal(answerConfidence(answer({ guardrail_checks: [] })), null);
});
