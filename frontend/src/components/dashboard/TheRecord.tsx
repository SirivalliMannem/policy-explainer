import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, ChevronLeft, ChevronRight, RefreshCw, Search, X } from 'lucide-react';
import { getLedger, getLedgerFilters, getLedgerSummary } from '../../services/api';
import type { LedgerFilters, LedgerPage, LedgerQuery, LedgerSummary } from '../../types';
import { describeError, formatDate, formatDateTime, formatMs, lineLabel } from '../../lib/explainer';
import { GuardrailStatusBadge } from '../explainer/GuardrailSummary';
import { ConfidenceBadge, OutcomeBadge } from './RecordBadges';
import { LedgerDetailDrawer } from './LedgerDetailDrawer';


const PAGE_SIZE = 10;

const DATE_RANGES: { value: string; label: string; days: number | null }[] = [
  { value: '', label: 'Any date', days: null },
  { value: 'today', label: 'Today', days: 0 },
  { value: '7d', label: 'Last 7 days', days: 6 },
  { value: '30d', label: 'Last 30 days', days: 29 },
];

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-[#E2E8F0] bg-white px-4 py-3.5">
      <span className="block text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">{label}</span>
      <span className="mt-1 block text-2xl font-bold tabular-nums text-[#0F2A43]">{value}</span>
      <span className="mt-0.5 block text-[11px] leading-snug text-[#94A3B8]">{note}</span>
    </div>
  );
}

