import { AlertCircle, History, Loader2, Plus, RefreshCw } from 'lucide-react';
import type { RecentQuestionItem } from '../../types';
import { relativeTime } from '../../lib/explainer';

interface RecentQuestionsProps {
  items: RecentQuestionItem[] | null;
  error: string | null;
  loading: boolean;
  activeConversationId: string | null;
  disabled: boolean;
  onOpen: (conversationId: string) => void;
  onNewConversation: () => void;
  onRefresh: () => void;
}

interface ConversationEntry {
  latest: RecentQuestionItem;
  count: number;
}

/** One entry per conversation: its latest question, and how many questions it holds. */
function byConversation(items: RecentQuestionItem[]): ConversationEntry[] {
  const entries = new Map<string, ConversationEntry>();
  for (const item of items) {
    const entry = entries.get(item.conversation_id);
    if (entry) entry.count += 1;
    else entries.set(item.conversation_id, { latest: item, count: 1 });
  }
  return [...entries.values()];
}

function ConfidenceDot({ item }: { item: RecentQuestionItem }) {
  const color =
    item.status === 'failed'
      ? 'bg-red-500'
      : item.confidence === 'high'
      ? 'bg-emerald-500'
      : item.confidence === 'medium'
      ? 'bg-amber-500'
      : item.confidence === 'none' || item.status === 'insufficient_evidence'
      ? 'bg-slate-400'
      : 'bg-slate-300';
  const label =
    item.status === 'failed'
      ? 'Not answered'
      : item.status === 'insufficient_evidence'
      ? 'Insufficient evidence'
      : item.confidence
      ? `${item.confidence} confidence`
      : 'Pending';
  return <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${color}`} title={label} aria-label={label} />;
}

/** Recent policy questions, grouped by conversation; selecting one reopens it from the record. */
export function RecentQuestions({
  items,
  error,
  loading,
  activeConversationId,
  disabled,
  onOpen,
  onNewConversation,
  onRefresh,
}: RecentQuestionsProps) {
  const entries = items ? byConversation(items) : [];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onNewConversation}
          disabled={disabled}
          className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-[#0F2A43] px-3 py-2 text-[12px] font-semibold text-white transition-colors hover:bg-[#16385A] disabled:opacity-50 cursor-pointer"
        >
          <Plus className="h-3.5 w-3.5" /> New conversation
        </button>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          aria-label="Refresh recent questions"
          title="Refresh"
          className="rounded-lg border border-[#E2E8F0] p-2 text-[#64748B] transition-colors hover:border-[#F97316] hover:text-[#EA580C] disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-2.5 text-[11.5px] text-red-700">
          <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" />
          <span>Recent questions could not be loaded. {error}</span>
        </div>
      )}

      {!items && loading && (
        <div className="flex items-center justify-center gap-2 py-8 text-[12px] text-[#64748B]">
          <Loader2 className="h-4 w-4 animate-spin text-[#F97316]" /> Loading…
        </div>
      )}

      {items && entries.length === 0 && (
        <div className="py-8 text-center text-[12px] text-[#64748B]">
          <History className="mx-auto mb-2 h-6 w-6 text-slate-300" />
          No policy questions have been asked yet.
        </div>
      )}

      {entries.length > 0 && (
        <ul className="space-y-1">
          {entries.map(({ latest, count }) => {
            const active = latest.conversation_id === activeConversationId;
            const portfolio = latest.policy_number === 'Portfolio';
            return (
              <li key={latest.conversation_id}>
                <button
                  type="button"
                  onClick={() => onOpen(latest.conversation_id)}
                  disabled={disabled || active}
                  aria-current={active ? 'true' : undefined}
                  className={`flex w-full items-start gap-2.5 rounded-lg border px-2.5 py-2 text-left transition-colors cursor-pointer disabled:cursor-default ${
                    active
                      ? 'border-[#FDBA74] bg-[#FFF7ED]'
                      : 'border-transparent hover:border-[#E2E8F0] hover:bg-[#F8FAFC] disabled:opacity-60'
                  }`}
                >
                  <ConfidenceDot item={latest} />
                  <span className="min-w-0 flex-1">
                    <span className="line-clamp-2 text-[12.5px] font-medium leading-snug text-[#0F2A43]">{latest.question}</span>
                    <span className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[10.5px] text-[#64748B]">
                      <span className="truncate">{latest.customer_name}</span>
                      <span className="text-slate-300">·</span>
                      <span className={portfolio ? '' : 'font-mono'}>{latest.policy_number}</span>
                    </span>
                    <span className="mt-0.5 flex items-center gap-1.5 text-[10.5px] text-[#94A3B8]">
                      {relativeTime(latest.created_at)}
                      {count > 1 && <span>· {count} questions</span>}
                      {active && <span className="font-semibold text-[#C2410C]">· Open now</span>}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
