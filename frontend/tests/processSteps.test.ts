// Run with `npm test`. The AI process panel's steps: live states, failures and stored answers.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildProcessSteps, type ProcessStep } from '../src/lib/processSteps.ts';
import type { QuestionAnswerResponse } from '../src/types/index.ts';

type Stages = NonNullable<Parameters<typeof buildProcessSteps>[0]['stages']>;

const asker = { employee_id: 'EMP-1002', name: 'Dev Service Agent', role: 'csr' };

function stages(overrides: Partial<Stages>): Stages {
  return {
    context: { status: 'waiting' },
    retrieve: { status: 'waiting' },
    ground: { status: 'waiting' },
    generate: { status: 'waiting' },
    validate: { status: 'waiting' },
    deliver: { status: 'waiting' },
    ...overrides,
  };
}

function step(steps: ProcessStep[], key: ProcessStep['key']): ProcessStep {
  const found = steps.find((s) => s.key === key);
  assert.ok(found, key);
  return found;
}

function answer(overrides: Partial<QuestionAnswerResponse> = {}): QuestionAnswerResponse {
  return {
    conversation_id: 'conv-1',
    question_id: 'q-1',
    question: 'What is the water back-up limit?',
    answer: 'The limit is $5,000 [1].',
    answer_type: 'policy_explanation',
    policy_context: {
      policy_id: 'p-1',
      policy_number: 'HO-2847-1193',
      customer_name: 'Margaret Chen',
    } as QuestionAnswerResponse['policy_context'],
    evidence: [
      { source_type: 'clause', source_id: 'c1', form_number: 'HO 04 95', page: 1, content: 'We will pay up to $5,000.', relevance_score: 12 },
      { source_type: 'clause', source_id: 'c2', form_number: 'HO 00 03', page: 14, content: 'Water damage…', relevance_score: 3 },
    ],
    citations: [],
    confidence: 'high',
    status: 'answered',
    suggested_questions: [],
    guardrail_status: 'passed',
    guardrail_checks: [
      { name: 'citations_verified', status: 'passed', detail: '1 of 1 citations verified against retrieved passages.' },
      { name: 'no_unsupported_claims', status: 'warning', detail: '' },
    ],
    outcome: 'answered',
    model_used: 'openai/gpt-oss-120b',
    provider: 'groq',
    is_fallback: false,
    retrieval: { clauses_searched: 47, coverages_searched: 6, forms_searched: 4 },
    timings_ms: { retrieval: 24, grounding: 1, generation: 867, validation: 2 },
    latency_ms: 1210,
    ledger_id: 'ledger-123',
    grounding_context_chars: 4498,
    asked_by: asker,
    ...overrides,
  };
}

test('a failed step shows the error, stops the run, and leaves no spinner', () => {
  const steps = buildProcessSteps({
    askedBy: asker,
    stages: stages({
      context: { status: 'completed', detail: 'Margaret Chen · HO-2847-1193 — matched on policy number' },
      retrieve: { status: 'failed', detail: 'AI service unavailable. The answering service could not be reached.' },
      // A stale in-progress state after the failure must not keep spinning.
      ground: { status: 'processing' },
    }),
  });
  const retrieve = step(steps, 'retrieve');
  assert.equal(retrieve.status, 'failed');
  assert.deepEqual(retrieve.lines, [{ kind: 'error', text: 'AI service unavailable. The answering service could not be reached.' }]);
  assert.equal(steps.filter((s) => s.status === 'running').length, 0);
  for (const key of ['ground', 'generate', 'validate', 'deliver'] as const) {
    assert.equal(step(steps, key).status, 'skipped', key);
  }
});

test('a failed step with no message still explains itself', () => {
  const steps = buildProcessSteps({ stages: stages({ context: { status: 'failed' } }) });
  assert.equal(step(steps, 'context').lines[0].kind, 'error');
});

