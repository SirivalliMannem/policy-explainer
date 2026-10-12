import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, ArrowLeft, Send } from 'lucide-react';
import type { AskedBy, EvidenceItem, PolicyContextCandidate, QuestionResolution, SourceTarget } from '../types';
import {
  ApiError,
  clearConversationContext,
  createConversation,
  getConversation,
  getConversationMessages,
  resolvePolicyContext,
  resolvePolicyFromQuestion,
  setConversationContext,
  submitQuestion,
} from '../services/api';
import { currentEmployee } from '../services/auth';
import { PolicyContextBanner } from '../components/explainer/PolicyContextBanner';
import { PolicyFeaturesPanel, PolicyFeatureTab } from '../components/explainer/PolicyFeaturesPanel';
import { ChatMessage, ConversationStream } from '../components/explainer/ConversationStream';
import { QuestionInput } from '../components/explainer/QuestionInput';
import { SourceViewer } from '../components/explainer/SourceViewer';
import { AIProcessPanel, AuditTarget, PanelContent } from '../components/explainer/AIProcessPanel';
import { Skeleton } from '../components/ui/Skeleton';
import {
  FriendlyError,
  IDLE_PROCESS,
  ProcessState,
  StageKey,
  describeError,
  freshStages,
  interpretedText,
} from '../lib/explainer';
import { notifyConversationsChanged } from '../lib/conversations';

const MATCH_LABEL: Record<string, string> = {
  policy_number: 'policy number',
  customer_name: 'policyholder name',
  surname: 'surname',
  first_name: 'first name',
};

/** Wide enough for the chat column and the docked AI process panel side by side. */
const DOCK_QUERY = '(min-width: 1000px)';

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia?.(query).matches ?? true);
  useEffect(() => {
    const list = window.matchMedia?.(query);
    if (!list) return;
    const update = () => setMatches(list.matches);
    update();
    list.addEventListener('change', update);
    return () => list.removeEventListener('change', update);
  }, [query]);
  return matches;
}

const FILLER_WORDS = new Set([
  'it', 'its', "it's", 'is', 'the', 'for', 'on', 'about', 'policy', 'customer', 'policyholder', 'please',
  'check', 'use', 'that', 'one', 'this', 'their', 'his', 'her', 'number', 'insured', 'account',
]);

