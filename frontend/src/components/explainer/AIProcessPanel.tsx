import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowUpRight, Check, ChevronDown, Circle, FileText, Loader2, Minus, X } from 'lucide-react';
import type { AskedBy, QuestionAnswerResponse } from '../../types';
import type { ProcessState } from '../../lib/explainer';
import { citationLine, distinctSources, sourceKindLabel, sourceTitle } from '../../lib/explainer';
import { buildProcessSteps, formatDuration, type ProcessStep, type StepLine, type StepStatus } from '../../lib/processSteps';
import { askerName, fullWhen, outcomeBadge, roleLabel } from '../../lib/conversations';
import { GuardrailStatusBadge } from './GuardrailSummary';

/** A recorded answer opened from "How this was answered". */
export interface AuditTarget {
  question: string;
  result: QuestionAnswerResponse;
  askedBy?: AskedBy | null;
  askedAt?: string | null;
}

/** What the panel is showing: the question being answered now, or a recorded answer. */
export type PanelContent = { mode: 'live' } | { mode: 'history'; target: AuditTarget };

export const PANEL_WIDTH = 440;
const ANIMATION_MS = 300;

const STATUS: Record<StepStatus, { word: string; icon: ReactNode }> = {
  pending: { word: 'Pending', icon: <Circle className="h-4 w-4 text-slate-300" /> },
  running: {
    word: 'In progress',
    icon: <Loader2 className="h-4 w-4 animate-spin text-orange-btn motion-reduce:animate-none" />,
  },
  done: {
    word: 'Done',
    icon: (
      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-600 text-white">
        <Check className="h-2.5 w-2.5" strokeWidth={3.5} />
      </span>
    ),
  },
  warning: { word: 'Needs attention', icon: <AlertTriangle className="h-4 w-4 text-amber-600" /> },
  failed: { word: 'Failed', icon: <AlertTriangle className="h-4 w-4 text-red-600" /> },
  skipped: {
    word: 'Skipped',
    icon: (
      <span className="flex h-4 w-4 items-center justify-center rounded-full border border-slate-300 text-slate-400">
        <Minus className="h-2.5 w-2.5" strokeWidth={3} />
      </span>
    ),
  },
};

function Line({ line }: { line: StepLine }) {
  switch (line.kind) {
    case 'passage':
      return (
        <li className="flex items-center gap-2 text-[11.5px] text-espresso">
          <span className="min-w-0 flex-1 truncate">
            <span className="font-mono">{line.form}</span>
            {line.page ? <span className="text-muted-foreground"> · p.{line.page}</span> : null}
            {line.matchedBy && line.matchedBy !== 'words' && (
              <span
                className="ml-1.5 rounded border border-[#BFDBFE] bg-[#F0F7FF] px-1 py-px text-[9.5px] font-semibold uppercase tracking-wide text-[#1D4ED8]"
                title={line.matchedBy === 'meaning' ? 'Found by meaning; no words in common with the question' : 'Matched by words and by meaning'}
              >
                {line.matchedBy === 'meaning' ? 'meaning' : 'words + meaning'}
              </span>
            )}
          </span>
          <span className="h-1 w-14 shrink-0 overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
            <span className="block h-full rounded-full bg-orange-btn" style={{ width: `${line.percent}%` }} />
          </span>
          <span className="w-[5.5rem] shrink-0 text-right font-mono text-[11px] text-muted-foreground">
            <span className="sr-only">relevance score </span>
            {line.score.toFixed(1)}
            <span className="sr-only">, evidence confidence</span> · <span className="font-semibold text-espresso">{line.percent}%</span>
          </span>
        </li>
      );
    case 'check':
      return (
        <li className="flex items-start gap-1.5 text-[11.5px] text-espresso">
          {line.ok ? (
            <Check className="mt-0.5 h-3 w-3 shrink-0 text-emerald-600" strokeWidth={3} aria-hidden="true" />
          ) : (
            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-600" aria-hidden="true" />
          )}
          <span>
            <span className="sr-only">{line.ok ? 'Passed: ' : 'Warning: '}</span>
            {line.text}
          </span>
        </li>
      );
    case 'result':
      return (
        <li
          className={`flex items-start gap-1.5 rounded-md px-2 py-1.5 text-[11.5px] font-semibold ${
            line.tone === 'passed'
              ? 'bg-emerald-50 text-emerald-800'
              : line.tone === 'failed'
              ? 'bg-red-50 text-red-700'
              : 'bg-amber-50 text-amber-800'
          }`}
        >
          {line.tone === 'passed' ? (
            <Check className="mt-0.5 h-3 w-3 shrink-0" strokeWidth={3} aria-hidden="true" />
          ) : (
            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
          )}
          <span>{line.text}</span>
        </li>
      );
    case 'warning':
      return (
        <li className="flex items-start gap-1.5 text-[11.5px] font-medium text-amber-800">
          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
          {line.text}
        </li>
      );
    case 'error':
      return (
        <li className="flex items-start gap-1.5 rounded-md bg-red-50 px-2 py-1.5 text-[11.5px] font-medium text-red-700">
          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
          {line.text}
        </li>
      );
    default:
      return (
        <li className="text-[11.5px] leading-snug text-muted-foreground">
          {line.text}
          {line.mono && <span className="break-all font-mono text-espresso">{line.mono}</span>}
        </li>
      );
  }
}

