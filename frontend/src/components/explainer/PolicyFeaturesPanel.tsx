import React, { useState, useEffect } from 'react';
import {
  FileText,
  ShieldCheck,
  FileStack,
  AlertTriangle,
  Receipt,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Layers,
  Calendar,
  DollarSign,
  MapPin,
  CheckCircle,
  Clock,
} from 'lucide-react';
import {
  PolicyDetail,
  CoverageItem,
  FormItem,
  ClaimItem,
  BillingItem,
} from '../../types';
import {
  getPolicy,
  getPolicyCoverages,
  getPolicyForms,
  getPolicyClaims,
  getPolicyBilling,
} from '../../services/api';

export type PolicyFeatureTab = 'overview' | 'coverages' | 'forms' | 'claims' | 'billing';

interface PolicyFeaturesPanelProps {
  policyId: string | null;
  activeTab: PolicyFeatureTab;
  onTabChange: (tab: PolicyFeatureTab) => void;
  targetHighlight?: { type: 'coverage' | 'form'; id: string } | null;
  isOpen: boolean;
  onToggleOpen: () => void;
}

function formatCurrency(val?: number | null): string {
  if (val === null || val === undefined) return 'N/A';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(val);
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

export function PolicyFeaturesPanel({
  policyId,
  activeTab,
  onTabChange,
  targetHighlight,
  isOpen,
  onToggleOpen,
}: PolicyFeaturesPanelProps) {
  const [policyDetail, setPolicyDetail] = useState<PolicyDetail | null>(null);
  const [coverages, setCoverages] = useState<CoverageItem[]>([]);
  const [forms, setForms] = useState<FormItem[]>([]);
  const [claims, setClaims] = useState<ClaimItem[]>([]);
  const [billing, setBilling] = useState<BillingItem[]>([]);

  const [isLoadingPolicy, setIsLoadingPolicy] = useState(false);
  const [isLoadingCoverages, setIsLoadingCoverages] = useState(false);
  const [isLoadingForms, setIsLoadingForms] = useState(false);
  const [isLoadingClaims, setIsLoadingClaims] = useState(false);
  const [isLoadingBilling, setIsLoadingBilling] = useState(false);

  // Load policy details & features whenever policyId changes
  useEffect(() => {
    if (!policyId) {
      setPolicyDetail(null);
      setCoverages([]);
      setForms([]);
      setClaims([]);
      setBilling([]);
      return;
    }

    let isMounted = true;

    // Load Policy Overview
    setIsLoadingPolicy(true);
    getPolicy(policyId)
      .then((data) => {
        if (isMounted) setPolicyDetail(data);
      })
      .catch((err) => console.error('Failed to load policy overview:', err))
      .finally(() => {
        if (isMounted) setIsLoadingPolicy(false);
      });

    // Load Coverages
    setIsLoadingCoverages(true);
    getPolicyCoverages(policyId)
      .then((data) => {
        if (isMounted) setCoverages(data);
      })
      .catch((err) => console.error('Failed to load coverages:', err))
      .finally(() => {
        if (isMounted) setIsLoadingCoverages(false);
      });

    // Load Forms
    setIsLoadingForms(true);
    getPolicyForms(policyId)
      .then((data) => {
        if (isMounted) setForms(data);
      })
      .catch((err) => console.error('Failed to load forms:', err))
      .finally(() => {
        if (isMounted) setIsLoadingForms(false);
      });

    // Load Claims
    setIsLoadingClaims(true);
    getPolicyClaims(policyId)
      .then((data) => {
        if (isMounted) setClaims(data);
      })
      .catch((err) => console.error('Failed to load claims:', err))
      .finally(() => {
        if (isMounted) setIsLoadingClaims(false);
      });

    // Load Billing
    setIsLoadingBilling(true);
    getPolicyBilling(policyId)
      .then((data) => {
        if (isMounted) setBilling(data);
      })
      .catch((err) => console.error('Failed to load billing:', err))
      .finally(() => {
        if (isMounted) setIsLoadingBilling(false);
      });

    return () => {
      isMounted = false;
    };
  }, [policyId]);

  if (!policyId) {
    return null;
  }

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-xl shadow-xs overflow-hidden transition-all">
      {/* Segmented Header & Tab Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between border-b border-[#E2E8F0] bg-[#F8FAFC] px-3 sm:px-4 py-2 gap-2">
        <div className="flex items-center justify-between sm:justify-start gap-1 overflow-x-auto scrollbar-none py-1">
          <button
            type="button"
            onClick={() => onTabChange('overview')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
              activeTab === 'overview'
                ? 'bg-[#0F2A43] text-white shadow-xs'
                : 'text-[#64748B] hover:text-[#0F2A43] hover:bg-slate-200/60'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Overview</span>
          </button>

          <button
            type="button"
            onClick={() => onTabChange('coverages')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
              activeTab === 'coverages'
                ? 'bg-[#0F2A43] text-white shadow-xs'
                : 'text-[#64748B] hover:text-[#0F2A43] hover:bg-slate-200/60'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Coverages</span>
            <span
              className={`ml-0.5 px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                activeTab === 'coverages' ? 'bg-[#F97316] text-white' : 'bg-slate-200 text-[#0F2A43]'
              }`}
            >
              {coverages.length}
            </span>
          </button>

          <button
            type="button"
            onClick={() => onTabChange('forms')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
              activeTab === 'forms'
                ? 'bg-[#0F2A43] text-white shadow-xs'
                : 'text-[#64748B] hover:text-[#0F2A43] hover:bg-slate-200/60'
            }`}
          >
            <FileStack className="w-3.5 h-3.5" />
            <span>Forms & Endorsements</span>
            <span
              className={`ml-0.5 px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                activeTab === 'forms' ? 'bg-[#F97316] text-white' : 'bg-slate-200 text-[#0F2A43]'
              }`}
            >
              {forms.length}
            </span>
          </button>

          <button
            type="button"
            onClick={() => onTabChange('claims')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
              activeTab === 'claims'
                ? 'bg-[#0F2A43] text-white shadow-xs'
                : 'text-[#64748B] hover:text-[#0F2A43] hover:bg-slate-200/60'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Claims</span>
            <span
              className={`ml-0.5 px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                activeTab === 'claims' ? 'bg-[#F97316] text-white' : 'bg-slate-200 text-[#0F2A43]'
              }`}
            >
              {claims.length}
            </span>
          </button>

          <button
            type="button"
            onClick={() => onTabChange('billing')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
              activeTab === 'billing'
                ? 'bg-[#0F2A43] text-white shadow-xs'
                : 'text-[#64748B] hover:text-[#0F2A43] hover:bg-slate-200/60'
            }`}
          >
            <Receipt className="w-3.5 h-3.5" />
            <span>Billing</span>
            <span
              className={`ml-0.5 px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                activeTab === 'billing' ? 'bg-[#F97316] text-white' : 'bg-slate-200 text-[#0F2A43]'
              }`}
            >
              {billing.length}
            </span>
          </button>
        </div>

        <button
          type="button"
          onClick={onToggleOpen}
          className="flex items-center justify-center gap-1 text-xs font-semibold text-[#64748B] hover:text-[#0F2A43] py-1 px-2 rounded hover:bg-slate-200/50 transition-colors cursor-pointer shrink-0 self-end sm:self-center"
        >
          <span>{isOpen ? 'Collapse Panel' : 'Expand Panel'}</span>
          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Collapsible Content Area */}
      {isOpen && (
        <div className="p-4 sm:p-5 max-h-[340px] overflow-y-auto bg-white">
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div>
              {isLoadingPolicy ? (
                <div className="py-8 text-center text-xs font-medium text-[#64748B] animate-pulse">
                  Loading policy overview...
                </div>
              ) : policyDetail ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4 text-xs">
                  <div className="bg-[#F8FAFC] p-3 rounded-lg border border-[#E2E8F0]">
                    <span className="text-[#64748B] block font-medium">Policyholder</span>
                    <span className="text-sm font-bold text-[#0F2A43] mt-0.5 block">
                      {policyDetail.customer_name}
                    </span>
                    <span className="text-[11px] text-[#64748B] font-mono mt-0.5 block">
                      {policyDetail.customer_id}
                    </span>
                  </div>

                  <div className="bg-[#F8FAFC] p-3 rounded-lg border border-[#E2E8F0]">
                    <span className="text-[#64748B] block font-medium">Policy Number</span>
                    <span className="text-sm font-bold text-[#0F2A43] font-mono mt-0.5 block">
                      {policyDetail.policy_number}
                    </span>
                    <span className="text-[11px] text-[#64748B] mt-0.5 block">
                      Term #{policyDetail.term_number}
                    </span>
                  </div>

                  <div className="bg-[#F8FAFC] p-3 rounded-lg border border-[#E2E8F0]">
                    <span className="text-[#64748B] block font-medium">Product / Line</span>
                    <span className="text-sm font-bold text-[#0F2A43] mt-0.5 block truncate">
                      {policyDetail.product_name || policyDetail.line_of_business}
                    </span>
                    <span className="text-[11px] text-[#F97316] font-semibold mt-0.5 block capitalize">
                      {policyDetail.line_of_business}
                    </span>
                  </div>

                  <div className="bg-[#F8FAFC] p-3 rounded-lg border border-[#E2E8F0]">
                    <span className="text-[#64748B] block font-medium">Annual Premium</span>
                    <span className="text-sm font-bold text-[#EA580C] mt-0.5 block">
                      {formatCurrency(policyDetail.annual_premium)}
                    </span>
                    <span className="text-[11px] text-[#64748B] mt-0.5 block">Yearly billing total</span>
                  </div>

                  <div className="bg-[#F8FAFC] p-3 rounded-lg border border-[#E2E8F0]">
                    <span className="text-[#64748B] block font-medium">Status</span>
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold mt-1 bg-emerald-50 text-emerald-700 border border-emerald-200">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                      {policyDetail.status === 'in_force' ? 'In Force' : policyDetail.status}
                    </span>
                  </div>

                  <div className="bg-[#F8FAFC] p-3 rounded-lg border border-[#E2E8F0]">
                    <span className="text-[#64748B] block font-medium">Policy Term</span>
                    <span className="text-[11px] font-semibold text-[#0F2A43] mt-0.5 block">
                      {formatDate(policyDetail.effective_date)} — {formatDate(policyDetail.expiration_date)}
                    </span>
                  </div>

                  <div className="bg-[#F8FAFC] p-3 rounded-lg border border-[#E2E8F0] col-span-2">
                    <span className="text-[#64748B] block font-medium">Insured Location</span>
                    <span className="text-xs font-semibold text-[#0F2A43] mt-0.5 block flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-[#F97316] shrink-0" />
                      {policyDetail.insured_location || 'Not specified'}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center text-xs text-[#64748B]">
                  No policy overview available.
                </div>
              )}
            </div>
          )}

          {/* TAB 2: COVERAGES */}
          {activeTab === 'coverages' && (
            <div>
              {isLoadingCoverages ? (
                <div className="py-8 text-center text-xs font-medium text-[#64748B] animate-pulse">
                  Loading coverages...
                </div>
              ) : coverages.length === 0 ? (
                <div className="py-8 text-center text-xs text-[#64748B]">
                  No coverages found for this policy.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {coverages.map((cov) => {
                    const isTarget =
                      targetHighlight?.type === 'coverage' &&
                      (targetHighlight.id.toLowerCase().includes(cov.name.toLowerCase()) ||
                        cov.name.toLowerCase().includes(targetHighlight.id.toLowerCase()));

                    return (
                      <div
                        key={cov.id}
                        id={`coverage-${cov.id}`}
                        className={`p-3 rounded-lg border transition-all text-xs ${
                          isTarget
                            ? 'border-[#F97316] bg-orange-50/50 ring-2 ring-[#F97316]/30'
                            : 'border-[#E2E8F0] bg-[#F8FAFC] hover:border-slate-300'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="font-bold text-[#0F2A43] text-xs leading-snug">
                            {cov.name}
                          </h4>
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-semibold shrink-0 ${
                              cov.included
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : 'bg-slate-100 text-slate-500'
                            }`}
                          >
                            {cov.included ? 'Included' : 'Excluded'}
                          </span>
                        </div>

                        <div className="mt-2 space-y-1 text-[#64748B]">
                          <div className="flex justify-between items-baseline">
                            <span>Limit:</span>
                            <span className="font-bold text-[#0F2A43]">
                              {cov.limit_text || (cov.limit_amount ? formatCurrency(cov.limit_amount) : 'Standard Limit')}
                            </span>
                          </div>

                          {cov.deductible_text || cov.deductible_amount !== null ? (
                            <div className="flex justify-between items-baseline">
                              <span>Deductible:</span>
                              <span className="font-semibold text-[#0F2A43]">
                                {cov.deductible_text || (cov.deductible_amount ? formatCurrency(cov.deductible_amount) : '$0')}
                              </span>
                            </div>
                          ) : null}

                          {cov.governing_form && (
                            <div className="flex justify-between items-baseline pt-1 border-t border-slate-200/60 mt-1">
                              <span>Governing Form:</span>
                              <span className="font-mono text-[11px] font-semibold text-[#F97316]">
                                {cov.governing_form}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: FORMS & ENDORSEMENTS */}
          {activeTab === 'forms' && (
            <div>
              {isLoadingForms ? (
                <div className="py-8 text-center text-xs font-medium text-[#64748B] animate-pulse">
                  Loading forms...
                </div>
              ) : forms.length === 0 ? (
                <div className="py-8 text-center text-xs text-[#64748B]">
                  No forms or endorsements found for this policy.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {forms.map((form) => {
                    const isTarget =
                      targetHighlight?.type === 'form' &&
                      form.form_number.toLowerCase().includes(targetHighlight.id.toLowerCase());

                    return (
                      <div
                        key={form.id}
                        id={`form-${form.form_number.replace(/\s+/g, '-')}`}
                        className={`p-3 rounded-lg border transition-all text-xs flex flex-col justify-between ${
                          isTarget
                            ? 'border-[#F97316] bg-orange-50/50 ring-2 ring-[#F97316]/30'
                            : 'border-[#E2E8F0] bg-[#F8FAFC] hover:border-slate-300'
                        }`}
                      >
                        <div>
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-mono text-xs font-bold text-[#0F2A43] bg-white px-2 py-0.5 rounded border border-[#E2E8F0]">
                              {form.form_number}
                            </span>
                            <span className="text-[11px] font-medium text-[#64748B]">
                              Ed. {form.edition}
                            </span>
                          </div>
                          <h4 className="font-bold text-[#0F2A43] mt-1.5 leading-snug">
                            {form.title}
                          </h4>
                        </div>

                        <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-200/60 text-[11px] text-[#64748B]">
                          <span className="capitalize">{form.kind.replace('_', ' ')}</span>
                          <span>{form.page_count} {form.page_count === 1 ? 'Page' : 'Pages'}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: CLAIMS */}
          {activeTab === 'claims' && (
            <div>
              {isLoadingClaims ? (
                <div className="py-8 text-center text-xs font-medium text-[#64748B] animate-pulse">
                  Loading claims...
                </div>
              ) : claims.length === 0 ? (
                <div className="py-8 text-center text-xs text-[#64748B] bg-slate-50 border border-dashed border-[#E2E8F0] rounded-lg p-6">
                  <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-80" />
                  <p className="font-semibold text-[#0F2A43]">No claims found for this policy.</p>
                  <p className="text-[11px] text-[#64748B] mt-1">
                    No open or past claim records exist for this policy term.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {claims.map((claim) => (
                    <div
                      key={claim.id}
                      className="p-3.5 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-[#0F2A43]">
                          {claim.claim_number}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200 capitalize">
                          {claim.status}
                        </span>
                      </div>
                      <p className="text-[#0F2A43] mt-1 font-medium">{claim.description || claim.loss_cause || 'Claim reported'}</p>
                      <div className="flex items-center gap-4 text-[#64748B] text-[11px] mt-2">
                        <span>Loss Date: {formatDate(claim.loss_date)}</span>
                        {claim.adjuster && <span>Adjuster: {claim.adjuster}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 5: BILLING */}
          {activeTab === 'billing' && (
            <div>
              {isLoadingBilling ? (
                <div className="py-8 text-center text-xs font-medium text-[#64748B] animate-pulse">
                  Loading billing...
                </div>
              ) : billing.length === 0 ? (
                <div className="py-8 text-center text-xs text-[#64748B] bg-slate-50 border border-dashed border-[#E2E8F0] rounded-lg p-6">
                  <p className="font-semibold text-[#0F2A43]">No billing information available.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
                  {billing.map((bill) => (
                    <div
                      key={bill.id}
                      className="p-3.5 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[#64748B]">Account</span>
                        <span className="font-mono font-bold text-[#0F2A43]">
                          {bill.account_number || 'N/A'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-[#64748B]">Payment Plan</span>
                        <span className="font-semibold text-[#0F2A43]">{bill.plan}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-[#64748B]">Payment Status</span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 uppercase">
                          {bill.status}
                        </span>
                      </div>
                      <div className="flex items-center justify-between pt-1 border-t border-slate-200">
                        <span className="text-[#64748B]">Next Due Date</span>
                        <span className="font-semibold text-[#0F2A43]">
                          {formatDate(bill.next_due_date)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-[#64748B]">Next Amount Due</span>
                        <span className="font-bold text-[#EA580C]">
                          {formatCurrency(bill.next_due_amount)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-[#64748B]">Paid to Date</span>
                        <span className="font-medium text-[#0F2A43]">
                          {formatCurrency(bill.paid_to_date)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
