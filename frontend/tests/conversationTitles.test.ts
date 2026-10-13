import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatConversationTitle } from '../src/lib/conversationTitles.ts';

test('expected examples from specification generate concise human-readable titles', () => {
  // 1. What policies do we have? -> Policy Overview
  assert.equal(formatConversationTitle('What policies do we have?'), 'Policy Overview');
  assert.equal(formatConversationTitle('What policies do we have'), 'Policy Overview');
  assert.equal(formatConversationTitle('what policies do we have?'), 'Policy Overview');

  // 2. What policies does Elena Moreau have? -> Elena Moreau — Policies
  assert.equal(
    formatConversationTitle('What policies does Elena Moreau have?'),
    'Elena Moreau — Policies'
  );

  // 3. What are David Chen's policies? -> David Chen — Policies
  assert.equal(
    formatConversationTitle("What are David Chen's policies?"),
    'David Chen — Policies'
  );
  assert.equal(
    formatConversationTitle('What are David Chen’s policies?'),
    'David Chen — Policies'
  );

  // 4. What does HO-9021-4477 cover? -> HO-9021-4477 — Coverage Details
  assert.equal(
    formatConversationTitle('What does HO-9021-4477 cover?'),
    'HO-9021-4477 — Coverage Details'
  );

  // 5. HO-908-023 limits and deductibles -> HO-908-023 — Limits & Deductibles
  assert.equal(
    formatConversationTitle('HO-908-023 limits and deductibles'),
    'HO-908-023 — Limits & Deductibles'
  );
  assert.equal(
    formatConversationTitle('HO-908-023 deductibles and limits'),
    'HO-908-023 — Limits & Deductibles'
  );

  // 6. Explain this policy -> Policy Explanation
  assert.equal(formatConversationTitle('Explain this policy'), 'Policy Explanation');
  assert.equal(formatConversationTitle('explain this policy?'), 'Policy Explanation');

  // 7. What is the deductible for Coverage A? -> Coverage A — Deductible
  assert.equal(
    formatConversationTitle('What is the deductible for Coverage A?'),
    'Coverage A — Deductible'
  );
});

test('handles context parameters when customerName or policyNumber is passed', () => {
  // Uses customer context when question references customer's policies
  assert.equal(
    formatConversationTitle('Show policies for Elena Moreau', 'Elena Moreau', null),
    'Elena Moreau — Policies'
  );

  // Uses policy context when policy number is present or passed
  assert.equal(
    formatConversationTitle('What is the deductible for HO-9021-4477?', null, 'HO-9021-4477'),
    'HO-9021-4477 — Deductible'
  );
  assert.equal(
    formatConversationTitle('What are the limits?', null, 'HO-9021-4477'),
    'What are the limits?'
  );
});

test('handles fallback for ambiguous or unsupported questions cleanly', () => {
  // Short questions remain intact
  assert.equal(
    formatConversationTitle('General inquiry about insurance'),
    'General inquiry about insurance'
  );

  // Empty or whitespace fallback
  assert.equal(formatConversationTitle(''), 'New Conversation');
  assert.equal(formatConversationTitle('   '), 'New Conversation');

  // Long questions cleanly truncate without cutting words in half
  const longQuestion = 'Does this homeowners policy cover water backup from a sump pump failure in the basement?';
  const title = formatConversationTitle(longQuestion);
  assert.ok(title.endsWith('…'));
  assert.ok(title.length <= 41);
  assert.equal(title, 'Does this homeowners policy cover water…');
});
