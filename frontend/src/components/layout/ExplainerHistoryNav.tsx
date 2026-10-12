import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Archive, Plus, RefreshCw, Search } from 'lucide-react';
import { archiveConversation } from '../../services/api';
import { groupConversations, notifyConversationsChanged, shortWhen, useMyConversations } from '../../lib/conversations';
import { describeError } from '../../lib/explainer';
import { cn } from '../../lib/utils';

const SIDEBAR_LIMIT = 30;

/**
 * Sub-menu under "Policy Explainer": new conversation, search, and the signed-in employee's own
 * conversation history grouped by day. A shortcut list; the landing page has the full cards.
 */
export function ExplainerHistoryNav({ onNavigate }: { onNavigate?: () => void }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [search, setSearch] = useState('');
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const { items, total, error, loading, reload } = useMyConversations(search, SIDEBAR_LIMIT);
  const activeId = location.pathname.match(/^\/app\/explainer\/c\/([^/]+)/)?.[1] ?? null;

  const archive = async (id: string, title: string) => {
    if (!window.confirm(`Archive “${title}”?\n\nIt will be hidden from your list. Its answers stay in The Record.`)) return;
    try {
      await archiveConversation(id);
      setArchiveError(null);
      notifyConversationsChanged();
      if (id === activeId) navigate('/app/explainer');
    } catch (err) {
      setArchiveError(describeError(err).message);
    }
  };

  return (
    <div className="ml-5 mt-1 space-y-2 border-l border-border pl-2.5" aria-label="Your conversations">
      <button
        type="button"
        onClick={() => {
          onNavigate?.();
          navigate('/app/explainer/new');
        }}
        className="flex w-full items-center gap-2 rounded-lg border border-dashed border-[#FDBA74] px-2.5 py-1.5 text-[12.5px] font-semibold text-orange-btn transition-colors hover:bg-[#FFF7ED] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn"
      >
        <Plus className="h-3.5 w-3.5" /> New conversation
      </button>

      <label className="relative block">
        <span className="sr-only">Search your conversations</span>
        <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search conversations"
          className="h-8 w-full rounded-lg border border-border bg-white pl-7 pr-2 text-[12px] text-espresso placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn"
        />
      </label>

      <div className="max-h-[42vh] space-y-2 overflow-y-auto pr-0.5">
        {loading && !items ? (
          <div className="space-y-1.5" aria-label="Loading conversations">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-8 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : error && !items ? (
          <div className="rounded-md bg-red-50 px-2 py-1.5 text-[11.5px] text-red-700">
            Could not load conversations.{' '}
            <button type="button" onClick={reload} className="inline-flex items-center gap-1 font-semibold underline">
              <RefreshCw className="h-3 w-3" /> Retry
            </button>
          </div>
        ) : items && items.length === 0 ? (
          <p className="px-1 py-1 text-[11.5px] leading-snug text-muted-foreground">
            {search ? 'No conversations match.' : 'No conversations yet. Ask your first policy question.'}
          </p>
        ) : (
          groupConversations(items ?? []).map(({ group, items: groupItems }) => (
            <div key={group}>
              <div className="px-1 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{group}</div>
              <ul className="space-y-0.5">
                {groupItems.map((c) => {
                  const active = c.conversation_id === activeId;
                  return (
                    <li key={c.conversation_id} className="group relative">
                      <Link
                        to={`/app/explainer/c/${c.conversation_id}`}
                        onClick={onNavigate}
                        aria-current={active ? 'page' : undefined}
                        className={cn(
                          'block rounded-md px-2 py-1.5 pr-7 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn',
                          active ? 'bg-[#FFF1E6] text-[#9A3D09]' : 'text-espresso hover:bg-muted'
                        )}
                        title={c.title}
                      >
                        <span className={cn('block truncate text-[12.5px]', active ? 'font-semibold' : 'font-medium')}>
                          {c.title}
                        </span>
                        <span className="block truncate text-[10.5px] text-muted-foreground">
                          {shortWhen(c.last_activity_at)}
                          {c.policy_number ? ` · ${c.policy_number}` : ''}
                        </span>
                      </Link>
                      <button
                        type="button"
                        onClick={() => archive(c.conversation_id, c.title)}
                        aria-label={`Archive conversation: ${c.title}`}
                        title="Archive"
                        className="absolute right-1 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-white hover:text-espresso focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn group-hover:opacity-100"
                      >
                        <Archive className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))
        )}
      </div>

      {archiveError && <p className="px-1 text-[11px] text-red-700">{archiveError}</p>}
      {items && total > items.length && (
        <Link
          to="/app/explainer"
          onClick={onNavigate}
          className="block px-1 text-[11.5px] font-semibold text-orange-btn hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn"
        >
          View all {total} →
        </Link>
      )}
    </div>
  );
}
