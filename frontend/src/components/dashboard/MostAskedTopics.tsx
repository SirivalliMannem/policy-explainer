import { useEffect, useState } from 'react';
import { FileText, Loader2 } from 'lucide-react';
import { Skeleton } from '../ui/Skeleton';
import { getDashboardTopics } from '../../services/api';
import type { TopicItem, TopicsResponse } from '../../types';

type Range = 'today' | '7d' | '30d';

const RANGE_LABEL: Record<Range, string> = { today: 'today', '7d': 'in the last 7 days', '30d': 'in the last 30 days' };

function lineLabel(line?: string | null): string | null {
  if (!line) return null;
  const text = line.replace(/_/g, ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** The most-cited form, set apart on the brand navy. */
function Spotlight({ topic, answers }: { topic: TopicItem; answers: number }) {
  const r = 30;
  const c = 2 * Math.PI * r;
  const line = lineLabel(topic.line_of_business);
  return (
    <div className="relative overflow-hidden rounded-xl bg-navy p-6 text-white h-full flex flex-col justify-between">
      <div
        className="absolute inset-0 pointer-events-none opacity-60"
        style={{
          backgroundImage: 'radial-gradient(rgba(249,115,22,0.22) 1.2px, transparent 1.2px)',
          backgroundSize: '22px 22px',
        }}
        aria-hidden="true"
      />
      <div
        className="absolute w-56 h-56 rounded-full bg-orange blur-[90px] opacity-25 -right-16 -bottom-16 pointer-events-none"
        aria-hidden="true"
      />

      <div className="relative">
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-orange-gold">Most cited form</span>
        <div className="mt-3 font-mono text-sm font-semibold text-white/90">{topic.form_number}</div>
        <div className="mt-1 font-display text-xl leading-snug text-white">{topic.title}</div>
        {line && (
          <span className="mt-3 inline-block rounded-full border border-white/20 px-2.5 py-0.5 text-[11px] text-white/80">
            {line}
          </span>
        )}
      </div>

      <div className="relative mt-6 flex items-center gap-4">
        <svg width="76" height="76" viewBox="0 0 76 76" aria-hidden="true" className="shrink-0">
          <circle cx="38" cy="38" r={r} fill="none" stroke="rgba(255,255,255,0.14)" strokeWidth="7" />
          <circle
            cx="38"
            cy="38"
            r={r}
            fill="none"
            stroke="#F97316"
            strokeWidth="7"
            strokeLinecap="round"
            strokeDasharray={`${(Math.min(100, topic.share_pct) / 100) * c} ${c}`}
            transform="rotate(-90 38 38)"
            style={{ transition: 'stroke-dasharray 0.6s ease-out' }}
          />
        </svg>
        <div>
          <div className="font-display text-4xl leading-none tabular-nums">{Math.round(topic.share_pct)}%</div>
          <div className="mt-1.5 text-xs text-white/70">
            of answers cite it · {topic.count} of {answers}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * The policy forms recorded answers cite most. One answer that cites a form several times
 * counts once, so each bar is "% of answers that cite this form" on a 0–100% track.
 * View only: rows are not links.
 */
export function MostAskedTopics({ timeRange, refreshKey = 0 }: { timeRange: Range; refreshKey?: number }) {
  const [data, setData] = useState<TopicsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    getDashboardTopics(timeRange)
      .then((res) => !cancelled && setData(res))
      .catch(() => !cancelled && setFailed(true))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [timeRange, refreshKey]);

  const topics = data?.topics ?? [];
  const answers = data?.answers_considered ?? 0;

  return (
    <section className="rounded-xl border border-border bg-card p-6 sm:p-7 shadow-card" aria-labelledby="topics-heading">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 pb-4 border-b border-border/50">
        <div>
          <div className="flex items-center gap-2">
            <h2 id="topics-heading" className="text-xl sm:text-2xl font-display font-normal text-espresso leading-none">
              Most-asked topics
            </h2>
            {loading && data && <Loader2 className="h-3.5 w-3.5 animate-spin text-caramel" aria-label="Updating" />}
          </div>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1.5">
            Policy forms cited most often in answers {RANGE_LABEL[timeRange]}
          </p>
        </div>
        {data && answers > 0 && (
          <dl className="flex items-center gap-2 text-xs">
            <div className="rounded-lg border border-border bg-surface-subtle px-3 py-1.5">
              <dt className="sr-only">Answers with citations</dt>
              <dd>
                <span className="font-semibold text-espresso tabular-nums">{answers}</span>{' '}
                <span className="text-muted-foreground">{answers === 1 ? 'answer' : 'answers'}</span>
              </dd>
            </div>
            <div className="rounded-lg border border-border bg-surface-subtle px-3 py-1.5">
              <dt className="sr-only">Distinct forms cited</dt>
              <dd>
                <span className="font-semibold text-espresso tabular-nums">{data.forms_cited}</span>{' '}
                <span className="text-muted-foreground">{data.forms_cited === 1 ? 'form cited' : 'forms cited'}</span>
              </dd>
            </div>
          </dl>
        )}
      </div>

      <div className={`pt-5 transition-opacity ${loading && data ? 'opacity-60' : ''}`}>
        {loading && !data ? (
          <div className="grid gap-5 lg:grid-cols-12">
            <Skeleton className="h-56 w-full lg:col-span-4" />
            <div className="space-y-4 lg:col-span-8">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          </div>
        ) : failed ? (
          <p className="py-8 text-center text-xs text-muted-foreground">Topics could not be loaded. Try Refresh Data.</p>
        ) : topics.length === 0 ? (
          <div className="py-10 flex flex-col items-center text-center border border-dashed border-border rounded-lg">
            <FileText className="h-6 w-6 text-caramel/70 mb-2" />
            <p className="text-sm font-medium text-espresso">No cited forms {RANGE_LABEL[timeRange]}.</p>
            <p className="text-xs text-muted-foreground mt-0.5">Forms appear here once answers cite them.</p>
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-12 items-stretch">
            <div className="lg:col-span-4">
              <Spotlight topic={topics[0]} answers={answers} />
            </div>

            <div className="lg:col-span-8 flex flex-col">
              <ol className="flex-1 flex flex-col justify-around gap-1">
                {topics.map((t, i) => {
                  const line = lineLabel(t.line_of_business);
                  const isHovered = hovered === t.form_number;
                  return (
                    <li
                      key={t.form_number}
                      onMouseEnter={() => setHovered(t.form_number)}
                      onMouseLeave={() => setHovered(null)}
                      className={`grid grid-cols-[2rem_minmax(0,1fr)] sm:grid-cols-[2rem_minmax(0,16rem)_minmax(0,1fr)] items-center gap-x-3 gap-y-2 rounded-lg px-2 py-2.5 transition-colors cursor-default ${
                        isHovered ? 'bg-surface-subtle' : ''
                      }`}
                    >
                      <span
                        className={`flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-semibold tabular-nums ${
                          i === 0 ? 'bg-orange-btn text-white' : 'bg-muted text-espresso'
                        }`}
                        aria-label={`Rank ${i + 1}`}
                      >
                        {i + 1}
                      </span>
                      <span className="min-w-0">
                        <span className="flex items-center gap-2">
                          <span className="font-mono text-xs font-semibold text-espresso">{t.form_number}</span>
                          {line && (
                            <span className="rounded-full bg-muted px-1.5 py-px text-[10px] text-muted-foreground">{line}</span>
                          )}
                        </span>
                        <span className="block truncate text-xs text-muted-foreground" title={t.title}>
                          {t.title}
                        </span>
                      </span>
                      <span className="col-start-2 sm:col-start-auto flex items-center gap-3 min-w-0">
                        <span className="relative flex-1">
                          <span className="relative block h-2.5 rounded-full bg-muted overflow-hidden">
                            <span
                              className="absolute inset-y-0 left-0 rounded-full bg-orange-btn transition-[width] duration-500"
                              style={{ width: `${Math.max(1.5, Math.min(100, t.share_pct))}%` }}
                            />
                          </span>
                          {isHovered && (
                            <span
                              role="tooltip"
                              className="absolute left-0 bottom-full mb-2 z-10 whitespace-nowrap rounded-md border border-border bg-card px-2.5 py-1.5 text-[11px] shadow-dropdown pointer-events-none"
                            >
                              <span className="font-semibold text-espresso">{t.form_number}</span>
                              <span className="text-muted-foreground">
                                {' '}· cited in {t.count} of {answers} answers ({t.share_pct}%)
                              </span>
                            </span>
                          )}
                        </span>
                        <span className="w-20 shrink-0 text-right text-xs tabular-nums">
                          <span className="font-semibold text-espresso">{t.count}</span>
                          <span className="text-muted-foreground"> · {Math.round(t.share_pct)}%</span>
                        </span>
                      </span>
                    </li>
                  );
                })}
              </ol>
              <p className="mt-3 px-2 text-[11px] text-muted-foreground">
                Bars show the share of answers that cite each form; one answer can cite several forms.
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
