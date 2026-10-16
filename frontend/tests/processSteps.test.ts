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

test('a live run shows the verified customer the same way', () => {
  const steps = buildProcessSteps({
    verification,
    stages: stages({ verify: { status: 'completed', detail: verification.message }, context: { status: 'processing' } }),
  });
  assert.deepEqual(step(steps, 'verify').lines.map((l) => ('text' in l ? l.text : '')), [
    'Verified: Margaret Chen',
    'Found in the customer records, matched on policy number (HO-2847-1193)',
    'Account ID ',
  ]);
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
  // Verified customer, then where they were found in the records, then their account ID.
  assert.deepEqual(verify.lines, [
    { kind: 'result', tone: 'passed', text: 'Verified: Margaret Chen' },
    { kind: 'text', text: 'Found in the customer records, matched on policy number (HO-2847-1193)' },
    { kind: 'text', text: 'Account ID ', mono: 'ACCT-100241' },
  ]);

  const retrieve = step(steps, 'retrieve');
  assert.deepEqual(results(retrieve), [
    { kind: 'result', tone: 'passed', text: 'Evidence confidence: 100%' },
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

test('a several-facts answer lists each part and its source, and record facts are not scored passages', () => {
  const steps = buildProcessSteps({
    result: answer({
      retrieval: {
        answer_type: 'multi_part',
        customer_verification: verification,
        parts: [
          { label: 'Deductible', question: 'What is the wind deductible', source: 'records', found: true },
          { label: 'What the policy wording says', question: 'does it cover hail', source: 'wording', found: true },
        ],
      },
      evidence: [
        { source_type: 'coverage', source_id: 'cov', content: 'Windstorm or Hail — 2%', relevance_score: 1, scope: 'policy_record' },
        { source_type: 'clause', source_id: 'c1', form_number: 'HO 00 03', page: 9, content: 'Hail…', relevance_score: 15 },
      ],
    }),
  });
  const retrieve = step(steps, 'retrieve');
  assert.deepEqual(retrieve.lines.slice(0, 2), [
    { kind: 'text', text: 'Part 1 · Deductible: read from the policy records' },
    { kind: 'text', text: 'Part 2 · What the policy wording says: clause search and the language model' },
  ]);
  assert.deepEqual(retrieve.lines.filter((l) => l.kind === 'passage'), [
    { kind: 'passage', form: 'HO 00 03', page: 9, score: 15, percent: 100 },
  ]);
});

const guidanceArticle = {
  ref: 'G1',
  document_id: 'doc-1',
  title: 'Water backup and sump overflow cover',
  collection: 'Homeowners — what it covers',
  kind: 'product_article',
  body: 'Water that backs up through sewers or drains…',
  spoken: 'That one is an add-on…',
  matched_on: ['backup', 'sewer', 'basement'],
  version: '1',
  approved_by: 'Product & Service Content',
};

test('company guidance is listed in the retrieve step with the words it matched on', () => {
  const steps = buildProcessSteps({
    result: answer({
      retrieval: { ...answer().retrieval, company_guidance: { searched: true, articles: [guidanceArticle] } },
      guardrail_checks: [
        ...answer().guardrail_checks,
        {
          name: 'guidance_not_overriding_form',
          status: 'passed',
          detail: 'Guidance does not override the form: the policy answer cites only policy forms and records; 1 guidance article is shown separately.',
        },
      ],
    }),
  });
  const retrieve = step(steps, 'retrieve').lines;
  assert.deepEqual(retrieve.slice(-2), [
    { kind: 'text', text: 'Company guidance: 1 article matched' },
    { kind: 'text', text: 'G1 · Water backup and sump overflow cover (matched: backup, sewer, basement)' },
  ]);
  const guardrails = step(steps, 'validate');
  assert.equal(guardrails.status, 'done');
  assert.ok(
    guardrails.lines.some((l) => l.kind === 'check' && l.ok && l.text.startsWith('Guidance does not override the form'))
  );
});

test('no matching article, a withheld answer, and older answers each say so', () => {
  const lines = (company_guidance: unknown) =>
    step(buildProcessSteps({ result: answer({ retrieval: { ...answer().retrieval, company_guidance } as never }) }), 'retrieve').lines;
  assert.deepEqual(lines({ searched: true, articles: [] }).at(-1), { kind: 'text', text: 'Company guidance: no article on this topic' });
  assert.deepEqual(lines({ searched: false, articles: [] }).at(-1), {
    kind: 'text',
    text: 'Company guidance: not shown, because no policy answer was delivered',
  });
  assert.ok(!lines(undefined).some((l) => 'text' in l && l.text.startsWith('Company guidance')));
});

test('meaning search: passages found by meaning are tagged, and the retrieve step says what it added', () => {
  const steps = buildProcessSteps({
    result: answer({
      retrieval: {
        ...answer().retrieval,
        meaning_search: { status: 'used', model: 'BAAI/bge-small-en-v1.5', found_by_meaning: 1, words_and_meaning: 1 },
      },
      evidence: [
        { source_type: 'clause', source_id: 'c1', form_number: 'HO 00 03', page: 7, content: '…', relevance_score: 18.1, matched_by: 'meaning' },
        { source_type: 'clause', source_id: 'c2', form_number: 'HO 00 03', page: 19, content: '…', relevance_score: 14, matched_by: 'words and meaning' },
      ],
    }),
  });
  const lines = step(steps, 'retrieve').lines;
  assert.ok(
    lines.some((l) => l.kind === 'text' && l.text === 'Meaning search: 1 passage found by meaning only, 1 passage matched by words and meaning')
  );
  assert.deepEqual(
    lines.filter((l) => l.kind === 'passage').map((l) => (l.kind === 'passage' ? l.matchedBy : null)),
    ['meaning', 'words and meaning']
  );
});

test('meaning search unavailable or finding nothing says so; older answers show nothing', () => {
  const lines = (meaning_search: unknown) =>
    step(buildProcessSteps({ result: answer({ retrieval: { ...answer().retrieval, meaning_search } as never }) }), 'retrieve').lines;
  assert.ok(
    lines({ status: 'unavailable', reason: 'switched off (SEMANTIC_SEARCH=off)' }).some(
      (l) => l.kind === 'warning' && l.text === 'Meaning search unavailable (switched off (SEMANTIC_SEARCH=off)): word match only'
    )
  );
  assert.ok(
    lines({ status: 'used', found_by_meaning: 0, words_and_meaning: 0 }).some(
      (l) => l.kind === 'text' && l.text === 'Meaning search: no passage stood out by meaning'
    )
  );
  assert.ok(!lines(undefined).some((l) => 'text' in l && l.text.startsWith('Meaning search')));
});

test('an answer from an uploaded document names the document and skips customer verification', () => {
  const steps = buildProcessSteps({
    result: answer({
      answer_type: 'document',
      policy_context: null,
      retrieval: {
        answer_type: 'document',
        mode: 'question',
        passages_searched: 4,
        document: { id: 'doc-1', filename: 'renters.pdf', unit: 'page', page_count: 2 },
      },
    }),
  });
  assert.deepEqual(step(steps, 'verify').lines, [{ kind: 'text', text: 'Not needed: answered from the uploaded document.' }]);
  assert.ok(step(steps, 'context').lines.some((l) => l.kind === 'text' && l.text === 'Uploaded document: renters.pdf · 2 pages'));
  assert.ok(step(steps, 'retrieve').lines.some((l) => l.kind === 'text' && l.text === 'Searched 4 passages of renters.pdf'));
});

test('the whole-document explanation shows no search scores (nothing was searched)', () => {
  const steps = buildProcessSteps({
    result: answer({
      answer_type: 'document',
      policy_context: null,
      evidence: [{ source_type: 'document', source_id: 'p1', form_number: 'renters.pdf', page: 1, content: '…', relevance_score: 0 }],
      retrieval: { answer_type: 'document', mode: 'summary', passages_searched: 2, document: { id: 'd', filename: 'renters.pdf', unit: 'page', page_count: 2 } },
    }),
  });
  const lines = step(steps, 'retrieve').lines;
  assert.ok(lines.some((l) => l.kind === 'text' && l.text === 'Read 2 passages across renters.pdf for the explanation'));
  assert.ok(!lines.some((l) => l.kind === 'passage' || ('text' in l && l.text.startsWith('Evidence confidence'))));
});
