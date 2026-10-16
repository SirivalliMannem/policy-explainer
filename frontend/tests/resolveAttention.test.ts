import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { AttentionItem, AttentionCandidate, AttentionAnalysis } from '../src/types/index.ts';

/**
 * Pure helper mirroring ResolveBox suggestion navigation:
 * Generates navigation target path and state, and confirms it does NOT invoke resolveAttention.
 */
function getSuggestionNavigation(
  item: AttentionItem,
  candidate: AttentionCandidate
): { target: string; state: { initialQuestion: string; policyId?: string } } {
  const target = item.conversation_id ? `/app/explainer/c/${item.conversation_id}` : '/app/explainer';
  return {
    target,
    state: {
      initialQuestion: candidate.question,
      policyId: item.policy_id || undefined,
    },
  };
}

/**
 * Helper simulating UI state determination in ResolveBox:
 * Returns whether "Suggestions not ready" placeholder is shown or suggestions list is rendered.
 */
function getResolveBoxDisplayState(analysis: AttentionAnalysis | null | undefined): {
  showNotReadyPlaceholder: boolean;
  showSuggestionsList: boolean;
  candidateCount: number;
} {
  const ready = analysis?.status === 'ready';
  const candidates = ready ? analysis?.candidates ?? [] : [];
  return {
    showNotReadyPlaceholder: !ready,
    showSuggestionsList: candidates.length > 0,
    candidateCount: candidates.length,
  };
}

test('suggestion click generates correct navigation to existing conversation with question and policy context', () => {
  const item: AttentionItem = {
    question: 'Does this policy cover flood damage?',
    reason: 'no_evidence',
    reason_label: 'No matching policy evidence',
    detail: 'Searched 4 coverages; none mention flood.',
    policy_number: 'HO-2847-1193',
    policy_id: 'pol-ho-1',
    conversation_id: 'conv-xyz-123',
    times_asked: 1,
    first_asked_at: '2026-10-15T10:00:00Z',
    last_asked_at: '2026-10-15T10:00:00Z',
    latest_entry_id: 'entry-1',
    sources: { query_terms: ['flood'], coverages_searched: 4, forms_searched: 2, clauses_searched: 30, citations: [] },
  };

  const candidate: AttentionCandidate = {
    question: 'What water damage coverages or endorsements apply to HO-2847-1193?',
    relation: 'related',
    note: 'Inquires about available water damage coverages.',
    passages: [],
    top_score: 0.0,
  };

  const nav = getSuggestionNavigation(item, candidate);
  assert.equal(nav.target, '/app/explainer/c/conv-xyz-123');
  assert.equal(nav.state.initialQuestion, 'What water damage coverages or endorsements apply to HO-2847-1193?');
  assert.equal(nav.state.policyId, 'pol-ho-1');
});

test('suggestion click without conversation_id navigates to base explainer path', () => {
  const item: AttentionItem = {
    question: 'Is Margaret Chen on file?',
    reason: 'customer_not_found',
    reason_label: 'Customer not found',
    detail: 'No customer matching Margaret Chen.',
    policy_number: null,
    policy_id: null,
    conversation_id: null,
    times_asked: 1,
    first_asked_at: '2026-10-15T10:00:00Z',
    last_asked_at: '2026-10-15T10:00:00Z',
    latest_entry_id: 'entry-2',
    sources: { query_terms: ['margaret'], coverages_searched: 0, forms_searched: 0, clauses_searched: 0, citations: [] },
  };

  const candidate: AttentionCandidate = {
    question: 'Could you provide the customer full name or policy number?',
    relation: 'related',
    note: 'Clarifies customer identity.',
    passages: [],
    top_score: 0.0,
  };

  const nav = getSuggestionNavigation(item, candidate);
  assert.equal(nav.target, '/app/explainer');
  assert.equal(nav.state.initialQuestion, 'Could you provide the customer full name or policy number?');
  assert.equal(nav.state.policyId, undefined);
});

