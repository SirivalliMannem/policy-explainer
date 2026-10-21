import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ExplainerContextModel } from './contextSelector.test.ts';
import type { CustomerListItem, PolicyListItem, PolicyContextCandidate, QuestionResolution } from '../src/types/index.ts';
import { contextAction, currentCustomer } from '../src/lib/conversationContext.ts';

const margaretChen: CustomerListItem = {
  id: 'cust-chen',
  name: 'Margaret Chen',
  account_number: 'ACCT-1001',
  email: 'margaret@example.com',
  policy_count: 2,
};

const elenaMoreau: CustomerListItem = {
  id: 'cust-moreau',
  name: 'Elena Moreau',
  account_number: 'ACCT-2002',
  email: 'elena@example.com',
  policy_count: 1,
};

const margaretHome: PolicyListItem = {
  id: 'pol-chen-home',
  policy_number: 'HO-2847-1193',
  customer_id: 'cust-chen',
  customer_name: 'Margaret Chen',
  line_of_business: 'homeowners',
  status: 'in_force',
  effective_date: '2024-01-01',
  expiration_date: '2025-01-01',
};

const margaretAuto: PolicyListItem = {
  id: 'pol-chen-auto',
  policy_number: 'PA-6120-7742',
  customer_id: 'cust-chen',
  customer_name: 'Margaret Chen',
  line_of_business: 'personal_auto',
  status: 'in_force',
  effective_date: '2024-02-01',
  expiration_date: '2025-02-01',
};

const elenaHome: PolicyListItem = {
  id: 'pol-moreau-home',
  policy_number: 'HO-9021-4477',
  customer_id: 'cust-moreau',
  customer_name: 'Elena Moreau',
  line_of_business: 'homeowners',
  status: 'in_force',
  effective_date: '2024-03-01',
  expiration_date: '2025-03-01',
};

test('Scenario 1: Typing a different customer name triggers the existing confirmation flow', () => {
  // Current conversation context is Margaret Chen's Homeowners policy
  const cur = currentCustomer(
    {
      policy_id: margaretHome.id,
      policy_number: margaretHome.policy_number,
      customer_id: margaretHome.customer_id,
      customer_name: margaretHome.customer_name,
      line_of_business: margaretHome.line_of_business,
      status: margaretHome.status,
    },
    null
  );

  // User types "What are Elena's exclusions?"
  const resolution: QuestionResolution = {
    status: 'resolved',
    intent: 'policy',
    customer: { customer_id: elenaMoreau.id, name: elenaMoreau.name },
    policy: {
      policy_id: elenaHome.id,
      policy_number: elenaHome.policy_number,
      customer_id: elenaHome.customer_id,
      customer_name: elenaHome.customer_name,
      line_of_business: elenaHome.line_of_business,
      status: elenaHome.status,
    },
    candidates: [],
    message: '',
  };

  const action = contextAction(resolution, cur);
  assert.equal(action.kind, 'switch');
  if (action.kind === 'switch') {
    assert.equal(action.target.customer_id, 'cust-moreau');
    assert.equal(action.target.customer_name, 'Elena Moreau');
  }
});

test('Scenario 2: Selecting a different customer through @ triggers the same confirmation flow', () => {
  const model = new ExplainerContextModel();

  // Active context: Margaret Chen policy
  model.selectPolicyForConfirmation(margaretHome);
  model.confirmPolicyContext();
  assert.equal(model.activePolicy?.policy_number, 'HO-2847-1193');
  assert.equal(model.activePolicy?.customer_name, 'Margaret Chen');

  // User has draft question in input and selects Elena Moreau through @ selector
  model.typeInput('What does water backup cover? @');
  model.selectCustomer(elenaMoreau);

  // Must NOT immediately switch or display backend error
  assert.ok(model.pendingSwitch, 'Context switch confirmation card must be triggered');
  assert.equal(model.pendingSwitch.current.customer_name, 'Margaret Chen');
  assert.equal(model.pendingSwitch.target.customer_name, 'Elena Moreau');
  assert.equal(model.pendingSwitch.matchedOn, '@ selector');
  assert.equal(model.pendingSwitch.pendingQuestion, 'What does water backup cover?');

  // Context remains on Margaret Chen while awaiting confirmation
  assert.equal(model.activePolicy?.policy_number, 'HO-2847-1193');
  assert.equal(model.activeCustomer, null);
});

test('Scenario 3: Selecting a policy belonging to another customer through @ triggers the same confirmation flow', () => {
  const model = new ExplainerContextModel();

  // Active context: Margaret Chen policy
  model.selectPolicyForConfirmation(margaretHome);
  model.confirmPolicyContext();

  // User types question and selects Elena Moreau's policy HO-9021-4477 through @ selector
  model.typeInput('Is earthquake covered? @');
  model.selectPolicyForConfirmation(elenaHome);
  model.confirmPolicyContext();

  // Must trigger pending switch modal/card with pending question preserved
  assert.ok(model.pendingSwitch, 'Pending switch must be created');
  assert.equal(model.pendingSwitch.current.customer_name, 'Margaret Chen');
  assert.equal(model.pendingSwitch.target.customer_name, 'Elena Moreau');
  assert.equal(model.pendingSwitch.target.policy?.policy_number, 'HO-9021-4477');
  assert.equal(model.pendingSwitch.pendingQuestion, 'Is earthquake covered?');
  assert.equal(model.pendingSwitch.matchedOn, '@ selector');

  // Current context untouched
  assert.equal(model.activePolicy?.policy_number, 'HO-2847-1193');
});

