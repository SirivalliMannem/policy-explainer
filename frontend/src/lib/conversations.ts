import { useCallback, useEffect, useRef, useState } from 'react';
import { listConversations } from '../services/api';
import type { AskedBy, ConversationSummary } from '../types';
import { describeError } from './explainer';
import { groupByActivity, historyGroup, parseUtc, type HistoryGroup } from './historyGroups';

/** Fired after a question is asked or a conversation archived, so every history list refreshes. */
const CHANGED_EVENT = 'policy-explainer:conversations-changed';

export function notifyConversationsChanged(): void {
  window.dispatchEvent(new Event(CHANGED_EVENT));
}

export { parseUtc, historyGroup } from './historyGroups';
export type { HistoryGroup } from './historyGroups';

export function groupConversations(items: ConversationSummary[]): { group: HistoryGroup; items: ConversationSummary[] }[] {
  return groupByActivity(items);
}

/** "14:05" today, "Yesterday 09:12", or "3 Oct" for older activity. */
export function shortWhen(iso: string): string {
  const d = parseUtc(iso);
  if (isNaN(d.getTime())) return '';
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const group = historyGroup(iso);
  if (group === 'Today') return time;
  if (group === 'Yesterday') return `Yesterday ${time}`;
  return d.toLocaleDateString([], { day: 'numeric', month: 'short' });
}

/** Full timestamp for audit lines: "12 Oct 2026, 14:05". */
export function fullWhen(iso?: string | null): string {
  if (!iso) return '';
  const d = parseUtc(iso);
  if (isNaN(d.getTime())) return '';
  return `${d.toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })}, ${d.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })}`;
}

export function initials(name?: string | null, fallback = '?'): string {
  const letters = (name || '')
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
  return letters || fallback;
}

const ROLE_LABEL: Record<string, string> = {
  csr: 'Customer service',
  underwriter: 'Underwriter',
  adjuster: 'Claims adjuster',
  manager: 'Manager',
  auditor: 'Auditor',
};

export function roleLabel(role?: string | null): string {
  if (!role) return 'Not recorded';
  return ROLE_LABEL[role] || role.charAt(0).toUpperCase() + role.slice(1);
}

/** Name for display; entries recorded before names were stored show the employee ID only. */
export function askerName(asker?: AskedBy | null): string {
  return asker?.name || 'Name not recorded';
}

/** Answered vs needs a person, the two outcomes shown to employees. */
export function outcomeBadge(outcome?: string | null): { label: string; tone: 'answered' | 'review' | 'none' } {
  if (outcome === 'answered') return { label: 'Answered', tone: 'answered' };
  if (outcome === 'needs_review' || outcome === 'insufficient_evidence') return { label: 'Needs review', tone: 'review' };
  return { label: 'No answer', tone: 'none' };
}

/**
 * The signed-in employee's conversations, refreshed when any list changes.
 * `limit` grows with "load more"; `search` matches titles.
 */
export function useMyConversations(search: string, limit: number) {
  const [items, setItems] = useState<ConversationSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const requestRef = useRef(0);

  const load = useCallback(async () => {
    const id = ++requestRef.current;
    setLoading(true);
    try {
      const page = await listConversations({ search: search.trim() || undefined, limit });
      if (id !== requestRef.current) return;
      setItems(page.items);
      setTotal(page.total);
      setError(null);
    } catch (err) {
      if (id !== requestRef.current) return;
      setError(describeError(err).message);
    } finally {
      if (id === requestRef.current) setLoading(false);
    }
  }, [search, limit]);

  useEffect(() => {
    const t = setTimeout(load, search ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, search]);

  useEffect(() => {
    window.addEventListener(CHANGED_EVENT, load);
    return () => window.removeEventListener(CHANGED_EVENT, load);
  }, [load]);

  return { items, total, error, loading, reload: load };
}
