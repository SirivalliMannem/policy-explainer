import React, { useState } from 'react';
import {
  Sparkles,
  CheckCircle2,
  Clock,
  ShieldCheck,
  FileCheck,
  ChevronDown,
  ChevronUp,
  Cpu,
  Layers,
} from 'lucide-react';
import { QuestionAnswerResponse } from '../../types';

interface AIProcessSidebarProps {
  isAnalyzing: boolean;
  stepIndex: number;
  latestResult: QuestionAnswerResponse | null;
  policyNumber?: string | null;
}

const PROCESS_STEPS = [
  'Question received',
  'Policy resolved',
  'Evidence retrieved',
  'Building grounding',
  'Explanation generated',
  'Guardrails validated',
  'Citations validated',
];

export function AIProcessSidebar({
  isAnalyzing,
  stepIndex,
  latestResult,
  policyNumber,
}: AIProcessSidebarProps) {
  const [showGrounding, setShowGrounding] = useState(false);

  return (
    <aside className="w-full lg:w-72 xl:w-80 bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-sm flex flex-col gap-4 text-xs">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2.5">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-[#0F2A43] text-[#F97316] flex items-center justify-center font-bold">
            <Cpu className="w-3.5 h-3.5" />
          </div>
          <h3 className="font-bold text-[#0F2A43] uppercase tracking-wider text-xs">
            AI PROCESS
          </h3>
        </div>

        {isAnalyzing ? (
          <span className="flex items-center gap-1.5 text-[11px] font-semibold text-[#F97316] animate-pulse">
            <span className="w-2 h-2 rounded-full bg-[#F97316]" />
            Analyzing
          </span>
        ) : latestResult ? (
          <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
            <CheckCircle2 className="w-3 h-3" />
            Verified
          </span>
        ) : (
          <span className="text-[11px] text-[#64748B]">Idle</span>
        )}
      </div>

      {/* State 1: Active Analysis in Progress */}
      {isAnalyzing && (
        <div className="space-y-2.5 py-1">
          <p className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider">
            Execution Pipeline
          </p>
          <div className="space-y-2">
            {PROCESS_STEPS.map((step, idx) => {
              const isCompleted = idx < stepIndex;
              const isCurrent = idx === stepIndex;
              const isUpcoming = idx > stepIndex;

              return (
                <div
                  key={step}
                  className={`flex items-center gap-2.5 transition-all ${
                    isCurrent
                      ? 'text-[#0F2A43] font-bold scale-[1.01]'
                      : isCompleted
                      ? 'text-emerald-700 font-medium'
                      : 'text-slate-400'
                  }`}
                >
                  {isCompleted ? (
                    <span className="text-emerald-600 font-bold shrink-0">✓</span>
                  ) : isCurrent ? (
                    <span className="inline-block w-2.5 h-2.5 rounded-full bg-[#F97316] animate-ping shrink-0" />
                  ) : (
                    <span className="text-slate-300 shrink-0">○</span>
                  )}
                  <span className="text-xs">{step}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* State 2: Result Summary Metadata */}
      {!isAnalyzing && latestResult && (
        <div className="space-y-3.5">
          <div>
            <span className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider block">
              Confidence Level
            </span>
            <div className="mt-1 flex items-center gap-2">
              <span
                className={`px-2.5 py-1 rounded text-xs font-bold uppercase tracking-wider inline-flex items-center gap-1.5 ${
                  latestResult.confidence === 'high'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : latestResult.confidence === 'medium'
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : 'bg-slate-100 text-slate-600 border border-slate-200'
                }`}
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                Confidence: {latestResult.confidence || 'Standard'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-2.5 rounded-lg">
              <span className="text-[#64748B] text-[11px] block">Evidence Sources</span>
              <span className="text-base font-bold text-[#0F2A43] mt-0.5 block">
                {latestResult.evidence?.length || 0}
              </span>
              <span className="text-[10px] text-[#64748B]">retrieved chunks</span>
            </div>

            <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-2.5 rounded-lg">
              <span className="text-[#64748B] text-[11px] block">Cited Sources</span>
              <span className="text-base font-bold text-[#EA580C] mt-0.5 block">
                {latestResult.citations?.length || 0}
              </span>
              <span className="text-[10px] text-[#64748B]">verified references</span>
            </div>
          </div>

          {policyNumber && (
            <div className="border-t border-slate-100 pt-2 text-[11px] text-[#64748B]">
              <span>Active Bound Policy:</span>
              <span className="font-mono font-bold text-[#0F2A43] ml-1">{policyNumber}</span>
            </div>
          )}

          {/* Citations Preview List */}
          {latestResult.citations && latestResult.citations.length > 0 && (
            <div className="space-y-1.5 border-t border-slate-100 pt-2.5">
              <span className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wider block">
                Source Citations
              </span>
              <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                {latestResult.citations.map((c, i) => (
                  <div
                    key={i}
                    className="p-1.5 rounded bg-[#F8FAFC] border border-[#E2E8F0] text-[11px]"
                  >
                    <span className="font-mono font-bold text-[#0F2A43] mr-1">
                      {c.form_number}
                    </span>
                    {c.edition && <span className="text-[#64748B] mr-1">Ed. {c.edition}</span>}
                    {c.page && <span className="text-[#64748B]">p.{c.page}</span>}
                    {c.heading && (
                      <p className="text-[#0F2A43] text-[10px] truncate mt-0.5 font-medium">
                        {c.heading}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* State 3: Idle / Waiting for first question */}
      {!isAnalyzing && !latestResult && (
        <div className="py-6 text-center text-[#64748B] space-y-2">
          <Layers className="w-8 h-8 text-slate-300 mx-auto" />
          <p className="text-xs">
            Ask a policy question to monitor real-time AI retrieval, grounding, and citation validation.
          </p>
        </div>
      )}
    </aside>
  );
}
