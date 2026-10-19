import { Loader2, Shield, User, X } from 'lucide-react';
import type { CustomerContextSummary, PolicyContextCandidate } from '../../types';
import type { PolicyFeatureTab } from './PolicyFeaturesPanel';
import { QUICK_ACTIONS } from './QuickPolicyActions';
import { formatDate, lineLabel, statusLabel } from '../../lib/explainer';

interface PolicyContextBannerProps {
  policy: PolicyContextCandidate | null;
  customer?: CustomerContextSummary | null;
  isResolving?: boolean;
  openTab?: PolicyFeatureTab | null;
  onOpenTab: (tab: PolicyFeatureTab) => void;
  onClear?: () => void;
  onOpenSwitcher?: () => void;
  processAvailable?: boolean;
  processOpen?: boolean;
  onToggleProcess?: (opener: HTMLElement) => void;
}

const TABS: { tab: PolicyFeatureTab; label: string }[] = [
  { tab: 'overview', label: 'Overview' },
  ...QUICK_ACTIONS.map(({ tab, shortTitle }) => ({ tab, label: shortTitle })),
];

/**
 * The conversation's header bar: displays active customer and policy details
 * (policy number, line of business, status, term dates) and navigation tabs.
 */
export function PolicyContextBanner({
  policy,
  customer,
  isResolving,
  openTab,
  onOpenTab,
  onClear,
}: PolicyContextBannerProps) {
  const inForce = policy?.status === 'in_force';

  return (
    <div
      className={`flex min-h-[60px] shrink-0 items-center gap-3 border-b border-[#E2E8F0] ${
        policy || customer ? 'bg-white' : 'bg-[#F8FAFC]'
      } px-4 py-2.5 sm:px-6`}
    >
      <span
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
          policy
            ? 'bg-[#0F2A43]'
            : customer
            ? 'bg-sky-50 border border-sky-200 shadow-xs'
            : 'border border-[#E2E8F0] bg-white shadow-xs'
        }`}
        aria-hidden="true"
      >
        {isResolving ? (
          <Loader2 className="h-4 w-4 animate-spin text-[#F97316] motion-reduce:animate-none" />
        ) : policy ? (
          <Shield className="h-4 w-4 text-[#F97316]" />
        ) : customer ? (
          <User className="h-4 w-4 text-sky-700" />
        ) : (
          <Shield className="h-4 w-4 text-[#64748B]" />
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
      ) : customer ? (
        <div className="flex min-w-0 flex-1 items-center justify-between gap-2" role="group" aria-label="Conversation customer">
          <div className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5">
              <span className="truncate text-[14px] font-semibold text-[#0F2A43]">{customer.customer_name}</span>
              {customer.account_number && (
                <span className="font-mono text-[12px] font-semibold text-[#64748B]">{customer.account_number}</span>
              )}
              <span className="rounded border border-sky-200 bg-sky-50 px-1.5 py-px text-[10px] font-semibold uppercase text-sky-700">
                Customer Context
              </span>
              {typeof customer.policy_count === 'number' && (
                <span className="text-[11.5px] text-[#64748B]">
                  ({customer.policy_count} {customer.policy_count === 1 ? 'policy' : 'policies'})
                </span>
              )}
            </div>
            <p className="mt-0.5 truncate text-[11.5px] text-[#64748B]">
              Customer selected — questions will answer from this customer’s policies or portfolio records.
            </p>
          </div>
          {onClear && (
            <button
              type="button"
              onClick={onClear}
              aria-label="Clear customer context"
              title="Clear context"
              className="rounded-lg p-1.5 text-[#64748B] hover:bg-slate-100 hover:text-[#0F2A43] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      ) : (
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold text-[#0F2A43]">
            {isResolving ? 'Finding policy context…' : 'Conversation context'}
          </p>
          <p className="truncate text-[12px] text-[#64748B]">
            {isResolving
              ? 'Resolving policy from your question…'
              : 'No context selected — click @ in chat to select a Customer or Policy, or ask a question.'}
          </p>
        </div>
      )}
    </div>
  );
}


