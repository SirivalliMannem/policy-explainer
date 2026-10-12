import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, FileText, ShieldCheck, X } from 'lucide-react';
import type { AskedBy, QuestionAnswerResponse } from '../../types';
import {
  citationLine,
  distinctSources,
  formatMs,
  interpretedText,
  modelLabel,
  sourceKindLabel,
  sourceTitle,
  stagesFromResult,
} from '../../lib/explainer';
import { askerName, fullWhen, roleLabel } from '../../lib/conversations';
import { GuardrailCheckList, GuardrailStatusBadge } from './GuardrailSummary';
import { StepTracker } from './StepTracker';

export interface AuditTarget {
  question: string;
  result: QuestionAnswerResponse;
  askedBy?: AskedBy | null;
  askedAt?: string | null;
}

const FOCUSABLE = 'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])';

function contextDetail(result: QuestionAnswerResponse): string {
  const understood = interpretedText(result.interpretation);
  const base = result.policy_context
    ? `${result.policy_context.customer_name} · ${result.policy_context.policy_number}`
    : 'Customer question — answered from policy records';
  return understood ? `${base} · understood as “${understood}”` : base;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border px-5 py-4">
      <h3 className="mb-2.5 text-[10.5px] font-bold uppercase tracking-[0.12em] text-orange-btn">{title}</h3>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-2 py-1 text-[12.5px]">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-espresso">{children}</dd>
    </div>
  );
}

/**
 * "How this was answered": the recorded pipeline, sources, guardrails and audit record for one
 * answer. Everything shown is read from the stored answer; nothing is re-run.
 */
export function AnswerAuditPanel({ target, onClose }: { target: AuditTarget | null; onClose: () => void }) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const [entered, setEntered] = useState(false);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!target) return;
    returnFocusRef.current = document.activeElement as HTMLElement | null;
    const raf = requestAnimationFrame(() => setEntered(true));
    closeRef.current?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onCloseRef.current();
        return;
      }
      if (e.key !== 'Tab' || !panelRef.current) return;
      const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('keydown', onKey);
      setEntered(false);
      returnFocusRef.current?.focus();
    };
  }, [target]);

  if (!target) return null;
  const { result, askedBy, askedAt } = target;
  const stages = stagesFromResult(result, contextDetail(result));
  if (result.interpretation?.latency_ms !== undefined) stages.context = { ...stages.context, ms: result.interpretation.latency_ms };
  const sources = distinctSources(result.citations, result.evidence);
  const policy = result.policy_context
    ? `${result.policy_context.policy_number} · ${result.policy_context.customer_name}`
    : result.answer_type === 'portfolio'
    ? 'Customer / portfolio question (no single policy)'
    : '—';

  return (
    <div className="fixed inset-0 z-50" role="presentation">
      <div
        className={`absolute inset-0 bg-navy/30 transition-opacity duration-200 motion-reduce:transition-none ${
          entered ? 'opacity-100' : 'opacity-0'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="audit-panel-title"
        className={`absolute inset-y-0 right-0 flex w-full flex-col bg-white shadow-[-12px_0_32px_rgba(15,42,67,0.18)] transition-transform duration-200 ease-out motion-reduce:transition-none sm:w-[410px] ${
          entered ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-start justify-between gap-3 px-5 pb-3 pt-5">
          <div className="min-w-0">
            <h2 id="audit-panel-title" className="font-display text-xl text-espresso">
              How this was answered
            </h2>
            <p className="mt-1 line-clamp-2 text-[12.5px] text-muted-foreground">“{target.question}”</p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-espresso focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <Section title="Pipeline steps">
            <StepTracker stages={stages} label="Pipeline steps with recorded timings" />
            <p className="mt-3 flex justify-between text-[11.5px] text-muted-foreground">
              <span>{modelLabel(result)}</span>
              <span>
                Total <span className="font-mono">{formatMs(result.latency_ms)}</span>
              </span>
            </p>
          </Section>

          <Section title={`Cited sources (${sources.length})`}>
            {sources.length === 0 ? (
              <p className="text-[12.5px] text-muted-foreground">This answer cites no sources.</p>
            ) : (
              <ol className="space-y-3">
                {sources.map(({ key, evidence }, i) => (
                  <li key={key} className="rounded-lg border border-border bg-[#F8FAFC] p-3">
                    <div className="flex items-start gap-2">
                      <span className="mt-px inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-orange-btn px-1.5 text-[10.5px] font-bold text-white">
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <div className="text-[12.5px] font-semibold text-espresso">{sourceTitle(evidence)}</div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-1 font-mono text-[11px] text-muted-foreground">
                          <FileText className="h-3 w-3" />
                          {citationLine(evidence) || sourceKindLabel(evidence.source_type)}
                          {evidence.section && <span>· {evidence.section}</span>}
                        </div>
                      </div>
                    </div>
                    {evidence.content && (
                      <blockquote className="mt-2 border-l-2 border-[#FDBA74] pl-2.5 font-serif text-[12.5px] leading-relaxed text-espresso">
                        {evidence.content.length > 420 ? `${evidence.content.slice(0, 420)}…` : evidence.content}
                      </blockquote>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </Section>

          <Section title="Guardrails">
            <div className="mb-2.5 flex items-center gap-2 text-[12.5px] text-espresso">
              <ShieldCheck className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              Result <GuardrailStatusBadge status={result.guardrail_status} />
            </div>
            <GuardrailCheckList checks={result.guardrail_checks} />
          </Section>

          <Section title="Audit record">
            <dl>
              <Row label="Asked by">{askerName(askedBy)}</Row>
              <Row label="Employee ID">
                <span className="font-mono">{askedBy?.employee_id ?? '—'}</span>
              </Row>
              <Row label="Role">{roleLabel(askedBy?.role)}</Row>
              <Row label="Asked at">{fullWhen(askedAt) || '—'}</Row>
              <Row label="Policy">
                <span className="font-mono">{policy}</span>
              </Row>
              <Row label="Ledger ref">
                <span className="break-all font-mono text-[11.5px]">{result.ledger_id ?? 'Not recorded'}</span>
              </Row>
            </dl>
            {result.ledger_id && (
              <Link
                to={`/app/dashboard?entry=${encodeURIComponent(result.ledger_id)}`}
                className="mt-3 inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-[12.5px] font-semibold text-espresso transition-colors hover:border-orange-btn hover:text-orange-btn focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn"
              >
                View in The Record <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}
