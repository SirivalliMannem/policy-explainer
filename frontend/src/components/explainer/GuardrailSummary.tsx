import { useState } from 'react';
import { AlertTriangle, Check, ChevronDown, ChevronUp, X } from 'lucide-react';
import type { GuardrailCheck } from '../../types';
import { checkLabel } from '../../lib/explainer';

function CheckIcon({ status }: { status: string }) {
  if (status === 'passed') {
    return (
      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 ring-1 ring-emerald-200">
        <Check className="h-2.5 w-2.5" strokeWidth={3} />
      </span>
    );
  }
  if (status === 'warning') {
    return (
      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-600 ring-1 ring-amber-200">
        <AlertTriangle className="h-2.5 w-2.5" strokeWidth={2.5} />
      </span>
    );
  }
  return (
    <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-red-50 text-red-600 ring-1 ring-red-200">
      <X className="h-2.5 w-2.5" strokeWidth={3} />
    </span>
  );
}

export function GuardrailStatusBadge({ status }: { status: string }) {
  const passed = status === 'passed';
  const noEvidence = status === 'no_evidence' || status === 'not_applicable';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold ${
        passed
          ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
          : noEvidence
          ? 'bg-slate-100 text-slate-600 ring-1 ring-slate-200'
          : 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
      }`}
    >
      {passed ? <Check className="h-3 w-3" strokeWidth={3} /> : <AlertTriangle className="h-3 w-3" />}
      {passed
        ? 'Passed'
        : status === 'not_applicable'
        ? 'Not applicable'
        : noEvidence
        ? 'No evidence'
        : status === 'flagged'
        ? 'Flagged'
        : 'Failed'}
    </span>
  );
}

/** The individual checks the AI service actually ran on the answer, exactly as recorded. */
export function GuardrailCheckList({ checks }: { checks: GuardrailCheck[] }) {
  if (!checks.length) {
    return <p className="text-[11px] text-[#64748B]">No guardrail checks were recorded for this answer.</p>;
  }
  return (
    <ul className="space-y-1.5">
      {checks.map((c) => (
        <li key={c.name} className="flex items-start gap-2">
          <span className="mt-px">
            <CheckIcon status={c.status} />
          </span>
          <div className="min-w-0">
            <span className="block font-mono text-[11px] font-semibold text-[#0F2A43]">{checkLabel(c.name)}</span>
            {c.detail && <span className="block text-[11px] leading-snug text-[#64748B]">{c.detail}</span>}
          </div>
        </li>
      ))}
    </ul>
  );
}

export function GuardrailSummary({
  status,
  checks,
  defaultOpen = false,
}: {
  status: string;
  checks: GuardrailCheck[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-2 text-left cursor-pointer"
        aria-expanded={open}
      >
        <span className="text-[10.5px] font-semibold uppercase tracking-wider text-[#64748B]">Guardrails</span>
        <span className="flex items-center gap-1.5">
          <GuardrailStatusBadge status={status} />
          {checks.length > 0 && (
            <span className="text-[10.5px] text-[#64748B]">{checks.length} checks</span>
          )}
          {open ? <ChevronUp className="h-3.5 w-3.5 text-[#64748B]" /> : <ChevronDown className="h-3.5 w-3.5 text-[#64748B]" />}
        </span>
      </button>
      {open && (
        <div className="mt-2.5 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
          <GuardrailCheckList checks={checks} />
        </div>
      )}
    </div>
  );
}
