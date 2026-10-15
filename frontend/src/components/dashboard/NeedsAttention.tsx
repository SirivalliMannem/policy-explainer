import { useEffect, useState } from 'react';
import { CheckCircle2, ChevronDown, History, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Skeleton } from '../ui/Skeleton';
import { LedgerDetailDrawer } from './LedgerDetailDrawer';
import { ApiError, getNeedsAttention, getResolutionLog } from '../../services/api';
import { formatDateTime, relativeTime } from '../../lib/explainer';
import type { AttentionItem, AttentionReason, AttentionResolution, AttentionResolveResponse, AttentionResponse } from '../../types';
import { ResolveBox } from './ResolveBox';

type Range = 'today' | '7d' | '30d';

const RANGE_LABEL: Record<Range, string> = { today: 'today', '7d': 'in the last 7 days', '30d': 'in the last 30 days' };
const DAY_MS = 24 * 60 * 60 * 1000;
const COLLAPSED_ROWS = 5;

const TAG_STYLE: Record<AttentionReason, string> = {
  guardrail_flagged: 'bg-[#FFF1E6] text-[#9A3D09]',
  no_evidence: 'bg-[#FDECEC] text-[#A12A2A]',
  customer_not_found: 'bg-slate-100 text-slate-600',
  low_confidence: 'bg-[#E8EEF6] text-[#1F4A73]',
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
  onClosed,
}: {
  item: AttentionItem;
  open: boolean;
  onToggle: () => void;
  onOpenRecord: () => void;
  onClosed: (result: AttentionResolveResponse, summary: string) => void;
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
          {item.rerun_of && (
            <span className="mt-0.5 block text-[11.5px] text-[#9A3D09]">re-run of “{item.rerun_of.question}”</span>
          )}
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
          title={`Last asked ${new Date(parseUtc(item.last_asked_at)).toLocaleString()} · first asked ${new Date(
            parseUtc(item.first_asked_at)
          ).toLocaleString()}`}
        >
          {relativeTime(item.last_asked_at)}
        </span>
        <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div id={detailId} className="grid gap-4 px-1 pb-5 md:grid-cols-2 animate-fade-in opacity-0">
          <div className="rounded-xl border border-border bg-slate-50 p-4 text-[13px] leading-relaxed text-espresso">
            <h5 className="mb-1.5 text-[10.5px] font-semibold tracking-[0.08em] text-orange-btn">WHY IT WAS FLAGGED</h5>
            <p>{item.detail}</p>
            {item.times_asked > 1 && (
              <p className="mt-2 text-xs text-muted-foreground">
                Asked {item.times_asked} times, most recently {relativeTime(item.last_asked_at).toLowerCase()}.
              </p>
            )}
            <h5 className="mb-1.5 mt-4 text-[10.5px] font-semibold tracking-[0.08em] text-orange-btn">
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
            <button
              type="button"
              onClick={onOpenRecord}
              className="mt-3 rounded-lg border border-border bg-white px-3 py-1.5 text-[12.5px] font-semibold text-espresso transition-colors hover:border-espresso"
            >
              Open record
            </button>
          </div>
          <ResolveBox item={item} onClosed={onClosed} />
        </div>
      )}
    </li>
  );
}

/**
 * Questions that need a person, from the evidence ledger, grouped by question. Opening one shows
 * why it was flagged and the actions that resolve it; a resolved question leaves the queue (and
 * comes back if it is asked again). Resolutions are recorded; ledger entries are never changed.
 */
