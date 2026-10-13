// Conversation history grouping. Kept free of runtime imports so `node --test` can load it directly.

export type HistoryGroup = 'Today' | 'Yesterday' | 'Earlier';

export const HISTORY_GROUPS: HistoryGroup[] = ['Today', 'Yesterday', 'Earlier'];

/** Server timestamps are UTC; older ones carry no offset. */
export function parseUtc(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
}

/** Local midnight `offset` days from `d`. Calendar arithmetic, so daylight-saving days still count as one day. */
function localMidnight(d: Date, offset = 0): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + offset).getTime();
}

/** Which group a last-activity time falls in, by calendar day in the viewer's local timezone. */
export function historyGroup(iso: string, now = new Date()): HistoryGroup {
  const at = parseUtc(iso).getTime();
  if (isNaN(at)) return 'Earlier';
  if (at >= localMidnight(now)) return 'Today';
  if (at >= localMidnight(now, -1)) return 'Yesterday';
  return 'Earlier';
}

/** Items split into Today / Yesterday / Earlier, in that order, keeping their order within a group; empty groups are left out. */
export function groupByActivity<T extends { last_activity_at: string }>(
  items: T[],
  now = new Date()
): { group: HistoryGroup; items: T[] }[] {
  return HISTORY_GROUPS.map((group) => ({
    group,
    items: items.filter((item) => historyGroup(item.last_activity_at, now) === group),
  })).filter((g) => g.items.length > 0);
}
