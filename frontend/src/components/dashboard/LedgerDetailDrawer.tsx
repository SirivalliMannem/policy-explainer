import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, ExternalLink, Loader2, MessageSquare, X } from 'lucide-react';
import { getLedgerEntry } from '../../services/api';
import type { EvidenceItem, LedgerDetail, SourceTarget } from '../../types';
import { AnswerText, SourceChip } from '../explainer/AnswerText';
import { GuardrailCheckList, GuardrailStatusBadge } from '../explainer/GuardrailSummary';
import { SourceViewer } from '../explainer/SourceViewer';
import {
  citationLine,
  describeError,
  evidenceByIndex,
  formatDate,
  formatDateTime,
  formatMs,
  lineLabel,
  modelLabel,
} from '../../lib/explainer';
import { ConfidenceBadge, OutcomeBadge } from './RecordBadges';

const SCOPE_LABEL: Record<string, string> = {
  customer_form: 'Own form',
  product_wording: 'Product wording',
  policy_record: 'Policy record',
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h4 className="text-[10.5px] font-bold uppercase tracking-[0.14em] text-[#64748B]">{title}</h4>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-[#94A3B8]">{label}</dt>
      <dd className="mt-0.5 text-[12.5px] font-medium text-[#0F2A43]">{children}</dd>
    </div>
  );
}

