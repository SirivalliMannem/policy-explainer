import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUpRight, FileText, Loader2 } from 'lucide-react';
import { Skeleton } from '../ui/Skeleton';
import { getDashboardTopics } from '../../services/api';
import type { TopicsResponse } from '../../types';

type Range = 'today' | '7d' | '30d';

const RANGE_LABEL: Record<Range, string> = { today: 'today', '7d': 'in the last 7 days', '30d': 'in the last 30 days' };

/**
 * The policy forms recorded answers cite most, as one bar per form. One answer that cites a
 * form several times counts once, so the share reads "% of answers that cite this form".
 */
export function MostAskedTopics({ timeRange, refreshKey = 0 }: { timeRange: Range; refreshKey?: number }) {
  const navigate = useNavigate();
  const [data, setData] = useState<TopicsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

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
  const maxCount = Math.max(1, ...topics.map((t) => t.count));

  const askAbout = (formNumber: string, title: string) =>
    navigate('/app/explainer', { state: { initialQuestion: `What does form ${formNumber} (${title}) cover?` } });

  return (
    <section className="rounded-xl border border-border bg-card p-6 sm:p-7 shadow-card" aria-labelledby="topics-heading">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2 pb-4 border-b border-border/50">
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
        {data && data.answers_considered > 0 && (
          <span className="text-xs text-muted-foreground">
            From <span className="font-semibold text-espresso tabular-nums">{data.answers_considered}</span>{' '}
            {data.answers_considered === 1 ? 'answer' : 'answers'}
          </span>
        )}
      </div>

      <div className={`pt-4 transition-opacity ${loading && data ? 'opacity-60' : ''}`}>
        {loading && !data ? (
          <div className="space-y-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ) : failed ? (
          <p className="py-8 text-center text-xs text-muted-foreground">Topics could not be loaded. Try Refresh Data.</p>
        ) : topics.length === 0 ? (
          <div className="py-8 flex flex-col items-center text-center border border-dashed border-border rounded-lg">
            <FileText className="h-6 w-6 text-caramel/70 mb-2" />
            <p className="text-sm font-medium text-espresso">No cited forms {RANGE_LABEL[timeRange]}.</p>
            <p className="text-xs text-muted-foreground mt-0.5">Forms appear here once answers cite them.</p>
          </div>
        ) : (
          <>
            <ul className="space-y-1">
              {topics.map((t) => (
                <li key={t.form_number}>
                  <button
                    type="button"
                    onClick={() => askAbout(t.form_number, t.title)}
                    title={`${t.form_number} — ${t.title}\nCited in ${t.count} of ${data?.answers_considered} answers (${t.share_pct}%)\nClick to ask about this form`}
                    className="group w-full grid grid-cols-[minmax(0,15rem)_1fr] sm:grid-cols-[minmax(0,18rem)_1fr] items-center gap-4 rounded-lg px-2 py-2 text-left hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    <span className="min-w-0">
                      <span className="flex items-center gap-1.5">
                        <span className="font-mono text-xs font-semibold text-espresso">{t.form_number}</span>
                        <ArrowUpRight className="h-3 w-3 text-caramel opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 transition-opacity" />
                      </span>
                      <span className="block truncate text-xs text-muted-foreground">{t.title}</span>
                    </span>
                    <span className="flex items-center gap-3 min-w-0">
                      <span className="flex-1 h-2.5 rounded-r bg-transparent">
                        <span
                          className="block h-full rounded-r bg-orange-btn transition-[width] duration-500"
                          style={{ width: `${Math.max(2, (t.count / maxCount) * 100)}%` }}
                        />
                      </span>
                      <span className="w-24 shrink-0 text-right text-xs tabular-nums">
                        <span className="font-semibold text-espresso">{t.count}</span>
                        <span className="text-muted-foreground"> · {Math.round(t.share_pct)}%</span>
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <p className="mt-3 px-2 text-[11px] text-muted-foreground">
              Count = answers citing the form · % of answers that cite it. Select a form to ask about it.
            </p>
          </>
        )}
      </div>
    </section>
  );
}
