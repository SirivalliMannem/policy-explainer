import { useEffect, useRef } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  ChevronRight,
  Compass,
  Database,
  Wand2,
  ExternalLink,
  FileSearch,
  FileText,
  Link2,
  Shield,
  ShieldCheck,
  User,
  Info,
  ListChecks,
  Loader2,
} from 'lucide-react';
import type { AskedBy, EvidenceItem, PolicyContextCandidate, QuestionAnswerResponse } from '../../types';
import type { ProcessState } from '../../lib/explainer';
import { askerName, fullWhen } from '../../lib/conversations';
import { answerConfidence, confidenceExplanation, isRecordAnswer } from '../../lib/confidence';
import type { AuditTarget } from './AIProcessPanel';
import { AnswerText } from './AnswerText';
import { CompanyGuidanceBox } from './CompanyGuidanceBox';
import type { PolicyFeatureTab } from './PolicyFeaturesPanel';
import {
  checkLabel,
  distinctSources,
  evidenceByIndex,
  evidenceChipLabel,
  formatDate,
  interpretationMethodLabel,
  interpretedText,
  lineLabel,
  modelLabel,
  sourceKindLabel,
  sourceTitle,
  statusLabel,
} from '../../lib/explainer';

export type ChatMessage =
  | { kind: 'user'; id: string; time: string; text: string; askedBy?: AskedBy | null; askedAt?: string | null }
  | {
      kind: 'context';
      id: string;
      time: string;
      policy: PolicyContextCandidate;
      matchedOn?: string | null;
      switched: boolean;
      switchType?: 'same_customer_different_policy' | 'different_customer' | 'initial_selection' | string;
      answering?: string;
    }
  | {
      kind: 'clarify';
      id: string;
      time: string;
      text: string;
      candidates: PolicyContextCandidate[];
      /** Heading over the candidates, e.g. "Your recent policies". */
      candidatesLabel?: string;
    }
  /** A conversational reply (greeting, thanks, help, off-topic) with example questions to continue. */
  | { kind: 'assistant'; id: string; time: string; text: string; suggestions: string[] }
  | {
      kind: 'answer';
      id: string;
      time: string;
      question: string;
      result: QuestionAnswerResponse;
      /** One of several answers to the same question, one per matching policy: label it with its policy. */
      labelled?: boolean;
    }
  | { kind: 'error'; id: string; time: string; title: string; text: string };

import { InlineCustomerSwitchCard } from './InlineCustomerSwitchCard';

export interface PendingCustomerSwitch {
  currentPolicy: PolicyContextCandidate;
  targetPolicy: PolicyContextCandidate;
  pendingQuestion?: string | null;
  matchedOn?: string | null;
}

interface ConversationStreamProps {
  messages: ChatMessage[];
  isWorking: boolean;
  /** Live pipeline state; its steps are shown in the AI process panel. */
  process: ProcessState;
  onShowAudit: (target: AuditTarget, opener: HTMLElement) => void;
  /** Reopen the AI process panel for the question being answered. */
  onShowProcess: (opener: HTMLElement) => void;
  /** Put a starter question in the composer (empty conversation). */
  onPrefill: (text: string) => void;
  /** First name for the greeting on an empty conversation. */
  firstName?: string | null;
  activePolicy: PolicyContextCandidate | null;
  onAsk: (question: string) => void;
  onChooseCandidate: (candidate: PolicyContextCandidate) => void;
  onOpenSource: (item: EvidenceItem) => void;
  onOpenTab: (tab: PolicyFeatureTab, highlight?: { type: 'coverage' | 'form'; id: string }) => void;
  pendingSwitch?: PendingCustomerSwitch | null;
  onConfirmSwitchContext?: () => Promise<void> | void;
  onConfirmStartNew?: () => Promise<void> | void;
  onCancelSwitch?: () => void;
}

const MATCH_LABEL: Record<string, string> = {
  policy_number: 'matched on policy number',
  customer_name: 'matched on policyholder name',
  surname: 'matched on surname',
  first_name: 'matched on first name',
  claim_number: 'matched on claim number',
  account_number: 'matched on account number',
  email: 'matched on email address',
  phone: 'matched on phone number',
  vin: 'matched on VIN',
  plate: 'matched on license plate',
  address: 'matched on address',
  vehicle: 'matched on vehicle',
  loss_date: 'term in force on the date of loss',
};

