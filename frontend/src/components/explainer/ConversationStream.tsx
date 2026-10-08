import React, { useRef, useEffect } from 'react';
import {
  Shield,
  User,
  Sparkles,
  FileText,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  AlertCircle,
  HelpCircle,
} from 'lucide-react';
import { ChatMessage, EvidenceItem, CitationItem } from '../../types';

interface ConversationStreamProps {
  messages: ChatMessage[];
  isAnalyzing: boolean;
  analyzingStepIndex: number;
  onSelectSuggestion: (question: string) => void;
  onViewCoverage: (coverageName: string) => void;
  onViewForm: (formNumber: string) => void;
}

const THINKING_STEPS = [
  'Identifying relevant policy context',
  'Reviewing applicable coverage',
  'Checking forms and exclusions',
  'Validating supporting evidence',
  'Preparing cited response',
];

export function ConversationStream({
  messages,
  isAnalyzing,
  analyzingStepIndex,
  onSelectSuggestion,
  onViewCoverage,
  onViewForm,
}: ConversationStreamProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAnalyzing, analyzingStepIndex]);

  // Initial State when there are no messages
  if (messages.length === 0 && !isAnalyzing) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center p-6 sm:p-12">
        <div className="w-14 h-14 rounded-2xl bg-[#0F2A43] text-white flex items-center justify-center shadow-md mb-4">
          <Shield className="w-7 h-7 text-[#F97316]" strokeWidth={2.2} />
        </div>
        <h2 className="text-2xl sm:text-3xl font-display font-bold text-[#0F2A43] tracking-tight">
          Policy Explainer
        </h2>
        <p className="text-sm sm:text-base text-[#64748B] max-w-md mt-2 leading-relaxed">
          Understand coverage, terms, and policy details with grounded evidence and verified citations.
        </p>

        {/* Suggested Questions */}
        <div className="mt-8 w-full max-w-xl">
          <span className="text-xs font-bold text-[#64748B] uppercase tracking-wider block mb-3">
            Suggested Questions
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <button
              type="button"
              onClick={() => onSelectSuggestion('Does Margaret Chen have water backup coverage?')}
              className="text-left p-3 rounded-xl border border-[#E2E8F0] hover:border-[#F97316] bg-white hover:bg-orange-50/50 text-xs font-medium text-[#0F2A43] transition-all shadow-2xs hover:shadow-xs group cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[#EA580C]">Featured Query</span>
                <ChevronRight className="w-3.5 h-3.5 text-[#F97316] group-hover:translate-x-0.5 transition-transform" />
              </div>
              <p className="mt-1 text-[#0F2A43]">
                "Does Margaret Chen have water backup coverage?"
              </p>
            </button>

            <button
              type="button"
              onClick={() => onSelectSuggestion('What is covered?')}
              className="text-left p-3 rounded-xl border border-[#E2E8F0] hover:border-[#F97316] bg-white hover:bg-orange-50/50 text-xs font-medium text-[#0F2A43] transition-all shadow-2xs hover:shadow-xs group cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <span>Coverage Summary</span>
                <ChevronRight className="w-3.5 h-3.5 text-[#64748B] group-hover:translate-x-0.5 transition-transform" />
              </div>
              <p className="mt-1 text-[#0F2A43]">"What is covered?"</p>
            </button>

            <button
              type="button"
              onClick={() => onSelectSuggestion('What are the deductibles?')}
              className="text-left p-3 rounded-xl border border-[#E2E8F0] hover:border-[#F97316] bg-white hover:bg-orange-50/50 text-xs font-medium text-[#0F2A43] transition-all shadow-2xs hover:shadow-xs group cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <span>Deductible Schedule</span>
                <ChevronRight className="w-3.5 h-3.5 text-[#64748B] group-hover:translate-x-0.5 transition-transform" />
              </div>
              <p className="mt-1 text-[#0F2A43]">"What are the deductibles?"</p>
            </button>

            <button
              type="button"
              onClick={() => onSelectSuggestion('What endorsements are included?')}
              className="text-left p-3 rounded-xl border border-[#E2E8F0] hover:border-[#F97316] bg-white hover:bg-orange-50/50 text-xs font-medium text-[#0F2A43] transition-all shadow-2xs hover:shadow-xs group cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <span>Forms & Endorsements</span>
                <ChevronRight className="w-3.5 h-3.5 text-[#64748B] group-hover:translate-x-0.5 transition-transform" />
              </div>
              <p className="mt-1 text-[#0F2A43]">"What endorsements are included?"</p>
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
      {messages.map((msg) => {
        if (msg.sender === 'user') {
          return (
            <div key={msg.id} className="flex justify-end items-start gap-2.5">
              <div className="max-w-[85%] sm:max-w-[70%] bg-[#0F2A43] text-white rounded-2xl rounded-tr-xs px-4 py-3 shadow-xs">
                <p className="text-xs sm:text-sm font-medium leading-relaxed whitespace-pre-wrap">
                  {msg.text}
                </p>
                <span className="text-[10px] text-slate-300/80 block text-right mt-1.5">
                  {msg.timestamp}
                </span>
              </div>
              <div className="w-7 h-7 rounded-full bg-[#16385A] border border-[#0F2A43] text-white flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-3.5 h-3.5 text-slate-200" />
              </div>
            </div>
          );
        }

        // Policy Explainer Message (LEFT)
        const isInsufficient = msg.status === 'insufficient_evidence';
        const primaryForm = msg.citations?.[0]?.form_number || msg.evidence?.[0]?.form_number;
        const primaryCov = msg.evidence?.find((e) => e.source_type === 'coverage')?.title;

        return (
          <div key={msg.id} className="flex justify-start items-start gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#0F2A43] text-white flex items-center justify-center shrink-0 mt-0.5 shadow-xs">
              <Shield className="w-4 h-4 text-[#F97316]" />
            </div>

            <div className="max-w-[92%] sm:max-w-[80%] bg-white border border-[#E2E8F0] rounded-2xl rounded-tl-xs p-4 sm:p-5 shadow-xs space-y-3.5">
              {/* Header Label */}
              <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2">
                <div className="flex items-center gap-1.5">
                  <span className="font-bold text-[#0F2A43] text-xs">Policy Explainer</span>
                  <span className="text-slate-300">·</span>
                  <span className="text-[11px] text-[#64748B]">{msg.timestamp}</span>
                </div>

                {msg.confidence && (
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider inline-flex items-center gap-1 ${
                      msg.confidence === 'high'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : msg.confidence === 'medium'
                        ? 'bg-amber-50 text-amber-700 border border-amber-200'
                        : 'bg-slate-100 text-slate-600 border border-slate-200'
                    }`}
                  >
                    <ShieldCheck className="w-3 h-3" />
                    Confidence: {msg.confidence}
                  </span>
                )}
              </div>

              {/* Answer Text */}
              <div className="text-xs sm:text-sm text-[#0F2A43] leading-relaxed whitespace-pre-wrap">
                {msg.text}
              </div>

              {/* Real Evidence & Citation Block */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] p-3 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-[#F97316]" />
                      Evidence & Policy Source
                    </span>

                    {/* Deep Link Actions to Policy Features */}
                    <div className="flex items-center gap-2">
                      {primaryCov && (
                        <button
                          type="button"
                          onClick={() => onViewCoverage(primaryCov)}
                          className="inline-flex items-center gap-1 px-2 py-0.8 rounded text-[11px] font-semibold text-[#0F2A43] bg-white hover:bg-slate-100 border border-[#E2E8F0] transition-colors cursor-pointer"
                        >
                          View Coverage
                          <ExternalLink className="w-3 h-3 text-[#F97316]" />
                        </button>
                      )}

                      {primaryForm && (
                        <button
                          type="button"
                          onClick={() => onViewForm(primaryForm)}
                          className="inline-flex items-center gap-1 px-2 py-0.8 rounded text-[11px] font-semibold text-[#0F2A43] bg-white hover:bg-slate-100 border border-[#E2E8F0] transition-colors cursor-pointer"
                        >
                          View Form
                          <ExternalLink className="w-3 h-3 text-[#F97316]" />
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {msg.citations.map((c, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 bg-white border border-[#E2E8F0] px-2.5 py-1 rounded text-[11px] font-medium text-[#0F2A43]"
                      >
                        <strong className="font-mono font-bold text-[#EA580C]">{c.form_number}</strong>
                        {c.edition && <span className="text-[#64748B]">· Ed. {c.edition}</span>}
                        {c.page && <span className="text-[#64748B]">· p.{c.page}</span>}
                        {c.heading && <span className="text-[#0F2A43] font-normal truncate max-w-[160px]">· {c.heading}</span>}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Suggested Follow-up Questions */}
              {msg.suggestedQuestions && msg.suggestedQuestions.length > 0 && (
                <div className="pt-2 border-t border-slate-100">
                  <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider block mb-2">
                    Suggested Questions
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {msg.suggestedQuestions.map((q, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => onSelectSuggestion(q)}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-[#E2E8F0] hover:border-[#F97316] bg-slate-50 hover:bg-orange-50/60 text-xs font-medium text-[#0F2A43] hover:text-[#EA580C] transition-all cursor-pointer shadow-2xs"
                      >
                        <span>{q}</span>
                        <ChevronRight className="w-3 h-3 text-[#F97316]" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })}

      {/* Thinking State on LEFT (Section 15) */}
      {isAnalyzing && (
        <div className="flex justify-start items-start gap-2.5 animate-fade-in">
          <div className="w-8 h-8 rounded-lg bg-[#0F2A43] text-white flex items-center justify-center shrink-0 mt-0.5 shadow-xs">
            <Shield className="w-4 h-4 text-[#F97316] animate-pulse" />
          </div>

          <div className="max-w-[85%] sm:max-w-[70%] bg-white border border-[#E2E8F0] rounded-2xl rounded-tl-xs p-4 sm:p-5 shadow-xs space-y-3">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-2">
              <span className="font-bold text-[#0F2A43] text-xs">Analyzing policy</span>
              <span className="inline-block w-2 h-2 rounded-full bg-[#F97316] animate-ping" />
            </div>

            <div className="space-y-1.5 text-xs">
              {THINKING_STEPS.map((step, idx) => {
                const isCompleted = idx < analyzingStepIndex;
                const isCurrent = idx === analyzingStepIndex;

                return (
                  <div
                    key={step}
                    className={`flex items-center gap-2 ${
                      isCurrent
                        ? 'text-[#0F2A43] font-bold'
                        : isCompleted
                        ? 'text-emerald-700'
                        : 'text-slate-400'
                    }`}
                  >
                    {isCompleted ? (
                      <span className="text-emerald-600 font-bold shrink-0">✓</span>
                    ) : isCurrent ? (
                      <span className="text-[#F97316] font-bold shrink-0">◉</span>
                    ) : (
                      <span className="text-slate-300 shrink-0">○</span>
                    )}
                    <span>{step}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
