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
  Link2,
  Shield,
  ShieldCheck,
  User,
} from 'lucide-react';
import type { EvidenceItem, PolicyContextCandidate, QuestionAnswerResponse } from '../../types';
import { AnswerText, SourceChip } from './AnswerText';
import { QuickPolicyActions } from './QuickPolicyActions';
import type { PolicyFeatureTab } from './PolicyFeaturesPanel';
import {
  checkLabel,
  citationLine,
  evidenceByIndex,
  formatDate,
  interpretationMethodLabel,
  interpretedText,
  lineLabel,
  modelLabel,
  statusLabel,
} from '../../lib/explainer';

export type ChatMessage =
  | { kind: 'user'; id: string; time: string; text: string }
  | {
      kind: 'context';
      id: string;
      time: string;
      policy: PolicyContextCandidate;
      matchedOn?: string | null;
      switched: boolean;
      answering?: string;
    }
  | { kind: 'clarify'; id: string; time: string; text: string; candidates: PolicyContextCandidate[] }
  | { kind: 'answer'; id: string; time: string; result: QuestionAnswerResponse }
  | { kind: 'error'; id: string; time: string; title: string; text: string };

interface ConversationStreamProps {
  messages: ChatMessage[];
  isWorking: boolean;
  activePolicy: PolicyContextCandidate | null;
  onAsk: (question: string) => void;
  onChooseCandidate: (candidate: PolicyContextCandidate) => void;
  onOpenSource: (item: EvidenceItem) => void;
  onOpenTab: (tab: PolicyFeatureTab, highlight?: { type: 'coverage' | 'form'; id: string }) => void;
}

