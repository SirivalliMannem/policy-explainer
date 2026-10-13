import { useId, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Archive, ChevronDown, ChevronRight, RefreshCw, Search } from 'lucide-react';
import { archiveConversation } from '../../services/api';
import {
  formatConversationTitle,
  groupConversations,
  notifyConversationsChanged,
  shortWhen,
  useMyConversations,
} from '../../lib/conversations';
import { describeError } from '../../lib/explainer';
import { cn } from '../../lib/utils';

const PAGE_SIZE = 30;

/**
 * Sub-menu under "Policy Explainer": a New conversation button, then the signed-in employee's own
 * conversations (collapsible), with search, grouped Today / Yesterday / Earlier by last activity in
 * the viewer's local timezone. Archived conversations are not listed.
 */
export function ExplainerHistoryNav({ onNavigate }: { onNavigate?: () => void }) {
  const navigate = useNavigate();
  const location = useLocation();
  const listId = useId();
  const [open, setOpen] = useState(true);
  const [search, setSearch] = useState('');
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const { items, total, error, loading, reload } = useMyConversations(search, limit);
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
    <div className="ml-4 mt-1.5 flex flex-1 flex-col gap-2 pl-2.5" aria-label="Your conversations">
      <button
        type="button"
        onClick={() => {
          onNavigate?.();
          // The landing page focuses its composer on every visit.
          navigate('/app/explainer', { state: { focusComposer: true } });
        }}
        className="flex w-full shrink-0 items-center justify-center rounded-lg bg-[#EA580C] px-3 py-2 text-[12.5px] font-bold text-white shadow-sm transition-colors hover:bg-[#C2410C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] focus-visible:ring-offset-2 cursor-pointer"
      >
        New conversation
      </button>

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={listId}
        className="flex w-full shrink-0 items-center gap-1.5 rounded-md px-1 py-1 text-left text-[12px] font-semibold text-espresso transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn cursor-pointer"
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
        )}
        Recent conversations
      </button>

      <div id={listId} hidden={!open} className={open ? 'flex flex-1 flex-col gap-2' : 'hidden'}>
        <label className="relative block shrink-0">
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

        <div className="min-h-[7.5rem] flex-1 basis-0 space-y-2.5 overflow-y-auto overscroll-contain pr-0.5">
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
              {search.trim() ? 'No conversations found' : 'No conversations yet. Ask your first policy question.'}
            </p>
          ) : (
            groupConversations(items ?? []).map(({ group, items: groupItems }) => (
              <div key={group}>
                <h3 className="px-1 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{group}</h3>
                <ul className="space-y-0.5">
                  {groupItems.map((c) => {
                    const active = c.conversation_id === activeId;
                    const displayTitle = formatConversationTitle(c.title, c.customer_name, c.policy_number);
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
                          title={displayTitle}
                        >
                          <span className={cn('block truncate text-[12.5px]', active ? 'font-semibold' : 'font-medium')}>
                            {displayTitle}
                          </span>
                          <span className="block truncate text-[10.5px] text-muted-foreground">{shortWhen(c.last_activity_at)}</span>
                        </Link>
                        <button
                          type="button"
                          onClick={() => archive(c.conversation_id, displayTitle)}
                          aria-label={`Archive conversation: ${displayTitle}`}
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
          <button
            type="button"
            onClick={() => setLimit((n) => n + PAGE_SIZE)}
            disabled={loading}
            className="block shrink-0 px-1 text-left text-[11.5px] font-semibold text-orange-btn hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn disabled:opacity-60 cursor-pointer"
          >
            {loading ? 'Loading…' : `Show ${Math.min(PAGE_SIZE, total - items.length)} more`}
          </button>
        )}
      </div>
    </div>
  );
}
