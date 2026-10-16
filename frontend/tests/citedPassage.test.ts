// Run with `npm test`. A cited page of an uploaded document narrowed to the detail the answer used.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { MAX_HIGHLIGHTS, claimText, pageParagraphs, passageSentences } from '../src/lib/citedPassage.ts';

const PASSAGE =
  'Section 2 - Benefits. Flat battery: we will arrange a jump start at the roadside. ' +
  'Spare key: we will deliver a spare key to you, up to 2 times a year. Towing up to 50 km to the nearest garage.';

test('the sentences that support the answer are marked, not the whole passage', () => {
  const sentences = passageSentences(PASSAGE, 'It lists benefits such as a spare key delivered to you twice a year.');
  const marked = sentences.filter((s) => s.match).map((s) => s.text);
  assert.deepEqual(marked, ['Spare key: we will deliver a spare key to you, up to 2 times a year.']);
});

test('nothing is marked when the answer shares no real words with the passage', () => {
  assert.ok(passageSentences(PASSAGE, 'In general, it is an add-on.').every((s) => !s.match));
  assert.ok(passageSentences(PASSAGE).every((s) => !s.match));
});

test('never more than a few sentences are marked', () => {
  const many = Array.from({ length: 8 }, (_, i) => `Towing benefit ${i} applies to the garage.`).join(' ');
  assert.ok(passageSentences(many, 'towing benefit applies garage').filter((s) => s.match).length <= MAX_HIGHLIGHTS);
});

test("the page's paragraphs in the cited passage are marked", () => {
  const page = 'Add-on cover wording\n\nFlat battery: we will arrange a jump start.\n\nGeneral conditions apply to all benefits.';
  const marked = pageParagraphs(page, 'Flat battery: we will arrange a jump start.').map((p) => p.cited);
  assert.deepEqual(marked, [false, true, false]);
});

test("the claim is the answer's words without references or bold markup", () => {
  assert.equal(claimText('It covers a **spare key** delivery [E2][E3]'), 'It covers a spare key delivery');
});