test('while running, only real values are shown', () => {
  const steps = buildProcessSteps({
    askedBy: asker,
    stages: stages({
      context: { status: 'completed', detail: 'Margaret Chen · HO-2847-1193 — matched on policy number' },
      retrieve: { status: 'processing' },
    }),
  });
  assert.equal(step(steps, 'context').status, 'done');
  assert.deepEqual(step(steps, 'context').lines, [
    { kind: 'text', text: 'Margaret Chen · HO-2847-1193 — matched on policy number' },
    { kind: 'text', text: 'Asked by Dev Service Agent · ', mono: 'EMP-1002' },
  ]);
  assert.equal(step(steps, 'retrieve').status, 'running');
  assert.deepEqual(step(steps, 'retrieve').lines, []);
  assert.ok(steps.slice(2).every((s) => s.status === 'pending' && s.lines.length === 0));
  assert.ok(steps.every((s) => s.ms === undefined));
});

test('a stored answer fills every step from its recorded values', () => {
  const steps = buildProcessSteps({ result: answer() });
  assert.ok(steps.every((s) => s.status === 'done' || s.status === 'warning'));

  const retrieve = step(steps, 'retrieve');
  assert.equal(retrieve.ms, 24);
  assert.deepEqual(retrieve.lines[0], { kind: 'text', text: 'Searched 53 passages across 4 forms' });
  assert.deepEqual(retrieve.lines.slice(1), [
    { kind: 'passage', form: 'HO 04 95', page: 1, score: 12, ratio: 1 },
    { kind: 'passage', form: 'HO 00 03', page: 14, score: 3, ratio: 0.25 },
  ]);

  const ground = step(steps, 'ground');
  assert.equal(ground.lines[0].kind === 'text' && ground.lines[0].text, '2 passages kept in the grounding context');
  assert.equal(ground.lines[1].kind === 'text' && ground.lines[1].text, '≈ 1,125 tokens (estimated from 4,498 characters)');

  assert.deepEqual(step(steps, 'generate').lines[0], { kind: 'text', text: 'Model ', mono: 'openai/gpt-oss-120b' });
  assert.equal(step(steps, 'generate').ms, 867);
  assert.deepEqual(step(steps, 'validate').lines, [
    { kind: 'check', ok: true, text: '1 of 1 citations verified against retrieved passages.' },
    { kind: 'check', ok: false, text: 'no unsupported claims' },
  ]);
  assert.deepEqual(step(steps, 'deliver').lines.slice(0, 2), [
    { kind: 'text', text: 'Ledger reference ', mono: 'ledger-123' },
    { kind: 'text', text: 'Recorded under Dev Service Agent · ', mono: 'EMP-1002' },
  ]);
});

test('no evidence: generation is skipped and the answer is withheld for review', () => {
  const steps = buildProcessSteps({
    result: answer({
      status: 'insufficient_evidence',
      evidence: [],
      guardrail_status: 'no_evidence',
      guardrail_checks: [{ name: 'evidence_grounded', status: 'failed', detail: 'No policy evidence matched the question.' }],
      grounding_context_chars: null,
    }),
  });
  assert.equal(step(steps, 'retrieve').status, 'warning');
  assert.equal(step(steps, 'ground').status, 'skipped');
  assert.deepEqual(step(steps, 'generate').lines, [{ kind: 'text', text: 'Skipped: not enough evidence to draft an answer.' }]);
  const validate = step(steps, 'validate');
  assert.equal(validate.status, 'warning');
  assert.deepEqual(validate.lines.at(-1), { kind: 'warning', text: 'Answer withheld and flagged for specialist review.' });
});

test('details missing from older stored answers say so instead of inventing values', () => {
  const steps = buildProcessSteps({
    result: answer({ retrieval: {}, grounding_context_chars: null, model_used: 'unknown', ledger_id: null, asked_by: null }),
  });
  assert.equal(step(steps, 'retrieve').lines[0].kind === 'text' && step(steps, 'retrieve').lines[0].text, 'Search counts not recorded for this answer.');
  assert.equal(step(steps, 'ground').lines[1].kind === 'text' && step(steps, 'ground').lines[1].text, 'Context size not recorded for this answer.');
  assert.deepEqual(step(steps, 'generate').lines[0], { kind: 'text', text: 'Model: not recorded' });
  assert.equal(step(steps, 'deliver').lines[0].kind, 'warning');
  assert.deepEqual(step(steps, 'context').lines.at(-1), { kind: 'text', text: 'Asked by: not recorded' });
});
