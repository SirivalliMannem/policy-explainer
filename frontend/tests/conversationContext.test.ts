// Run with `npm test`. What a resolved question does to the conversation's customer and policy.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { contextAction, currentCustomer, sideLabel } from '../src/lib/conversationContext.ts';
import type { PolicyContextCandidate, QuestionResolution } from '../src/types/index.ts';

const policy = (id: string, customerId: string, name: string, number: string): PolicyContextCandidate => ({
  policy_id: id,
  policy_number: number,
  customer_id: customerId,
  customer_name: name,
  line_of_business: number.startsWith('HO') ? 'homeowners' : 'personal_auto',
  status: 'in_force',
  effective_date: '2026-01-01',
  expiration_date: '2027-01-01',
});
const elenaHome = policy('p1', 'elena', 'Elena Moreau', 'HO-9021-4477');
const elenaAuto = policy('p2', 'elena', 'Elena Moreau', 'PA-8830-2215');
const david = policy('p3', 'david', 'David Chen', 'PA-6120-7741');
const elena = { customer_id: 'elena', name: 'Elena Moreau' };

const resolution = (r: Partial<QuestionResolution>): QuestionResolution => ({
  status: 'no_reference',
  intent: 'policy',
  candidates: [],
  message: '',
  ...r,
});

test("\"What are Elena's policies?\" in a new conversation makes Elena the conversation's customer", () => {
  const action = contextAction(
    resolution({ status: 'ambiguous', intent: 'portfolio', candidates: [elenaHome, elenaAuto], answer_all: true, customer: elena }),
    null
  );
  assert.deepEqual(action, { kind: 'set_customer', target: { customer_id: 'elena', customer_name: 'Elena Moreau' } });
});

test('a lookup of a customer with one policy selects that policy', () => {
  const action = contextAction(
    resolution({ status: 'resolved', intent: 'portfolio', policy: david, customer: { customer_id: 'david', name: 'David Chen' } }),
    null
  );
  assert.deepEqual(action, { kind: 'set_policy', policy: david });
});

test('a follow-up about the same customer keeps the context', () => {
  const cur = currentCustomer(null, { customer_id: 'elena', customer_name: 'Elena Moreau' });
  const action = contextAction(
    resolution({ status: 'ambiguous', candidates: [elenaHome, elenaAuto], answer_all: true, customer: elena, from_context: true }),
    cur
  );
  assert.equal(action.kind, 'keep');
});

test('another customer while Elena is the context asks to switch, for a policy question or a lookup', () => {
  const cur = currentCustomer(elenaHome, null);
  const davidRes = { customer_id: 'david', name: 'David Chen' };
  const asked = contextAction(resolution({ status: 'resolved', policy: david, customer: davidRes }), cur);
  assert.equal(asked.kind, 'switch');
  const lookup = contextAction(resolution({ status: 'resolved', intent: 'portfolio', policy: david, customer: davidRes }), cur);
  assert.equal(lookup.kind, 'switch');
  // Also when the conversation has Elena without a selected policy.
  const customerOnly = currentCustomer(null, { customer_id: 'elena', customer_name: 'Elena Moreau' });
  assert.equal(contextAction(resolution({ status: 'resolved', policy: david, customer: davidRes }), customerOnly).kind, 'switch');
});

test('an unverified or book-level question changes nothing', () => {
  assert.equal(contextAction(resolution({ status: 'not_found' }), null).kind, 'keep');
  assert.equal(contextAction(resolution({ intent: 'portfolio' }), currentCustomer(elenaHome, null)).kind, 'keep');
});

test('the selected policy decides the current customer; otherwise the customer chosen alone', () => {
  assert.equal(currentCustomer(elenaAuto, { customer_id: 'x', customer_name: 'X' })?.customer_id, 'elena');
  assert.equal(currentCustomer(null, null), null);
});

test('a switch card describes a customer without one policy by their policy count', () => {
  assert.equal(sideLabel(elenaHome), 'HO-9021-4477');
  assert.equal(sideLabel(null, 2), '2 policies');
  assert.equal(sideLabel(null, 1), '1 policy');
  assert.equal(sideLabel(null), 'All policies');
});
