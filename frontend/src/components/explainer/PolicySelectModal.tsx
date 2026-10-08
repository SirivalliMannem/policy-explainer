import React, { useState, useEffect } from 'react';
import { Search, X, Shield, User, Check, AlertCircle } from 'lucide-react';
import { PolicyContextCandidate } from '../../types';
import { searchPolicyContext } from '../../services/api';

interface PolicySelectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectPolicy: (policy: PolicyContextCandidate) => void;
  currentPolicyId?: string | null;
}

export function PolicySelectModal({
  isOpen,
  onClose,
  onSelectPolicy,
  currentPolicyId,
}: PolicySelectModalProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [results, setResults] = useState<PolicyContextCandidate[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Search when modal opens or searchTerm changes
  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    // Initial search for Margaret or common terms if empty
    const query = searchTerm.trim() || 'Chen';
    searchPolicyContext(query)
      .then((data) => {
        if (isMounted) setResults(data);
      })
      .catch((err) => {
        if (isMounted) setError('Unable to load policy list. Please check network.');
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, searchTerm]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-lg bg-white rounded-2xl border border-[#E2E8F0] shadow-xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F8FAFC]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#0F2A43] text-white flex items-center justify-center">
              <Shield className="w-4 h-4 text-[#F97316]" />
            </div>
            <div>
              <h3 className="font-bold text-[#0F2A43] text-sm leading-tight">
                Select Active Policy
              </h3>
              <p className="text-xs text-[#64748B]">
                Choose an enterprise carrier policyholder context
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search Input */}
        <div className="p-4 border-b border-slate-100">
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by customer name (e.g. Margaret Chen), policy number, or line..."
              className="w-full pl-10 pr-4 py-2.5 text-xs rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] focus:bg-white text-[#0F2A43] placeholder-[#64748B] focus:border-[#F97316] focus:ring-2 focus:ring-[#F97316]/20 focus:outline-none transition-all"
              autoFocus
            />
          </div>
        </div>

        {/* Results List */}
        <div className="p-4 overflow-y-auto flex-1 space-y-2">
          {isLoading ? (
            <div className="py-12 text-center text-xs text-[#64748B] animate-pulse">
              Searching policies...
            </div>
          ) : error ? (
            <div className="py-8 text-center text-xs text-red-600 flex flex-col items-center gap-1">
              <AlertCircle className="w-5 h-5 text-red-500" />
              <span>{error}</span>
            </div>
          ) : results.length === 0 ? (
            <div className="py-12 text-center text-xs text-[#64748B]">
              No policies matched your search.
            </div>
          ) : (
            results.map((policy) => {
              const isSelected = currentPolicyId === policy.policy_id;
              const isInForce = (policy.status || '').toLowerCase() === 'in_force';

              return (
                <button
                  key={policy.policy_id}
                  type="button"
                  onClick={() => {
                    onSelectPolicy(policy);
                    onClose();
                  }}
                  className={`w-full text-left p-3.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                    isSelected
                      ? 'border-[#F97316] bg-orange-50/60 ring-2 ring-[#F97316]/30'
                      : 'border-[#E2E8F0] hover:border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-[#0F2A43] text-sm truncate">
                        {policy.customer_name}
                      </span>
                      <span
                        className={`px-2 py-0.2 rounded-full text-[10px] font-bold ${
                          isInForce
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-slate-100 text-slate-500 border border-slate-200'
                        }`}
                      >
                        {isInForce ? 'In Force' : policy.status}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-xs">
                      <span className="font-mono font-semibold text-[#0F2A43]">
                        {policy.policy_number}
                      </span>
                      <span className="text-slate-300">·</span>
                      <span className="text-[#F97316] font-medium capitalize">
                        {policy.line_of_business}
                      </span>
                    </div>
                  </div>

                  {isSelected && (
                    <div className="w-6 h-6 rounded-full bg-[#EA580C] text-white flex items-center justify-center shrink-0">
                      <Check className="w-4 h-4" />
                    </div>
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
