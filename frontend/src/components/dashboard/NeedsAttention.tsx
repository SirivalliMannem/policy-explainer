import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, ChevronDown, Loader2 } from 'lucide-react';
import { Skeleton } from '../ui/Skeleton';
import { LedgerDetailDrawer } from './LedgerDetailDrawer';
import { getNeedsAttention } from '../../services/api';
import { relativeTime } from '../../lib/explainer';
import type { AttentionCause, AttentionItem, AttentionReason, AttentionResponse } from '../../types';

type Range = 'today' | '7d' | '30d';
type Tab = 'queue' | 'gaps';

const RANGE_LABEL: Record<Range, string> = { today: 'today', '7d': 'in the last 7 days', '30d': 'in the last 30 days' };
const DAY_MS = 24 * 60 * 60 * 1000;
const COLLAPSED_ROWS = 5;

const TAG_STYLE: Record<AttentionReason, string> = {
  guardrail_flagged: 'bg-[#FFF1E6] text-[#9A3D09]',
  no_evidence: 'bg-[#FDECEC] text-[#A12A2A]',
  customer_not_found: 'bg-slate-100 text-slate-600',
  low_confidence: 'bg-[#E8EEF6] text-[#1F4A73]',
};

const EXAMPLES_LABEL: Record<AttentionReason, string> = {
  guardrail_flagged: 'Checks failed:',
  no_evidence: 'Unmatched terms:',
  customer_not_found: 'Asked:',
  low_confidence: 'Asked:',
};