export function LedgerDetailDrawer({ entryId, onClose }: { entryId: string | null; onClose: () => void }) {
  const navigate = useNavigate();
  const [entry, setEntry] = useState<LedgerDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<SourceTarget | null>(null);

  useEffect(() => {
    if (!entryId) return;
    let active = true;
    setEntry(null);
    setError(null);
    getLedgerEntry(entryId)
      .then((e) => active && setEntry(e))
      .catch((err) => active && setError(describeError(err).message));
    return () => {
      active = false;
    };
  }, [entryId]);

  useEffect(() => {
    if (!entryId) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !source && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [entryId, source, onClose]);

  if (!entryId) return null;

  const openSource = (item: EvidenceItem) =>
    setSource({ sourceType: item.source_type, sourceId: item.source_id, evidence: item });

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-[#0F2A43]/40 backdrop-blur-[1px]" onClick={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Evidence ledger record"
        onClick={(e) => e.stopPropagation()}
        className="drawer-in flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[#E2E8F0] px-5 py-4 sm:px-6">
          <div className="min-w-0">
            <span className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-[#F97316]">The Record · entry</span>
            <h3 className="mt-1 text-[15px] font-bold leading-snug text-[#0F2A43]">{entry?.question ?? 'Loading…'}</h3>
            {entry && <p className="mt-0.5 font-mono text-[10.5px] text-[#94A3B8]">{entry.id}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close record"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5 sm:px-6">
          {!entry && !error && (
            <div className="flex items-center justify-center gap-2 py-20 text-xs text-[#64748B]">
              <Loader2 className="h-4 w-4 animate-spin text-[#F97316]" /> Loading record…
            </div>
          )}
          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              <AlertCircle className="h-4 w-4" /> {error}
            </div>
          )}

          {entry && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <OutcomeBadge outcome={entry.outcome} />
                <ConfidenceBadge confidence={entry.confidence} />
                <GuardrailStatusBadge status={entry.guardrail_status} />
                <span className="ml-auto text-[11px] text-[#64748B]">{formatDateTime(entry.created_at)}</span>
              </div>

              <Section title="Answer">
                <div className="rounded-xl border border-[#E2E8F0] bg-white px-4 py-3">
                  <AnswerText text={entry.answer} evidence={entry.evidence} onOpenSource={openSource} />
                </div>
              </Section>

              <Section title="Resolved policy">
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3 sm:grid-cols-3">
                  <Field label="Insured">{entry.insured ?? '—'}</Field>
                  <Field label="Policy">
                    <span className="font-mono">{entry.policy_number ?? '—'}</span>
                  </Field>
                  <Field label="Policy version">
                    Term {entry.policy_term ?? '—'} · {formatDate(entry.policy_effective)} – {formatDate(entry.policy_expiration)}
                  </Field>
                  <Field label="Line">{lineLabel(entry.line_of_business)}</Field>
                  <Field label="State">{entry.state ?? '—'}</Field>
                  <Field label="Agent">{entry.agent ?? '—'}</Field>
                </dl>
              </Section>

              <Section title={`Sources (${entry.citations.length} verified)`}>
                {entry.citations.length === 0 ? (
                  <p className="text-[12px] text-[#64748B]">No citations were attached to this answer.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {entry.citations.map((c, i) => {
                      const ev = c.evidence_index ? evidenceByIndex(entry.evidence, c.evidence_index) : undefined;
                      return (
                        <li key={i} className="flex flex-wrap items-center gap-2">
                          {ev ? <SourceChip item={ev} onOpen={openSource} size="md" /> : null}
                          <span className="text-[11.5px] text-[#475569]">{citationLine(c)}</span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </Section>

              <Section title={`Retrieved evidence (${entry.evidence.length})`}>
                <ul className="divide-y divide-[#E2E8F0] rounded-xl border border-[#E2E8F0]">
                  {entry.evidence.map((e) => (
                    <li key={e.source_id} className="flex items-start gap-3 px-3 py-2.5">
                      <span className="mt-0.5 w-6 shrink-0 text-right font-mono text-[10.5px] text-[#94A3B8]">
                        E{e.evidence_index ?? '·'}
                      </span>
                      <div className="min-w-0 flex-1">
                        <button
                          type="button"
                          onClick={() => openSource(e)}
                          className="text-left text-[12.5px] font-semibold text-[#0F2A43] hover:text-[#EA580C] cursor-pointer"
                        >
                          {e.title}
                        </button>
                        <p className="mt-0.5 line-clamp-2 text-[11.5px] text-[#64748B]">{e.content}</p>
                      </div>
                      <span className="shrink-0 text-right text-[10.5px] text-[#94A3B8]">
                        {e.scope ? SCOPE_LABEL[e.scope] ?? e.scope : e.source_type}
                        <br />
                        score {e.relevance_score?.toFixed(1)}
                      </span>
                    </li>
                  ))}
                  {entry.evidence.length === 0 && (
                    <li className="px-3 py-3 text-[12px] text-[#64748B]">
                      No evidence matched. Searched {entry.retrieval.clauses_searched ?? 0} clauses,{' '}
                      {entry.retrieval.coverages_searched ?? 0} coverages and {entry.retrieval.forms_searched ?? 0} forms.
                    </li>
                  )}
                </ul>
              </Section>

              <Section title="Guardrail checks">
                <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] p-3">
                  <GuardrailCheckList checks={entry.guardrail_checks} />
                </div>
              </Section>

              <Section title="Model decision">
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-[#E2E8F0] px-4 py-3 sm:grid-cols-3">
                  <Field label="Model">
                    {entry.model_used ? modelLabel({ model_used: entry.model_used, provider: entry.provider || '', is_fallback: Boolean(entry.is_fallback) }) : '—'}
                  </Field>
                  <Field label="End-to-end">{formatMs(entry.latency_ms)}</Field>
                  <Field label="Reviewer">{entry.reviewer ?? 'Not assigned'}</Field>
                  <Field label="Retrieval">{formatMs(entry.timings_ms.retrieval)}</Field>
                  <Field label="Generation">{formatMs(entry.timings_ms.generation)}</Field>
                  <Field label="Validation">{formatMs(entry.timings_ms.validation)}</Field>
                </dl>
                {entry.fallback_reason && (
                  <p className="text-[11.5px] text-[#64748B]">Fallback reason: {entry.fallback_reason}</p>
                )}
              </Section>
            </>
          )}
        </div>

        {entry && (
          <div className="border-t border-[#E2E8F0] px-5 py-3 sm:px-6">
            <button
              type="button"
              onClick={() => navigate('/app/explainer', { state: { conversationId: entry.conversation_id } })}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#0F2A43] px-3.5 py-2 text-[12px] font-semibold text-white hover:bg-[#16385A] cursor-pointer"
            >
              <MessageSquare className="h-3.5 w-3.5" /> Open conversation <ExternalLink className="h-3 w-3" />
            </button>
          </div>
        )}
      </aside>
      <SourceViewer target={source} onClose={() => setSource(null)} />
    </div>
  );
}
