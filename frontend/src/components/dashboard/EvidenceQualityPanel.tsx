import { useEffect, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { Skeleton } from '../ui/Skeleton';
import { getLedgerSummary } from '../../services/api';
import type { EvidenceQualityBreakdown, LedgerSummary } from '../../types';

/** One hue, dark to light: higher confidence reads heavier. */
const LEVELS = [
  { key: 'high', label: 'High', color: '#0F2A43' },
  { key: 'medium', label: 'Medium', color: '#3A5F84' },
  { key: 'low', label: 'Low / none', color: '#728CA8' },
] as const;

type LevelKey = (typeof LEVELS)[number]['key'];

function pct(part: number, whole: number): number {
  return whole > 0 ? Math.round((part / whole) * 100) : 0;
}

function RateRow({ label, hint, value }: { label: string; hint: string; value: number | null }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-xs">
        <span className="font-medium text-espresso" title={hint}>
          {label}
        </span>
        <span className="font-semibold text-espresso tabular-nums">{value === null ? '—' : `${value}%`}</span>
      </div>
      <div className="mt-1.5 h-1.5 w-full rounded-full bg-muted overflow-hidden" aria-hidden="true">
        <div
          className="h-full rounded-full bg-navy transition-[width] duration-500"
          style={{ width: `${value ?? 0}%` }}
        />
      </div>
    </div>
  );
}

export function EvidenceQualityPanel({
  quality,
  isLoading,
}: {
  quality?: EvidenceQualityBreakdown;
  isLoading: boolean;
}) {
  const [summary, setSummary] = useState<LedgerSummary | null>(null);
  const [hovered, setHovered] = useState<LevelKey | null>(null);

  useEffect(() => {
    getLedgerSummary()
      .then(setSummary)
      .catch(() => setSummary(null));
  }, [quality?.total]);

  const total = quality?.total ?? 0;
  const highShare = pct(quality?.high ?? 0, total);
  const generated = summary ? summary.model_answers + summary.fallback_answers : 0;
  const modelShare = summary && generated > 0 ? pct(summary.model_answers, generated) : null;
  const selfServeShare = summary && summary.answers_recorded > 0 ? Math.round(summary.resolved_without_person_pct) : null;
  const hoveredLevel = LEVELS.find((l) => l.key === hovered);

  /** Horizontal centre of a segment in the stacked bar, as a % of its width. */
  const segmentCentre = (key: LevelKey) => {
    let before = 0;
    for (const l of LEVELS) {
      const share = total > 0 ? ((quality?.[l.key] ?? 0) / total) * 100 : 0;
      if (l.key === key) return before + share / 2;
      before += share;
    }
    return 50;
  };

  return (
    <div className="lg:col-span-4 min-w-0 h-full flex flex-col justify-between rounded-xl border border-border bg-card p-6 shadow-card">
      <div className="flex flex-col justify-center pb-4 border-b border-border/50 min-h-[58px]">
        <h3 className="text-lg font-display font-normal text-espresso">Evidence Quality</h3>
        <p className="text-xs text-muted-foreground mt-0.5">How well recorded answers are supported</p>
      </div>

      <div className="flex-1 min-h-[260px] flex flex-col justify-center py-4">
        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-10 w-24" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : quality && total > 0 ? (
          <div className="space-y-4">
            {/* Headline */}
            <div>
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-display font-normal text-espresso tabular-nums leading-none">
                  {highShare}%
                </span>
                <span className="text-xs font-medium text-espresso">high confidence</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1.5">
                of {total} recorded {total === 1 ? 'answer' : 'answers'}
              </p>
            </div>

            {/* Confidence split: one stacked bar; the top padding leaves room for its tooltip */}
            <div className="pt-6">
              <div className="relative">
                <div
                  className="flex h-3 w-full gap-[2px]"
                  role="img"
                  aria-label={LEVELS.map((l) => `${l.label} ${quality[l.key]} (${pct(quality[l.key], total)}%)`).join(', ')}
                >
                  {LEVELS.filter((l) => quality[l.key] > 0).map((l, i, shown) => (
                    <div
                      key={l.key}
                      onMouseEnter={() => setHovered(l.key)}
                      onMouseLeave={() => setHovered(null)}
                      className={`h-full transition-opacity ${i === 0 ? 'rounded-l' : ''} ${
                        i === shown.length - 1 ? 'rounded-r' : ''
                      } ${hovered && hovered !== l.key ? 'opacity-50' : ''}`}
                      style={{ width: `${(quality[l.key] / total) * 100}%`, backgroundColor: l.color, minWidth: 4 }}
                    />
                  ))}
                </div>
                {hoveredLevel && (
                  <div
                    className="absolute -top-9 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-card px-2.5 py-1.5 text-[11px] shadow-dropdown pointer-events-none"
                    style={{ left: `${Math.min(80, Math.max(20, segmentCentre(hoveredLevel.key)))}%` }}
                  >
                    <span className="font-semibold text-espresso">{hoveredLevel.label}</span>
                    <span className="text-muted-foreground">
                      {' '}· {quality[hoveredLevel.key]} answers · {pct(quality[hoveredLevel.key], total)}%
                    </span>
                  </div>
                )}
              </div>

              <ul className="mt-3 space-y-1.5 text-xs">
                {LEVELS.map((l) => (
                  <li
                    key={l.key}
                    className="flex items-center justify-between"
                    onMouseEnter={() => setHovered(l.key)}
                    onMouseLeave={() => setHovered(null)}
                  >
                    <span className="flex items-center gap-2 text-espresso">
                      <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: l.color }} />
                      {l.label}
                    </span>
                    <span className="tabular-nums text-muted-foreground">
                      <span className="font-semibold text-espresso">{quality[l.key]}</span> ·{' '}
                      {pct(quality[l.key], total)}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Supporting rates from the evidence ledger */}
            <div className="space-y-3 pt-4 border-t border-border/50">
              <RateRow
                label="Resolved without a person"
                hint="Answers recorded without a hand-off to a specialist"
                value={selfServeShare}
              />
              <RateRow
                label="Answered by the language model"
                hint="Share of answers written by the language model rather than the built-in fallback"
                value={modelShare}
              />
            </div>
          </div>
        ) : (
          <div className="h-[200px] flex flex-col items-center justify-center text-center text-xs text-muted-foreground border border-dashed border-border rounded-lg">
            <ShieldCheck className="h-6 w-6 text-caramel mb-2 opacity-60" />
            <span>No answers recorded yet.</span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-center pt-3 border-t border-border/40 text-[11px] text-muted-foreground text-center min-h-[40px]">
        All answers in the evidence ledger
      </div>
    </div>
  );
}
