import type { ReactNode } from 'react';
import { AlertTriangle, Check, Circle, Loader2, Minus, X } from 'lucide-react';
import { STAGES, StageKey, StageState, StageStatus, formatMs } from '../../lib/explainer';

/** Each status has an icon and words, so state never depends on colour alone. */
const STATUS: Record<StageStatus, { label: string; icon: ReactNode }> = {
  processing: {
    label: 'In progress',
    icon: <Loader2 className="h-3.5 w-3.5 animate-spin text-orange-btn motion-reduce:animate-none" />,
  },
  completed: {
    label: 'Done',
    icon: (
      <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-emerald-600 text-white">
        <Check className="h-2.5 w-2.5" strokeWidth={3.5} />
      </span>
    ),
  },
  waiting: { label: 'Pending', icon: <Circle className="h-3.5 w-3.5 text-slate-300" /> },
  failed: {
    label: 'Failed',
    icon: (
      <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-red-600 text-white">
        <X className="h-2.5 w-2.5" strokeWidth={3.5} />
      </span>
    ),
  },
  attention: { label: 'Needs attention', icon: <AlertTriangle className="h-3.5 w-3.5 text-amber-600" /> },
  skipped: {
    label: 'Skipped',
    icon: (
      <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full border border-slate-300 text-slate-400">
        <Minus className="h-2.5 w-2.5" strokeWidth={3} />
      </span>
    ),
  },
};

/**
 * The six pipeline steps. `compact` is the live tracker inside the chat; the full form, with each
 * step's detail and recorded timing, is used in "How this was answered".
 */
export function StepTracker({
  stages,
  compact = false,
  label = 'AI process',
}: {
  stages: Record<StageKey, StageState>;
  compact?: boolean;
  label?: string;
}) {
  return (
    <ol aria-label={label} className={compact ? 'space-y-1' : 'space-y-2.5'}>
      {STAGES.map(({ key, label: stepLabel }) => {
        const stage = stages[key];
        const { icon, label: statusText } = STATUS[stage.status];
        const muted = stage.status === 'waiting' || stage.status === 'skipped';
        const showStatusWord = stage.status !== 'completed' && stage.status !== 'waiting';
        return (
          <li key={key} className="flex items-start gap-2.5" aria-current={stage.status === 'processing' ? 'step' : undefined}>
            <span className="mt-0.5 shrink-0" aria-hidden="true">
              {icon}
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-baseline justify-between gap-2">
                <span className={`text-[12.5px] ${muted ? 'text-muted-foreground' : 'font-medium text-espresso'}`}>
                  {stepLabel}
                  <span className="sr-only"> — {statusText}</span>
                  {showStatusWord && (
                    <span
                      className={`ml-1.5 text-[10.5px] font-semibold uppercase tracking-wide ${
                        stage.status === 'failed'
                          ? 'text-red-700'
                          : stage.status === 'attention'
                          ? 'text-amber-700'
                          : stage.status === 'processing'
                          ? 'text-orange-btn'
                          : 'text-muted-foreground'
                      }`}
                      aria-hidden="true"
                    >
                      {statusText}
                    </span>
                  )}
                </span>
                {!compact && stage.ms !== undefined && stage.ms !== null && (
                  <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{formatMs(stage.ms)}</span>
                )}
              </span>
              {!compact && stage.detail && (
                <span className="mt-0.5 block text-[11.5px] leading-snug text-muted-foreground">{stage.detail}</span>
              )}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
