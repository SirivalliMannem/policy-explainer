import { ListChecks, Loader2, Shield, X } from 'lucide-react';
import type { PolicyContextCandidate } from '../../types';
import type { PolicyFeatureTab } from './PolicyFeaturesPanel';
import { QUICK_ACTIONS } from './QuickPolicyActions';
import { formatDate, lineLabel, statusLabel } from '../../lib/explainer';

interface PolicyContextBannerProps {
  policy: PolicyContextCandidate | null;
  isResolving?: boolean;
  openTab?: PolicyFeatureTab | null;
  onOpenTab: (tab: PolicyFeatureTab) => void;
  onClear: () => void;
  /** The AI process panel toggle; hidden when there is nothing to show yet. */
  processAvailable: boolean;
  processOpen: boolean;
  onToggleProcess: (opener: HTMLElement) => void;
}

const TABS: { tab: PolicyFeatureTab; label: string }[] = [
  { tab: 'overview', label: 'Overview' },
  ...QUICK_ACTIONS.map(({ tab, shortTitle }) => ({ tab, label: shortTitle })),
];

/**
 * The conversation's header bar: which policy the conversation is about (with its details one click
 * away), and the AI process panel toggle. Before a policy is identified it says how to name one.
 */
export function PolicyContextBanner({
  policy,
  isResolving,
  openTab,
  onOpenTab,
  onClear,
  processAvailable,
  processOpen,
  onToggleProcess,
}: PolicyContextBannerProps) {
  const inForce = policy?.status === 'in_force';

  return (
    <div className="flex min-h-[60px] shrink-0 items-center gap-3 border-b border-[#E2E8F0] bg-white px-4 py-2.5 sm:px-6">
      <span
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
          policy ? 'bg-[#0F2A43]' : 'border border-[#E2E8F0] bg-[#F8FAFC]'
        }`}
        aria-hidden="true"
      >
        {isResolving ? (
          <Loader2 className="h-4 w-4 animate-spin text-[#F97316] motion-reduce:animate-none" />
        ) : (
          <Shield className={`h-4 w-4 ${policy ? 'text-[#F97316]' : 'text-[#94A3B8]'}`} />
        )}
      </span>

      {policy ? (
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="truncate text-[14px] font-semibold text-[#0F2A43]">{policy.customer_name}</span>
            <span className="font-mono text-[12.5px] font-semibold text-[#0F2A43]">{policy.policy_number}</span>
            <span className="rounded border border-[#FDBA74] bg-[#FFF7ED] px-1.5 py-px text-[10px] font-semibold uppercase text-[#C2410C]">
              {lineLabel(policy.line_of_business)}
            </span>
            <span className={`inline-flex items-center gap-1 text-[11.5px] font-medium ${inForce ? 'text-emerald-700' : 'text-[#64748B]'}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${inForce ? 'bg-emerald-500' : 'bg-slate-400'}`} aria-hidden="true" />
              {statusLabel(policy.status)}
            </span>
          </div>
          <div className="mt-0.5 flex min-w-0 items-center gap-1 overflow-x-auto text-[11.5px] text-[#64748B]">
            <span className="hidden shrink-0 sm:inline">
              {formatDate(policy.effective_date)} – {formatDate(policy.expiration_date)}
            </span>
            <span className="mx-1 hidden text-[#CBD5E1] sm:inline" aria-hidden="true">
              |
            </span>
            <nav aria-label="Policy details" className="flex shrink-0 items-center gap-0.5">
              {TABS.map(({ tab, label }) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => onOpenTab(tab)}
                  aria-pressed={openTab === tab}
                  className={`rounded-md px-1.5 py-0.5 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer ${
                    openTab === tab ? 'bg-[#0F2A43] text-white' : 'text-[#475569] hover:bg-slate-100 hover:text-[#0F2A43]'
                  }`}
                >
                  {label}
                </button>
              ))}
            </nav>
          </div>
        </div>
      ) : (
        <div className="min-w-0 flex-1">
          <p className="text-[13.5px] font-semibold text-[#0F2A43]">{isResolving ? 'Finding the policy…' : 'No policy selected'}</p>
          <p className="truncate text-[11.5px] text-[#64748B]">Name a policy number or policyholder in your question.</p>
        </div>
      )}

      <div className="flex shrink-0 items-center gap-1">
        {processAvailable && (
          <button
            type="button"
            onClick={(e) => onToggleProcess(e.currentTarget)}
            aria-pressed={processOpen}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer ${
              processOpen
                ? 'border-[#0F2A43] bg-[#0F2A43] text-white'
                : 'border-[#E2E8F0] text-[#0F2A43] hover:border-[#F97316] hover:text-[#EA580C]'
            }`}
          >
            <ListChecks className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="hidden sm:inline">AI process</span>
          </button>
        )}
        {policy && (
          <button
            type="button"
            onClick={onClear}
            title="Clear policy context"
            aria-label="Clear policy context"
            className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}

