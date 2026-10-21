// Run with `npm test`. Page numbers for the Needs attention queue and the Audit Log.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PAGE_SIZE, pageWindow } from '../src/lib/pagination.ts';

test('ten rows per page', () => {
  assert.equal(PAGE_SIZE, 10);
});

test('a few pages are all shown', () => {
  assert.deepEqual(pageWindow(2, 5), [1, 2, 3, 4, 5]);
});

test('many pages show the first, the last and the current page with its neighbours', () => {
  assert.deepEqual(pageWindow(1, 20), [1, 2, null, 20]);
  assert.deepEqual(pageWindow(10, 20), [1, null, 9, 10, 11, null, 20]);
  assert.deepEqual(pageWindow(20, 20), [1, null, 19, 20]);
});
