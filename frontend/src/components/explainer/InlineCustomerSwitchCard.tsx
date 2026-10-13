import { useState } from 'react';
import { ArrowRightLeft, MessageSquarePlus, Shield } from 'lucide-react';
import { lineLabel } from '../../lib/explainer';

export interface InlineCustomerSwitchCardProps {
  currentCustomerName: string;
  currentPolicyNumber: string;
  currentLineOfBusiness?: string | null;
  targetCustomerName: string;
  targetPolicyNumber: string;
  targetLineOfBusiness?: string | null;
  onSwitchContext: () => Promise<void> | void;
  onStartNewConversation: () => Promise<void> | void;
  onCancel: () => void;
}

/**
 * Compact inline customer-switch card rendered inside the conversation stream.
 * Replaces the modal to provide a non-blocking, inline context-switch experience
 * while adhering to regulated customer-data isolation guardrails.
 */
export function InlineCustomerSwitchCard({
  currentCustomerName,
  currentPolicyNumber,
  currentLineOfBusiness,
  targetCustomerName,
  targetPolicyNumber,
  targetLineOfBusiness,
  onSwitchContext,
  onStartNewConversation,
  onCancel,
}: InlineCustomerSwitchCardProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleSwitch = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setActionError(null);
    try {
      await onSwitchContext();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to switch context.');
      setIsSubmitting(false);
    }
  };

  const handleStartNew = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setActionError(null);
    try {
      await onStartNewConversation();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to start a new conversation.');
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="region"
      aria-label="Switching customer context"
      className="w-full max-w-xl rounded-2xl border border-[#FDBA74] bg-[#FFFBF7] p-4 shadow-sm"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#FFF7ED] text-[#EA580C] ring-1 ring-[#FDBA74]">
            <ArrowRightLeft className="h-3.5 w-3.5" />
          </span>
          <h3 className="text-[13.5px] font-bold text-[#0F2A43]">
            Switching customer context
          </h3>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full border border-[#FDBA74] bg-[#FFF7ED] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[#EA580C]">
          <Shield className="h-3 w-3" /> Data Guardrail
        </span>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 rounded-xl border border-[#FED7AA] bg-white p-3 text-[12px] sm:grid-cols-2">
        <div className="space-y-0.5 border-b border-slate-100 pb-2 sm:border-b-0 sm:border-r sm:pb-0 sm:pr-2.5">
          <span className="block text-[10px] font-bold uppercase tracking-wider text-[#64748B]">
            Current
          </span>
          <p className="truncate font-semibold text-[#0F2A43]">{currentCustomerName}</p>
          <p className="font-mono text-[11px] text-[#475569]">
            {currentPolicyNumber}
            {currentLineOfBusiness ? ` · ${lineLabel(currentLineOfBusiness)}` : ''}
          </p>
        </div>
        <div className="space-y-0.5 sm:pl-2">
          <span className="block text-[10px] font-bold uppercase tracking-wider text-[#EA580C]">
            Selected
          </span>
          <p className="truncate font-semibold text-[#0F2A43]">{targetCustomerName}</p>
          <p className="font-mono text-[11px] font-medium text-[#C2410C]">
            {targetPolicyNumber}
            {targetLineOfBusiness ? ` · ${lineLabel(targetLineOfBusiness)}` : ''}
          </p>
        </div>
      </div>

      <p className="mt-2 text-[12.5px] text-[#334155]">
        How would you like to continue?
      </p>

      {actionError && (
        <div className="mt-2 rounded-lg border border-red-200 bg-red-50 p-2 text-[11.5px] text-red-700">
          {actionError}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={handleSwitch}
          disabled={isSubmitting}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[#0F2A43] px-3.5 py-1.5 text-[12px] font-semibold text-white shadow-sm transition-colors hover:bg-[#16385A] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0F2A43] disabled:opacity-50 cursor-pointer"
        >
          <ArrowRightLeft className="h-3.5 w-3.5" />
          Switch Context
        </button>

        <button
          type="button"
          onClick={handleStartNew}
          disabled={isSubmitting}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[#EA580C] px-3.5 py-1.5 text-[12px] font-semibold text-white shadow-sm transition-colors hover:bg-[#C2410C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] disabled:opacity-50 cursor-pointer"
        >
          <MessageSquarePlus className="h-3.5 w-3.5" />
          Start New Conversation
        </button>

        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="inline-flex items-center rounded-lg border border-[#CBD5E1] bg-white px-3 py-1.5 text-[12px] font-semibold text-[#475569] transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:opacity-50 cursor-pointer"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
