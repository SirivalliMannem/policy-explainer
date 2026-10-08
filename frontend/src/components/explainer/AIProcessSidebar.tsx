import { AlertTriangle, Check, Cpu, Minus, X } from 'lucide-react';
import { GuardrailSummary } from './GuardrailSummary';
import {
  ProcessState,
  STAGES,
  StageState,
  formatMs,
  modelLabel,
} from '../../lib/explainer';

interface AIProcessSidebarProps {
  process: ProcessState;
  policyNumber?: string | null;
}

const PHASE_BADGE: Record<string, { label: string; className: string }> = {
  idle: { label: 'Idle', className: 'bg-slate-100 text-[#64748B] ring-slate-200' },
  running: { label: 'Processing', className: 'bg-[#FFF7ED] text-[#C2410C] ring-[#FDBA74]' },
  completed: { label: 'Completed', className: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  needs_input: { label: 'Needs input', className: 'bg-[#FFF7ED] text-[#C2410C] ring-[#FDBA74]' },
  failed: { label: 'Failed', className: 'bg-red-50 text-red-700 ring-red-200' },
};

function StageIcon({ status }: { status: StageState['status'] }) {
  switch (status) {
    case 'completed':
      return (
        <span className="stage-pop flex h-5 w-5 items-center justify-center rounded-full bg-[#0F2A43] text-white">
          <Check className="h-3 w-3" strokeWidth={3} />
        </span>
      );
    case 'processing':
      return (
        <span className="relative flex h-5 w-5 items-center justify-center rounded-full border-2 border-[#F97316] bg-white">
          <span className="absolute inset-0 rounded-full border-2 border-[#F97316] stage-ring" />
          <span className="h-2 w-2 rounded-full bg-[#F97316]" />
        </span>
      );
    case 'failed':
      return (
        <span className="stage-pop flex h-5 w-5 items-center justify-center rounded-full bg-red-600 text-white">
          <X className="h-3 w-3" strokeWidth={3} />
        </span>
      );
    case 'attention':
      return (
        <span className="stage-pop flex h-5 w-5 items-center justify-center rounded-full bg-amber-500 text-white">
          <AlertTriangle className="h-3 w-3" strokeWidth={2.5} />
        </span>
      );
    case 'skipped':
      return (
        <span className="flex h-5 w-5 items-center justify-center rounded-full border border-dashed border-slate-300 text-slate-300">
          <Minus className="h-3 w-3" />
        </span>
      );
    default:
      return <span className="h-5 w-5 rounded-full border-2 border-slate-200 bg-white" />;
  }
}

function stageStatusText(stage: StageState): string {
  switch (stage.status) {
    case 'processing':
      return 'Processing';
    case 'completed':
      return stage.ms !== undefined && stage.ms !== null ? `Completed · ${formatMs(stage.ms)}` : 'Completed';
    case 'failed':
      return 'Failed';
    case 'attention':
      return stage.ms !== undefined && stage.ms !== null ? `Review · ${formatMs(stage.ms)}` : 'Needs attention';
    case 'skipped':
      return 'Skipped';
    default:
      return 'Waiting';
  }
}

export function AIProcessSidebar({ process, policyNumber }: AIProcessSidebarProps) {
  const badge = PHASE_BADGE[process.phase];
  const result = process.result;

  return (
    <aside aria-label="AI process" className="flex w-full flex-col gap-4 rounded-xl border border-[#E2E8F0] bg-white p-4 text-xs shadow-sm lg:w-[19rem]">
      <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[#0F2A43] text-[#F97316]">
            <Cpu className="h-3.5 w-3.5" />
          </span>
          <h3 className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#0F2A43]">AI Process</h3>
        </div>
        <span className={`rounded-md px-2 py-0.5 text-[10.5px] font-semibold ring-1 ${badge.className}`}>
          {result?.status === 'insufficient_evidence' && process.phase === 'completed' ? 'Insufficient evidence' : badge.label}
        </span>
      </div>

      {process.phase === 'idle' ? (
        <div className="space-y-3 py-1">
          <p className="leading-relaxed text-[#64748B]">
            Each question runs through the grounded pipeline below. Progress appears here while it runs.
          </p>
          <ol className="space-y-2">
            {STAGES.map((s, i) => (
              <li key={s.key} className="flex items-center gap-2.5 text-[#94A3B8]">
                <span className="w-4 text-right font-mono text-[10px]">{i + 1}</span>
                <span>{s.label}</span>
              </li>
            ))}
          </ol>
        </div>
      ) : (
        <ol className="relative">
          {STAGES.map((s, i) => {
            const stage = process.stages[s.key];
            const isLast = i === STAGES.length - 1;
            const active = stage.status === 'processing';
            return (
              <li key={s.key} className="relative flex gap-3 pb-3.5 last:pb-0">
                {!isLast && (
                  <span
                    className={`absolute left-[9px] top-6 bottom-0 w-px transition-colors duration-500 ${
                      stage.status === 'completed' ? 'bg-[#0F2A43]' : 'bg-slate-200'
                    }`}
                  />
                )}
                <span className="relative z-10 mt-px">
                  <StageIcon status={stage.status} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <span
                      className={`text-[12px] leading-5 transition-colors ${
                        active
                          ? 'font-semibold text-[#0F2A43]'
                          : stage.status === 'waiting' || stage.status === 'skipped'
                          ? 'text-[#94A3B8]'
                          : 'font-medium text-[#0F2A43]'
                      }`}
                    >
                      {s.label}
                    </span>
                  </div>
                  <span
                    className={`block text-[10.5px] ${
                      active
                        ? 'font-semibold text-[#EA580C]'
                        : stage.status === 'failed'
                        ? 'text-red-600'
                        : stage.status === 'attention'
                        ? 'text-amber-700'
                        : 'text-[#64748B]'
                    }`}
                  >
                    {stageStatusText(stage)}
                  </span>
                  {stage.detail && stage.status !== 'processing' && stage.status !== 'waiting' && (
                    <span className="mt-0.5 block text-[10.5px] leading-snug text-[#64748B] break-words">{stage.detail}</span>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {process.phase === 'running' && (
        <p className="border-t border-slate-100 pt-2.5 text-[10.5px] leading-snug text-[#94A3B8]">
          Stages 2–6 run inside one request to the AI service. Progress advances on a fixed schedule while it runs;
          measured stage times replace it when the answer returns.
        </p>
      )}

      {process.phase === 'completed' && result && (
        <div className="space-y-3 border-t border-[#E2E8F0] pt-3">
          <dl className="grid grid-cols-2 gap-2">
            <div className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
              <dt className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">Confidence</dt>
              <dd
                className={`mt-0.5 text-sm font-bold uppercase ${
                  result.confidence === 'high'
                    ? 'text-emerald-700'
                    : result.confidence === 'medium'
                    ? 'text-amber-700'
                    : 'text-[#64748B]'
                }`}
              >
                {result.confidence}
              </dd>
            </div>
            <div className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
              <dt className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">Policy context</dt>
              <dd className="mt-0.5 truncate font-mono text-[12px] font-bold text-[#0F2A43]">
                {result.policy_context?.policy_number || policyNumber || '—'}
              </dd>
            </div>
            <div className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
              <dt className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">Evidence sources</dt>
              <dd className="mt-0.5 text-sm font-bold text-[#0F2A43]">
                {result.evidence.length}
                <span className="ml-1 text-[10.5px] font-medium text-[#64748B]">retrieved</span>
              </dd>
            </div>
            <div className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
              <dt className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">Citations</dt>
              <dd className="mt-0.5 text-sm font-bold text-[#EA580C]">
                {result.citations.length}
                <span className="ml-1 text-[10.5px] font-medium text-[#64748B]">verified</span>
              </dd>
            </div>
          </dl>

          <GuardrailSummary status={result.guardrail_status} checks={result.guardrail_checks} />

          <div className="flex items-center justify-between border-t border-slate-100 pt-2.5 text-[10.5px] text-[#64748B]">
            <span className="truncate" title={modelLabel(result)}>
              {modelLabel(result)}
            </span>
            <span className="shrink-0 font-mono">{formatMs(result.latency_ms)}</span>
          </div>
        </div>
      )}
    </aside>
  );
}
