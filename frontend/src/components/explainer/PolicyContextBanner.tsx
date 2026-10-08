import { FileText, Loader2, Shield, X } from 'lucide-react';
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
}

/**
 * Lightweight context strip. Before a policy is resolved it only explains that context is
 * resolved from the question; after, it shows just what is needed to read the answers.
 */
export function PolicyContextBanner({ policy, isResolving, openTab, onOpenTab, onClear }: PolicyContextBannerProps) {
  if (!policy) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-[#E2E8F0] bg-white px-4 py-3 shadow-sm">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[#0F2A43]/10 bg-[#0F2A43]/5">
          {isResolving ? <Loader2 className="h-4 w-4 animate-spin text-[#F97316]" /> : <Shield className="h-4 w-4 text-[#F97316]" />}
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10.5px] font-bold uppercase tracking-[0.14em] text-[#64748B]">Policy context</span>
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-[#64748B]">
              {isResolving ? 'Resolving…' : 'Auto-resolving on question'}
            </span>
          </div>
          <p className="mt-0.5 text-[12.5px] text-[#475569]">
            Ask any question directly about coverage, deductibles, forms, exclusions, claims, or billing.
          </p>
        </div>
      </div>
    );
  }

  const inForce = policy.status === 'in_force';

  return (
    <div className="message-in rounded-xl border border-[#E2E8F0] bg-white px-4 py-3 shadow-sm">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#0F2A43]">
            <Shield className="h-4 w-4 text-[#F97316]" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="text-[10.5px] font-bold uppercase tracking-[0.14em] text-[#64748B]">Policy context</span>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-px text-[10.5px] font-semibold ring-1 ${
                  inForce ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-slate-200'
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${inForce ? 'bg-emerald-500' : 'bg-slate-400'}`} />
                {statusLabel(policy.status)}
              </span>
              <span className="rounded border border-[#FDBA74] bg-[#FFF7ED] px-1.5 py-px text-[10.5px] font-semibold uppercase text-[#C2410C]">
                {lineLabel(policy.line_of_business)}
              </span>
            </div>
            <div className="mt-0.5 flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
              <span className="text-[15px] font-bold text-[#0F2A43]">{policy.customer_name}</span>
              <span className="font-mono text-[12.5px] font-semibold text-[#0F2A43]">{policy.policy_number}</span>
              <span className="text-[11.5px] text-[#64748B]">
                {formatDate(policy.effective_date)} – {formatDate(policy.expiration_date)}
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => onOpenTab('overview')}
            className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-[11.5px] font-semibold transition-colors cursor-pointer ${
              openTab === 'overview'
                ? 'border-[#0F2A43] bg-[#0F2A43] text-white'
                : 'border-[#E2E8F0] text-[#0F2A43] hover:border-[#F97316] hover:text-[#EA580C]'
            }`}
          >
            <FileText className="h-3.5 w-3.5" /> Overview
          </button>
          {QUICK_ACTIONS.map(({ tab, shortTitle, icon: Icon }) => (
            <button
              key={tab}
              type="button"
              onClick={() => onOpenTab(tab)}
              className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-[11.5px] font-semibold transition-colors cursor-pointer ${
                openTab === tab
                  ? 'border-[#0F2A43] bg-[#0F2A43] text-white'
                  : 'border-[#E2E8F0] text-[#0F2A43] hover:border-[#F97316] hover:text-[#EA580C]'
              }`}
            >
              <Icon className="h-3.5 w-3.5" /> {shortTitle}
            </button>
          ))}
          <button
            type="button"
            onClick={onClear}
            title="Clear policy context"
            aria-label="Clear policy context"
            className="ml-0.5 rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
