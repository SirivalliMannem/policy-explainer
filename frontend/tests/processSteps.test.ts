// Run with `npm test`. The AI process panel's steps: live states, failures and stored answers.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildProcessSteps, type ProcessStep, type StepLine } from '../src/lib/processSteps.ts';
import type { QuestionAnswerResponse } from '../src/types/index.ts';

type Stages = NonNullable<Parameters<typeof buildProcessSteps>[0]['stages']>;

const asker = { employee_id: 'EMP-1002', name: 'Dev Service Agent', role: 'csr' };
const verification = {
  status: 'verified',
  matched_on: 'policy_number',
  reference: 'HO-2847-1193',
  customers: [{ customer_id: 'acct-1', name: 'Margaret Chen', account_number: 'ACCT-100241' }],
  message: 'Margaret Chen is in the customer records, matched on policy number.',
};

function stages(overrides: Partial<Stages>): Stages {
  const waiting = { status: 'waiting' as const };
  return {
    verify: waiting,
    context: waiting,
    retrieve: waiting,
    ground: waiting,
    generate: waiting,
    citations: waiting,
    validate: waiting,
    deliver: waiting,
    ...overrides,
  };
}

function step(steps: ProcessStep[], key: ProcessStep['key']): ProcessStep {
  const found = steps.find((s) => s.key === key);
  assert.ok(found, key);
  return found;
}

function results(s: ProcessStep): StepLine[] {
  return s.lines.filter((l) => l.kind === 'result');
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
      { source_type: 'clause', source_id: 'c1', form_number: 'HO 04 95', page: 1, content: 'We will pay up to $5,000.', relevance_score: 24 },
      { source_type: 'clause', source_id: 'c2', form_number: 'HO 00 03', page: 14, content: 'Water damage…', relevance_score: 3 },
    ],
    citations: [{ source_id: 'c1' }, { source_id: 'c2' }],
    confidence: 'high',
    status: 'answered',
    suggested_questions: [],
    guardrail_status: 'passed',
    guardrail_checks: [
      { name: 'answer_present', status: 'passed', detail: 'A non-empty answer was produced.' },
      { name: 'inline_citations', status: 'passed', detail: '2 inline reference(s) to retrieved evidence.' },
      { name: 'citations_verified', status: 'passed', detail: '2 of 2 citations verified against retrieved evidence.' },
      { name: 'cross_policy_leak', status: 'passed', detail: 'Answer references only the active policy.' },
    ],
    outcome: 'answered',
    model_used: 'openai/gpt-oss-120b',
    provider: 'groq',
    is_fallback: false,
    retrieval: { clauses_searched: 47, coverages_searched: 6, forms_searched: 4, customer_verification: verification },
    timings_ms: { retrieval: 24, grounding: 1, generation: 867, validation: 2 },
    latency_ms: 1210,
    ledger_id: 'ledger-123',
    grounding_context_chars: 4498,
    asked_by: asker,
    ...overrides,
  };
}

test('steps run in order, starting with customer verification', () => {
  const steps = buildProcessSteps({ result: answer() });
  assert.deepEqual(
    steps.map((s) => s.label),
    [
      'Verify customer',
      'Identify policy context',
      'Retrieve relevant evidence',
      'Build grounding context',
      'Generate grounded answer',
      'Verify citations',
      'Check guardrails',
      'Deliver cited answer',
    ]
  );
});

