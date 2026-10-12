import { FormEvent, useEffect, useRef, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { AlertTriangle, ArrowUp, CheckCircle2, ChevronRight, RefreshCw, ShieldCheck } from 'lucide-react';
import { QuestionInput } from '../components/explainer/QuestionInput';
import { QUICK_ACTIONS } from '../components/explainer/QuickPolicyActions';
import type { PolicyFeatureTab } from '../components/explainer/PolicyFeaturesPanel';
import { Skeleton } from '../components/ui/Skeleton';
import type { ConversationSummary } from '../types';
import { askerName, initials, outcomeBadge, shortWhen, useMyConversations } from '../lib/conversations';
import { currentEmployee } from '../services/auth';

const RECENT_COUNT = 5;
const ALL_PAGE = 20;

/** Quick actions start a question about a policy; the policy-number suggestions finish it. */
const ACTION_PROMPTS: Record<Exclude<PolicyFeatureTab, 'overview'>, string> = {
  coverages: 'What are the coverages, limits and deductibles on policy ',
  forms: 'Which forms and endorsements are attached to policy ',
  claims: 'What claims are on policy ',
  billing: 'What is the billing and payment status of policy ',
};

function OutcomeBadge({ outcome }: { outcome?: string | null }) {
  const { label, tone } = outcomeBadge(outcome);
  const style =
    tone === 'answered'
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
      : tone === 'review'
      ? 'bg-[#FFF1E6] text-[#9A3D09] ring-[#FDC9A0]'
      : 'bg-slate-100 text-slate-600 ring-slate-200';
  return (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${style}`}>
      {tone === 'answered' ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
      {label}
    </span>
  );
}

function timeGreeting(now = new Date()): string {
  const hour = now.getHours();
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

function ConversationRow({ conversation }: { conversation: ConversationSummary }) {
  const c = conversation;
  return (
    <li>
      <Link
        to={`/app/explainer/c/${c.conversation_id}`}
        className="group flex items-center gap-3.5 px-4 py-3.5 transition-colors hover:bg-[#F8FAFC] focus-visible:bg-[#FFF7ED] focus-visible:outline-none sm:px-5"
      >
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#0F2A43] text-[11px] font-bold text-white"
          aria-hidden="true"
        >
          {initials(c.asked_by.name, '··')}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13.5px] font-semibold text-[#0F2A43]" title={c.title}>
            {c.title}
          </p>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[12px] text-[#64748B]">
            <span className="font-medium text-[#475569]">{askerName(c.asked_by)}</span>
            <span className="font-mono text-[11px]">{c.asked_by.employee_id}</span>
            <span aria-hidden="true">·</span>
            {c.policy_number ? (
              <span className="font-mono text-[11.5px] text-[#0F2A43]">{c.policy_number}</span>
            ) : (
              <span>{c.customer_name || 'No policy'}</span>
            )}
            {c.question_count > 1 && (
              <>
                <span aria-hidden="true">·</span>
                <span>{c.question_count} questions</span>
              </>
            )}
          </p>
        </div>
        <span className="hidden shrink-0 text-[12px] text-[#64748B] sm:block">{shortWhen(c.last_activity_at)}</span>
        <OutcomeBadge outcome={c.latest_outcome} />
        <ChevronRight className="h-4 w-4 shrink-0 text-[#CBD5E1] transition-colors group-hover:text-[#EA580C]" aria-hidden="true" />
      </Link>
    </li>
  );
}

/**
 * Policy Explainer landing page: start a conversation, quick policy actions, and the signed-in
 * employee's own recent conversations. Only their conversations are listed; The Record is the
 * company-wide view.
 */
export function ExplainerLandingPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [input, setInput] = useState('');
  const [limit, setLimit] = useState(RECENT_COUNT);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { items, total, error, loading, reload } = useMyConversations('', limit);

  // Links from elsewhere (dashboard "ask again", ledger "open conversation", old ?q / ?conv URLs).
  const incoming = (location.state || {}) as { initialQuestion?: string; conversationId?: string };
  const forwardQuestion = incoming.initialQuestion || searchParams.get('q');
  const forwardConversation = incoming.conversationId || searchParams.get('conv');

  // Every visit focuses the composer, including "New conversation" pressed while already here.
  useEffect(() => {
    inputRef.current?.focus();
  }, [location.key]);

  if (forwardConversation) return <Navigate to={`/app/explainer/c/${forwardConversation}`} replace />;
  if (forwardQuestion) return <Navigate to="/app/explainer/new" replace state={{ initialQuestion: forwardQuestion }} />;

  const start = (e: FormEvent) => {
    e.preventDefault();
    const question = input.trim();
    if (!question) return;
    navigate('/app/explainer/new', { state: { initialQuestion: question } });
  };

  const startAction = (tab: Exclude<PolicyFeatureTab, 'overview'>) => {
    setInput(ACTION_PROMPTS[tab]);
    requestAnimationFrame(() => {
      const el = inputRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    });
  };

  const showingAll = limit > RECENT_COUNT;

  const firstName = currentEmployee()?.name?.split(/\s+/)[0];

  return (
    <div className="mx-auto max-w-[920px] space-y-8 pb-10 pt-2 sm:pt-6">
      <header>
        <h1 className="font-display text-[32px] leading-tight text-[#0F2A43]">
          {timeGreeting()}
          {firstName ? `, ${firstName}` : ''}
        </h1>
        <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-[#64748B]">
          Ask about any policy's coverage, limits, forms, claims or billing. Answers come from the policy's own wording,
          cite their sources, are checked by guardrails and are recorded in The Record.
        </p>
      </header>

      <section aria-label="New conversation" className="space-y-4">
        <form onSubmit={start}>
          <div className="flex items-center gap-2 rounded-2xl border border-[#CBD5E1] bg-white py-2 pl-5 pr-2 shadow-[0_6px_24px_rgba(15,42,67,0.07)] transition-colors focus-within:border-[#F97316] focus-within:ring-2 focus-within:ring-[#F97316]/20">
            <QuestionInput
              variant="bare"
              value={input}
              onChange={setInput}
              placeholder="Ask a policy question, or just say hi — name a policyholder or policy number"
              inputRef={inputRef}
            />
            <button
              type="submit"
              aria-label="Ask"
              disabled={!input.trim()}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#EA580C] text-white transition-colors hover:bg-[#C2410C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#E2E8F0] disabled:text-[#94A3B8] cursor-pointer"
            >
              <ArrowUp className="h-4 w-4" strokeWidth={2.5} />
            </button>
          </div>
        </form>

        <div>
          <h2 className="sr-only">Quick policy actions</h2>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
            {QUICK_ACTIONS.map(({ tab, title, description, icon: Icon }) => (
              <button
                key={tab}
                type="button"
                onClick={() => startAction(tab)}
                className="group flex flex-col gap-2.5 rounded-xl border border-[#E2E8F0] bg-white p-3.5 text-left transition-all hover:border-[#F97316] hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#FFF7ED] text-[#EA580C]">
                  <Icon className="h-4 w-4" />
                </span>
                <span>
                  <span className="block text-[13px] font-semibold text-[#0F2A43]">{title}</span>
                  <span className="mt-0.5 block text-[11.5px] leading-snug text-[#64748B]">{description}</span>
                </span>
              </button>
            ))}
          </div>
          <p className="mt-2.5 flex items-center gap-1.5 text-[11.5px] text-[#94A3B8]">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            An action starts the question; add a policy number and the suggestions complete it.
          </p>
        </div>
      </section>

      <section aria-labelledby="recent-conversations-heading">
        <div className="mb-3 flex items-end justify-between gap-3">
          <div>
            <h2 id="recent-conversations-heading" className="font-display text-xl text-[#0F2A43]">
              Recent conversations
            </h2>
            <p className="mt-0.5 text-[12.5px] text-[#64748B]">Your own conversations. The Record on the dashboard holds every answer.</p>
          </div>
          {items && total > RECENT_COUNT && (
            <button
              type="button"
              onClick={() => setLimit(showingAll ? RECENT_COUNT : ALL_PAGE)}
              className="shrink-0 text-[12.5px] font-semibold text-[#EA580C] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] cursor-pointer"
            >
              {showingAll ? 'Show fewer' : `View all ${total} →`}
            </button>
          )}
        </div>

        {loading && !items ? (
          <ul className="divide-y divide-[#F1F5F9] overflow-hidden rounded-xl border border-[#E2E8F0] bg-white" aria-label="Loading conversations">
            {Array.from({ length: 3 }, (_, i) => (
              <li key={i} className="flex items-center gap-3.5 px-5 py-3.5">
                <Skeleton className="h-9 w-9 rounded-full" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-2/3" />
                  <Skeleton className="h-3 w-1/3" />
                </div>
              </li>
            ))}
          </ul>
        ) : error && !items ? (
          <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
            <span>Your conversations could not be loaded. {error}</span>
            <button
              type="button"
              onClick={reload}
              className="inline-flex shrink-0 items-center gap-1 rounded-md border border-red-200 bg-white px-2.5 py-1 text-[12px] font-semibold hover:bg-red-100 cursor-pointer"
            >
              <RefreshCw className="h-3 w-3" /> Retry
            </button>
          </div>
        ) : items && items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[#CBD5E1] bg-white px-6 py-10 text-center">
            <p className="text-[14px] font-medium text-[#0F2A43]">No conversations yet. Ask your first policy question.</p>
            <p className="mt-1 text-[12.5px] text-[#64748B]">Your conversations will appear here.</p>
          </div>
        ) : (
          <>
            <ul className="divide-y divide-[#F1F5F9] overflow-hidden rounded-xl border border-[#E2E8F0] bg-white">
              {(items ?? []).map((c) => (
                <ConversationRow key={c.conversation_id} conversation={c} />
              ))}
            </ul>
            {showingAll && items && total > items.length && (
              <button
                type="button"
                onClick={() => setLimit((n) => n + ALL_PAGE)}
                disabled={loading}
                className="mt-3 w-full rounded-lg border border-[#E2E8F0] bg-white py-2 text-[12.5px] font-semibold text-[#0F2A43] hover:border-[#EA580C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] disabled:opacity-60 cursor-pointer"
              >
                {loading ? 'Loading…' : `Load more (${total - items.length} more)`}
              </button>
            )}
          </>
        )}
      </section>
    </div>
  );
}

export default ExplainerLandingPage;
