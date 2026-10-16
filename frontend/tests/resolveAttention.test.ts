// Run with `npm test`. The Needs attention Resolve box: what it shows (resolveView, in its decision
// order) and where a suggestion is asked (suggestionNavigation). ResolveBox renders exactly these.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { SUGGESTION_COUNT, resolveView, suggestionNavigation } from '../src/lib/resolveSuggestions.ts';
import type { AttentionAnalysis, AttentionCandidate, AttentionItem } from '../src/types/index.ts';

function item(overrides: Partial<AttentionItem> = {}): AttentionItem {
  return {
    question: 'Is sewer backup covered?',
    reason: 'no_evidence',
    reason_label: 'No matching evidence',
    detail: 'No policy evidence matched the question.',
    policy_number: 'HO-2847-1193',
    policy_id: 'pol-ho-1',
    times_asked: 1,
    first_asked_at: '2026-10-16T10:00:00Z',
    last_asked_at: '2026-10-16T10:00:00Z',
    latest_entry_id: 'entry-1',
    sources: { query_terms: ['sewer'], coverages_searched: 6, forms_searched: 4, clauses_searched: 47, citations: [] },
    ...overrides,
  };
}

function candidate(question: string, relation: 'same' | 'related' = 'related'): AttentionCandidate {
  return { question, relation, note: relation === 'related' ? 'Does not answer sewer backup itself.' : null, passages: [], top_score: 0 };
}

function ready(candidates: AttentionCandidate[], overrides: Partial<AttentionAnalysis> = {}): AttentionAnalysis {
  return { status: 'ready', type: 'coverage_no_evidence', category: 'evidence_missing', reason: 'No clause.', candidates, ...overrides };
}

const TWO = [
  candidate('Which water-damage coverages are listed on HO-2847-1193?'),
  candidate('Is a water back-up endorsement attached to HO-2847-1193?'),
];

test('customer not found: zero suggestions, even if an analysis carries some', () => {
  const view = resolveView(item({ reason: 'customer_not_found', policy_id: null, policy_number: null }), ready(TWO));
  assert.equal(view.mode, 'customer_not_found');
  assert.equal(view.candidates.length, 0);
});

test('customer found but no verified policy: no policy-specific suggestions', () => {
  const view = resolveView(item({ policy_id: null }), ready(TWO));
  assert.equal(view.mode, 'policy_context_missing');
  assert.equal(view.candidates.length, 0);
  assert.equal(resolveView(item(), ready([], { type: 'policy_context_missing' })).mode, 'policy_context_missing');
});

test('verified policy, evidence missing: exactly two suggestions', () => {
  const view = resolveView(item(), ready(TWO));
  assert.equal(view.mode, 'suggestions');
  assert.equal(view.candidates.length, SUGGESTION_COUNT);
  assert.equal(view.heading, 'ASK THIS INSTEAD');
});

test('spelling or wording error with a verified policy: two corrected suggestions', () => {
  const view = resolveView(
    item({ question: 'is sewr bakup coverd' }),
    ready([candidate('Is sewer backup covered?', 'same'), candidate('Does the policy cover water backing up through a sewer?', 'same')], {
      type: 'typo',
      category: 'wrong_wording',
    })
  );
  assert.equal(view.mode, 'suggestions');
  assert.equal(view.heading, 'WRONG WORDING · TRY THESE');
  assert.deepEqual(view.candidates.map((c) => c.relation), ['same', 'same']);
});

test('anything other than exactly two suggestions shows none', () => {
  assert.equal(resolveView(item(), ready(TWO.slice(0, 1))).mode, 'no_alternative');
  assert.equal(resolveView(item(), ready(TWO.slice(0, 1))).candidates.length, 0);
});

test('not analysed, or the analysis failed: no suggestions are shown', () => {
  assert.equal(resolveView(item(), null).mode, 'not_ready');
  const failed = resolveView(item(), { status: 'failed', reason: 'The language model is not available right now.' });
  assert.equal(failed.mode, 'not_ready');
  assert.equal(failed.candidates.length, 0);
});

test('out of scope: no suggestions', () => {
  const view = resolveView(item(), ready([], { type: 'out_of_scope', category: 'out_of_scope' }));
  assert.equal(view.mode, 'out_of_scope');
  assert.equal(view.candidates.length, 0);
});

test('a suggestion opens a new conversation of the employee with the verified policy, never the asker’s', () => {
  const nav = suggestionNavigation(item(), TWO[0].question);
  assert.equal(nav.path, '/app/explainer/new');
  assert.deepEqual(nav.state, { initialQuestion: TWO[0].question, policyId: 'pol-ho-1' });
  // The queue item carries no conversation id at all: conversations belong to their owner.
  assert.equal('conversation_id' in item(), false);
});
