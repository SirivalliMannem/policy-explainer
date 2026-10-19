import React, { useState, useEffect, useRef } from 'react';
import {
  ArrowLeft,
  ChevronRight,
  Loader2,
  Search,
  Shield,
  User,
  Users,
  X,
  AlertCircle,
  Check,
} from 'lucide-react';
import type { CustomerListItem, PolicyListItem } from '../../types';
import { searchCustomers, searchPoliciesList } from '../../services/api';
import { lineLabel, statusLabel } from '../../lib/explainer';

export type ContextSelectorView = 'menu' | 'customers' | 'policies' | 'policy-confirm';

export interface ContextSelectorPopoverProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectCustomer: (customer: CustomerListItem) => void;
  onSelectPolicy: (policy: PolicyListItem) => void;
  disabled?: boolean;
}

export function ContextSelectorPopover({
  isOpen,
  onClose,
  onSelectCustomer,
  onSelectPolicy,
  disabled,
}: ContextSelectorPopoverProps) {
  const [view, setView] = useState<ContextSelectorView>('menu');
  const [menuFocusIndex, setMenuFocusIndex] = useState<0 | 1>(0);

  // Customers state
  const [customerSearch, setCustomerSearch] = useState('');
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [isCustomerLoading, setIsCustomerLoading] = useState(false);
  const [customerError, setCustomerError] = useState<string | null>(null);
  const [focusedCustomerIndex, setFocusedCustomerIndex] = useState<number>(-1);

  // Policies state
  const [policySearch, setPolicySearch] = useState('');
  const [policies, setPolicies] = useState<PolicyListItem[]>([]);
  const [isPolicyLoading, setIsPolicyLoading] = useState(false);
  const [policyError, setPolicyError] = useState<string | null>(null);
  const [focusedPolicyIndex, setFocusedPolicyIndex] = useState<number>(-1);

  // Policy confirmation state
  const [pendingPolicy, setPendingPolicy] = useState<PolicyListItem | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  // Reset view whenever popover opens
  useEffect(() => {
    if (isOpen) {
      setView('menu');
      setMenuFocusIndex(0);
      setCustomerSearch('');
      setCustomers([]);
      setCustomerError(null);
      setFocusedCustomerIndex(-1);
      setPolicySearch('');
      setPolicies([]);
      setPolicyError(null);
      setFocusedPolicyIndex(-1);
      setPendingPolicy(null);
    }
  }, [isOpen]);

  // Handle outside click & global popover keyboard shortcuts
  useEffect(() => {
    if (!isOpen) return;

    const handleMouseDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        if (view === 'policy-confirm') {
          setView('policies');
        } else if (view === 'customers' || view === 'policies') {
          setView('menu');
        } else {
          onClose();
        }
        return;
      }

      if (view === 'menu') {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          setMenuFocusIndex((prev) => (prev === 0 ? 1 : 0));
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          setMenuFocusIndex((prev) => (prev === 1 ? 0 : 1));
        } else if (e.key === 'Enter') {
          e.preventDefault();
          if (menuFocusIndex === 0) {
            setView('customers');
          } else {
            setView('policies');
          }
        }
      } else if (view === 'customers') {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          setFocusedCustomerIndex((prev) =>
            customers.length > 0 ? Math.min(prev + 1, customers.length - 1) : -1
          );
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          setFocusedCustomerIndex((prev) => Math.max(prev - 1, 0));
        } else if (e.key === 'Enter') {
          e.preventDefault();
          const targetIndex = focusedCustomerIndex >= 0 ? focusedCustomerIndex : 0;
          if (customers.length > 0 && customers[targetIndex]) {
            onSelectCustomer(customers[targetIndex]);
            onClose();
          }
        }
      } else if (view === 'policies') {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          setFocusedPolicyIndex((prev) =>
            policies.length > 0 ? Math.min(prev + 1, policies.length - 1) : -1
          );
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          setFocusedPolicyIndex((prev) => Math.max(prev - 1, 0));
        } else if (e.key === 'Enter') {
          e.preventDefault();
          const targetIndex = focusedPolicyIndex >= 0 ? focusedPolicyIndex : 0;
          if (policies.length > 0 && policies[targetIndex]) {
            setPendingPolicy(policies[targetIndex]);
            setView('policy-confirm');
          }
        }
      } else if (view === 'policy-confirm') {
        if (e.key === 'Enter') {
          e.preventDefault();
          if (pendingPolicy) {
            onSelectPolicy(pendingPolicy);
            onClose();
          }
        }
      }
    };

    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, view, menuFocusIndex, customers, focusedCustomerIndex, policies, focusedPolicyIndex, pendingPolicy, onClose, onSelectCustomer, onSelectPolicy]);

  // Focus search input when navigating into sub-views
  useEffect(() => {
    if (view === 'customers' || view === 'policies') {
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
    }
  }, [view]);

  // Fetch customer list (customers names only)
  const fetchCustomers = async (query: string) => {
    setIsCustomerLoading(true);
    setCustomerError(null);
    try {
      const results = await searchCustomers(query.trim() || undefined, 30);
      setCustomers(results);
      setFocusedCustomerIndex(-1);
    } catch {
      setCustomerError('Unable to load customers from database. Please try again.');
    } finally {
      setIsCustomerLoading(false);
    }
  };

  useEffect(() => {
    if (view === 'customers') {
      const timer = setTimeout(() => {
        fetchCustomers(customerSearch);
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [view, customerSearch]);

  // Fetch policy list (policy records only)
  const fetchPolicies = async (query: string) => {
    setIsPolicyLoading(true);
    setPolicyError(null);
    try {
      const results = await searchPoliciesList(query.trim() || undefined, undefined, 30);
      setPolicies(results);
      setFocusedPolicyIndex(-1);
    } catch {
      setPolicyError('Unable to load policies from database. Please try again.');
    } finally {
      setIsPolicyLoading(false);
    }
  };

  useEffect(() => {
    if (view === 'policies') {
      const timer = setTimeout(() => {
        fetchPolicies(policySearch);
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [view, policySearch]);

  if (!isOpen || disabled) return null;

  return (
    <div
      ref={containerRef}
      role="dialog"
      aria-modal="false"
      aria-label="Select context"
      className="absolute bottom-full right-0 z-40 mb-2 w-[340px] sm:w-[380px] overflow-hidden rounded-2xl border border-[#CBD5E1] bg-white p-2.5 shadow-[0_12px_36px_rgba(15,42,67,0.16)] transition-all animate-in fade-in zoom-in-95 duration-150"
    >
      {/* 1. ROOT MENU */}
      {view === 'menu' && (
        <div className="space-y-1.5" role="menu" aria-label="Context options">
          <div className="flex items-center justify-between px-2 py-1">
            <span className="text-[12px] font-semibold uppercase tracking-wider text-[#64748B]">
              Select Context
            </span>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="rounded-lg p-1 text-[#64748B] hover:bg-[#F1F5F9] hover:text-[#0F2A43] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <button
            type="button"
            role="menuitem"
            onClick={() => setView('customers')}
            onMouseEnter={() => setMenuFocusIndex(0)}
            className={`group flex w-full items-center gap-3 rounded-xl p-2.5 text-left transition-colors cursor-pointer ${
              menuFocusIndex === 0 ? 'bg-[#FFF7ED] ring-1 ring-[#EA580C]/40' : 'hover:bg-[#F8FAFC]'
            }`}
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-sky-50 text-sky-700 transition-colors group-hover:bg-sky-100">
              <Users className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <span className="block text-[13.5px] font-semibold text-[#0F2A43]">Customers</span>
              <span className="block text-[11.5px] text-[#64748B]">
                Filter conversations to a customer account
              </span>
            </div>
            <ChevronRight className="h-4 w-4 text-[#94A3B8] transition-transform group-hover:translate-x-0.5" />
          </button>

          <button
            type="button"
            role="menuitem"
            onClick={() => setView('policies')}
            onMouseEnter={() => setMenuFocusIndex(1)}
            className={`group flex w-full items-center gap-3 rounded-xl p-2.5 text-left transition-colors cursor-pointer ${
              menuFocusIndex === 1 ? 'bg-[#FFF7ED] ring-1 ring-[#EA580C]/40' : 'hover:bg-[#F8FAFC]'
            }`}
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-orange-50 text-[#EA580C] transition-colors group-hover:bg-orange-100">
              <Shield className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <span className="block text-[13.5px] font-semibold text-[#0F2A43]">Policies</span>
              <span className="block text-[11.5px] text-[#64748B]">
                Focus on a specific insurance policy and wording
              </span>
            </div>
            <ChevronRight className="h-4 w-4 text-[#94A3B8] transition-transform group-hover:translate-x-0.5" />
          </button>
        </div>
      )}

      {/* 2. CUSTOMERS VIEW (CUSTOMER NAMES ONLY) */}
      {view === 'customers' && (
        <div className="space-y-2">
          <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-2">
            <button
              type="button"
              onClick={() => setView('menu')}
              aria-label="Back to context options"
              className="flex items-center gap-1.5 rounded-lg px-1.5 py-1 text-[12px] font-medium text-[#475569] hover:bg-[#F1F5F9] hover:text-[#0F2A43] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back</span>
            </button>
            <span className="text-[13px] font-semibold text-[#0F2A43]">Customers</span>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="rounded-lg p-1 text-[#64748B] hover:bg-[#F1F5F9] hover:text-[#0F2A43] cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#94A3B8]" />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search customer names…"
              value={customerSearch}
              onChange={(e) => setCustomerSearch(e.target.value)}
              className="w-full rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] py-1.5 pl-8 pr-7 text-[13px] text-[#0F2A43] placeholder-[#94A3B8] transition-colors focus:border-[#EA580C] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#EA580C]"
            />
            {customerSearch && (
              <button
                type="button"
                onClick={() => setCustomerSearch('')}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-[#94A3B8] hover:text-[#0F2A43]"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <div className="max-h-[260px] min-h-[140px] overflow-y-auto space-y-1 pr-0.5" role="listbox" aria-label="Customer list">
            {isCustomerLoading ? (
              <div className="space-y-2 p-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center gap-2.5 animate-pulse">
                    <div className="h-7 w-7 rounded-lg bg-slate-200" />
                    <div className="flex-1 space-y-1">
                      <div className="h-3.5 w-3/4 rounded bg-slate-200" />
                    </div>
                  </div>
                ))}
              </div>
            ) : customerError ? (
              <div className="flex flex-col items-center justify-center p-4 text-center">
                <AlertCircle className="h-5 w-5 text-red-500 mb-1" />
                <p className="text-[12px] text-red-600 mb-2">{customerError}</p>
                <button
                  type="button"
                  onClick={() => fetchCustomers(customerSearch)}
                  className="rounded-lg bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-[#0F2A43] hover:bg-slate-200 cursor-pointer"
                >
                  Retry
                </button>
              </div>
            ) : customers.length === 0 ? (
              <div className="p-6 text-center">
                <User className="mx-auto h-6 w-6 text-[#94A3B8] mb-1.5" />
                <p className="text-[12.5px] font-semibold text-[#0F2A43]">No customers found</p>
                <p className="text-[11.5px] text-[#64748B]">
                  {customerSearch ? `No matches for “${customerSearch}”` : 'No customer records available.'}
                </p>
              </div>
            ) : (
              customers.map((cust, idx) => {
                const isFocused = idx === focusedCustomerIndex;
                return (
                  <button
                    key={cust.id}
                    type="button"
                    role="option"
                    aria-selected={isFocused}
                    onClick={() => {
                      onSelectCustomer(cust);
                      onClose();
                    }}
                    onMouseEnter={() => setFocusedCustomerIndex(idx)}
                    className={`flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition-colors cursor-pointer ${
                      isFocused ? 'bg-[#FFF7ED] ring-1 ring-[#EA580C]/40' : 'hover:bg-[#F8FAFC]'
                    }`}
                  >
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sky-50 text-sky-700">
                      <User className="h-4 w-4" />
                    </div>
                    <span className="truncate text-[13.5px] font-semibold text-[#0F2A43]">
                      {cust.name}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* 3. POLICIES VIEW (POLICY RECORDS) */}
      {view === 'policies' && (
        <div className="space-y-2">
          <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-2">
            <button
              type="button"
              onClick={() => setView('menu')}
              aria-label="Back to context options"
              className="flex items-center gap-1.5 rounded-lg px-1.5 py-1 text-[12px] font-medium text-[#475569] hover:bg-[#F1F5F9] hover:text-[#0F2A43] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back</span>
            </button>
            <span className="text-[13px] font-semibold text-[#0F2A43]">Policies</span>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="rounded-lg p-1 text-[#64748B] hover:bg-[#F1F5F9] hover:text-[#0F2A43] cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#94A3B8]" />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search policies by number, type…"
              value={policySearch}
              onChange={(e) => setPolicySearch(e.target.value)}
              className="w-full rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] py-1.5 pl-8 pr-7 text-[13px] text-[#0F2A43] placeholder-[#94A3B8] transition-colors focus:border-[#EA580C] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#EA580C]"
            />
            {policySearch && (
              <button
                type="button"
                onClick={() => setPolicySearch('')}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-[#94A3B8] hover:text-[#0F2A43]"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <div className="max-h-[260px] min-h-[140px] overflow-y-auto space-y-1 pr-0.5" role="listbox" aria-label="Policy list">
            {isPolicyLoading ? (
              <div className="space-y-2 p-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center gap-2.5 animate-pulse">
                    <div className="h-8 w-8 rounded-lg bg-slate-200" />
                    <div className="flex-1 space-y-1">
                      <div className="h-3.5 w-3/4 rounded bg-slate-200" />
                      <div className="h-2.5 w-1/2 rounded bg-slate-100" />
                    </div>
                  </div>
                ))}
              </div>
            ) : policyError ? (
              <div className="flex flex-col items-center justify-center p-4 text-center">
                <AlertCircle className="h-5 w-5 text-red-500 mb-1" />
                <p className="text-[12px] text-red-600 mb-2">{policyError}</p>
                <button
                  type="button"
                  onClick={() => fetchPolicies(policySearch)}
                  className="rounded-lg bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-[#0F2A43] hover:bg-slate-200 cursor-pointer"
                >
                  Retry
                </button>
              </div>
            ) : policies.length === 0 ? (
              <div className="p-6 text-center">
                <Shield className="mx-auto h-6 w-6 text-[#94A3B8] mb-1.5" />
                <p className="text-[12.5px] font-semibold text-[#0F2A43]">No policies found</p>
                <p className="text-[11.5px] text-[#64748B]">
                  {policySearch ? `No matches for “${policySearch}”` : 'No policy records available.'}
                </p>
              </div>
            ) : (
              policies.map((pol, idx) => {
                const inForce = pol.status === 'in_force';
                const isFocused = idx === focusedPolicyIndex;
                return (
                  <button
                    key={pol.id}
                    type="button"
                    role="option"
                    aria-selected={isFocused}
                    onClick={() => {
                      setPendingPolicy(pol);
                      setView('policy-confirm');
                    }}
                    onMouseEnter={() => setFocusedPolicyIndex(idx)}
                    className={`flex w-full items-center justify-between gap-2 rounded-xl p-2.5 text-left transition-colors cursor-pointer ${
                      isFocused ? 'bg-[#FFF7ED] ring-1 ring-[#EA580C]/40' : 'hover:bg-[#F8FAFC]'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[13.5px] font-bold text-[#0F2A43]">
                          {pol.policy_number}
                        </span>
                        <span className="rounded border border-[#FDBA74] bg-[#FFF7ED] px-1.5 py-px text-[9.5px] font-semibold uppercase text-[#C2410C]">
                          {lineLabel(pol.line_of_business)}
                        </span>
                      </div>
                    </div>
                    <span
                      className={`shrink-0 inline-flex items-center gap-1 text-[10.5px] font-medium ${
                        inForce ? 'text-emerald-700' : 'text-[#64748B]'
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          inForce ? 'bg-emerald-500' : 'bg-slate-400'
                        }`}
                        aria-hidden="true"
                      />
                      {statusLabel(pol.status)}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* 4. POLICY CONFIRMATION STEP (CONFIRM POLICY & CUSTOMER) */}
      {view === 'policy-confirm' && pendingPolicy && (
        <div className="space-y-3 p-1">
          <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-2">
            <button
              type="button"
              onClick={() => setView('policies')}
              aria-label="Back to policy list"
              className="flex items-center gap-1.5 rounded-lg px-1.5 py-1 text-[12px] font-medium text-[#475569] hover:bg-[#F1F5F9] hover:text-[#0F2A43] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back</span>
            </button>
            <span className="text-[13px] font-semibold text-[#0F2A43]">Confirm Context</span>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="rounded-lg p-1 text-[#64748B] hover:bg-[#F1F5F9] hover:text-[#0F2A43] cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="rounded-xl border border-[#FED7AA] bg-[#FFF7ED]/70 p-3 space-y-2.5">
            <div className="flex items-start justify-between gap-2">
              <div>
                <span className="block font-mono text-[14px] font-bold text-[#0F2A43]">
                  {pendingPolicy.policy_number}
                </span>
                <span className="mt-0.5 inline-block rounded border border-[#FDBA74] bg-[#FFF7ED] px-1.5 py-px text-[10px] font-semibold uppercase text-[#C2410C]">
                  {lineLabel(pendingPolicy.line_of_business)}
                </span>
              </div>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${
                  pendingPolicy.status === 'in_force'
                    ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
                    : 'bg-slate-100 text-slate-600 ring-1 ring-slate-200'
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    pendingPolicy.status === 'in_force' ? 'bg-emerald-500' : 'bg-slate-400'
                  }`}
                  aria-hidden="true"
                />
                {statusLabel(pendingPolicy.status)}
              </span>
            </div>

            <div className="border-t border-[#FDBA74]/40 pt-2.5">
              <span className="block text-[10.5px] font-semibold uppercase tracking-wider text-[#64748B]">
                Associated Customer
              </span>
              <div className="mt-1 flex items-center gap-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-sky-100 text-sky-800">
                  <User className="h-3.5 w-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-semibold text-[#0F2A43]">
                    {pendingPolicy.customer_name}
                  </span>
                </div>
                <span className="shrink-0 text-[10.5px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-1.5 py-0.5">
                  Verified
                </span>
              </div>
            </div>
          </div>

          <p className="text-[11.5px] text-[#64748B] px-1">
            Setting context activates both policy <strong>{pendingPolicy.policy_number}</strong> and customer <strong>{pendingPolicy.customer_name}</strong>.
          </p>

          <div className="flex items-center gap-2 pt-1">
            <button
              type="button"
              onClick={() => {
                onSelectPolicy(pendingPolicy);
                onClose();
              }}
              className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-[#EA580C] px-3.5 py-2 text-[13px] font-semibold text-white shadow-xs transition-colors hover:bg-[#C2410C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
            >
              <Check className="h-4 w-4" />
              <span>Select Context</span>
            </button>
            <button
              type="button"
              onClick={() => setView('policies')}
              className="rounded-xl border border-[#CBD5E1] bg-white px-3 py-2 text-[13px] font-medium text-[#475569] transition-colors hover:bg-slate-50 hover:text-[#0F2A43] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
            >
              Back
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