test('Scenario 4: Selecting another policy belonging to the same customer does not unnecessarily trigger confirmation', () => {
  const model = new ExplainerContextModel();

  // Active context: Margaret Chen's Homeowners policy
  model.selectPolicyForConfirmation(margaretHome);
  model.confirmPolicyContext();
  assert.equal(model.activePolicy?.policy_number, 'HO-2847-1193');

  // User selects Margaret Chen's Auto policy through @ selector
  model.typeInput('What is the collision deductible? @');
  model.selectPolicyForConfirmation(margaretAuto);
  model.confirmPolicyContext();

  // Must NOT trigger confirmation prompt because it is the same customer
  assert.equal(model.pendingSwitch, null);

  // Directly switches policy context
  assert.equal(model.activePolicy?.policy_number, 'PA-6120-7742');
  assert.equal(model.activePolicy?.customer_name, 'Margaret Chen');
  // Pending question submitted
  assert.equal(model.submittedQuestions.length, 1);
  assert.equal(model.submittedQuestions[0], 'What is the collision deductible?');
});

test('Scenario 5: Confirming a switch updates active context and processes pending question exactly once', () => {
  const model = new ExplainerContextModel();

  // Initial active context: Margaret Chen
  model.selectPolicyForConfirmation(margaretHome);
  model.confirmPolicyContext();

  // Select Elena Moreau through @ selector with pending question
  model.typeInput('Does this cover wind damage? @');
  model.selectCustomer(elenaMoreau);
  assert.ok(model.pendingSwitch);

  // Confirm context switch
  model.confirmSwitchContext();

  // State is updated to Elena Moreau
  assert.equal(model.pendingSwitch, null);
  assert.equal(model.activePolicy, null);
  assert.equal(model.activeCustomer?.customer_name, 'Elena Moreau');
  assert.equal(model.activeCustomer?.customer_id, 'cust-moreau');

  // Pending question is processed exactly once
  assert.equal(model.submittedQuestions.length, 1);
  assert.equal(model.submittedQuestions[0], 'Does this cover wind damage?');
  assert.equal(model.input, '');
});

test('Scenario 6: Cancelling a switch preserves previous context and does not submit pending question', () => {
  const model = new ExplainerContextModel();

  // Active context: Margaret Chen
  model.selectPolicyForConfirmation(margaretHome);
  model.confirmPolicyContext();

  // Select Elena Moreau through @ selector
  model.typeInput('What about flood? @');
  model.selectCustomer(elenaMoreau);
  assert.ok(model.pendingSwitch);

  // Cancel switch
  model.cancelSwitch();

  // State retains Margaret Chen
  assert.equal(model.pendingSwitch, null);
  assert.equal(model.activePolicy?.policy_number, 'HO-2847-1193');
  assert.equal(model.activePolicy?.customer_name, 'Margaret Chen');
  assert.equal(model.activeCustomer, null);

  // Question is NOT submitted against Elena Moreau
  assert.equal(model.submittedQuestions.length, 0);
  assert.equal(model.input, 'What about flood?');
});

test('Scenario 6b: Start New Conversation creates separate thread and submits pending question', () => {
  const model = new ExplainerContextModel();

  // Active context: Margaret Chen
  model.selectPolicyForConfirmation(margaretHome);
  model.confirmPolicyContext();

  // Select Elena Moreau policy through @ selector
  model.typeInput('What is deductible? @');
  model.selectPolicyForConfirmation(elenaHome);
  model.confirmPolicyContext();
  assert.ok(model.pendingSwitch);

  // User chooses Start New Conversation
  const newThread = model.confirmStartNew();
  assert.ok(newThread);

  // Old conversation context preserved
  assert.equal(model.activePolicy?.policy_number, 'HO-2847-1193');
  assert.equal(model.pendingSwitch, null);

  // New conversation has Elena Moreau's policy context and received the question once
  assert.equal(newThread.activePolicy?.policy_number, 'HO-9021-4477');
  assert.equal(newThread.activePolicy?.customer_name, 'Elena Moreau');
  assert.equal(newThread.submittedQuestions.length, 1);
  assert.equal(newThread.submittedQuestions[0], 'What is deductible?');
});

test('Scenario 7: Unknown customer or invalid policy cannot leak evidence from previous customer', () => {
  const model = new ExplainerContextModel();

  // Active context: Margaret Chen
  model.selectPolicyForConfirmation(margaretHome);
  model.confirmPolicyContext();

  // Unknown customer resolution simulation
  const unknownResolution: QuestionResolution = {
    status: 'not_found',
    intent: 'policy',
    customer: null,
    customer_verification: { status: 'not_found', customer_name: null },
    candidates: [],
    message: "No customer found matching 'Unknown Person'.",
    suggestions: [],
    suggested_policies: [],
  };

  // Unknown customer does NOT switch context
  const action = contextAction(unknownResolution, currentCustomer(model.activePolicy, null));
  assert.equal(action.kind, 'keep');

  // No policy suggestions are returned for unknown customer
  assert.equal(unknownResolution.suggestions.length, 0);
  assert.equal(unknownResolution.suggested_policies.length, 0);
});

test('Scenario 8: Customer-level context to same customer policy binding works without switch modal', () => {
  const model = new ExplainerContextModel();

  // Initial customer context: Margaret Chen (customer level, no policy selected)
  model.selectCustomer(margaretChen);
  assert.equal(model.activeCustomer?.customer_name, 'Margaret Chen');
  assert.equal(model.activePolicy, null);

  // Selecting a policy belonging to Margaret Chen binds directly
  model.selectPolicyForConfirmation(margaretHome);
  model.confirmPolicyContext();

  assert.equal(model.pendingSwitch, null);
  assert.equal(model.activePolicy?.policy_number, 'HO-2847-1193');
  assert.equal(model.activePolicy?.customer_name, 'Margaret Chen');
});