function nowTime(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function timeOf(iso: string): string {
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  return isNaN(d.getTime()) ? '' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/** The signed-in employee, as shown on questions asked in this session. */
function me(): AskedBy | null {
  const employee = currentEmployee();
  return employee ? { employee_id: employee.employeeId, name: employee.name, role: employee.role } : null;
}

/** Clarification replies are short ("Margaret Chen", "HO-2847-1193"); a full question is a new question. */
function looksLikeReply(text: string): boolean {
  return !text.includes('?') && (text.match(/\S+/g) || []).length <= 4;
}

/** True when a message only names a policy ("Margaret Chen", "it's HO-2847-1193") rather than asking something new. */
function isBareReference(text: string, resolution: QuestionResolution): boolean {
  if (text.includes('?')) return false;
  let rest = text.toLowerCase();
  for (const ref of (resolution.reference || '').split(',')) {
    if (ref.trim()) rest = rest.split(ref.trim().toLowerCase()).join(' ');
  }
  const words = (rest.match(/[a-z0-9'-]+/g) || []).filter((w) => !FILLER_WORDS.has(w));
  return words.length <= 1;
}

/**
 * The conversation screen: `/app/explainer/new` for a new conversation, `/app/explainer/c/:id` for
 * an existing one. History is read from stored answers only; nothing is re-run to display it.
 */
export function ExplainerPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { conversationId: routeConversationId } = useParams<{ conversationId?: string }>();

  const [activePolicy, setActivePolicyState] = useState<PolicyContextCandidate | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [process, setProcess] = useState<ProcessState>(IDLE_PROCESS);
  const [isWorking, setIsWorking] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [loadError, setLoadError] = useState<FriendlyError | null>(null);
  const [featureTab, setFeatureTab] = useState<PolicyFeatureTab | null>(null);
  const [highlight, setHighlight] = useState<{ type: 'coverage' | 'form'; id: string } | null>(null);
  const [sourceTarget, setSourceTarget] = useState<SourceTarget | null>(null);
  const [panel, setPanel] = useState<PanelContent | null>(null);
  const [panelAutoFocus, setPanelAutoFocus] = useState(false);
  const docked = useMediaQuery(DOCK_QUERY);

  // Refs mirror state for async flows that must not read stale closures.
  const conversationRef = useRef<string | null>(null);
  const policyRef = useRef<PolicyContextCandidate | null>(null);
  const pendingQuestionRef = useRef<string | null>(null);
  const busyRef = useRef(false);
  const panelOpenerRef = useRef<HTMLElement | null>(null);
  const idRef = useRef(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const newVisitRef = useRef<string | null>(null);
  const loadIdRef = useRef(0);

  const setActivePolicy = (policy: PolicyContextCandidate | null) => {
    policyRef.current = policy;
    setActivePolicyState(policy);
  };
  const nextId = (prefix: string) => `${prefix}-${++idRef.current}`;
  const push = (msg: ChatMessage) => setMessages((prev) => [...prev, msg]);

  /** Mark whichever stage was in flight as failed, with the reason in plain language, and stop. */
  const failProcess = (friendly: FriendlyError) =>
    setProcess((prev) => {
      const stages = { ...prev.stages };
      let failed = false;
      (Object.keys(stages) as StageKey[]).forEach((key) => {
        if (stages[key].status === 'processing' && !failed) {
          const repeatsTitle = friendly.message.toLowerCase().startsWith(friendly.title.toLowerCase());
          stages[key] = { status: 'failed', detail: repeatsTitle ? friendly.message : `${friendly.title}. ${friendly.message}` };
          failed = true;
        } else if (stages[key].status === 'waiting' || stages[key].status === 'processing') {
          stages[key] = { status: 'skipped', detail: 'Not run: an earlier step failed.' };
        }
      });
      return { ...prev, phase: 'failed', stages, result: null };
    });

  /** Open the AI process panel. `opener` is the button that asked for it; focus returns there on close. */
  const openPanel = (content: PanelContent, opener: HTMLElement | null) => {
    panelOpenerRef.current = opener;
    setPanelAutoFocus(Boolean(opener));
    setPanel(content);
  };

  const closePanel = useCallback(() => {
    setPanel(null);
    const opener = panelOpenerRef.current;
    panelOpenerRef.current = null;
    if (opener && opener.isConnected) opener.focus();
    else inputRef.current?.focus();
  }, []);

  /** A conversation is created only when the first question is asked, then gets its own URL. */
  const ensureConversation = async (): Promise<string> => {
    if (conversationRef.current) return conversationRef.current;
    const conv = await createConversation();
    conversationRef.current = conv.conversation_id;
    navigate(`/app/explainer/c/${conv.conversation_id}`, { replace: true });
    return conv.conversation_id;
  };

  /** Stages 2–6: submit to the backend, which answers it (AI service or policy records) and records the Evidence Ledger. */
  // The backend answers in one request, so stages 2–6 are reported together when it returns: step 2
  // shows as in progress until then, and every value shown afterwards is the one the pipeline measured.
  const runPipeline = async (question: string, convId: string, contextDetail: string) => {
    setProcess((prev) => ({
      ...prev,
      phase: 'running',
      result: null,
      question,
      contextDetail,
      stages: { ...freshStages(), context: { status: 'completed', detail: contextDetail }, retrieve: { status: 'processing' } },
    }));

    try {
      const result = await submitQuestion(convId, question);
      setProcess((prev) => ({
        ...prev,
        phase: 'completed',
        result,
        askedBy: result.asked_by ?? prev.askedBy,
        askedAt: result.asked_at ?? prev.askedAt,
      }));
      push({ kind: 'answer', id: nextId('answer'), time: nowTime(), question, result });
    } catch (err) {
      const friendly = describeError(err);
      failProcess(friendly);
      push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
    }
    notifyConversationsChanged();
  };

  /** Clear the conversation view before opening another conversation or starting a new one. */
  const resetView = () => {
    loadIdRef.current += 1;
    setIsLoadingHistory(false);
    setMessages([]);
    setActivePolicy(null);
    pendingQuestionRef.current = null;
    setFeatureTab(null);
    setHighlight(null);
    setSourceTarget(null);
    setPanel(null);
    panelOpenerRef.current = null;
    setLoadError(null);
    setProcess(IDLE_PROCESS);
  };

  const askForPolicy = (text: string, candidates: PolicyContextCandidate[], stageDetail: string) => {
    push({ kind: 'clarify', id: nextId('clarify'), time: nowTime(), text, candidates });
    setProcess((prev) => ({
      phase: 'needs_input',
      result: null,
      stages: { ...prev.stages, context: { status: 'attention', detail: stageDetail } },
    }));
  };

  const handleAsk = async (raw: string) => {
    const text = raw.trim();
    if (!text || busyRef.current) return;
    busyRef.current = true;
    setIsWorking(true);
    setInput('');
    const askedAt = new Date().toISOString();
    push({ kind: 'user', id: nextId('user'), time: nowTime(), text, askedBy: me(), askedAt });
    setProcess({
      phase: 'running',
      result: null,
      question: text,
      askedBy: me(),
      askedAt,
      contextDetail: null,
      stages: { ...freshStages(), context: { status: 'processing' } },
    });
    // A new question opens the AI process panel without taking focus from the composer.
    openPanel({ mode: 'live' }, null);

    try {
      let convId: string;
      try {
        convId = await ensureConversation();
      } catch (err) {
        const friendly = describeError(err);
        failProcess(friendly);
        push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
        return;
      }

      // Stage 1: identify policy context from the question (server-side resolution).
      const current = policyRef.current;
      setIsResolving(!current);
      let resolution: QuestionResolution;
      try {
        // A reply to a clarification is resolved together with the question it answers, so the
        // question's wording ("water backup", "my car") can narrow a policyholder's policies.
        const pending = pendingQuestionRef.current;
        resolution = await resolvePolicyFromQuestion(
          pending && looksLikeReply(text) ? `${text} — ${pending}` : text,
          convId
        );
      } catch (err) {
        const friendly = describeError(err);
        failProcess(friendly);
        push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
        return;
      } finally {
        setIsResolving(false);
      }

      const understood = interpretedText(resolution.interpretation);
      const understoodNote = understood ? ` · understood as “${understood}”` : '';

      // Customer / portfolio questions are answered from policy records. They need no single-policy
      // context, and they neither change the active context nor ask which policy to check.
      if (resolution.intent === 'portfolio') {
        const subject = resolution.reference ? `Customer question · ${resolution.reference}` : 'Portfolio question · whole book';
        await runPipeline(text, convId, `Portfolio lookup · ${subject} — answered from policy records${understoodNote}`);
        return;
      }

      let question = text;
      let contextDetail: string;

      if (resolution.status === 'resolved' && resolution.policy) {
        const resolved = resolution.policy;
        // A reply that only names the policy answers the question we were waiting on.
        const pending = pendingQuestionRef.current;
        if (pending && isBareReference(text, resolution)) {
          question = pending;
        }
        pendingQuestionRef.current = null;
        if (!current || current.policy_id !== resolved.policy_id) {
          try {
            await setConversationContext(convId, resolved.policy_id);
          } catch (err) {
            const friendly = describeError(err);
            failProcess(friendly);
            push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
            return;
          }
          setActivePolicy(resolved);
          setFeatureTab(null);
          push({
            kind: 'context',
            id: nextId('context'),
            time: nowTime(),
            policy: resolved,
            matchedOn: resolution.matched_on,
            switched: Boolean(current),
            answering: question !== text ? question : undefined,
          });
        }
        contextDetail = `${resolved.customer_name} · ${resolved.policy_number} — matched on ${
          MATCH_LABEL[resolution.matched_on || ''] || 'reference'
        }${understoodNote}`;
      } else if (resolution.status === 'ambiguous') {
        if (current && resolution.candidates.some((c) => c.policy_id === current.policy_id)) {
          contextDetail = `Using active context · ${current.policy_number}${understoodNote}`;
        } else {
          pendingQuestionRef.current = pendingQuestionRef.current ?? text;
          askForPolicy(
            `${resolution.message} Which policy should I check?`,
            resolution.candidates,
            'Several policies match — waiting for the employee to choose'
          );
          return;
        }
      } else if (resolution.status === 'not_found') {
        pendingQuestionRef.current = pendingQuestionRef.current ?? text;
        askForPolicy(
          `${resolution.message} Which policy or policyholder should I check?`,
          [],
          `${resolution.reference} did not match a policy on file`
        );
        return;
      } else if (current) {
        contextDetail = `Using active context · ${current.policy_number}${understoodNote}`;
      } else {
        pendingQuestionRef.current = text;
        askForPolicy('Which policy or policyholder should I check?', [], 'No policy named and no active context');
        return;
      }

      await runPipeline(question, convId, contextDetail);
    } finally {
      busyRef.current = false;
      setIsWorking(false);
      inputRef.current?.focus();
    }
  };

  const handleChooseCandidate = async (candidate: PolicyContextCandidate) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setIsWorking(true);
    try {
      const convId = await ensureConversation();
      await setConversationContext(convId, candidate.policy_id);
      const previous = policyRef.current;
      setActivePolicy(candidate);
      setFeatureTab(null);
      const pending = pendingQuestionRef.current;
      pendingQuestionRef.current = null;
      push({
        kind: 'context',
        id: nextId('context'),
        time: nowTime(),
        policy: candidate,
        matchedOn: null,
        switched: Boolean(previous),
        answering: pending ?? undefined,
      });
      if (pending) {
        await runPipeline(pending, convId, `${candidate.customer_name} · ${candidate.policy_number} — selected by employee`);
      } else {
        setProcess(IDLE_PROCESS);
      }
    } catch (err) {
      const friendly = describeError(err);
      failProcess(friendly);
      push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
    } finally {
      busyRef.current = false;
      setIsWorking(false);
    }
  };

  const handleClearContext = async () => {
    const convId = conversationRef.current;
    setActivePolicy(null);
    setFeatureTab(null);
    pendingQuestionRef.current = null;
    if (convId) {
      try {
        await clearConversationContext(convId);
      } catch (err) {
        const friendly = describeError(err);
        push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
      }
    }
  };

  const openTab = useCallback(
    (tab: PolicyFeatureTab, target?: { type: 'coverage' | 'form'; id: string }) => {
      if (!policyRef.current) return;
      setHighlight(target ?? null);
      setFeatureTab((open) => (open === tab && !target ? null : tab));
    },
    []
  );

  const openSource = useCallback((item: EvidenceItem) => {
    setSourceTarget({ sourceType: item.source_type, sourceId: item.source_id, evidence: item });
  }, []);

  const showAudit = useCallback((target: AuditTarget, opener: HTMLElement) => {
    panelOpenerRef.current = opener;
    setPanelAutoFocus(true);
    setPanel({ mode: 'history', target });
  }, []);

  const showProcess = useCallback((opener: HTMLElement) => {
    panelOpenerRef.current = opener;
    setPanelAutoFocus(true);
    setPanel({ mode: 'live' });
  }, []);

  /** Reopen a recorded conversation from stored answers; nothing is asked again. */
  const loadConversation = async (convId: string) => {
    const conv = await getConversation(convId);
    if (conv.policy_context && conversationRef.current === convId) {
      setActivePolicy(await resolvePolicyContext(conv.policy_context.policy_id));
    }
    const records = await getConversationMessages(convId);
    const restored: ChatMessage[] = [];
    for (const record of records) {
      restored.push({
        kind: 'user',
        id: nextId('user'),
        time: timeOf(record.created_at),
        text: record.question,
        askedBy: record.asked_by,
        askedAt: record.created_at,
      });
      if (record.answer) {
        restored.push({
          kind: 'answer',
          id: nextId('answer'),
          time: timeOf(record.created_at),
          question: record.question,
          result: record.answer,
        });
      } else if (record.status === 'failed') {
        restored.push({
          kind: 'error',
          id: nextId('error'),
          time: timeOf(record.created_at),
          title: 'Not answered',
          text: 'The AI service could not be reached when this question was asked.',
        });
      }
    }
    if (conversationRef.current === convId) setMessages(restored);
  };

  // Follow the URL: a conversation id opens that conversation; /new starts an empty one.
  // Written to be safe when React runs it twice for the same URL (StrictMode in development).
  useEffect(() => {
    // Already showing this conversation (including one this page just created by asking).
    if (routeConversationId && routeConversationId === conversationRef.current) return;
    // Already started this visit to /new.
    if (!routeConversationId && newVisitRef.current === location.key) return;

    resetView();
    conversationRef.current = routeConversationId ?? null;
    if (!routeConversationId) {
      newVisitRef.current = location.key;
      const state = (location.state || {}) as { initialQuestion?: string };
      if (state.initialQuestion) {
        navigate(location.pathname, { replace: true, state: null });
        handleAsk(state.initialQuestion);
      } else {
        inputRef.current?.focus();
      }
      return;
    }

    const convId = routeConversationId;
    const load = ++loadIdRef.current;
    setIsLoadingHistory(true);
    loadConversation(convId)
      .catch((err) => {
        if (load !== loadIdRef.current) return; // the employee has moved on
        conversationRef.current = null;
        setLoadError(
          err instanceof ApiError && err.status === 404
            ? { title: 'Conversation not available', message: 'It does not exist or belongs to another employee.' }
            : describeError(err)
        );
      })
      .finally(() => load === loadIdRef.current && setIsLoadingHistory(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeConversationId]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    handleAsk(input);
  };

  return (
    <div className="flex h-[calc(100vh-6rem)] w-full sm:h-[calc(100vh-7rem)] lg:h-[calc(100vh-8rem)]">
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="mx-auto flex w-full max-w-[780px] flex-col gap-3">
          <PolicyContextBanner
            policy={activePolicy}
            isResolving={isResolving}
            openTab={featureTab}
            onOpenTab={(tab) => openTab(tab)}
            onClear={handleClearContext}
          />

          {activePolicy && featureTab && (
            <PolicyFeaturesPanel
              policyId={activePolicy.policy_id}
              activeTab={featureTab}
              onTabChange={(tab) => {
                setHighlight(null);
                setFeatureTab(tab);
              }}
              targetHighlight={highlight}
              isOpen
              onToggleOpen={() => setFeatureTab(null)}
            />
          )}
        </div>

        <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-[#E2E8F0] bg-white shadow-sm">
          {isLoadingHistory ? (
            <div className="mx-auto w-full max-w-[780px] flex-1 space-y-5 px-4 py-6" aria-label="Loading conversation">
              <Skeleton className="ml-auto h-12 w-2/3 rounded-2xl" />
              <Skeleton className="h-40 w-full rounded-2xl" />
              <Skeleton className="ml-auto h-12 w-1/2 rounded-2xl" />
            </div>
          ) : loadError ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
              <AlertCircle className="h-7 w-7 text-red-600" aria-hidden="true" />
              <p className="text-[15px] font-semibold text-[#0F2A43]">{loadError.title}</p>
              <p className="max-w-md text-[13px] text-[#64748B]">{loadError.message}</p>
              <Link
                to="/app/explainer"
                className="mt-1 inline-flex items-center gap-1.5 rounded-lg border border-[#E2E8F0] px-3 py-1.5 text-[12.5px] font-semibold text-[#0F2A43] hover:border-[#EA580C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C]"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> Back to Policy Explainer
              </Link>
            </div>
          ) : (
            <ConversationStream
              messages={messages}
              isWorking={isWorking}
              process={process}
              onShowAudit={showAudit}
              onShowProcess={showProcess}
              activePolicy={activePolicy}
              onAsk={handleAsk}
              onChooseCandidate={handleChooseCandidate}
              onOpenSource={openSource}
              onOpenTab={openTab}
            />
          )}

          <div className="border-t border-[#E2E8F0] bg-[#F8FAFC] p-3 sm:p-4">
            <form onSubmit={onSubmit} className="mx-auto flex w-full max-w-[780px] items-center gap-2">
              <QuestionInput
                value={input}
                onChange={setInput}
                disabled={isWorking || isLoadingHistory || Boolean(loadError)}
                placeholder={activePolicy ? `Ask about ${activePolicy.customer_name}'s policy...` : 'Ask a policy question...'}
                inputRef={inputRef}
              />
              <button
                type="submit"
                disabled={!input.trim() || isWorking || Boolean(loadError)}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-[#EA580C] px-4 py-3 text-[13px] font-semibold text-white transition-colors hover:bg-[#C2410C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 sm:px-5 cursor-pointer"
              >
                <span className="hidden sm:inline">Send</span>
                <Send className="h-4 w-4" />
              </button>
            </form>
          </div>
        </section>
      </div>

      <AIProcessPanel content={panel} process={process} docked={docked} autoFocus={panelAutoFocus} onClose={closePanel} />
      <SourceViewer target={sourceTarget} onClose={() => setSourceTarget(null)} />
      {routeConversationId && <span className="sr-only" data-conversation-id={routeConversationId} />}
    </div>
  );
}

export default ExplainerPage;
