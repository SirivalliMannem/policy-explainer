// Run with `npm test`. Reopening a conversation where one question was answered for several policies.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { groupPolicyAnswers } from '../src/lib/answerGroups.ts';

const me = { employee_id: 'EMP-1002' };
const q = (question: string, policy_id: string | null, created_at: string, asked_by = me) => ({ question, policy_id, created_at, asked_by });

function shape(records: ReturnType<typeof q>[]) {
  return groupPolicyAnswers(records).map((r) => [r.record.policy_id, r.startsQuestion, r.inGroup]);
}

test('one question answered for two policies shows once, both answers labelled', () => {
  assert.deepEqual(
    shape([
      q('Does Margaret Chen have a deductible?', 'home', '2026-10-13T09:00:00Z'),
      q('Does Margaret Chen have a deductible?', 'auto', '2026-10-13T09:00:09Z'),
    ]),
    [
      ['home', true, true],
      ['auto', false, true],
    ]
  );
});

test('separate questions stay separate and unlabelled', () => {
  assert.deepEqual(
    shape([
      q('What is the deductible?', 'home', '2026-10-13T09:00:00Z'),
      q('What forms are attached?', 'home', '2026-10-13T09:01:00Z'),
    ]),
    [
      ['home', true, false],
      ['home', true, false],
    ]
  );
});

test('asking the same question again on the same policy is a new question', () => {
  assert.deepEqual(
    shape([
      q('What is the deductible?', 'home', '2026-10-13T09:00:00Z'),
      q('What is the deductible?', 'home', '2026-10-13T09:00:30Z'),
    ]),
    [
      ['home', true, false],
      ['home', true, false],
    ]
  );
});

test('the same words asked much later are a new question', () => {
  assert.deepEqual(
    shape([
      q('What is the deductible?', 'home', '2026-10-13T09:00:00Z'),
      q('What is the deductible?', 'auto', '2026-10-13T10:00:00Z'),
    ]),
    [
      ['home', true, false],
      ['auto', true, false],
    ]
  );
});

test('three policies group together; a following question starts fresh', () => {
  assert.deepEqual(
    shape([
      q('Any claims?', 'a', '2026-10-13T09:00:00Z'),
      q('Any claims?', 'b', '2026-10-13T09:00:05Z'),
      q('Any claims?', 'c', '2026-10-13T09:00:10Z'),
      q('And billing?', 'a', '2026-10-13T09:02:00Z'),
    ]),
    [
      ['a', true, true],
      ['b', false, true],
      ['c', false, true],
      ['a', true, false],
    ]
  );
});
