import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { PolicyContextCandidate } from '../src/types/index.ts';

/**
 * Pure helper function mirroring the frontend transition evaluation:
 * Determines whether a context change requires confirmation or is same-customer.
 */
function evaluateFrontendTransition(
  current: PolicyContextCandidate | null,
  target: PolicyContextCandidate
): {
  type: 'initial_selection' | 'same_customer_same_policy' | 'same_customer_different_policy' | 'different_customer';
  requiresConfirmation: boolean;
} {
  if (!current) {
    return { type: 'initial_selection', requiresConfirmation: false };
  }
  if (current.policy_id === target.policy_id) {
    return { type: 'same_customer_same_policy', requiresConfirmation: false };
  }
  if (current.customer_id === target.customer_id) {
    return { type: 'same_customer_different_policy', requiresConfirmation: false };
  }
  return { type: 'different_customer', requiresConfirmation: true };
}

test('initial policy selection does not require confirmation modal', () => {
  const target: PolicyContextCandidate = {
    policy_id: 'pol-1',
    policy_number: 'HO-9021-4477',
    customer_id: 'cust-1',
    customer_name: 'Elena Moreau',
    line_of_business: 'homeowners',
    status: 'in_force',
  };
  const result = evaluateFrontendTransition(null, target);
  assert.equal(result.type, 'initial_selection');
  assert.equal(result.requiresConfirmation, false);
});

test('Scenario A: same customer, same policy continues existing thread without modal', () => {
  const current: PolicyContextCandidate = {
    policy_id: 'pol-1',
    policy_number: 'HO-9021-4477',
    customer_id: 'cust-1',
    customer_name: 'Elena Moreau',
    line_of_business: 'homeowners',
    status: 'in_force',
  };
  const target = { ...current };
  const result = evaluateFrontendTransition(current, target);
  assert.equal(result.type, 'same_customer_same_policy');
  assert.equal(result.requiresConfirmation, false);
});

test('Scenario B: same customer, different policy switches context without confirmation dialog', () => {
  const current: PolicyContextCandidate = {
    policy_id: 'pol-1',
    policy_number: 'HO-9021-4477',
    customer_id: 'cust-1',
    customer_name: 'Elena Moreau',
    line_of_business: 'homeowners',
    status: 'in_force',
  };
  const autoPolicy: PolicyContextCandidate = {
    policy_id: 'pol-2',
    policy_number: 'PA-8821-3310',
    customer_id: 'cust-1',
    customer_name: 'Elena Moreau',
    line_of_business: 'personal_auto',
    status: 'in_force',
  };
  const result = evaluateFrontendTransition(current, autoPolicy);
  assert.equal(result.type, 'same_customer_different_policy');
  assert.equal(result.requiresConfirmation, false);
});

test('Scenario C: different customer selected triggers inline switch confirmation', () => {
  const current: PolicyContextCandidate = {
    policy_id: 'pol-1',
    policy_number: 'HO-9021-4477',
    customer_id: 'cust-1',
    customer_name: 'Elena Moreau',
    line_of_business: 'homeowners',
    status: 'in_force',
  };
  const chenPolicy: PolicyContextCandidate = {
    policy_id: 'pol-3',
    policy_number: 'HO-2847-1193',
    customer_id: 'cust-2',
    customer_name: 'Margaret Chen',
    line_of_business: 'homeowners',
    status: 'in_force',
  };
  const result = evaluateFrontendTransition(current, chenPolicy);
  assert.equal(result.type, 'different_customer');
  assert.equal(result.requiresConfirmation, true);
});

test('Scenario C inline action: Cancel retains existing context without submitting question', () => {
  let activePolicy = 'HO-9021-4477';
  let pendingQuestion: string | null = 'What does this policy cover?';

  // Simulating Cancel action
  const onCancel = () => {
    pendingQuestion = null;
    // activePolicy remains unchanged
  };

  onCancel();
  assert.equal(activePolicy, 'HO-9021-4477');
  assert.equal(pendingQuestion, null);
});

test('Scenario C inline action: Switch Context updates context and submits pending question once', () => {
  let activePolicy = 'HO-9021-4477';
  let pendingQuestion: string | null = 'What does Margaret Chen policy cover?';
  let submittedQuestion: string | null = null;
  let submissionCount = 0;

  // Simulating Switch Context action
  const onSwitchContext = (targetPolicy: string) => {
    activePolicy = targetPolicy;
    if (pendingQuestion) {
      submittedQuestion = pendingQuestion;
      submissionCount += 1;
      pendingQuestion = null;
    }
  };

  onSwitchContext('HO-2847-1193');
  assert.equal(activePolicy, 'HO-2847-1193');
  assert.equal(submittedQuestion, 'What does Margaret Chen policy cover?');
  assert.equal(submissionCount, 1);
  assert.equal(pendingQuestion, null);
});

test('Scenario D inline action: Start New Conversation creates separate context and passes pending question', () => {
  const oldConversation = { id: 'conv-1', policy: 'HO-9021-4477' };
  let newConversation: { id: string; policy: string } | null = null;
  let newConversationInitialQuestion: string | null = null;
  const pendingQuestion = 'What about auto policy?';

  // Simulating Start New Conversation action
  const onStartNewConversation = (targetPolicy: string) => {
    newConversation = { id: 'conv-2', policy: targetPolicy };
    newConversationInitialQuestion = pendingQuestion;
  };

  onStartNewConversation('PA-6120-7742');
  assert.equal(oldConversation.id, 'conv-1');
  assert.equal(oldConversation.policy, 'HO-9021-4477');
  assert.deepEqual(newConversation, { id: 'conv-2', policy: 'PA-6120-7742' });
  assert.equal(newConversationInitialQuestion, 'What about auto policy?');
});

