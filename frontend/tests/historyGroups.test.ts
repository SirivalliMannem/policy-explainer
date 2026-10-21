// Run with `npm test`. Grouping is by calendar day in the viewer's local timezone.
import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { groupByActivity, historyGroup } from '../src/lib/historyGroups.ts';

const originalTz = process.env.TZ;
after(() => {
  process.env.TZ = originalTz;
});

/** Node re-reads TZ when it is assigned, so each test can pick the viewer's timezone. */
function inTimezone(tz: string, fn: () => void) {
  process.env.TZ = tz;
  try {
    fn();
  } finally {
    process.env.TZ = originalTz;
  }
}

test('the same instant is Today in Kolkata but Yesterday in New York', () => {
  const activity = '2026-10-11T20:00:00Z'; // 01:30 on 12 Oct in Kolkata, 16:00 on 11 Oct in New York
  inTimezone('Asia/Kolkata', () => {
    assert.equal(historyGroup(activity, new Date(2026, 9, 12, 10, 0)), 'Today');
  });
  inTimezone('America/New_York', () => {
    assert.equal(historyGroup(activity, new Date(2026, 9, 12, 10, 0)), 'Yesterday');
  });
});

test('Today, Yesterday and Earlier follow local midnights', () => {
  inTimezone('Europe/London', () => {
    const now = new Date(2026, 9, 12, 9, 0);
    assert.equal(historyGroup(new Date(2026, 9, 12, 0, 0, 1).toISOString(), now), 'Today');
    assert.equal(historyGroup(new Date(2026, 9, 11, 23, 59).toISOString(), now), 'Yesterday');
    assert.equal(historyGroup(new Date(2026, 9, 11, 0, 0).toISOString(), now), 'Yesterday');
    assert.equal(historyGroup(new Date(2026, 9, 10, 23, 59).toISOString(), now), 'Earlier');
  });
});

test('yesterday is a calendar day even across a daylight-saving change', () => {
  inTimezone('America/New_York', () => {
    // Clocks went back on 1 Nov 2026, so that day lasted 25 hours.
    const now = new Date(2026, 10, 2, 0, 30);
    assert.equal(historyGroup(new Date(2026, 10, 1, 0, 30).toISOString(), now), 'Yesterday');
    assert.equal(historyGroup(new Date(2026, 9, 31, 23, 30).toISOString(), now), 'Earlier');
  });
});

test('server timestamps without an offset are read as UTC', () => {
  inTimezone('Asia/Kolkata', () => {
    const now = new Date(2026, 9, 12, 10, 0);
    // 19:00 UTC on 11 Oct is 00:30 on 12 Oct in Kolkata.
    assert.equal(historyGroup('2026-10-11T19:00:00', now), 'Today');
    assert.equal(historyGroup('2026-10-11T18:00:00', now), 'Yesterday');
  });
});

test('groups come in order, keep item order, and empty groups are left out', () => {
  inTimezone('UTC', () => {
    const now = new Date('2026-10-12T12:00:00Z');
    const items = [
      { id: 'a', last_activity_at: '2026-10-12T11:00:00Z' },
      { id: 'b', last_activity_at: '2026-10-12T08:00:00Z' },
      { id: 'c', last_activity_at: '2026-10-01T08:00:00Z' },
    ];
    const groups = groupByActivity(items, now);
    assert.deepEqual(
      groups.map((g) => [g.group, g.items.map((i) => i.id)]),
      [
        ['Today', ['a', 'b']],
        ['Earlier', ['c']],
      ]
    );
    assert.deepEqual(groupByActivity([], now), []);
  });
});