export function NeedsAttention({ timeRange, refreshKey = 0 }: { timeRange: Range; refreshKey?: number }) {
  const [data, setData] = useState<AttentionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState<string | null>(null);
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [record, setRecord] = useState<string | null>(null);
  const [resolvedNote, setResolvedNote] = useState<{ text: string; conversationId?: string } | null>(null);
  const [reload, setReload] = useState(0);
  const [showLog, setShowLog] = useState(false);
  const [log, setLog] = useState<AttentionResolution[] | null>(null);

  useEffect(() => {
    if (!showLog) return;
    let cancelled = false;
    getResolutionLog(timeRange)
      .then((rows) => !cancelled && setLog(rows))
      .catch(() => !cancelled && setLog([]));
    return () => {
      cancelled = true;
    };
  }, [showLog, timeRange, reload]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(null);
    getNeedsAttention(timeRange)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setOpenKey((key) => key ?? res.items[0]?.latest_entry_id ?? null);
      })
      .catch((err) => {
        if (cancelled) return;
        // 404: the backend predates this panel's endpoint and needs a restart (or image rebuild).
        setFailed(
          err instanceof ApiError && err.status === 404
            ? 'The backend is running an older version without this panel. Restart the backend (or rebuild its Docker image) to load it.'
            : 'This list could not be loaded. Try Refresh Data.'
        );
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [timeRange, refreshKey, reload]);

  const items = data?.items ?? [];
  const shown = showAll ? items : items.slice(0, COLLAPSED_ROWS);
  const oldCount = items.filter(isOld).length;
  const repeatCount = items.filter((i) => i.times_asked > 1).length;

  const markClosed = (item: AttentionItem, result: AttentionResolveResponse, summary: string) => {
    // Leave the queue at once; the reload brings the counts (and any re-run item) up to date.
    setData((d) => (d ? { ...d, items: d.items.filter((i) => i.latest_entry_id !== item.latest_entry_id) } : d));
    setOpenKey(null);
    const answer = result.new_answer;
    setResolvedNote({
      text: answer
        ? answer.flagged
          ? `${summary}. Closed. The new answer was flagged too, so it is in the queue as a re-run.`
          : `${summary}. Closed: the new answer is grounded.`
        : `${summary}. Closed.`,
      conversationId: answer?.conversation_id,
    });
    setReload((n) => n + 1);
  };

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
        {data && data.questions_flagged > 0 && (
          <span className="rounded-full bg-orange px-2.5 py-1 text-[12px] font-bold text-white tabular-nums">
            {data.questions_flagged} in queue
          </span>
        )}
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
          {failed}
        </p>
      ) : !data || items.length === 0 ? (
        <div className="mt-5 flex flex-col items-center border-t border-border py-10 text-center">
          <CheckCircle2 className="mb-2 h-7 w-7 text-success" />
          <p className="text-sm font-medium text-espresso">Nothing needs attention {RANGE_LABEL[timeRange]}.</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {data?.questions_resolved
              ? `${data.questions_resolved} flagged ${data.questions_resolved === 1 ? 'question was' : 'questions were'} resolved; the rest of the ${data.answers_total} recorded answers were grounded in policy evidence.`
              : `Every one of ${data?.answers_total ?? 0} recorded answers was grounded in policy evidence.`}
          </p>
          {resolvedNote && <p className="mt-2 text-xs font-semibold text-success">{resolvedNote.text}</p>}
        </div>
      ) : (
        <div key="queue" className="animate-fade-in opacity-0">
          <div className="mt-4 mb-1 flex flex-wrap gap-2.5 border-t border-border pt-4">
            {oldCount > 0 && <Pill hot value={oldCount} label="first flagged over 24h ago" />}
            <Pill value={repeatCount} label="asked more than once" />
            <Pill value={data.flagged_total} label={`flagged of ${data.answers_total} answers`} />
            {(data.questions_resolved ?? 0) > 0 && <Pill value={data.questions_resolved ?? 0} label="resolved" />}
          </div>
          {resolvedNote && (
            <p role="status" className="mt-2 flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-2 text-[12.5px] font-medium text-emerald-800">
              <CheckCircle2 className="h-4 w-4 shrink-0" /> {resolvedNote.text}
              {resolvedNote.conversationId && (
                <Link to={`/app/explainer/c/${resolvedNote.conversationId}`} className="ml-auto font-semibold underline">
                  Open the answer
                </Link>
              )}
            </p>
          )}
          <ul>
            {shown.map((item) => (
              <QueueRow
                key={item.latest_entry_id}
                item={item}
                open={openKey === item.latest_entry_id}
                onToggle={() => setOpenKey((k) => (k === item.latest_entry_id ? null : item.latest_entry_id))}
                onOpenRecord={() => setRecord(item.latest_entry_id)}
                onClosed={(result, summary) => markClosed(item, result, summary)}
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

      )}

      {data && !failed && (
        <div className="mt-4 border-t border-border pt-3">
          <button
            type="button"
            onClick={() => setShowLog((v) => !v)}
            aria-expanded={showLog}
            className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-espresso hover:text-orange-btn"
          >
            <History className="h-4 w-4" /> Resolution log
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${showLog ? 'rotate-180' : ''}`} />
          </button>
          {showLog && (
            <div className="mt-2">
              <p className="mb-2 text-[11.5px] text-muted-foreground">
                Each closure is recorded here. The original flagged record is unchanged in the Audit Log.
              </p>
              {log === null ? (
                <Skeleton className="h-10 w-full" />
              ) : log.length === 0 ? (
                <p className="text-[12.5px] text-muted-foreground">Nothing was closed {RANGE_LABEL[timeRange]}.</p>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {log.map((r) => (
                    <li key={r.id} className="py-2 text-[12.5px] text-espresso">
                      <span className="font-semibold">{r.action_label}</span>
                      <span className="text-muted-foreground"> · {formatDateTime(r.resolved_at)} · {r.resolved_by_name || 'Name not recorded'} </span>
                      <span className="font-mono text-[11px] text-muted-foreground">{r.resolved_by}</span>
                      <span className="block">“{r.question}”</span>
                      {r.new_question && (
                        <span className="block text-[#334155]">
                          → asked “{r.new_question}”
                          {r.new_entry_id && (
                            <Link to={`/app/audit-log?entry=${encodeURIComponent(r.new_entry_id)}`} className="ml-1.5 font-semibold text-orange-btn hover:underline">
                              new answer
                            </Link>
                          )}
                        </span>
                      )}
                      {r.note && <span className="block text-muted-foreground">Reason: {r.note}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      <LedgerDetailDrawer entryId={record} onClose={() => setRecord(null)} />
    </section>
  );
}