function StepRow({ step }: { step: ProcessStep }) {
  const { icon, word } = STATUS[step.status];
  const muted = step.status === 'pending' || step.status === 'skipped';
  const showMs = (step.status === 'done' || step.status === 'warning') && step.ms !== null && step.ms !== undefined;
  return (
    <li className="flex gap-3" aria-current={step.status === 'running' ? 'step' : undefined}>
      <span className="mt-0.5 shrink-0" aria-hidden="true">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className={`text-[13px] ${muted ? 'text-muted-foreground' : 'font-semibold text-espresso'}`}>
            {step.label}
            <span className="sr-only"> — {word}</span>
          </span>
          {showMs && <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{formatDuration(step.ms)}</span>}
          {step.status === 'failed' && <span className="shrink-0 text-[10.5px] font-bold uppercase text-red-700">Failed</span>}
        </div>
        {step.status !== 'pending' && step.lines.length > 0 && (
          <ul className="mt-1.5 space-y-1">
            {step.lines.map((line, i) => (
              <Line key={i} line={line} />
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-border px-5 py-4">
      <h3 className="mb-2.5 text-[10.5px] font-bold uppercase tracking-[0.12em] text-orange-btn">{title}</h3>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-2 py-1 text-[12.5px]">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-espresso">{children}</dd>
    </div>
  );
}

/** Sources, guardrail result and audit record, shown once an answer is complete. */
function AnswerRecord({ result, askedBy, askedAt }: { result: QuestionAnswerResponse; askedBy?: AskedBy | null; askedAt?: string | null }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const sources = distinctSources(result.citations, result.evidence);
  const policy = result.policy_context
    ? `${result.policy_context.policy_number} · ${result.policy_context.customer_name}`
    : result.answer_type === 'portfolio'
    ? 'Customer / portfolio question (no single policy)'
    : 'Not recorded';
  return (
    <>
      <section className="border-t border-border px-5 py-4">
        <button
          type="button"
          onClick={() => setSourcesOpen((prev) => !prev)}
          aria-expanded={sourcesOpen}
          className="flex w-full items-center justify-between text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn rounded cursor-pointer"
        >
          <h3 className="text-[10.5px] font-bold uppercase tracking-[0.12em] text-orange-btn">
            {`Sources cited (${sources.length})`}
          </h3>
          <ChevronDown
            className={`h-3.5 w-3.5 text-muted-foreground transition-transform duration-200 ${
              sourcesOpen ? 'rotate-180' : ''
            }`}
            aria-hidden="true"
          />
        </button>
        {sourcesOpen && (
          <div className="mt-3">
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
                          <FileText className="h-3 w-3" aria-hidden="true" />
                          {citationLine(evidence) || sourceKindLabel(evidence.source_type)}
                          {evidence.section && <span>· {evidence.section}</span>}
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </section>

      <Section title="Guardrail result">
        <dl>
          <Row label="Status">
            <GuardrailStatusBadge status={result.guardrail_status} />
          </Row>
          <Row label="Citations verified">{result.citations.length}</Row>
          <Row label="Outcome">{outcomeBadge(result.outcome).label}</Row>
        </dl>
      </Section>

      <Section title="Audit record">
        <dl>
          <Row label="Asked by">{askerName(askedBy)}</Row>
          <Row label="Employee ID">
            <span className="font-mono">{askedBy?.employee_id ?? 'Not recorded'}</span>
          </Row>
          <Row label="Role">{roleLabel(askedBy?.role)}</Row>
          <Row label="Timestamp">{fullWhen(askedAt) || 'Not recorded'}</Row>
          <Row label="Policy">
            <span className="font-mono">{policy}</span>
          </Row>
          <Row label="Ledger reference">
            <span className="break-all font-mono text-[11.5px]">{result.ledger_id ?? 'Not recorded'}</span>
          </Row>
        </dl>
        {result.ledger_id && (
          <Link
            to={`/app/audit-log?entry=${encodeURIComponent(result.ledger_id)}`}
            className="mt-3 inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-[12.5px] font-semibold text-espresso transition-colors hover:border-orange-btn hover:text-orange-btn focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn"
          >
            View in the Audit Log <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        )}
      </Section>
    </>
  );
}

function liveTitle(phase: ProcessState['phase']): string {
  switch (phase) {
    case 'running':
      return 'AI process · live';
    case 'completed':
      return 'AI process · complete';
    case 'failed':
      return 'AI process · stopped';
    case 'needs_input':
      return 'AI process · waiting for you';
    default:
      return 'AI process';
  }
}

/** One sentence for screen readers describing where the run is. */
function announcement(steps: ProcessStep[], complete: boolean): string {
  const failed = steps.find((s) => s.status === 'failed');
  if (failed) {
    const error = failed.lines.find((l) => l.kind === 'error');
    return `${failed.label} failed. ${error && 'text' in error ? error.text : ''}`;
  }
  const running = steps.find((s) => s.status === 'running');
  if (running) return `${running.label}: in progress.`;
  if (complete) return 'All steps complete. The answer is ready.';
  return '';
}

/**
 * The AI process panel. Shows the six pipeline steps in detail for the question being answered, or
 * for a recorded answer ("How this was answered", built from stored data only). At desktop width it
 * is a docked column beside the chat, never over it; on narrow screens it slides over the chat.
 * A complementary region rather than a modal: the chat and composer keep working while it is open.
 */
export function AIProcessPanel({
  content,
  process,
  docked,
  autoFocus,
  onClose,
}: {
  /** null closes the panel. */
  content: PanelContent | null;
  process: ProcessState;
  docked: boolean;
  /** Move focus into the panel when it opens (when the employee opened it, not when it opened itself). */
  autoFocus: boolean;
  onClose: () => void;
}) {
  // Keep the last content while the closing animation runs.
  const [rendered, setRendered] = useState<PanelContent | null>(content);
  const [shown, setShown] = useState(false);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const isOpen = content !== null;

  useEffect(() => {
    if (content) {
      setRendered(content);
      const raf = requestAnimationFrame(() => setShown(true));
      return () => cancelAnimationFrame(raf);
    }
    setShown(false);
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const timer = setTimeout(() => setRendered(null), reduce ? 0 : ANIMATION_MS);
    return () => clearTimeout(timer);
  }, [content]);

  // Focus moves once the requested content has rendered, so the Close button exists.
  const focusPendingRef = useRef(false);
  useEffect(() => {
    focusPendingRef.current = Boolean(content && autoFocus);
  }, [content, autoFocus]);
  useEffect(() => {
    if (rendered && rendered === content && focusPendingRef.current) {
      focusPendingRef.current = false;
      closeRef.current?.focus({ preventScroll: true });
    }
  }, [rendered, content]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return;
      // A modal on top (the source viewer) handles its own Escape first.
      if (document.querySelector('[role="dialog"][aria-modal="true"]')) return;
      onCloseRef.current();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [isOpen]);

  if (!rendered) return null;

  const history = rendered.mode === 'history' ? rendered.target : null;
  const result = history ? history.result : process.result;
  const question = history ? history.question : process.question;
  const askedBy = history ? history.askedBy : process.askedBy;
  const askedAt = history ? history.askedAt : process.askedAt;
  const steps = buildProcessSteps({
    result,
    stages: history ? null : process.stages,
    askedBy,
    contextDetail: history ? null : process.contextDetail,
    verification: history ? null : process.verification,
  });
  const complete = Boolean(result);
  const title = history ? 'How this was answered' : liveTitle(process.phase);

  const body = (
    <PanelBody
      title={title}
      question={question}
      steps={steps}
      complete={complete}
      closeRef={closeRef}
      onClose={onClose}
      live={!history}
      record={result ? <AnswerRecord result={result} askedBy={askedBy ?? result.asked_by} askedAt={askedAt ?? result.asked_at} /> : null}
    />
  );

  if (docked) {
    return (
      <aside
        role="complementary"
        aria-labelledby="ai-process-title"
        className="h-full min-h-0 shrink-0 overflow-hidden transition-[width] duration-300 ease-out motion-reduce:transition-none"
        style={{ width: shown ? PANEL_WIDTH : 0 }}
      >
        <div className="flex h-full min-h-0 flex-col overflow-hidden border-l border-[#E2E8F0] bg-white" style={{ width: PANEL_WIDTH }}>
          {body}
        </div>
      </aside>
    );
  }

  return (
    <aside
      role="complementary"
      aria-labelledby="ai-process-title"
      className={`fixed inset-y-0 right-0 z-40 flex h-full max-h-screen w-full max-w-[440px] flex-col overflow-hidden bg-white shadow-[-12px_0_32px_rgba(15,42,67,0.18)] transition-transform duration-300 ease-out motion-reduce:transition-none ${
        shown ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      {body}
    </aside>
  );
}

function PanelBody({
  title,
  question,
  steps,
  complete,
  live,
  record,
  closeRef,
  onClose,
}: {
  title: string;
  question?: string;
  steps: ProcessStep[];
  complete: boolean;
  live: boolean;
  record: ReactNode;
  closeRef: RefObject<HTMLButtonElement>;
  onClose: () => void;
}) {
  return (
    <>
      <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border px-5 pb-3 pt-4">
        <div className="min-w-0">
          <h2 id="ai-process-title" className="flex items-center gap-2 font-display text-lg text-espresso">
            {live && !complete && steps.some((s) => s.status === 'running') && (
              <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-orange-btn motion-reduce:animate-none" aria-hidden="true" />
            )}
            {title}
          </h2>
          {question && <p className="mt-1 line-clamp-2 text-[12.5px] text-muted-foreground">“{question}”</p>}
        </div>
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          aria-label="Close AI process panel"
          className="shrink-0 rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-espresso focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn cursor-pointer"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <div className="px-5 py-4">
          <h3 className="mb-3 text-[10.5px] font-bold uppercase tracking-[0.12em] text-orange-btn">Pipeline steps</h3>
          <ol className="space-y-3.5" aria-label="Pipeline steps">
            {steps.map((step) => (
              <StepRow key={step.key} step={step} />
            ))}
          </ol>
          <p className="sr-only" aria-live="polite">
            {live ? announcement(steps, complete) : ''}
          </p>
        </div>
        {record}
      </div>
    </>
  );
}
