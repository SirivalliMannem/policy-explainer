import { AlertTriangle, FileStack, Lock, Receipt, ShieldCheck } from 'lucide-react';
import type { PolicyContextCandidate } from '../../types';
import type { PolicyFeatureTab } from './PolicyFeaturesPanel';

export const QUICK_ACTIONS: {
  tab: Exclude<PolicyFeatureTab, 'overview'>;
  title: string;
  shortTitle: string;
  description: string;
  icon: typeof ShieldCheck;
}[] = [
  {
    tab: 'coverages',
    title: 'Coverage & Limits',
    shortTitle: 'Coverages',
    description: 'Review applicable coverages, limits, and deductibles.',
    icon: ShieldCheck,
  },
  {
    tab: 'forms',
    title: 'Forms & Endorsements',
    shortTitle: 'Forms',
    description: 'Review attached forms and endorsements.',
    icon: FileStack,
  },
  {
    tab: 'claims',
    title: 'Claims',
    shortTitle: 'Claims',
    description: 'Review claims associated with the policy.',
    icon: AlertTriangle,
  },
  {
    tab: 'billing',
    title: 'Billing',
    shortTitle: 'Billing',
    description: 'Review billing and payment information.',
    icon: Receipt,
  },
];

interface QuickPolicyActionsProps {
  policy: PolicyContextCandidate | null;
  onOpen: (tab: PolicyFeatureTab) => void;
}

/** Cards that open the real policy records once a policy context exists. */
export function QuickPolicyActions({ policy, onOpen }: QuickPolicyActionsProps) {
  const enabled = Boolean(policy);
  return (
    <section className="w-full max-w-2xl">
      <div className="mb-2.5 flex items-baseline justify-between gap-3">
        <h3 className="text-[10.5px] font-bold uppercase tracking-[0.14em] text-[#64748B]">Quick policy actions</h3>
        <span className="flex items-center gap-1 text-[11px] text-[#94A3B8]">
          {enabled ? (
            <>
              Opens records for <span className="font-mono font-semibold text-[#0F2A43]">{policy!.policy_number}</span>
            </>
          ) : (
            <>
              <Lock className="h-3 w-3" /> Available once a policy is identified
            </>
          )}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        {QUICK_ACTIONS.map(({ tab, title, description, icon: Icon }) => (
          <button
            key={tab}
            type="button"
            disabled={!enabled}
            onClick={() => onOpen(tab)}
            title={enabled ? undefined : 'Ask a question that names a policyholder or policy number first'}
            className="group flex items-start gap-3 rounded-xl border border-[#E2E8F0] bg-white p-3.5 text-left transition-all enabled:hover:border-[#F97316] enabled:hover:shadow-sm disabled:cursor-not-allowed disabled:bg-[#F8FAFC] cursor-pointer"
          >
            <span
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                enabled ? 'bg-[#0F2A43] text-[#F97316]' : 'bg-slate-100 text-slate-400'
              }`}
            >
              <Icon className="h-4 w-4" />
            </span>
            <span className="min-w-0">
              <span className={`block text-[13px] font-semibold ${enabled ? 'text-[#0F2A43]' : 'text-[#94A3B8]'}`}>{title}</span>
              <span className={`mt-0.5 block text-[11.5px] leading-snug ${enabled ? 'text-[#64748B]' : 'text-[#94A3B8]'}`}>
                {description}
              </span>
            </span>
          </button>
        ))}
      </div>
      {!enabled && (
        <p className="mt-2.5 text-[11.5px] leading-relaxed text-[#94A3B8]">
          Name a policyholder or a policy number in your question and these open that policy's records.
        </p>
      )}
    </section>
  );
}
