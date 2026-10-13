import { useState } from 'react';
import { AlertTriangle, ArrowRightLeft, MessageSquarePlus, Shield, X } from 'lucide-react';
import { lineLabel } from '../../lib/explainer';

export interface CustomerSwitchModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentCustomerName: string;
  currentPolicyNumber: string;
  currentLineOfBusiness?: string | null;
  targetCustomerName: string;
  targetPolicyNumber: string;
  targetLineOfBusiness?: string | null;
  onStartNewConversation: () => Promise<void> | void;
  onSwitchExistingConversation: () => Promise<void> | void;
}

/**
 * Regulated customer switch confirmation modal.
 * Prevents accidental cross-customer data leakage by requiring explicit confirmation
 * when selecting a policy belonging to a different customer.
 */
export function CustomerSwitchModal({
  isOpen,
  onClose,
  currentCustomerName,
  currentPolicyNumber,
  currentLineOfBusiness,
  targetCustomerName,
  targetPolicyNumber,
  targetLineOfBusiness,
  onStartNewConversation,
  onSwitchExistingConversation,
}: CustomerSwitchModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  if (!isOpen) return null;

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

  const handleSwitchExisting = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setActionError(null);
    try {
      await onSwitchExistingConversation();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to switch customer context.');
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="customer-switch-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-[#0F2A43]/50 backdrop-blur-sm transition-opacity"
        onClick={() => !isSubmitting && onClose()}
        aria-hidden="true"
      />

      {/* Modal Dialog Content */}
      <div className="relative z-50 w-full max-w-lg rounded-2xl border border-[#CBD5E1] bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#FFF7ED] text-[#EA580C] ring-1 ring-[#FDBA74]">
              <AlertTriangle className="h-5 w-5" />
            </span>
            <div>
              <h2 id="customer-switch-title" className="text-[17px] font-bold text-[#0F2A43]">
                You're switching to a different customer
              </h2>
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-[#EA580C]">
                <Shield className="h-3 w-3" /> Data Isolation Guardrail
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Cancel customer switch"
            className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50 cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-4 space-y-3.5 text-[13.5px] leading-relaxed text-[#334155]">
          <p>
            You're currently discussing a policy belonging to{' '}
            <strong className="text-[#0F2A43]">{currentCustomerName}</strong>. The selected policy belongs to{' '}
            <strong className="text-[#0F2A43]">{targetCustomerName}</strong>.
          </p>

          {/* Context Comparison Cards */}
          <div className="grid grid-cols-2 gap-2.5 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] p-3 text-[12px]">
            <div className="space-y-1 border-r border-[#E2E8F0] pr-2.5">
              <span className="block text-[10.5px] font-bold uppercase tracking-wider text-[#64748B]">
                Current Context
              </span>
              <p className="truncate font-semibold text-[#0F2A43]">{currentCustomerName}</p>
              <p className="font-mono text-[11px] text-[#475569]">{currentPolicyNumber}</p>
              {currentLineOfBusiness && (
                <span className="inline-block rounded border border-[#CBD5E1] bg-white px-1.5 py-0.5 text-[10px] font-medium text-[#475569]">
                  {lineLabel(currentLineOfBusiness)}
                </span>
              )}
            </div>
            <div className="space-y-1 pl-1">
              <span className="block text-[10.5px] font-bold uppercase tracking-wider text-[#EA580C]">
                Selected Context
              </span>
              <p className="truncate font-semibold text-[#0F2A43]">{targetCustomerName}</p>
              <p className="font-mono text-[11px] text-[#475569]">{targetPolicyNumber}</p>
              {targetLineOfBusiness && (
                <span className="inline-block rounded border border-[#FDBA74] bg-[#FFF7ED] px-1.5 py-0.5 text-[10px] font-medium text-[#C2410C]">
                  {lineLabel(targetLineOfBusiness)}
                </span>
              )}
            </div>
          </div>

          <p className="text-[#475569]">
            Would you like to start a new conversation or switch the existing conversation to the selected customer?
          </p>

          <p className="rounded-lg bg-[#F1F5F9] px-3 py-2 text-[11.5px] text-[#64748B]">
            <strong>Compliance Note:</strong> Starting a new conversation preserves complete customer-data isolation and
            prevents retrieved policy evidence from mixing across accounts.
          </p>

          {actionError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-2.5 text-[12px] text-red-700">
              {actionError}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="inline-flex items-center justify-center rounded-xl border border-[#CBD5E1] bg-white px-4 py-2.5 text-[13px] font-semibold text-[#475569] transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] disabled:opacity-50 cursor-pointer"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleSwitchExisting}
            disabled={isSubmitting}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-[#0F2A43] bg-white px-4 py-2.5 text-[13px] font-semibold text-[#0F2A43] transition-colors hover:bg-[#F8FAFC] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0F2A43] disabled:opacity-50 cursor-pointer"
          >
            <ArrowRightLeft className="h-4 w-4" />
            Switch Context
          </button>

          <button
            type="button"
            onClick={handleStartNew}
            disabled={isSubmitting}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-[#EA580C] px-4 py-2.5 text-[13px] font-semibold text-white shadow-sm transition-colors hover:bg-[#C2410C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] focus-visible:ring-offset-2 disabled:opacity-50 cursor-pointer"
          >
            <MessageSquarePlus className="h-4 w-4" />
            Start New Conversation
          </button>
        </div>
      </div>
    </div>
  );
}