/** "Interpreted as …" — shown only when the understood wording differs from what was typed. */
function InterpretedAs({ result }: { result: QuestionAnswerResponse }) {
  const interpretation = result.interpretation;
  const understood = interpretedText(interpretation);
  if (!interpretation || !understood) return null;
  const details = [
    interpretation.corrections.length
      ? `Corrected: ${interpretation.corrections.map((c) => `${c.from} → ${c.to}`).join(', ')}`
      : '',
    interpretation.search_terms.length ? `Searched for: ${interpretation.search_terms.join(', ')}` : '',
  ]
    .filter(Boolean)
    .join('\n');
  return (
    <div
      className="mb-2.5 flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5 rounded-lg bg-[#F8FAFC] px-2.5 py-1.5 text-[11.5px] text-[#64748B]"
      title={details || undefined}
    >
      <Wand2 className="h-3 w-3 shrink-0 self-center text-[#F97316]" />
      <span>Interpreted as</span>
      <span className="font-medium text-[#0F2A43]">“{understood}”</span>
      <span className="text-[10.5px] text-[#94A3B8]">· {interpretationMethodLabel(interpretation)}</span>
    </div>
  );
}

/** Starter prompts for an empty conversation; the employee completes them with a policy. */
const STARTERS = [
  { label: 'Coverages, limits and deductibles', prompt: 'What are the coverages, limits and deductibles on policy ', icon: ShieldCheck },
  { label: 'Forms and endorsements', prompt: 'Which forms and endorsements are attached to policy ', icon: FileText },
  { label: 'Claims on a policy', prompt: 'What claims are on policy ', icon: AlertTriangle },
  { label: "A customer's policies", prompt: 'How many policies does ', icon: User },
];