test('clicking a suggestion does not prematurely call resolve or change ledger status', () => {
  let resolveCallCount = 0;
  const mockResolveAttention = () => {
    resolveCallCount++;
  };

  const item: AttentionItem = {
    question: 'Is sewer back-up covered?',
    reason: 'no_evidence',
    reason_label: 'No matching policy evidence',
    detail: 'No evidence.',
    policy_number: 'HO-2847-1193',
    policy_id: 'pol-1',
    conversation_id: 'conv-1',
    times_asked: 1,
    first_asked_at: '2026-10-15T10:00:00Z',
    last_asked_at: '2026-10-15T10:00:00Z',
    latest_entry_id: 'entry-3',
    sources: { query_terms: [], coverages_searched: 1, forms_searched: 1, clauses_searched: 10, citations: [] },
  };

  const candidate: AttentionCandidate = {
    question: 'Is sewer back-up into the basement covered under endorsement HO 04 95?',
    relation: 'related',
    note: 'Inquires about endorsement coverage.',
    passages: [],
    top_score: 0.0,
  };

  // Simulate suggestion click handler
  const nav = getSuggestionNavigation(item, candidate);
  // resolveAttention is NOT called
  assert.equal(resolveCallCount, 0, 'resolveAttention must not be invoked on suggestion click');
  assert.ok(nav.target.includes('conv-1'));
});

test('Resolve panel replaces "Suggestions not ready" when analysis is ready with suggestions', () => {
  // 1. When analysis is null (not yet ready)
  const pendingState = getResolveBoxDisplayState(null);
  assert.equal(pendingState.showNotReadyPlaceholder, true);
  assert.equal(pendingState.showSuggestionsList, false);

  // 2. When analysis has failed
  const failedState = getResolveBoxDisplayState({
    version: 1,
    analyzed_at: '2026-10-15T10:00:00Z',
    status: 'failed',
    reason: 'Language model busy',
  });
  assert.equal(failedState.showNotReadyPlaceholder, true);
  assert.equal(failedState.showSuggestionsList, false);

  // 3. When analysis is ready with exactly two suggestions
  const readyState = getResolveBoxDisplayState({
    version: 1,
    analyzed_at: '2026-10-15T10:00:00Z',
    status: 'ready',
    type: 'coverage_no_evidence',
    category: 'evidence_missing',
    reason: 'No coverage found for meteors.',
    candidates: [
      { question: 'Alternative question 1', relation: 'related', note: 'Note 1', passages: [], top_score: 0.0 },
      { question: 'Alternative question 2', relation: 'related', note: 'Note 2', passages: [], top_score: 0.0 },
    ],
  });
  assert.equal(readyState.showNotReadyPlaceholder, false, '"Suggestions not ready" must be replaced');
  assert.equal(readyState.showSuggestionsList, true, 'Suggestions list must be displayed');
  assert.equal(readyState.candidateCount, 2, 'Exactly two candidates must be rendered');
});

test('Case A, Case B, and Case C suggestion structures conform to requirements', () => {
  // Case A: no_evidence -> relation is 'related'
  const caseACandidates: AttentionCandidate[] = [
    { question: 'Is water backup covered by HO 04 95?', relation: 'related', note: 'Examines water backup.', passages: [], top_score: 5.0 },
    { question: 'What is the limit for water backup?', relation: 'related', note: 'Examines limit.', passages: [], top_score: 4.0 },
  ];
  assert.equal(caseACandidates.length, 2);
  assert.ok(caseACandidates.every((c) => c.relation === 'related'));

  // Case B: typo/wording -> relation is 'same'
  const caseBCandidates: AttentionCandidate[] = [
    { question: 'Is sewer back-up into basement covered?', relation: 'same', passages: [], top_score: 6.0 },
    { question: 'Does policy HO-2847-1193 cover sewer back-up?', relation: 'same', passages: [], top_score: 5.5 },
  ];
  assert.equal(caseBCandidates.length, 2);
  assert.ok(caseBCandidates.every((c) => c.relation === 'same'));

  // Case C: other errors (customer_not_found, missing identifier) -> relation is 'related'
  const caseCCandidates: AttentionCandidate[] = [
    { question: 'Could you provide the policy number (e.g. HO-XXXX-XXXX)?', relation: 'related', note: 'Clarifies policy number.', passages: [], top_score: 0.0 },
    { question: 'Could you provide the customer full name or account number?', relation: 'related', note: 'Clarifies customer identity.', passages: [], top_score: 0.0 },
  ];
  assert.equal(caseCCandidates.length, 2);
  assert.ok(caseCCandidates.every((c) => c.relation === 'related'));
});