test('a failed step shows the error, stops the run, and leaves no spinner', () => {
  const steps = buildProcessSteps({
    askedBy: asker,
    stages: stages({
      verify: { status: 'completed', detail: 'Margaret Chen is in the customer records.' },
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
  for (const key of ['ground', 'generate', 'citations', 'validate', 'deliver'] as const) {
    assert.equal(step(steps, key).status, 'skipped', key);
  }
});

test('a customer who is not in the records stops the run at verification', () => {
  const steps = buildProcessSteps({
    stages: stages({ verify: { status: 'failed', detail: 'No customer named John Smith is in the customer records.' } }),
  });
  assert.equal(step(steps, 'verify').status, 'failed');
  assert.deepEqual(step(steps, 'verify').lines, [{ kind: 'error', text: 'No customer named John Smith is in the customer records.' }]);
  assert.ok(steps.slice(1).every((s) => s.status === 'skipped'));
});

test('several matching customers wait for the employee at verification', () => {
  const steps = buildProcessSteps({
    stages: stages({ verify: { status: 'attention', detail: '2 customers in the records match: David Chen and Margaret Chen.' } }),
  });
  assert.equal(step(steps, 'verify').status, 'warning');
  assert.ok(steps.slice(1).every((s) => s.status === 'pending'), 'nothing after verification runs');
});

test('while running, only real values are shown', () => {
  const steps = buildProcessSteps({
    askedBy: asker,
    stages: stages({
      verify: { status: 'completed', detail: 'Margaret Chen is in the customer records.' },
      context: { status: 'completed', detail: 'Margaret Chen · HO-2847-1193 — matched on policy number' },
      retrieve: { status: 'processing' },
    }),
  });
  assert.deepEqual(step(steps, 'verify').lines, [{ kind: 'result', tone: 'passed', text: 'Verified: Margaret Chen is in the customer records.' }]);
  assert.deepEqual(step(steps, 'context').lines, [
    { kind: 'text', text: 'Margaret Chen · HO-2847-1193 — matched on policy number' },
    { kind: 'text', text: 'Asked by Dev Service Agent · ', mono: 'EMP-1002' },
  ]);
  assert.equal(step(steps, 'retrieve').status, 'running');
  assert.deepEqual(step(steps, 'retrieve').lines, []);
  assert.ok(steps.slice(3).every((s) => s.status === 'pending' && s.lines.length === 0));
});

test('a stored answer shows the recorded verification, evidence confidence, citations and guardrails separately', () => {
  const steps = buildProcessSteps({ result: answer() });
  const verify = step(steps, 'verify');
  assert.equal(verify.status, 'done');
  assert.deepEqual(results(verify), [{ kind: 'result', tone: 'passed', text: `Verified: ${verification.message}` }]);

  const retrieve = step(steps, 'retrieve');
  assert.deepEqual(results(retrieve), [
    { kind: 'result', tone: 'passed', text: 'Evidence confidence: 100%. The strongest passage scores 24.0 against the strong-evidence threshold of 12.' },
  ]);
  assert.deepEqual(retrieve.lines.filter((l) => l.kind === 'passage'), [
    { kind: 'passage', form: 'HO 04 95', page: 1, score: 24, percent: 100 },
    { kind: 'passage', form: 'HO 00 03', page: 14, score: 3, percent: 25 },
  ]);

  const citations = step(steps, 'citations');
  assert.equal(citations.status, 'done');
  assert.deepEqual(results(citations), [{ kind: 'result', tone: 'passed', text: 'Verified: 2 citations match the retrieved evidence.' }]);
  assert.ok(citations.lines.every((l) => l.kind !== 'check' || /inline|citations verified/.test(l.text)));

  const guardrails = step(steps, 'validate');
  assert.equal(guardrails.status, 'done');
  assert.deepEqual(results(guardrails), [{ kind: 'result', tone: 'passed', text: 'Passed: all 2 guardrail checks passed.' }]);
  assert.equal(guardrails.lines.filter((l) => l.kind === 'check').length, 2, 'citation checks are not listed as guardrails');

  assert.deepEqual(results(step(steps, 'deliver')), [{ kind: 'result', tone: 'passed', text: 'Delivered: the cited answer was shown to the employee.' }]);
});

test('a blocking guardrail failure is shown as failed and the delivery as flagged', () => {
  const steps = buildProcessSteps({
    result: answer({
      guardrail_status: 'flagged',
      outcome: 'needs_review',
      confidence: 'low',
      guardrail_checks: [
        { name: 'citations_verified', status: 'passed', detail: '2 of 2 citations verified.' },
        { name: 'coverage_determination', status: 'failed', detail: 'Claim outcome language: "your claim will be paid".' },
      ],
    }),
  });
  const guardrails = step(steps, 'validate');
  assert.equal(guardrails.status, 'failed');
  assert.deepEqual(results(guardrails), [
    { kind: 'result', tone: 'failed', text: 'Failed: coverage determination. The answer is flagged for specialist review.' },
  ]);
  assert.equal(step(steps, 'citations').status, 'done', 'citations are judged separately from guardrails');
  const deliver = step(steps, 'deliver');
  assert.equal(deliver.status, 'warning');
  assert.equal(results(deliver)[0].kind === 'result' && results(deliver)[0].tone, 'attention');
});

test('no evidence: generation is skipped, guardrails fail, and the answer is withheld', () => {
  const steps = buildProcessSteps({
    result: answer({
      status: 'insufficient_evidence',
      outcome: 'insufficient_evidence',
      evidence: [],
      citations: [],
      guardrail_status: 'no_evidence',
      guardrail_checks: [{ name: 'evidence_grounded', status: 'failed', detail: 'No policy evidence matched the question.' }],
      grounding_context_chars: null,
    }),
  });
  assert.equal(step(steps, 'retrieve').status, 'warning');
  assert.equal(step(steps, 'ground').status, 'skipped');
  assert.deepEqual(step(steps, 'generate').lines, [{ kind: 'text', text: 'Skipped: not enough evidence to draft an answer.' }]);
  assert.equal(step(steps, 'citations').status, 'skipped');
  const guardrails = step(steps, 'validate');
  assert.equal(guardrails.status, 'failed');
  assert.match((results(guardrails)[0] as { text: string }).text, /withheld and flagged for specialist review/);
  const deliver = step(steps, 'deliver');
  assert.equal(deliver.status, 'warning');
  assert.deepEqual(results(deliver), [
    { kind: 'result', tone: 'failed', text: 'Withheld: no answer was delivered. The question is flagged for specialist review.' },
  ]);
});

test('values read from the records are an exact record match and skip the language model', () => {
  const steps = buildProcessSteps({
    result: answer({
      retrieval: { answer_type: 'factual_lookup', customer_verification: verification },
      evidence: [{ source_type: 'coverage', source_id: 'cov-1', content: 'Coverage A — Limit: $512,000', relevance_score: 1 }],
      citations: [{ source_id: 'cov-1' }],
      guardrail_checks: [{ name: 'records_grounded', status: 'passed', detail: 'Directly retrieved from the policy records.' }],
      model_used: 'none (records)',
    }),
  });
  assert.deepEqual(results(step(steps, 'retrieve')), [
    { kind: 'result', tone: 'passed', text: 'Evidence confidence: exact record match. Values were read from the policy’s own records.' },
  ]);
  assert.equal(step(steps, 'retrieve').lines.filter((l) => l.kind === 'passage').length, 0);
  assert.equal(step(steps, 'generate').status, 'skipped');
  assert.equal(step(steps, 'validate').status, 'done');
});

test('details missing from older stored answers say so instead of inventing values', () => {
  const steps = buildProcessSteps({
    result: answer({ retrieval: {}, grounding_context_chars: null, model_used: 'unknown', ledger_id: null, asked_by: null }),
  });
  assert.deepEqual(step(steps, 'verify').lines, [{ kind: 'text', text: 'Customer verification was not recorded for this answer.' }]);
  assert.equal((step(steps, 'retrieve').lines[0] as { text: string }).text, 'Search counts not recorded for this answer.');
  assert.equal((step(steps, 'ground').lines[1] as { text: string }).text, 'Context size not recorded for this answer.');
  assert.deepEqual(step(steps, 'generate').lines[0], { kind: 'text', text: 'Model: not recorded' });
  assert.ok(step(steps, 'deliver').lines.some((l) => l.kind === 'warning'));
  assert.deepEqual(step(steps, 'context').lines.at(-1), { kind: 'text', text: 'Asked by: not recorded' });
});

test('a dated question shows the term in force on the loss date in the policy step', () => {
  const message = 'Using term 1 of HO-2847-1193 (March 1, 2025 – March 1, 2026), the term in force on the loss date, November 3, 2025.';
  const steps = buildProcessSteps({
    result: answer({
      retrieval: {
        customer_verification: verification,
        term_selection: { status: 'matched', loss_date: '2025-11-03', date_text: '2025-11-03', is_loss: true, year_assumed: false, policy_number: 'HO-2847-1193', term_number: 1, message },
      },
    }),
  });
  assert.deepEqual(results(step(steps, 'context')), [{ kind: 'result', tone: 'passed', text: message }]);
});