function timeGreeting(now = new Date()): string {
  const hour = now.getHours();
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

/** Example questions under an assistant message; choosing one asks it. */
function SuggestionChips({ suggestions, onAsk, disabled }: { suggestions: string[]; onAsk: (q: string) => void; disabled: boolean }) {
  if (!suggestions.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {suggestions.map((q) => (
        <button
          key={q}
          type="button"
          onClick={() => onAsk(q)}
          disabled={disabled}
          className="inline-flex items-center gap-1 rounded-full border border-[#E2E8F0] bg-white px-3 py-1.5 text-left text-[12px] font-medium text-[#0F2A43] transition-colors hover:border-[#F97316] hover:text-[#C2410C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] disabled:opacity-50 cursor-pointer"
        >
          {q}
          <ChevronRight className="h-3 w-3 shrink-0 text-[#F97316]" aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}

/** "· 83%": the share of confidence criteria the answer meets (see lib/confidence). */
function confidenceSuffix(result: QuestionAnswerResponse): string {
  const confidence = answerConfidence(result);
  return confidence ? ` · ${confidence.percent}%` : '';
}

function confidenceTitle(result: QuestionAnswerResponse): string | undefined {
  const confidence = answerConfidence(result);
  if (!confidence) return undefined;
  const source = isRecordAnswer(result) ? 'Read straight from the policy records. ' : '';
  return source + confidenceExplanation(confidence);
}

function AssistantAvatar() {
  return (
    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#0F2A43] shadow-sm">
      <Shield className="h-4 w-4 text-[#F97316]" />
    </span>
  );
}

/** Under every answer: guardrail result, sources cited, and the way into the audit panel. */
function AuditFooter({
  question,
  result,
  onShowAudit,
}: {
  question: string;
  result: QuestionAnswerResponse;
  onShowAudit: ConversationStreamProps['onShowAudit'];
}) {
  const cited = distinctSources(result.citations, result.evidence).length;
  const status = result.guardrail_status;
  const guardrail =
    status === 'passed'
      ? { text: 'Guardrails passed', className: 'text-emerald-700', icon: <ShieldCheck className="h-3.5 w-3.5" /> }
      : status === 'not_applicable'
      ? { text: 'Guardrails not applicable', className: 'text-[#64748B]', icon: <Shield className="h-3.5 w-3.5" /> }
      : status === 'no_evidence'
      ? { text: 'No evidence to check', className: 'text-[#64748B]', icon: <Shield className="h-3.5 w-3.5" /> }
      : { text: 'Guardrails flagged', className: 'text-amber-700', icon: <AlertTriangle className="h-3.5 w-3.5" /> };
  return (
    <div className="mt-3.5 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-slate-100 pt-3 text-[11.5px]">
      <span className={`inline-flex items-center gap-1 font-semibold ${guardrail.className}`}>
        {guardrail.icon}
        {guardrail.text}
      </span>
      <span className="inline-flex items-center gap-1 text-[#64748B]">
        <FileText className="h-3.5 w-3.5" />
        {cited === 1 ? '1 source cited' : `${cited} sources cited`}
      </span>
      <button
        type="button"
        onClick={(e) => onShowAudit({ question, result, askedBy: result.asked_by, askedAt: result.asked_at }, e.currentTarget)}
        className="ml-auto inline-flex items-center gap-1 rounded-md border border-[#E2E8F0] px-2.5 py-1 font-semibold text-[#0F2A43] transition-colors hover:border-[#F97316] hover:text-[#EA580C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
      >
        <Info className="h-3.5 w-3.5" /> How this was answered
      </button>
    </div>
  );
}

function AnswerCard({
  question,
  result,
  time,
  labelled,
  onAsk,
  onOpenSource,
  onOpenTab,
  onShowAudit,
}: {
  question: string;
  labelled?: boolean;
  onShowAudit: ConversationStreamProps['onShowAudit'];
  result: QuestionAnswerResponse;
  time: string;
  onAsk: (q: string) => void;
  onOpenSource: (item: EvidenceItem) => void;
  onOpenTab: ConversationStreamProps['onOpenTab'];
}) {
  const insufficient = result.status === 'insufficient_evidence';
  const sources = distinctSources(result.citations, result.evidence);
  const citedCoverage = result.citations
    .map((c) => (c.evidence_index ? evidenceByIndex(result.evidence, c.evidence_index) : undefined))
    .find((e) => e?.source_type === 'coverage');
  const failedChecks = result.guardrail_checks.filter((c) => c.status === 'failed');
  const r = result.retrieval || {};

  return (
    <div className="message-in flex items-start gap-3">
      <AssistantAvatar />
      <div className="min-w-0 max-w-[46rem] flex-1 rounded-2xl rounded-tl-md border border-[#E2E8F0] bg-white px-4 py-3.5 shadow-sm sm:px-5">
        {labelled && result.policy_context && (
          <div className="-mx-4 -mt-3.5 mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-t-2xl rounded-tl-md border-b border-[#FDBA74] bg-[#FFF7ED] px-4 py-2 sm:-mx-5 sm:px-5">
            <span className="text-[10.5px] font-bold uppercase tracking-[0.12em] text-[#9A3D09]">Answer for</span>
            <span className="font-mono text-[12.5px] font-bold text-[#0F2A43]">{result.policy_context.policy_number}</span>
            <span className="rounded border border-[#FDBA74] bg-white px-1.5 py-px text-[10px] font-semibold uppercase text-[#C2410C]">
              {lineLabel(result.policy_context.line_of_business)}
            </span>
            <span className="text-[12px] text-[#475569]">{result.policy_context.customer_name}</span>
          </div>
        )}
        <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-[11px]">
            <span className="font-bold text-[#0F2A43]">Policy Explainer</span>
            <span className="text-slate-300">·</span>
            <span className="text-[#64748B]">{time}</span>
            {result.policy_context && (
              <>
                <span className="text-slate-300">·</span>
                <span className="font-mono text-[#64748B]">{result.policy_context.policy_number}</span>
              </>
            )}
          </div>
          {!insufficient && (
            <span
              title={confidenceTitle(result)}
              className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wider ring-1 ${
                result.confidence === 'high'
                  ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                  : result.confidence === 'medium'
                  ? 'bg-amber-50 text-amber-700 ring-amber-200'
                  : 'bg-slate-100 text-slate-600 ring-slate-200'
              }`}
            >
              <ShieldCheck className="h-3 w-3" /> Confidence: {result.confidence}
              {confidenceSuffix(result)}
            </span>
          )}
        </div>

        <InterpretedAs result={result} />

        {result.outcome === 'needs_review' && (
          <div className="mb-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800">
            <AlertTriangle className="mt-px h-4 w-4 shrink-0" />
            <span>
              Flagged for review — {failedChecks.map((c) => checkLabel(c.name)).join(', ') || 'guardrail check failed'}. Do not
              rely on this answer until a specialist has reviewed it.
            </span>
          </div>
        )}

        {insufficient ? (
          <div className="space-y-2.5">
            <div className="flex items-start gap-2.5">
              <FileSearch className="mt-0.5 h-4 w-4 shrink-0 text-[#F97316]" />
              <p className="text-[13.5px] font-medium leading-relaxed text-[#0F2A43]">
                I couldn't find sufficient policy evidence to answer this question confidently.
              </p>
            </div>
            <div className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-2.5 text-[12px] leading-relaxed text-[#475569]">
              <p>
                Searched {r.clauses_searched ?? 0} policy clauses, {r.coverages_searched ?? 0} schedule coverages and{' '}
                {r.forms_searched ?? 0} attached forms on{' '}
                <span className="font-mono font-semibold text-[#0F2A43]">{result.policy_context?.policy_number}</span>. None
                matched {r.query_terms?.length ? 'the terms ' : 'the question'}
                {r.query_terms?.map((t, i) => (
                  <span key={t}>
                    {i > 0 && ', '}
                    <span className="font-mono text-[#0F2A43]">{t}</span>
                  </span>
                ))}
                .
              </p>
              <p className="mt-1.5 text-[#64748B]">
                This policy's forms and declarations do not address it. Rephrase using policy terms (coverage, peril, form
                name), or refer the question to an underwriter.
              </p>
            </div>
          </div>
        ) : (
          <AnswerText text={result.answer} evidence={result.evidence} onOpenSource={onOpenSource} />
        )}

        {!insufficient && sources.length > 0 && (
          <div className="mt-3.5 border-t border-slate-100 pt-3">
            <span className="mb-1.5 block text-[10.5px] font-bold uppercase tracking-[0.14em] text-[#64748B]">
              {sources.length === 1 ? 'Source' : `Sources (${sources.length})`}
            </span>
            <ul className="space-y-1">
              {sources.map(({ key, evidence }) => (
                <li key={key}>
                  <button
                    type="button"
                    onClick={() => onOpenSource(evidence)}
                    title="Open this source"
                    className="group flex w-full items-center gap-2.5 rounded-lg border border-transparent px-1.5 py-1 text-left transition-colors hover:border-[#FDBA74] hover:bg-[#FFF7ED] cursor-pointer"
                  >
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-md border border-[#FDBA74] bg-[#FFF7ED] px-1.5 py-px font-mono text-[10.5px] font-semibold text-[#C2410C] group-hover:bg-[#F97316] group-hover:text-white">
                      <FileText className="h-2.5 w-2.5" />
                      {evidenceChipLabel(evidence)}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[12px] font-medium text-[#0F2A43]">
                      {sourceTitle(evidence)}
                    </span>
                    <span className="shrink-0 text-[10.5px] text-[#94A3B8]">
                      {sourceKindLabel(evidence.source_type)}
                      {evidence.edition ? ` · Ed. ${evidence.edition}` : ''}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {citedCoverage && (
                <button
                  type="button"
                  onClick={() =>
                    onOpenTab('coverages', {
                      type: 'coverage',
                      id: (citedCoverage.title || '').replace(/^Coverage:\s*/, ''),
                    })
                  }
                  className="inline-flex items-center gap-1 rounded-md border border-[#E2E8F0] px-2.5 py-1 text-[11.5px] font-semibold text-[#0F2A43] transition-colors hover:border-[#F97316] hover:text-[#EA580C] cursor-pointer"
                >
                  View coverage <ExternalLink className="h-3 w-3" />
                </button>
              )}
              <span className="ml-auto text-[10.5px] text-[#94A3B8]" title={result.fallback_reason || undefined}>
                {modelLabel(result)}
              </span>
            </div>
          </div>
        )}

        {!insufficient && <CompanyGuidanceBox guidance={r.company_guidance} />}

        {result.is_fallback && (
          <p className="mt-2.5 rounded-md bg-slate-50 px-2.5 py-1.5 text-[11px] text-[#64748B]">
            The language model was not used for this answer
            {result.fallback_reason ? ` (${result.fallback_reason})` : ''}; it was composed by the deterministic grounded engine
            from approved policy wording.
          </p>
        )}

        {result.suggested_questions.length > 0 && (
          <div className="mt-3.5 border-t border-slate-100 pt-3">
            <span className="mb-2 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-[0.14em] text-[#64748B]">
              <Compass className="h-3.5 w-3.5 text-[#F97316]" /> Explore this policy
            </span>
            <div className="flex flex-wrap gap-1.5">
              {result.suggested_questions.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => onAsk(q)}
                  className="inline-flex items-center gap-1 rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-1 text-[12px] text-[#0F2A43] transition-colors hover:border-[#F97316] hover:bg-[#FFF7ED] hover:text-[#C2410C] cursor-pointer"
                >
                  {q}
                  <ChevronRight className="h-3 w-3 text-[#F97316]" />
                </button>
              ))}
            </div>
          </div>
        )}

        <AuditFooter question={question} result={result} onShowAudit={onShowAudit} />
      </div>
    </div>
  );
}

function PortfolioCard({
  question,
  result,
  time,
  activePolicyId,
  isWorking,
  onAsk,
  onChooseCandidate,
  onOpenSource,
  onShowAudit,
}: {
  question: string;
  onShowAudit: ConversationStreamProps['onShowAudit'];
  result: QuestionAnswerResponse;
  time: string;
  activePolicyId?: string | null;
  isWorking: boolean;
  onAsk: (q: string) => void;
  onChooseCandidate: (candidate: PolicyContextCandidate) => void;
  onOpenSource: (item: EvidenceItem) => void;
}) {
  const portfolio = result.portfolio;
  const policies = portfolio?.policies ?? [];

  return (
    <div className="message-in flex items-start gap-3">
      <AssistantAvatar />
      <div className="min-w-0 max-w-[46rem] flex-1 rounded-2xl rounded-tl-md border border-[#E2E8F0] bg-white px-4 py-3.5 shadow-sm sm:px-5">
        <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-[11px]">
            <span className="font-bold text-[#0F2A43]">Policy Explainer</span>
            <span className="text-slate-300">·</span>
            <span className="text-[#64748B]">{time}</span>
          </div>
          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wider text-[#475569] ring-1 ring-slate-200">
            <Database className="h-3 w-3" /> From policy records
          </span>
        </div>

        <InterpretedAs result={result} />
        <p className="text-[13.5px] leading-relaxed text-[#1E293B]">{result.answer}</p>

        {policies.length > 0 && (
          <ul className="mt-3 divide-y divide-[#F1F5F9] overflow-hidden rounded-xl border border-[#E2E8F0]">
            {policies.map((p) => {
              const isActive = p.policy_id === activePolicyId;
              const evidence = result.evidence.find((e) => e.source_id === p.policy_id);
              return (
                <li key={p.policy_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[12.5px] font-bold text-[#0F2A43]">{p.policy_number}</span>
                      <span className="rounded border border-[#FDBA74] bg-[#FFF7ED] px-1.5 py-px text-[10px] font-semibold uppercase text-[#C2410C]">
                        {lineLabel(p.line_of_business)}
                      </span>
                      <span
                        className={`rounded-full px-2 py-px text-[10px] font-semibold ring-1 ${
                          p.status === 'in_force' ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-slate-200'
                        }`}
                      >
                        {statusLabel(p.status)}
                      </span>
                    </div>
                    <span className="mt-0.5 block text-[11.5px] text-[#64748B]">
                      {p.customer_name} · {p.state} · Term {p.term_number}, {formatDate(p.effective_date)} – {formatDate(p.expiration_date)}
                      {p.earlier_terms > 0 && ` · ${p.earlier_terms} earlier term${p.earlier_terms > 1 ? 's' : ''}`}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    {evidence && (
                      <button
                        type="button"
                        onClick={() => onOpenSource(evidence)}
                        className="rounded-md border border-[#E2E8F0] px-2 py-1 text-[11px] font-semibold text-[#0F2A43] transition-colors hover:border-[#F97316] hover:text-[#EA580C] cursor-pointer"
                      >
                        Record
                      </button>
                    )}
                    {isActive ? (
                      <span className="px-2 py-1 text-[11px] font-semibold text-emerald-700">Current context</span>
                    ) : (
                      <button
                        type="button"
                        disabled={isWorking}
                        onClick={() =>
                          onChooseCandidate({
                            policy_id: p.policy_id,
                            policy_number: p.policy_number,
                            customer_id: p.customer_id,
                            customer_name: p.customer_name,
                            line_of_business: p.line_of_business,
                            product_name: p.product_name,
                            status: p.status,
                            effective_date: p.effective_date,
                            expiration_date: p.expiration_date,
                          })
                        }
                        className="rounded-md bg-[#0F2A43] px-2 py-1 text-[11px] font-semibold text-white transition-colors hover:bg-[#16385A] disabled:opacity-60 cursor-pointer"
                      >
                        Use as context
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        <p className="mt-2.5 text-[10.5px] text-[#94A3B8]">
          Read directly from the policy system — no language model or policy wording involved.
        </p>

        {result.suggested_questions.length > 0 && (
          <div className="mt-3 border-t border-slate-100 pt-3">
            <span className="mb-2 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-[0.14em] text-[#64748B]">
              <Compass className="h-3.5 w-3.5 text-[#F97316]" /> Explore these policies
            </span>
            <div className="flex flex-wrap gap-1.5">
              {result.suggested_questions.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => onAsk(q)}
                  className="inline-flex items-center gap-1 rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-1 text-[12px] text-[#0F2A43] transition-colors hover:border-[#F97316] hover:bg-[#FFF7ED] hover:text-[#C2410C] cursor-pointer"
                >
                  {q}
                  <ChevronRight className="h-3 w-3 text-[#F97316]" />
                </button>
              ))}
            </div>
          </div>
        )}

        <AuditFooter question={question} result={result} onShowAudit={onShowAudit} />
      </div>
    </div>
  );
}

export function ConversationStream({
  messages,
  isWorking,
  process,
  onShowAudit,
  onShowProcess,
  onPrefill,
  firstName,
  activePolicy,
  onAsk,
  onChooseCandidate,
  onOpenSource,
  onOpenTab,
  pendingSwitch,
  onConfirmSwitchContext,
  onConfirmStartNew,
  onCancelSwitch,
}: ConversationStreamProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);
  // Verifying the customer and identifying the policy: shown as a typing indicator.
  const reading = process.stages.verify.status === 'processing' || process.stages.context.status === 'processing';

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isWorking, pendingSwitch]);

  if (messages.length === 0 && !isWorking) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-5 py-10 sm:px-10">
        <div className="w-full max-w-[640px] text-center">
          <span className="mx-auto mb-5 flex h-11 w-11 items-center justify-center rounded-xl bg-[#0F2A43] shadow-sm">
            <Shield className="h-5 w-5 text-[#F97316]" />
          </span>
          <h2 className="font-display text-[28px] leading-tight text-[#0F2A43]">
            Explore
          </h2>
          <p className="mx-auto mt-2 max-w-lg text-[14px] leading-relaxed text-[#64748B]">
            Explore policy coverage, limits, deductibles, forms, claims, billing, and customer policies. Ask a question to get evidence-grounded answers with citations.
          </p>
          <div className="mt-7 grid gap-2 text-left sm:grid-cols-2">
            {STARTERS.map(({ label, prompt, icon: Icon }) => (
              <button
                key={label}
                type="button"
                onClick={() => onPrefill(prompt)}
                className="group flex items-center gap-3 rounded-xl border border-[#E2E8F0] bg-white px-3.5 py-3 text-[13px] text-[#0F2A43] transition-colors hover:border-[#F97316] hover:bg-[#FFF7ED] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
              >
                <Icon className="h-4 w-4 shrink-0 text-[#EA580C]" aria-hidden="true" />
                <span className="min-w-0 flex-1 truncate">{label}</span>
                <ChevronRight className="h-4 w-4 shrink-0 text-[#CBD5E1] group-hover:text-[#EA580C]" aria-hidden="true" />
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
      <div className="mx-auto max-w-[780px] space-y-5">
      {messages.map((msg) => {
        switch (msg.kind) {
          case 'user':
            return (
              <div key={msg.id} className="message-in flex items-start justify-end gap-2.5">
                <div className="flex max-w-[85%] flex-col items-end sm:max-w-[70%]">
                  <div className="rounded-2xl rounded-tr-md bg-[#0F2A43] px-4 py-2.5 text-white shadow-sm">
                    <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed">{msg.text}</p>
                  </div>
                  <span className="mt-1 text-right text-[10.5px] text-[#64748B]">
                    Asked by <span className="font-semibold text-[#0F2A43]">{askerName(msg.askedBy)}</span>
                    {msg.askedBy?.employee_id && (
                      <>
                        {' · '}
                        <span className="font-mono">{msg.askedBy.employee_id}</span>
                      </>
                    )}
                    {' · '}
                    {fullWhen(msg.askedAt) || msg.time}
                  </span>
                </div>
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#16385A]">
                  <User className="h-3.5 w-3.5 text-slate-200" />
                </span>
              </div>
            );

          case 'context': {
            const isDiffCustomer = msg.switchType === 'different_customer';
            const isPolicySwitch = msg.switchType === 'same_customer_different_policy';
            return (
              <div key={msg.id} className="message-in flex justify-center">
                <span
                  className={`inline-flex flex-wrap items-center justify-center gap-1.5 rounded-full border px-3.5 py-1 text-[11.5px] shadow-sm ${
                    isDiffCustomer
                      ? 'border-[#FDBA74] bg-[#FFF7ED] text-[#C2410C]'
                      : isPolicySwitch
                      ? 'border-blue-200 bg-blue-50 text-blue-800'
                      : 'border-[#E2E8F0] bg-white text-[#64748B]'
                  }`}
                >
                  <Link2 className={`h-3.5 w-3.5 ${isDiffCustomer ? 'text-[#EA580C]' : isPolicySwitch ? 'text-blue-600' : 'text-[#F97316]'}`} />
                  {isDiffCustomer
                    ? 'Customer context switched to:'
                    : isPolicySwitch
                    ? 'Policy switched to:'
                    : msg.switched
                    ? 'Policy context switched to:'
                    : 'Policy context resolved:'}
                  <span className="font-semibold text-[#0F2A43]">{msg.policy.customer_name}</span>
                  <span className="font-mono font-semibold text-[#0F2A43]">{msg.policy.policy_number}</span>
                  <span>· {lineLabel(msg.policy.line_of_business)}</span>
                  {msg.matchedOn && MATCH_LABEL[msg.matchedOn] && <span className="text-[#94A3B8]">({MATCH_LABEL[msg.matchedOn]})</span>}
                  {msg.answering && (
                    <span className="basis-full text-center text-[#94A3B8]">
                      Answering your earlier question: “{msg.answering}”
                    </span>
                  )}
                </span>
              </div>
            );
          }

          case 'clarify':
            return (
              <div key={msg.id} className="message-in flex items-start gap-3">
                <AssistantAvatar />
                <div className="max-w-[40rem] rounded-2xl rounded-tl-md border border-[#E2E8F0] bg-white px-4 py-3 shadow-sm">
                  <p className="text-[13.5px] leading-relaxed text-[#0F2A43]">{msg.text}</p>
                  {msg.candidates.length > 0 ? (
                    <div className="mt-3 space-y-1.5">
                      {msg.candidatesLabel && (
                        <p className="text-[10.5px] font-bold uppercase tracking-[0.12em] text-[#64748B]">{msg.candidatesLabel}</p>
                      )}
                      {msg.candidates.map((c) => (
                        <button
                          key={c.policy_id}
                          type="button"
                          onClick={() => onChooseCandidate(c)}
                          disabled={isWorking}
                          className="flex w-full items-center justify-between gap-3 rounded-lg border border-[#E2E8F0] bg-white px-3 py-2 text-left transition-colors hover:border-[#F97316] disabled:opacity-60 cursor-pointer"
                        >
                          <span className="min-w-0">
                            <span className="block text-[12.5px] font-semibold text-[#0F2A43]">{c.customer_name}</span>
                            <span className="block text-[11px] text-[#64748B]">
                              <span className="font-mono">{c.policy_number}</span> · {lineLabel(c.line_of_business)}
                            </span>
                          </span>
                          <ChevronRight className="h-4 w-4 shrink-0 text-[#F97316]" />
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-1 text-[12px] text-[#64748B]">
                      For example a policy number such as HO-2847-1193, or the policyholder's full name.
                    </p>
                  )}
                </div>
              </div>
            );

          case 'assistant':
            return (
              <div key={msg.id} className="message-in flex items-start gap-3">
                <AssistantAvatar />
                <div className="max-w-[40rem] rounded-2xl rounded-tl-md border border-[#E2E8F0] bg-white px-4 py-3 shadow-sm">
                  <p className="whitespace-pre-line text-[13.5px] leading-relaxed text-[#0F2A43]">{msg.text}</p>
                  <SuggestionChips suggestions={msg.suggestions} onAsk={onAsk} disabled={isWorking} />
                </div>
              </div>
            );

          case 'error':
            return (
              <div key={msg.id} className="message-in flex items-start gap-3">
                <AssistantAvatar />
                <div className="max-w-[40rem] rounded-2xl rounded-tl-md border border-red-200 bg-red-50 px-4 py-3">
                  <p className="flex items-center gap-1.5 text-[13px] font-semibold text-red-800">
                    <AlertCircle className="h-4 w-4" /> {msg.title}
                  </p>
                  <p className="mt-1 text-[12.5px] leading-relaxed text-red-700">{msg.text}</p>
                </div>
              </div>
            );

          case 'answer':
            if (msg.result.answer_type === 'portfolio') {
              return (
                <PortfolioCard
                  key={msg.id}
                  question={msg.question}
                  onShowAudit={onShowAudit}
                  result={msg.result}
                  time={msg.time}
                  activePolicyId={activePolicy?.policy_id}
                  isWorking={isWorking}
                  onAsk={onAsk}
                  onChooseCandidate={onChooseCandidate}
                  onOpenSource={onOpenSource}
                />
              );
            }
            return (
              <AnswerCard
                key={msg.id}
                question={msg.question}
                labelled={msg.labelled}
                onShowAudit={onShowAudit}
                result={msg.result}
                time={msg.time}
                onAsk={onAsk}
                onOpenSource={onOpenSource}
                onOpenTab={onOpenTab}
              />
            );
        }
      })}

      {pendingSwitch && onConfirmSwitchContext && onConfirmStartNew && onCancelSwitch && (
        <div className="my-6 flex justify-center w-full" role="region" aria-label="Customer context switch">
          <InlineCustomerSwitchCard
            currentCustomerName={pendingSwitch.currentPolicy.customer_name}
            currentPolicyNumber={pendingSwitch.currentPolicy.policy_number}
            currentLineOfBusiness={pendingSwitch.currentPolicy.line_of_business}
            targetCustomerName={pendingSwitch.targetPolicy.customer_name}
            targetPolicyNumber={pendingSwitch.targetPolicy.policy_number}
            targetLineOfBusiness={pendingSwitch.targetPolicy.line_of_business}
            onSwitchContext={onConfirmSwitchContext}
            onStartNewConversation={onConfirmStartNew}
            onCancel={onCancelSwitch}
          />
        </div>
      )}

      {isWorking && process.phase === 'running' && reading && (
        <div className="message-in flex items-center gap-3" role="status" aria-label="Reading your question">
          <AssistantAvatar />
          <div className="flex items-center gap-1 rounded-2xl rounded-tl-md border border-[#E2E8F0] bg-white px-4 py-3.5 shadow-sm">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#94A3B8] [animation-delay:-0.3s] motion-reduce:animate-none" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#94A3B8] [animation-delay:-0.15s] motion-reduce:animate-none" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#94A3B8] motion-reduce:animate-none" />
          </div>
        </div>
      )}

      {isWorking && process.phase === 'running' && !reading && (
        <div className="message-in flex items-center gap-3">
          <AssistantAvatar />
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl rounded-tl-md border border-[#E2E8F0] bg-white px-4 py-2.5 text-[12.5px] text-[#475569] shadow-sm">
            <span className="inline-flex items-center gap-2" role="status">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-[#EA580C] motion-reduce:animate-none" aria-hidden="true" />
              Working on your answer. Follow each step in the AI process panel.
            </span>
            <button
              type="button"
              onClick={(e) => onShowProcess(e.currentTarget)}
              className="inline-flex items-center gap-1 rounded-md border border-[#E2E8F0] px-2.5 py-1 text-[11.5px] font-semibold text-[#0F2A43] transition-colors hover:border-[#F97316] hover:text-[#EA580C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
            >
              <ListChecks className="h-3.5 w-3.5" aria-hidden="true" /> Show AI process
            </button>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
      </div>
    </div>
  );
}
