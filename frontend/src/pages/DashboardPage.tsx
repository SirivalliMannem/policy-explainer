import { useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
} from 'recharts';
import { RefreshCw, Clock, AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Skeleton } from '../components/ui/Skeleton';
import { getDashboardStats } from '../services/api';
import { DashboardResponse } from '../types';
import { TheRecord } from '../components/dashboard/TheRecord';
import { MetricIllustration } from '../components/dashboard/MetricIllustration';
import { EvidenceQualityPanel } from '../components/dashboard/EvidenceQualityPanel';
import { MostAskedTopics } from '../components/dashboard/MostAskedTopics';

interface ActivityTooltipProps {
  active?: boolean;
  payload?: Array<{
    dataKey?: string;
    name?: string;
    value?: number;
    color?: string;
    payload?: {
      timestamp?: string;
      label?: string;
      questions_asked?: number;
      questions_answered?: number;
      insufficient_evidence?: number;
    };
  }>;
  label?: string;
  timeRange: 'today' | '7d' | '30d';
}

function CustomActivityTooltip({ active, payload, label, timeRange }: ActivityTooltipProps) {
  if (!active || !payload || !payload.length) return null;

  const currentPoint = payload[0]?.payload;
  const asked = currentPoint?.questions_asked ?? payload.find((p) => p.dataKey === 'questions_asked')?.value ?? 0;
  const answered = currentPoint?.questions_answered ?? payload.find((p) => p.dataKey === 'questions_answered')?.value ?? 0;
  const insufficient = currentPoint?.insufficient_evidence ?? payload.find((p) => p.dataKey === 'insufficient_evidence')?.value ?? 0;

  let periodTitle = label || 'Period';
  if (currentPoint?.timestamp) {
    try {
      const d = new Date(currentPoint.timestamp);
      if (!isNaN(d.getTime())) {
        if (timeRange === 'today') {
          periodTitle = `Today at ${label}`;
        } else {
          periodTitle = d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
        }
      }
    } catch {
      // fallback to label
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-3 shadow-dropdown text-xs min-w-[200px] pointer-events-none">
      <div className="flex items-center justify-between pb-1.5 mb-2 border-b border-border/60">
        <span className="font-display font-medium text-espresso text-xs tracking-tight">
          {periodTitle}
        </span>
        <span className="text-[10px] uppercase font-semibold tracking-wider text-muted-foreground">
          Policy Q&A
        </span>
      </div>
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-espresso font-medium">
            <span className="h-2 w-2 rounded-full bg-[#3B2418]" />
            Questions Asked
          </span>
          <span className="font-semibold text-espresso font-mono text-xs tabular-nums">
            {asked}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-caramel font-medium">
            <span className="h-2 w-2 rounded-full bg-[#A67C52]" />
            Questions Answered
          </span>
          <span className="font-semibold text-caramel font-mono text-xs tabular-nums">
            {answered}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-[#8C4A38] font-medium">
            <span className="h-2 w-2 rounded-full bg-[#8C4A38]" />
            Insufficient Evidence
          </span>
          <span className="font-semibold text-[#8C4A38] font-mono text-xs tabular-nums">
            {insufficient}
          </span>
        </div>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const [timeRange, setTimeRange] = useState<'today' | '7d' | '30d'>('7d');
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isRangeLoading, setIsRangeLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshCount, setRefreshCount] = useState(0);

  const loadData = async (range: 'today' | '7d' | '30d', isRangeChange = false) => {
    if (isRangeChange) {
      setIsRangeLoading(true);
    } else {
      setIsInitialLoading(true);
    }
    setError(null);
    try {
      const res = await getDashboardStats(range);
      setData(res);
    } catch {
      setError('Unable to load dashboard intelligence metrics. Please verify backend connection.');
    } finally {
      setIsInitialLoading(false);
      setIsRangeLoading(false);
    }
  };

  useEffect(() => {
    loadData(timeRange, false);
  }, []);

  const handleRangeChange = (newRange: 'today' | '7d' | '30d') => {
    if (newRange === timeRange || isRangeLoading) return;
    setTimeRange(newRange);
    loadData(newRange, true);
  };

  const hasActivityData = Boolean(
    data?.activity &&
      data.activity.length > 0 &&
      data.activity.some(
        (p) =>
          (p.questions_asked ?? 0) > 0 ||
          (p.questions_answered ?? 0) > 0 ||
          (p.insufficient_evidence ?? 0) > 0
      )
  );

  return (
    <div className="space-y-7 max-w-7xl mx-auto font-sans pb-10">
      {/* 1. HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-5">
        <div>
          <h1 className="text-2xl sm:text-3xl font-display font-normal text-espresso tracking-tight">
            Welcome!
          </h1>
          <p className="text-sm font-sans text-muted-foreground mt-0.5">
            Policy intelligence at a glance.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              loadData(timeRange, false);
              setRefreshCount((n) => n + 1);
            }}
            disabled={isInitialLoading || isRangeLoading}
            className="gap-2 text-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isInitialLoading ? 'animate-spin' : ''}`} />
            Refresh Data
          </Button>
        </div>
      </div>

      {/* ERROR STATE */}
      {error && (
        <div
          role="alert"
          className="rounded-xl border border-destructive/20 bg-destructive/10 p-4 text-xs font-medium text-destructive flex items-center justify-between"
        >
          <div className="flex items-center gap-2.5">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
          <Button variant="ghost" size="sm" onClick={() => loadData(timeRange, false)}>
            Retry
          </Button>
        </div>
      )}

      {/* 2. FOUR METRIC CARDS (EQUAL HEIGHT, EQUAL WIDTH) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5 items-stretch">
        {/* Card 1: Questions Answered */}
        <div className="h-full flex flex-col justify-between rounded-xl border border-border bg-card p-5 sm:p-6 shadow-card transition-shadow hover:shadow-dropdown">
          <div className="flex items-start justify-between gap-3">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">
                Questions Answered
              </span>
              {isInitialLoading ? (
                <Skeleton className="h-8 w-16 mt-2" />
              ) : (
                <div className="text-3xl font-display font-normal text-espresso mt-2">
                  {data?.metrics.questions_answered ?? 0}
                </div>
              )}
            </div>
            <MetricIllustration kind="answered" />
          </div>
          <div className="mt-4 pt-3 border-t border-border/50 text-xs text-muted-foreground">
            {isInitialLoading ? (
              <Skeleton className="h-4 w-28" />
            ) : (
              <span>Out of {data?.metrics.total_questions ?? 0} total queries</span>
            )}
          </div>
        </div>

        {/* Card 2: Resolution Rate */}
        <div className="h-full flex flex-col justify-between rounded-xl border border-border bg-card p-5 sm:p-6 shadow-card transition-shadow hover:shadow-dropdown">
          <div className="flex items-start justify-between gap-3">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">
                Resolution Rate
              </span>
              {isInitialLoading ? (
                <Skeleton className="h-8 w-20 mt-2" />
              ) : (
                <div className="text-3xl font-display font-normal text-espresso mt-2">
                  {data?.metrics.resolution_rate ?? 0}%
                </div>
              )}
            </div>
            <MetricIllustration kind="resolution" value={data?.metrics.resolution_rate ?? 0} />
          </div>
          <div className="mt-4 pt-3 border-t border-border/50 text-xs text-muted-foreground">
            {isInitialLoading ? (
              <Skeleton className="h-4 w-32" />
            ) : (
              <span>Grounded resolution ratio</span>
            )}
          </div>
        </div>

        {/* Card 3: Evidence Coverage */}
        <div className="h-full flex flex-col justify-between rounded-xl border border-border bg-card p-5 sm:p-6 shadow-card transition-shadow hover:shadow-dropdown">
          <div className="flex items-start justify-between gap-3">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">
                Evidence Coverage
              </span>
              {isInitialLoading ? (
                <Skeleton className="h-8 w-20 mt-2" />
              ) : (
                <div className="text-3xl font-display font-normal text-espresso mt-2">
                  {data?.metrics.evidence_coverage ?? 0}%
                </div>
              )}
            </div>
            <MetricIllustration kind="coverage" value={data?.metrics.evidence_coverage ?? 0} />
          </div>
          <div className="mt-4 pt-3 border-t border-border/50 text-xs text-muted-foreground">
            {isInitialLoading ? (
              <Skeleton className="h-4 w-36" />
            ) : (
              <span>Answers backed by policy citations</span>
            )}
          </div>
        </div>

        {/* Card 4: Low Confidence */}
        <div className="h-full flex flex-col justify-between rounded-xl border border-border bg-card p-5 sm:p-6 shadow-card transition-shadow hover:shadow-dropdown">
          <div className="flex items-start justify-between gap-3">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">
                Low Confidence
              </span>
              {isInitialLoading ? (
                <Skeleton className="h-8 w-14 mt-2" />
              ) : (
                <div className="text-3xl font-display font-normal text-espresso mt-2">
                  {data?.metrics.low_confidence ?? 0}
                </div>
              )}
            </div>
            <MetricIllustration kind="lowConfidence" />
          </div>
          <div className="mt-4 pt-3 border-t border-border/50 text-xs text-muted-foreground">
            {isInitialLoading ? (
              <Skeleton className="h-4 w-36" />
            ) : (
              <span>Queries flagged for specialist review</span>
            )}
          </div>
        </div>
      </div>

      {/* 3 & 4. POLICY QUESTIONS ACTIVITY + EVIDENCE QUALITY (IMMEDIATELY BELOW METRIC CARDS) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        {/* Left: Policy Questions Activity Chart (8 cols) */}
        <div className="lg:col-span-8 min-w-0 h-full flex flex-col justify-between rounded-xl border border-border bg-card p-6 shadow-card">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-border/50 min-h-[58px]">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-display font-normal text-espresso">
                  Policy Questions Activity
                </h3>
                {isRangeLoading && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-sans text-caramel">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    <span>Updating...</span>
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Volume and resolution distribution over time
              </p>
            </div>

            {/* Time range selector */}
            <div
              role="radiogroup"
              aria-label="Filter policy questions activity by time range"
              className="flex items-center rounded-lg border border-border bg-surface-subtle p-0.5 self-start sm:self-auto"
            >
              {(['today', '7d', '30d'] as const).map((range) => {
                const isSelected = timeRange === range;
                const label = range === 'today' ? 'Today' : range === '7d' ? '7 Days' : '30 Days';
                return (
                  <button
                    key={range}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    aria-label={`Show activity for ${label}`}
                    disabled={isRangeLoading}
                    onClick={() => handleRangeChange(range)}
                    onKeyDown={(e) => {
                      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                        e.preventDefault();
                        const ranges: Array<'today' | '7d' | '30d'> = ['today', '7d', '30d'];
                        const nextIdx = (ranges.indexOf(range) + 1) % ranges.length;
                        handleRangeChange(ranges[nextIdx]);
                      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                        e.preventDefault();
                        const ranges: Array<'today' | '7d' | '30d'> = ['today', '7d', '30d'];
                        const prevIdx = (ranges.indexOf(range) - 1 + ranges.length) % ranges.length;
                        handleRangeChange(ranges[prevIdx]);
                      }
                    }}
                    className={`px-3 py-1 text-xs font-medium rounded-md transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 ${
                      isSelected
                        ? 'bg-card text-espresso shadow-subtle font-semibold border border-border/60'
                        : 'text-muted-foreground hover:text-espresso hover:bg-card/60'
                    } ${isRangeLoading ? 'cursor-wait opacity-80' : 'cursor-pointer'}`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Chart Canvas Area */}
          <div className="flex-1 min-h-[260px] h-[260px] w-full pt-4 relative">
            {isInitialLoading ? (
              <div className="h-full flex items-center justify-center">
                <Skeleton className="h-[220px] w-full" />
              </div>
            ) : hasActivityData && data?.activity ? (
              <div className={`h-full w-full transition-opacity duration-200 ${isRangeLoading ? 'opacity-60 pointer-events-none' : 'opacity-100'}`}>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart
                    data={data.activity}
                    margin={{ top: 12, right: 12, left: -20, bottom: 4 }}
                  >
                    <CartesianGrid stroke="#EDE3D8" strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="label"
                      stroke="#75685E"
                      fontSize={11}
                      tickLine={false}
                      axisLine={{ stroke: '#D8CBBE' }}
                      dy={4}
                    />
                    <YAxis
                      stroke="#75685E"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                      allowDecimals={false}
                      dx={-4}
                    />
                    <RechartsTooltip
                      cursor={{ stroke: '#A67C52', strokeWidth: 1.5, strokeDasharray: '3 3' }}
                      content={<CustomActivityTooltip timeRange={timeRange} />}
                    />
                    <Line
                      type="monotone"
                      dataKey="questions_asked"
                      name="Questions Asked"
                      stroke="#3B2418"
                      strokeWidth={2.5}
                      dot={{ r: 3.5, fill: '#3B2418', stroke: '#FFFCF8', strokeWidth: 1.5 }}
                      activeDot={{ r: 6, fill: '#3B2418', stroke: '#FFFCF8', strokeWidth: 2 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="questions_answered"
                      name="Questions Answered"
                      stroke="#A67C52"
                      strokeWidth={2.5}
                      dot={{ r: 3.5, fill: '#A67C52', stroke: '#FFFCF8', strokeWidth: 1.5 }}
                      activeDot={{ r: 6, fill: '#A67C52', stroke: '#FFFCF8', strokeWidth: 2 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="insufficient_evidence"
                      name="Insufficient Evidence"
                      stroke="#8C4A38"
                      strokeWidth={2}
                      strokeDasharray="4 4"
                      dot={{ r: 3, fill: '#8C4A38', stroke: '#FFFCF8', strokeWidth: 1.5 }}
                      activeDot={{ r: 5.5, fill: '#8C4A38', stroke: '#FFFCF8', strokeWidth: 2 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-[260px] flex flex-col items-center justify-center text-center p-6 border border-dashed border-border/80 rounded-lg bg-surface-subtle/30">
                <Clock className="h-6 w-6 text-caramel/70 mb-2 opacity-60" />
                <p className="text-sm font-medium text-espresso">No policy questions in this period.</p>
                <p className="text-xs text-muted-foreground mt-0.5">Real question activity will plot here as inquiries are recorded.</p>
              </div>
            )}
          </div>

          {/* Chart Legend */}
          <div className="flex flex-wrap items-center justify-center gap-6 pt-3 border-t border-border/40 text-xs text-muted-foreground min-h-[40px]">
            <span className="flex items-center gap-1.5 font-medium text-espresso">
              <span className="h-2.5 w-2.5 rounded-full bg-[#3B2418]" /> Questions Asked
            </span>
            <span className="flex items-center gap-1.5 font-medium text-espresso">
              <span className="h-2.5 w-2.5 rounded-full bg-[#A67C52]" /> Questions Answered
            </span>
            <span className="flex items-center gap-1.5 font-medium text-espresso">
              <span className="h-2.5 w-2.5 rounded-full bg-[#8C4A38]" /> Insufficient Evidence
            </span>
          </div>
        </div>

        {/* Right: Evidence Quality (4 cols, EQUAL HEIGHT) */}
        <EvidenceQualityPanel quality={data?.evidence_quality} isLoading={isInitialLoading} />
      </div>

      {/* 5. MOST-ASKED TOPICS */}
      <MostAskedTopics timeRange={timeRange} refreshKey={refreshCount} />

      {/* 7. EVIDENCE LEDGER — THE RECORD */}
      <TheRecord />
    </div>
  );
}

export default DashboardPage;
