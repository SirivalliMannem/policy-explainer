import React from 'react';
import { Shield, User, Calendar, RefreshCw, ChevronDown, CheckCircle2 } from 'lucide-react';
import { PolicyDetail, PolicyContextCandidate } from '../../types';

interface PolicyContextBannerProps {
  policy: PolicyDetail | PolicyContextCandidate | null;
  onChangePolicyClick: () => void;
  isLoading?: boolean;
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return 'N/A';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

export function PolicyContextBanner({
  policy,
  onChangePolicyClick,
  isLoading,
}: PolicyContextBannerProps) {
  if (!policy) {
    return (
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-3.5 sm:p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[#0F2A43]/5 border border-[#0F2A43]/10 flex items-center justify-center text-[#0F2A43] shrink-0">
            <Shield className="w-5 h-5 text-[#F97316]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
                Policy Context
              </span>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-[#64748B]">
                Auto-Resolving on Question
              </span>
            </div>
            <p className="text-sm text-[#0F2A43] font-medium mt-0.5">
              Ask any question directly or choose a policyholder to inspect.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onChangePolicyClick}
          className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-[#E2E8F0] hover:border-[#F97316] bg-white text-xs font-semibold text-[#0F2A43] hover:text-[#F97316] transition-colors shadow-sm shrink-0 cursor-pointer"
        >
          <User className="w-3.5 h-3.5 text-[#F97316]" />
          Select Policy
          <ChevronDown className="w-3.5 h-3.5 text-[#64748B]" />
        </button>
      </div>
    );
  }

  const isInForce = (policy.status || '').toLowerCase() === 'in_force';

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-xl p-3 sm:p-4 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Left: Customer & Policy ID */}
        <div className="flex items-start sm:items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[#0F2A43] text-white flex items-center justify-center shrink-0 mt-0.5 sm:mt-0 shadow-sm">
            <Shield className="w-5 h-5 text-[#F97316]" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[#64748B]">
                POLICY CONTEXT
              </span>
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                  isInForce
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-slate-100 text-slate-600 border border-slate-200'
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${isInForce ? 'bg-emerald-500' : 'bg-slate-400'}`}
                />
                {isInForce ? 'In Force' : policy.status}
              </span>
              <span className="text-xs font-semibold text-[#F97316] uppercase bg-orange-50 px-2 py-0.5 rounded border border-orange-200">
                {policy.line_of_business === 'homeowners' ? 'Homeowners' : 'Personal Auto'}
              </span>
            </div>

            <div className="flex flex-wrap items-baseline gap-2 mt-0.5">
              <h3 className="text-base sm:text-lg font-bold text-[#0F2A43] tracking-tight">
                {policy.customer_name}
              </h3>
              <span className="font-mono text-xs sm:text-sm font-semibold text-[#0F2A43] bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                {policy.policy_number}
              </span>
              {'product_name' in policy && policy.product_name && (
                <span className="text-xs text-[#64748B] hidden lg:inline">
                  · {policy.product_name}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right: Dates & Change Policy Action */}
        <div className="flex items-center justify-between md:justify-end gap-3 sm:gap-4 border-t md:border-t-0 pt-2 md:pt-0 border-slate-100 text-xs">
          <div className="flex items-center gap-3 text-[#64748B]">
            <div className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-[#64748B]" />
              <span>
                Effective: <strong className="text-[#0F2A43]">{formatDate(policy.effective_date)}</strong>
              </span>
            </div>
            <span className="hidden sm:inline text-slate-300">|</span>
            <div className="hidden sm:flex items-center gap-1.5">
              <span>
                Expires: <strong className="text-[#0F2A43]">{formatDate(policy.expiration_date)}</strong>
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onChangePolicyClick}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#E2E8F0] hover:border-[#F97316] bg-slate-50 hover:bg-orange-50 text-xs font-semibold text-[#0F2A43] hover:text-[#EA580C] transition-all cursor-pointer shadow-xs disabled:opacity-60"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Change Policy</span>
          </button>
        </div>
      </div>
    </div>
  );
}
