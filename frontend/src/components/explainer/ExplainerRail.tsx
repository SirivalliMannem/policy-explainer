import { Cpu, History } from 'lucide-react';
import type { RecentQuestionItem } from '../../types';
import type { ProcessState } from '../../lib/explainer';
import { AIProcessSidebar, PHASE_BADGE } from './AIProcessSidebar';
import { RecentQuestions } from './RecentQuestions';

export type RailTab = 'process' | 'recent';

interface ExplainerRailProps {
  tab: RailTab;
  onTabChange: (tab: RailTab) => void;
  process: ProcessState;
  policyNumber?: string | null;
  recent: RecentQuestionItem[] | null;
  recentError: string | null;
  recentLoading: boolean;
  conversationId: string | null;
  busy: boolean;
  onOpenConversation: (conversationId: string) => void;
  onNewConversation: () => void;
  onRefreshRecent: () => void;
}

/** Right rail of the Explainer: the AI process of the current question, and recent questions. */
export function ExplainerRail({
  tab,
  onTabChange,
  process,
  policyNumber,
  recent,
  recentError,
  recentLoading,
  conversationId,
  busy,
  onOpenConversation,
  onNewConversation,
  onRefreshRecent,
}: ExplainerRailProps) {
  const badge = PHASE_BADGE[process.phase];
  const insufficient = process.phase === 'completed' && process.result?.status === 'insufficient_evidence';

  const tabClass = (active: boolean) =>
    `flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] font-bold uppercase tracking-[0.1em] transition-colors cursor-pointer ${
      active ? 'bg-white text-[#0F2A43] shadow-sm ring-1 ring-[#E2E8F0]' : 'text-[#64748B] hover:text-[#0F2A43]'
    }`;

  return (
    <div className="flex w-full flex-col gap-3 rounded-xl border border-[#E2E8F0] bg-white p-3 shadow-sm lg:w-[19rem]">
      <div role="tablist" aria-label="Explainer panel" className="flex gap-1 rounded-lg bg-[#F1F5F9] p-1">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'process'}
          onClick={() => onTabChange('process')}
          className={tabClass(tab === 'process')}
        >
          <Cpu className="h-3.5 w-3.5 text-[#F97316]" /> AI process
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'recent'}
          onClick={() => onTabChange('recent')}
          className={tabClass(tab === 'recent')}
        >
          <History className="h-3.5 w-3.5 text-[#F97316]" /> Recent
        </button>
      </div>

      {tab === 'process' ? (
        <div className="px-1 pb-1">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[#64748B]">Current question</span>
            <span className={`rounded-md px-2 py-0.5 text-[10.5px] font-semibold ring-1 ${badge.className}`}>
              {insufficient ? (process.result?.answer_type === 'portfolio' ? 'No match' : 'Insufficient evidence') : badge.label}
            </span>
          </div>
          <AIProcessSidebar process={process} policyNumber={policyNumber} embedded />
        </div>
      ) : (
        <div className="px-1 pb-1">
          <RecentQuestions
            items={recent}
            error={recentError}
            loading={recentLoading}
            activeConversationId={conversationId}
            disabled={busy}
            onOpen={onOpenConversation}
            onNewConversation={onNewConversation}
            onRefresh={onRefreshRecent}
          />
        </div>
      )}
    </div>
  );
}
