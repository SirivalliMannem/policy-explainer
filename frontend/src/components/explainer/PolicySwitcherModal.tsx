import { useEffect, useState } from 'react';
import { ArrowRight, Loader2, Search, Shield, X } from 'lucide-react';
import type { PolicyContextCandidate } from '../../types';
import { searchPolicyContext } from '../../services/api';
import { formatDate, lineLabel, statusLabel } from '../../lib/explainer';

export interface PolicySwitcherModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentPolicy: PolicyContextCandidate | null;
  onSelectPolicy: (policy: PolicyContextCandidate) => void;
}

export function PolicySwitcherModal({
  isOpen,
  onClose,
  currentPolicy,
  onSelectPolicy,
}: PolicySwitcherModalProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [results, setResults] = useState<PolicyContextCandidate[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If current policy exists, search for the customer's other policies by default on open
  useEffect(() => {
    if (!isOpen) {
      setSearchTerm('');
      setResults([]);
      setError(null);
      return;
    }

    if (currentPolicy?.customer_name) {
      setSearchTerm(currentPolicy.customer_name);
      setIsLoading(true);
      searchPolicyContext(currentPolicy.customer_name)
        .then((res) => setResults(res))
        .catch(() => setError('Failed to load customer policies'))
        .finally(() => setIsLoading(false));
    }
  }, [isOpen, currentPolicy]);

  const handleSearch = async (query: string) => {
    setSearchTerm(query);
    if (!query.trim()) {
      setResults([]);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const candidates = await searchPolicyContext(query.trim());
      setResults(candidates);
    } catch {
      setError('Could not search policies. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="policy-switcher-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-[#0F2A43]/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Dialog Content */}
      <div className="relative z-50 flex max-h-[85vh] w-full max-w-xl flex-col rounded-2xl border border-[#CBD5E1] bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-[#E2E8F0] px-5 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#0F2A43] text-white">
              <Shield className="h-4 w-4 text-[#F97316]" />
            </span>
            <div>
              <h2 id="policy-switcher-title" className="text-[16px] font-bold text-[#0F2A43]">
                Switch Policy or Customer
              </h2>
              <p className="text-[11.5px] text-[#64748B]">
                Select another policy for the current customer, or switch to a new customer
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Search input */}
        <div className="p-4 border-b border-[#E2E8F0] bg-[#F8FAFC]">
          <div className="flex items-center gap-2 rounded-xl border border-[#CBD5E1] bg-white px-3 py-2 focus-within:border-[#F97316] focus-within:ring-2 focus-within:ring-[#F97316]/20">
            <Search className="h-4 w-4 text-[#94A3B8]" />
            <input
              type="search"
              value={searchTerm}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="Search by policy number (e.g. HO-9021-4477) or customer name…"
              className="flex-1 bg-transparent text-[13px] text-[#0F2A43] placeholder-[#94A3B8] outline-none"
              autoFocus
            />
            {isLoading && <Loader2 className="h-4 w-4 animate-spin text-[#F97316]" />}
          </div>
        </div>

        {/* Results List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {error && <p className="text-[12.5px] text-red-600">{error}</p>}

          {!isLoading && results.length === 0 && searchTerm.trim() && (
            <p className="py-6 text-center text-[13px] text-[#64748B]">
              No policies found matching &ldquo;{searchTerm}&rdquo;.
            </p>
          )}

          {!isLoading && results.length === 0 && !searchTerm.trim() && (
            <p className="py-6 text-center text-[13px] text-[#64748B]">
              Type a policy number or customer name above to view policies.
            </p>
          )}

          {results.map((candidate) => {
            const isCurrent = currentPolicy?.policy_id === candidate.policy_id;
            const isSameCustomer = currentPolicy?.customer_id === candidate.customer_id;

            return (
              <button
                key={candidate.policy_id}
                type="button"
                onClick={() => {
                  onSelectPolicy(candidate);
                  onClose();
                }}
                disabled={isCurrent}
                className={`group flex w-full items-center justify-between rounded-xl border p-3.5 text-left transition-all cursor-pointer ${
                  isCurrent
                    ? 'border-[#CBD5E1] bg-[#F1F5F9] opacity-60 cursor-not-allowed'
                    : 'border-[#E2E8F0] bg-white hover:border-[#F97316] hover:bg-[#FFF7ED]/30'
                }`}
              >
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[13px] font-bold text-[#0F2A43]">
                      {candidate.policy_number}
                    </span>
                    <span className="rounded border border-[#FDBA74] bg-[#FFF7ED] px-1.5 py-px text-[10px] font-semibold uppercase text-[#C2410C]">
                      {lineLabel(candidate.line_of_business)}
                    </span>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-[#475569]">
                      {statusLabel(candidate.status)}
                    </span>
                    {isCurrent && (
                      <span className="rounded-full bg-[#0F2A43] px-2 py-0.5 text-[10px] font-semibold text-white">
                        Active Policy
                      </span>
                    )}
                    {!isCurrent && isSameCustomer && currentPolicy && (
                      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-emerald-200">
                        Same Customer
                      </span>
                    )}
                    {!isCurrent && !isSameCustomer && currentPolicy && (
                      <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 ring-1 ring-amber-200">
                        Different Customer
                      </span>
                    )}
                  </div>
                  <p className="text-[13px] font-medium text-[#1E293B]">{candidate.customer_name}</p>
                  <p className="text-[11px] text-[#64748B]">
                    {candidate.product_name} · Effective {formatDate(candidate.effective_date)}
                  </p>
                </div>
                {!isCurrent && (
                  <ArrowRight className="h-4 w-4 shrink-0 text-slate-300 transition-colors group-hover:text-[#EA580C]" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