function Select({
  value,
  onChange,
  children,
  label,
}: {
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
  label: string;
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 rounded-lg border border-[#E2E8F0] bg-white px-2.5 text-[12px] text-[#0F2A43] focus:border-[#F97316] focus:outline-none focus:ring-2 focus:ring-[#F97316]/20"
    >
      {children}
    </select>
  );
}

/** "The Record": every recorded policy answer, from the Evidence Ledger. */
export function TheRecord() {
  const [summary, setSummary] = useState<LedgerSummary | null>(null);
  const [filters, setFilters] = useState<LedgerFilters | null>(null);
  const [page, setPage] = useState<LedgerPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [insured, setInsured] = useState('');
  const [state, setState] = useState('');
  const [line, setLine] = useState('');
  const [outcome, setOutcome] = useState('');
  const [range, setRange] = useState('');
  const [sort, setSort] = useState<NonNullable<LedgerQuery['sort']>>('newest');
  const [offset, setOffset] = useState(0);

  // Debounce free-text search so typing does not issue a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(searchInput.trim());
      setOffset(0);
    }, 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const days = DATE_RANGES.find((r) => r.value === range)?.days;
    try {
      const [s, f, p] = await Promise.all([
        getLedgerSummary(),
        getLedgerFilters(),
        getLedger({
          search,
          insured,
          state,
          line,
          outcome,
          date_from: days === null || days === undefined ? undefined : isoDaysAgo(days),
          sort,
          limit: PAGE_SIZE,
          offset,
        }),
      ]);
      setSummary(s);
      setFilters(f);
      setPage(p);
    } catch (err) {
      setError(describeError(err).message);
    } finally {
      setLoading(false);
    }
  }, [search, insured, state, line, outcome, range, sort, offset]);

  useEffect(() => {
    load();
  }, [load]);

  const resetTo = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setOffset(0);
  };
  const hasFilters = Boolean(searchInput || insured || state || line || outcome || range || sort !== 'newest');
  const clearFilters = () => {
    setSearchInput('');
    setSearch('');
    setInsured('');
    setState('');
    setLine('');
    setOutcome('');
    setRange('');
    setSort('newest');
    setOffset(0);
  };

  const total = page?.total ?? 0;
  const from = total ? offset + 1 : 0;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <section className="space-y-4" aria-labelledby="the-record-title">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <span className="text-[10.5px] font-bold uppercase tracking-[0.16em] text-[#F97316]">Evidence Ledger</span>
          <h2 id="the-record-title" className="mt-0.5 text-2xl font-bold tracking-tight text-[#0F2A43]">
            The Record
          </h2>
          <p className="mt-0.5 max-w-2xl text-[13px] text-[#64748B]">
            Every policy question, answer, source, model decision, guardrail result, and outcome is traceable.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-1.5 self-start rounded-lg border border-[#E2E8F0] bg-white px-3 py-1.5 text-[12px] font-semibold text-[#0F2A43] hover:border-[#F97316] disabled:opacity-60 sm:self-auto cursor-pointer"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Metric
          label="Answers recorded"
          value={summary ? String(summary.answers_recorded) : '—'}
          note={summary ? `${summary.model_answers} by the model · ${summary.fallback_answers} by fallback` : 'Loading'}
        />
        <Metric
          label="Carrier source"
          value={summary ? `${summary.carrier_source_pct}%` : '—'}
          note={summary ? `${summary.carrier_source_count} cite the insured's own forms or schedule` : 'Loading'}
        />
        <Metric
          label="Resolved without a person"
          value={summary ? `${summary.resolved_without_person_pct}%` : '—'}
          note={summary ? `${summary.resolved_without_person_count} answered with guardrails passed` : 'Loading'}
        />
        <Metric
          label="P95 response"
          value={summary ? formatMs(summary.p95_response_ms) : '—'}
          note="Backend → AI service → answer, per question"
        />
        <Metric
          label="Waiting on a person"
          value={summary ? String(summary.waiting_on_person) : '—'}
          note="Flagged by guardrails or insufficient evidence"
        />
      </div>

      <div className="overflow-hidden rounded-xl border border-[#E2E8F0] bg-white shadow-sm">
        <div className="flex flex-wrap items-center gap-2 border-b border-[#E2E8F0] bg-[#F8FAFC] p-3">
          <div className="relative min-w-[14rem] flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#94A3B8]" />
            <input
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search question, answer, policy or insured"
              aria-label="Search the record"
              className="h-9 w-full rounded-lg border border-[#E2E8F0] bg-white pl-8 pr-3 text-[12px] text-[#0F2A43] placeholder-[#94A3B8] focus:border-[#F97316] focus:outline-none focus:ring-2 focus:ring-[#F97316]/20"
            />
          </div>
          <Select label="Insured" value={insured} onChange={resetTo(setInsured)}>
            <option value="">All insureds</option>
            {filters?.insureds.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
          <Select label="State" value={state} onChange={resetTo(setState)}>
            <option value="">All states</option>
            {filters?.states.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>
          <Select label="Line" value={line} onChange={resetTo(setLine)}>
            <option value="">All lines</option>
            {filters?.lines.map((l) => (
              <option key={l} value={l}>
                {lineLabel(l)}
              </option>
            ))}
          </Select>
          <Select label="Outcome" value={outcome} onChange={resetTo(setOutcome)}>
            <option value="">All outcomes</option>
            <option value="answered">Answered</option>
            <option value="needs_review">Needs review</option>
            <option value="insufficient_evidence">Insufficient evidence</option>
          </Select>
          <Select label="Date" value={range} onChange={resetTo(setRange)}>
            {DATE_RANGES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
          <Select label="Sort" value={sort} onChange={resetTo((v: string) => setSort(v as NonNullable<LedgerQuery['sort']>))}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="slowest">Slowest first</option>
            <option value="fastest">Fastest first</option>
          </Select>
          {hasFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="inline-flex h-9 items-center gap-1 rounded-lg px-2 text-[12px] font-semibold text-[#64748B] hover:text-[#0F2A43] cursor-pointer"
            >
              <X className="h-3.5 w-3.5" /> Clear
            </button>
          )}
        </div>

        {error && (
          <div className="flex items-center gap-2 border-b border-red-200 bg-red-50 px-4 py-2.5 text-[12px] text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0" /> Unable to load the record: {error}
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full min-w-[1180px] border-collapse text-left text-[12px]">
            <thead>
              <tr className="border-b border-[#E2E8F0] text-[10px] font-bold uppercase tracking-[0.12em] text-[#64748B]">
                {['When', 'Agent', 'Insured', 'Question', 'Policy version', 'Sources', 'Model', 'Confidence', 'Guardrail', 'Outcome', 'Reviewer'].map(
                  (h) => (
                    <th key={h} className="whitespace-nowrap px-3 py-2.5 font-bold">
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F1F5F9]">
              {page?.items.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => setSelected(row.id)}
                  onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setSelected(row.id)}
                  tabIndex={0}
                  className="cursor-pointer align-top transition-colors hover:bg-[#FFF7ED]/60 focus:bg-[#FFF7ED] focus:outline-none"
                >
                  <td className="whitespace-nowrap px-3 py-2.5 text-[#475569]">{formatDateTime(row.created_at)}</td>
                  <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[11px] text-[#475569]">{row.agent ?? '—'}</td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <span className="font-semibold text-[#0F2A43]">{row.insured ?? '—'}</span>
                    {row.answer_type !== 'portfolio' && (
                      <span className="block text-[10.5px] text-[#94A3B8]">
                        {lineLabel(row.line_of_business)} · {row.state ?? '—'}
                      </span>
                    )}
                  </td>
                  <td className="min-w-[16rem] max-w-[22rem] px-3 py-2.5 text-[#0F2A43]">
                    <span className="line-clamp-2">{row.question}</span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    {row.answer_type === 'portfolio' ? (
                      <>
                        <span className="font-semibold text-[#0F2A43]">Portfolio</span>
                        <span className="block text-[10.5px] text-[#94A3B8]">Policy records lookup</span>
                      </>
                    ) : (
                      <>
                        <span className="font-mono font-semibold text-[#0F2A43]">{row.policy_number ?? '—'}</span>
                        <span className="block text-[10.5px] text-[#94A3B8]">
                          Term {row.policy_term ?? '—'} · eff. {formatDate(row.policy_effective)}
                        </span>
                      </>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex max-w-[13rem] flex-wrap gap-1">
                      {row.sources.slice(0, 2).map((s) => (
                        <span
                          key={s}
                          className="whitespace-nowrap rounded border border-[#FDBA74] bg-[#FFF7ED] px-1.5 py-px font-mono text-[10.5px] font-semibold text-[#C2410C]"
                        >
                          {s}
                        </span>
                      ))}
                      {row.source_count > 2 && <span className="text-[10.5px] text-[#94A3B8]">+{row.source_count - 2}</span>}
                      {row.source_count === 0 && <span className="text-[#94A3B8]">—</span>}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[11px] text-[#475569]">
                    {row.model_used && row.model_used !== 'none' ? row.model_used : row.answer_type === 'portfolio' ? 'none (records)' : '—'}
                    {row.is_fallback && <span className="block text-[10.5px] text-amber-700">fallback engine</span>}
                    {row.latency_ms !== null && row.latency_ms !== undefined && (
                      <span className="block text-[10.5px] text-[#94A3B8]">{formatMs(row.latency_ms)}</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <ConfidenceBadge confidence={row.confidence} />
                  </td>
                  <td className="px-3 py-2.5">
                    <GuardrailStatusBadge status={row.guardrail_status} />
                  </td>
                  <td className="px-3 py-2.5">
                    <OutcomeBadge outcome={row.outcome} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[#94A3B8]" title="No review workflow has been configured">
                    {row.reviewer ?? '—'}
                  </td>
                </tr>
              ))}
              {page && page.items.length === 0 && (
                <tr>
                  <td colSpan={11} className="px-4 py-12 text-center text-[12.5px] text-[#64748B]">
                    {hasFilters ? 'No recorded answers match these filters.' : 'No answers have been recorded yet.'}
                  </td>
                </tr>
              )}
              {!page && loading && (
                <tr>
                  <td colSpan={11} className="px-4 py-12 text-center text-[12.5px] text-[#64748B]">
                    Loading the record…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between border-t border-[#E2E8F0] px-4 py-2.5 text-[11.5px] text-[#64748B]">
          <span>
            {from}–{to} of {total} recorded answers
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={offset === 0 || loading}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              aria-label="Previous page"
              className="rounded-md border border-[#E2E8F0] p-1 disabled:opacity-40 enabled:hover:border-[#F97316] cursor-pointer"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              disabled={to >= total || loading}
              onClick={() => setOffset(offset + PAGE_SIZE)}
              aria-label="Next page"
              className="rounded-md border border-[#E2E8F0] p-1 disabled:opacity-40 enabled:hover:border-[#F97316] cursor-pointer"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <LedgerDetailDrawer entryId={selected} onClose={() => setSelected(null)} />
    </section>
  );
}
