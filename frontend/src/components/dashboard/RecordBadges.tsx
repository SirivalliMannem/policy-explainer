import { outcomeLabel } from '../../lib/explainer';

export function OutcomeBadge({ outcome }: { outcome: string }) {
  const style =
    outcome === 'answered'
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
      : outcome === 'needs_review'
      ? 'bg-amber-50 text-amber-700 ring-amber-200'
      : 'bg-slate-100 text-slate-600 ring-slate-200';
  return (
    <span className={`inline-flex whitespace-nowrap rounded-md px-2 py-0.5 text-[10.5px] font-semibold ring-1 ${style}`}>
      {outcomeLabel(outcome)}
    </span>
  );
}

export function ConfidenceBadge({ confidence }: { confidence: string }) {
  const style =
    confidence === 'high'
      ? 'text-emerald-700'
      : confidence === 'medium'
      ? 'text-amber-700'
      : 'text-[#64748B]';
  return (
    <span className={`whitespace-nowrap text-[10.5px] font-bold uppercase tracking-wider ${style}`}>{confidence}</span>
  );
}