const MATCH_LABEL: Record<string, string> = {
  policy_number: 'matched on policy number',
  customer_name: 'matched on policyholder name',
  surname: 'matched on surname',
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

function AssistantAvatar() {
  return (
    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#0F2A43] shadow-sm">
      <Shield className="h-4 w-4 text-[#F97316]" />
    </span>
  );
}

function AnswerCard({
  result,
  time,
  onAsk,
  onOpenSource,
  onOpenTab,
}: {
  result: QuestionAnswerResponse;
  time: string;
  onAsk: (q: string) => void;
  onOpenSource: (item: EvidenceItem) => void;
  onOpenTab: ConversationStreamProps['onOpenTab'];
}) {
  const insufficient = result.status === 'insufficient_evidence';
  const primary = result.citations[0];
  const primaryEvidence = primary?.evidence_index ? evidenceByIndex(result.evidence, primary.evidence_index) : undefined;
  const citedCoverage = result.citations
    .map((c) => (c.evidence_index ? evidenceByIndex(result.evidence, c.evidence_index) : undefined))
    .find((e) => e?.source_type === 'coverage');
  const failedChecks = result.guardrail_checks.filter((c) => c.status === 'failed');
  const r = result.retrieval || {};

  return (
    <div className="message-in flex items-start gap-3">
      <AssistantAvatar />
      <div className="min-w-0 max-w-[46rem] flex-1 rounded-2xl rounded-tl-md border border-[#E2E8F0] bg-white px-4 py-3.5 shadow-sm sm:px-5">
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
              className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wider ring-1 ${
                result.confidence === 'high'
                  ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                  : result.confidence === 'medium'
                  ? 'bg-amber-50 text-amber-700 ring-amber-200'
                  : 'bg-slate-100 text-slate-600 ring-slate-200'
              }`}
            >
              <ShieldCheck className="h-3 w-3" /> Confidence: {result.confidence}
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

        {!insufficient && primary && (
          <div className="mt-3.5 space-y-2.5 border-t border-slate-100 pt-3">
            <div className="flex flex-wrap items-center gap-2">
              {primaryEvidence && <SourceChip item={primaryEvidence} onOpen={onOpenSource} size="md" />}
              <span className="text-[11.5px] text-[#64748B]">{citationLine(primary)}</span>
              {result.citations.length > 1 && (
                <span className="text-[11px] text-[#94A3B8]">+{result.citations.length - 1} more verified</span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {primaryEvidence && (
                <button
                  type="button"
                  onClick={() => onOpenSource(primaryEvidence)}
                  className="inline-flex items-center gap-1 rounded-md border border-[#E2E8F0] px-2.5 py-1 text-[11.5px] font-semibold text-[#0F2A43] transition-colors hover:border-[#F97316] hover:text-[#EA580C] cursor-pointer"
                >
                  View source <ExternalLink className="h-3 w-3" />
                </button>
              )}
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
      </div>
    </div>
  );
}

function PortfolioCard({
  result,
  time,
  activePolicyId,
  isWorking,
  onAsk,
  onChooseCandidate,
  onOpenSource,
}: {
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
      </div>
    </div>
  );
}

export function ConversationStream({
  messages,
  isWorking,
  activePolicy,
  onAsk,
  onChooseCandidate,
  onOpenSource,
  onOpenTab,
}: ConversationStreamProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isWorking]);

  if (messages.length === 0 && !isWorking) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-5 py-8 sm:px-10">
        <div className="mb-8 max-w-xl text-center">
          <span className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#0F2A43] shadow-md">
            <Shield className="h-6 w-6 text-[#F97316]" />
          </span>
          <h2 className="text-2xl font-bold tracking-tight text-[#0F2A43] sm:text-[28px]">Policy Explainer</h2>
          <p className="mt-2 text-[14px] leading-relaxed text-[#64748B]">
            Understand coverage, terms, exclusions, forms, and policy details using grounded evidence and verified citations.
          </p>
        </div>
        <QuickPolicyActions policy={activePolicy} onOpen={(tab) => onOpenTab(tab)} />
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:px-6">
      {messages.map((msg) => {
        switch (msg.kind) {
          case 'user':
            return (
              <div key={msg.id} className="message-in flex items-start justify-end gap-2.5">
                <div className="max-w-[85%] rounded-2xl rounded-tr-md bg-[#0F2A43] px-4 py-2.5 text-white shadow-sm sm:max-w-[70%]">
                  <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed">{msg.text}</p>
                  <span className="mt-1 block text-right text-[10px] text-slate-300/80">{msg.time}</span>
                </div>
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#16385A]">
                  <User className="h-3.5 w-3.5 text-slate-200" />
                </span>
              </div>
            );

          case 'context':
            return (
              <div key={msg.id} className="message-in flex justify-center">
                <span className="inline-flex flex-wrap items-center justify-center gap-1.5 rounded-full border border-[#E2E8F0] bg-white px-3 py-1 text-[11.5px] text-[#64748B] shadow-sm">
                  <Link2 className="h-3.5 w-3.5 text-[#F97316]" />
                  {msg.switched ? 'Policy context switched to' : 'Policy context resolved:'}
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

          case 'clarify':
            return (
              <div key={msg.id} className="message-in flex items-start gap-3">
                <AssistantAvatar />
                <div className="max-w-[40rem] rounded-2xl rounded-tl-md border border-[#FDBA74] bg-[#FFF7ED] px-4 py-3 shadow-sm">
                  <p className="text-[13.5px] font-medium leading-relaxed text-[#0F2A43]">{msg.text}</p>
                  {msg.candidates.length > 0 ? (
                    <div className="mt-2.5 space-y-1.5">
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
                      Reply with the policyholder's full name or the policy number, and I'll answer your question.
                    </p>
                  )}
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
                result={msg.result}
                time={msg.time}
                onAsk={onAsk}
                onOpenSource={onOpenSource}
                onOpenTab={onOpenTab}
              />
            );
        }
      })}

      {isWorking && (
        <div className="message-in flex items-center gap-3">
          <AssistantAvatar />
          <div className="flex items-center gap-2 rounded-2xl rounded-tl-md border border-[#E2E8F0] bg-white px-4 py-2.5 text-[12.5px] text-[#64748B] shadow-sm">
            <span className="flex gap-1">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#F97316] [animation-delay:-0.3s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#F97316] [animation-delay:-0.15s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#F97316]" />
            </span>
            Working through the grounded pipeline
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