function parseUtc(value: string): number {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`).getTime();
}

function isOld(item: AttentionItem): boolean {
  return Date.now() - parseUtc(item.first_asked_at) > DAY_MS;
}

function lineLabel(line?: string | null): string | null {
  if (!line) return null;
  const text = line.replace(/_/g, ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function Pill({ value, label, hot = false }: { value: string | number; label: string; hot?: boolean }) {
  return (
    <span
      className={`rounded-full border px-3 py-1 text-[12.5px] ${
        hot ? 'border-[#FDC9A0] bg-[#FFF1E6] text-[#9A3D09]' : 'border-border bg-slate-100 text-muted-foreground'
      }`}
    >
      <b className={`mr-1 font-bold ${hot ? 'text-orange-btn' : 'text-espresso'}`}>{value}</b>
      {label}
    </span>
  );
}

function QueueRow({
  item,
  open,
  onToggle,
  onOpenRecord,
  onAskAgain,
}: {
  item: AttentionItem;
  open: boolean;
  onToggle: () => void;
  onOpenRecord: () => void;
  onAskAgain: () => void;
}) {
  const old = isOld(item);
  const s = item.sources;
  const searched = s.coverages_searched + s.forms_searched + s.clauses_searched > 0;
  const detailId = `attention-${item.latest_entry_id}`;
  return (
    <li className="border-b border-slate-100">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={detailId}
        className="grid w-full grid-cols-[minmax(0,1fr)_20px] md:grid-cols-[minmax(0,1fr)_auto_auto_72px_20px] items-center gap-4 rounded-lg px-1 py-4 text-left hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <span className="min-w-0">
          <span className="block text-[14.5px] font-semibold leading-snug text-espresso">{item.question}</span>
          <span className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {item.policy_number && <code className="font-mono text-[11.5px] font-semibold text-espresso">{item.policy_number}</code>}
            {item.insured && <span>{item.insured}</span>}
            {lineLabel(item.line_of_business) && <span>· {lineLabel(item.line_of_business)}</span>}
            {!item.policy_number && !item.insured && <span>No policy selected</span>}
          </span>
          <span className={`mt-2 inline-block md:hidden rounded-full px-2.5 py-1 text-[11.5px] font-semibold ${TAG_STYLE[item.reason]}`}>
            {item.reason_label}
          </span>
        </span>
        <span className={`hidden md:inline-block whitespace-nowrap rounded-full px-2.5 py-1 text-[11.5px] font-semibold ${TAG_STYLE[item.reason]}`}>
          {item.reason_label}
        </span>
        <span className="hidden md:inline whitespace-nowrap text-xs text-muted-foreground">
          <b className="text-[13px] text-espresso">{item.times_asked}×</b> asked
        </span>
        <span
          className={`hidden md:block text-right text-xs ${old ? 'font-bold text-orange-btn' : 'text-muted-foreground'}`}
          title={`First asked ${new Date(parseUtc(item.first_asked_at)).toLocaleString()}`}
        >
          {relativeTime(item.first_asked_at)}
        </span>
        <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div id={detailId} className="grid gap-4 px-1 pb-5 md:grid-cols-[1.4fr_1fr] animate-fade-in opacity-0">
          <div className="rounded-xl border border-border bg-slate-50 p-4 text-[13px] leading-relaxed text-espresso">
            <h5 className="mb-1.5 text-[10.5px] font-semibold tracking-[0.08em] text-orange-btn">WHY IT WAS FLAGGED</h5>
            <p>{item.detail}</p>
            <p className="mt-2 text-xs text-muted-foreground md:hidden">
              Asked {item.times_asked}× · first {relativeTime(item.first_asked_at)}
            </p>
            {item.times_asked > 1 && (
              <p className="mt-2 hidden md:block text-xs text-muted-foreground">
                Asked {item.times_asked} times, most recently {relativeTime(item.last_asked_at).toLowerCase()}.
              </p>
            )}
          </div>
          <div className="rounded-xl border border-border bg-slate-50 p-4 text-[13px] leading-relaxed text-espresso">
            <h5 className="mb-1.5 text-[10.5px] font-semibold tracking-[0.08em] text-orange-btn">
              {s.citations.length ? 'SOURCES CITED' : 'SOURCES CHECKED'}
            </h5>
            {s.citations.length > 0 ? (
              <ul className="space-y-0.5">
                {s.citations.map((c) => (
                  <li key={c} className="font-mono text-[11.5px]">
                    {c}
                  </li>
                ))}
              </ul>
            ) : searched ? (
              <>
                <p>
                  Searched {s.coverages_searched} coverages, {s.forms_searched} forms and {s.clauses_searched} clauses
                  {item.policy_number ? ` on ${item.policy_number}` : ''}; none matched.
                </p>
                {s.query_terms.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {s.query_terms.map((t) => (
                      <code key={t} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11.5px]">
                        {t}
                      </code>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <p>Policy records were checked; no policy evidence applies.</p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onOpenRecord}
                className="rounded-lg border border-orange-btn bg-orange-btn px-3 py-1.5 text-[12.5px] font-semibold text-white transition-colors hover:bg-[#C2410C]"
              >
                Open record
              </button>
              <button
                type="button"
                onClick={onAskAgain}
                className="rounded-lg border border-border bg-white px-3 py-1.5 text-[12.5px] font-semibold text-espresso transition-colors hover:border-espresso"
              >
                Ask again
              </button>
            </div>
          </div>
        </div>
      )}
    </li>
  );
}

function CauseRow({ cause, first, animate }: { cause: AttentionCause; first: boolean; animate: boolean }) {
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_50px] md:grid-cols-[230px_minmax(0,1fr)_60px] items-center gap-x-5 gap-y-2 border-b border-slate-100 py-4 last:border-b-0">
      <div>
        <div className="text-sm font-bold text-espresso">{cause.label}</div>
        <div className="mt-0.5 text-xs text-muted-foreground">{cause.description}</div>
      </div>
      <div
        className="order-3 col-span-2 md:order-none md:col-span-1 h-2.5 overflow-hidden rounded-md bg-slate-100"
        role="img"
        aria-label={`${cause.label}: ${cause.count} answers, ${cause.share_pct}% of flagged`}
        title={`${cause.count} answers · ${cause.share_pct}% of flagged answers`}
      >
        <span
          className={`block h-full rounded-md transition-[width] duration-1000 ease-out ${first ? 'bg-orange-btn' : 'bg-[#1F4A73]'}`}
          style={{ width: animate ? `${Math.max(2, cause.share_pct)}%` : '0%' }}
        />
      </div>
      <div className="text-right font-mono text-sm font-bold text-espresso">{cause.count}</div>
      {cause.examples.length > 0 && (
        <div className="order-4 col-span-2 md:col-span-3 -mt-1 flex flex-wrap items-center gap-2 text-[12.5px] text-muted-foreground">
          {EXAMPLES_LABEL[cause.reason]}
          {cause.examples.map((e) => (
            <code key={e} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11.5px] text-espresso">
              {e}
            </code>
          ))}
        </div>
      )}
    </li>
  );
}

/**
 * Questions that need a person, from the evidence ledger: a review queue grouped by question,
 * and the causes behind them. No review workflow exists yet, so nothing is marked resolved;
 * the queue is everything flagged inside the selected range.
 */
export function NeedsAttention({ timeRange, refreshKey = 0 }: { timeRange: Range; refreshKey?: number }) {
  const navigate = useNavigate();
  const [data, setData] = useState<AttentionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [tab, setTab] = useState<Tab>('queue');
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [record, setRecord] = useState<string | null>(null);
  const [barsIn, setBarsIn] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    getNeedsAttention(timeRange)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setOpenKey((key) => key ?? res.items[0]?.latest_entry_id ?? null);
      })
      .catch(() => !cancelled && setFailed(true))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [timeRange, refreshKey]);

  // Grow the cause bars from zero each time the tab opens.
  useEffect(() => {
    if (tab !== 'gaps') return setBarsIn(false);
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setBarsIn(true)));
    return () => cancelAnimationFrame(id);
  }, [tab, data]);

  const items = data?.items ?? [];
  const causes = data?.causes ?? [];
  const shown = showAll ? items : items.slice(0, COLLAPSED_ROWS);
  const oldCount = items.filter(isOld).length;
  const repeatCount = items.filter((i) => i.times_asked > 1).length;
  const flaggedPct = data && data.answers_total ? Math.round((data.flagged_total / data.answers_total) * 100) : 0;
  const topCause = causes[0];

  const tabButton = (key: Tab, label: string, badge?: number) => (
    <button
      type="button"
      role="tab"
      aria-selected={tab === key}
      onClick={() => setTab(key)}
      className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
        tab === key ? 'bg-white text-espresso shadow-[0_1px_3px_rgba(15,42,67,0.15)]' : 'text-muted-foreground hover:text-espresso'
      }`}
    >
      {label}
      {badge !== undefined && badge > 0 && (
        <b className="rounded-full bg-orange px-1.5 py-px text-[11px] text-white tabular-nums">{badge}</b>
      )}
    </button>
  );

  return (
    <section className="rounded-2xl border border-border bg-card px-5 py-6 sm:px-7 shadow-card" aria-labelledby="attention-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 id="attention-heading" className="font-display text-[27px] font-normal leading-none text-espresso">
              Needs attention
            </h2>
            {loading && data && <Loader2 className="h-3.5 w-3.5 animate-spin text-caramel" aria-label="Updating" />}
          </div>
          <p className="mt-1.5 text-[13px] text-muted-foreground">
            Flagged questions and missing evidence that need a person
          </p>
        </div>
        <div role="tablist" aria-label="Needs attention view" className="flex rounded-[10px] border border-border bg-[#EEF2F7] p-[3px]">
          {tabButton('queue', 'Review queue', data?.questions_flagged)}
          {tabButton('gaps', 'Coverage gaps')}
        </div>
      </div>

      {loading && !data ? (
        <div className="mt-5 space-y-3 border-t border-border pt-4">
          <Skeleton className="h-7 w-80" />
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : failed ? (
        <p className="mt-5 border-t border-border py-8 text-center text-xs text-muted-foreground">
          This list could not be loaded. Try Refresh Data.
        </p>
      ) : !data || data.flagged_total === 0 ? (
        <div className="mt-5 flex flex-col items-center border-t border-border py-10 text-center">
          <CheckCircle2 className="mb-2 h-7 w-7 text-success" />
          <p className="text-sm font-medium text-espresso">Nothing needs attention {RANGE_LABEL[timeRange]}.</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Every one of {data?.answers_total ?? 0} recorded answers was grounded in policy evidence.
          </p>
        </div>
      ) : tab === 'queue' ? (
        <div key="queue" className="animate-fade-in opacity-0" role="tabpanel">
          <div className="mt-4 mb-1 flex flex-wrap gap-2.5 border-t border-border pt-4">
            {oldCount > 0 && <Pill hot value={oldCount} label="first flagged over 24h ago" />}
            <Pill value={repeatCount} label="asked more than once" />
            <Pill value={data.flagged_total} label={`flagged of ${data.answers_total} answers`} />
          </div>
          <ul>
            {shown.map((item) => (
              <QueueRow
                key={item.latest_entry_id}
                item={item}
                open={openKey === item.latest_entry_id}
                onToggle={() => setOpenKey((k) => (k === item.latest_entry_id ? null : item.latest_entry_id))}
                onOpenRecord={() => setRecord(item.latest_entry_id)}
                onAskAgain={() => navigate('/app/explainer', { state: { initialQuestion: item.question } })}
              />
            ))}
          </ul>
          <div className="flex items-center justify-between pt-4 text-[12.5px] text-muted-foreground">
            <span>
              Showing {shown.length} of {data.questions_flagged}, longest waiting first
            </span>
            {items.length > COLLAPSED_ROWS && (
              <button type="button" onClick={() => setShowAll((v) => !v)} className="font-bold text-orange-btn hover:underline">
                {showAll ? 'Show fewer' : `View all ${items.length} →`}
              </button>
            )}
          </div>
        </div>
      ) : (
        <div key="gaps" className="animate-fade-in opacity-0" role="tabpanel">
          <div className="mt-4 mb-1 flex flex-wrap gap-2.5 border-t border-border pt-4">
            <Pill hot value={data.flagged_total} label="answers need a person" />
            <Pill value={causes.length} label={causes.length === 1 ? 'cause' : 'causes'} />
            <Pill value={`${flaggedPct}%`} label="of recorded answers" />
          </div>
          <ul>
            {causes.map((c, i) => (
              <CauseRow key={c.reason} cause={c} first={i === 0} animate={barsIn} />
            ))}
          </ul>
          {topCause && (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-navy px-5 py-4 text-[13.5px] text-slate-200">
              <span>
                <b className="text-orange-gold">{topCause.label}</b> accounts for{' '}
                <b className="text-orange-gold">
                  {topCause.count} of {data.flagged_total}
                </b>{' '}
                flagged answers
                {topCause.reason === 'no_evidence' && topCause.examples.length > 0
                  ? ` — people asked about ${topCause.examples.slice(0, 2).join(' and ')}, and nothing in the indexed policy forms matched.`
                  : '.'}
              </span>
              <button
                type="button"
                onClick={() => setTab('queue')}
                className="rounded-lg border border-orange-btn bg-orange-btn px-3 py-1.5 text-[12.5px] font-semibold text-white transition-colors hover:bg-[#C2410C]"
              >
                See the questions
              </button>
            </div>
          )}
        </div>
      )}

      <LedgerDetailDrawer entryId={record} onClose={() => setRecord(null)} />
    </section>
  );
}
