import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { AlertCircle, ChevronDown, ChevronUp, Cpu, RefreshCw, Send } from 'lucide-react';
import type { EvidenceItem, PolicyContextCandidate, QuestionResolution, RecentQuestionItem, SourceTarget } from '../types';
import {
  clearConversationContext,
  createConversation,
  getConversation,
  getConversationMessages,
  getRecentQuestions,
  resolvePolicyContext,
  resolvePolicyFromQuestion,
  setConversationContext,
  submitQuestion,
} from '../services/api';
import { PolicyContextBanner } from '../components/explainer/PolicyContextBanner';
import { PolicyFeaturesPanel, PolicyFeatureTab } from '../components/explainer/PolicyFeaturesPanel';
import { ChatMessage, ConversationStream } from '../components/explainer/ConversationStream';
import { ExplainerRail, RailTab } from '../components/explainer/ExplainerRail';
import { QuestionInput } from '../components/explainer/QuestionInput';
import { SourceViewer } from '../components/explainer/SourceViewer';
import {
  FriendlyError,
  IDLE_PROCESS,
  ProcessState,
  StageKey,
  describeError,
  freshStages,
  interpretedText,
  stagesFromResult,
} from '../lib/explainer';

const MATCH_LABEL: Record<string, string> = {
  policy_number: 'policy number',
  customer_name: 'policyholder name',
  surname: 'surname',
  first_name: 'first name',
};

// Visual pacing for stages 2–4 while the single synchronous request runs. The real response
// always replaces these with the stage times measured by the AI service.
const STAGE_SCHEDULE: { at: number; complete: StageKey; start: StageKey }[] = [
  { at: 450, complete: 'retrieve', start: 'ground' },
  { at: 800, complete: 'ground', start: 'generate' },
];

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

export function ExplainerPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [conversationId, setConversationIdState] = useState<string | null>(null);
  const [activePolicy, setActivePolicyState] = useState<PolicyContextCandidate | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [process, setProcess] = useState<ProcessState>(IDLE_PROCESS);
  const [isWorking, setIsWorking] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [initError, setInitError] = useState<FriendlyError | null>(null);
  const [featureTab, setFeatureTab] = useState<PolicyFeatureTab | null>(null);
  const [highlight, setHighlight] = useState<{ type: 'coverage' | 'form'; id: string } | null>(null);
  const [sourceTarget, setSourceTarget] = useState<SourceTarget | null>(null);
  const [showMobileProcess, setShowMobileProcess] = useState(false);
  const [railTab, setRailTab] = useState<RailTab>('process');
  const [recent, setRecent] = useState<RecentQuestionItem[] | null>(null);
  const [recentError, setRecentError] = useState<string | null>(null);
  const [recentLoading, setRecentLoading] = useState(false);

  const loadRecent = useCallback(async () => {
    setRecentLoading(true);
    try {
      setRecent(await getRecentQuestions());
      setRecentError(null);
    } catch (err) {
      setRecentError(describeError(err).message);
    } finally {
      setRecentLoading(false);
    }
  }, []);

  // Refs mirror state for async flows that must not read stale closures.
  const conversationRef = useRef<string | null>(null);
  const policyRef = useRef<PolicyContextCandidate | null>(null);
  const pendingQuestionRef = useRef<string | null>(null);
  const busyRef = useRef(false);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const idRef = useRef(0);
  const initRef = useRef(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const setConversationId = (id: string | null) => {
    conversationRef.current = id;
    setConversationIdState(id);
  };
  const setActivePolicy = (policy: PolicyContextCandidate | null) => {
    policyRef.current = policy;
    setActivePolicyState(policy);
  };
  const nextId = (prefix: string) => `${prefix}-${++idRef.current}`;
  const push = (msg: ChatMessage) => setMessages((prev) => [...prev, msg]);

  const clearTimers = () => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  };

  const setStage = (key: StageKey, patch: ProcessState['stages'][StageKey]) =>
    setProcess((prev) => ({ ...prev, stages: { ...prev.stages, [key]: patch } }));

  /** Mark whichever stage was in flight as failed and everything after it as skipped. */
  const failProcess = (reason: string) =>
    setProcess((prev) => {
      const stages = { ...prev.stages };
      let failed = false;
      (Object.keys(stages) as StageKey[]).forEach((key) => {
        if (stages[key].status === 'processing' && !failed) {
          stages[key] = { status: 'failed', detail: reason };
          failed = true;
        } else if (stages[key].status === 'waiting' || stages[key].status === 'processing') {
          stages[key] = { status: 'skipped' };
        }
      });
      return { phase: 'failed', stages, result: null };
    });

  const ensureConversation = async (): Promise<string> => {
    if (conversationRef.current) return conversationRef.current;
    const conv = await createConversation();
    setConversationId(conv.conversation_id);
    setInitError(null);
    return conv.conversation_id;
  };

  /** Stages 2–6: submit to the backend, which answers it (AI service or policy records) and records the Evidence Ledger. */
  const runPipeline = async (question: string, convId: string, contextDetail: string, recordLookup = false) => {
    setProcess((prev) => ({
      phase: 'running',
      result: null,
      stages: { ...prev.stages, context: { status: 'completed', detail: contextDetail }, retrieve: { status: 'processing' } },
    }));
    clearTimers();
    // A records lookup has no grounding or generation stages to pace.
    if (!recordLookup) {
      timersRef.current = STAGE_SCHEDULE.map(({ at, complete, start }) =>
        setTimeout(() => {
          setStage(complete, { status: 'completed' });
          setStage(start, { status: 'processing' });
        }, at)
      );
    }

    try {
      const result = await submitQuestion(convId, question);
      clearTimers();
      setProcess({ phase: 'completed', stages: stagesFromResult(result, contextDetail), result });
      push({ kind: 'answer', id: nextId('answer'), time: nowTime(), result });
    } catch (err) {
      clearTimers();
      const friendly = describeError(err);
      failProcess(friendly.title);
      push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
    }
    loadRecent();
  };

  /** Clear the conversation view before reopening another conversation or starting a new one. */
  const resetView = () => {
    clearTimers();
    setMessages([]);
    setActivePolicy(null);
    pendingQuestionRef.current = null;
    setFeatureTab(null);
    setHighlight(null);
    setSourceTarget(null);
    setProcess(IDLE_PROCESS);
  };

  const openConversation = async (convId: string) => {
    if (busyRef.current) return;
    busyRef.current = true;
    resetView();
    try {
      await loadConversation(convId);
    } catch (err) {
      const friendly = describeError(err);
      push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
    } finally {
      busyRef.current = false;
    }
  };

  const newConversation = async () => {
    if (busyRef.current) return;
    resetView();
    setConversationId(null);
    try {
      await ensureConversation();
    } catch (err) {
      setInitError(describeError(err));
    }
    setRailTab('process');
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
    push({ kind: 'user', id: nextId('user'), time: nowTime(), text });
    setRailTab('process');
    setProcess({ phase: 'running', result: null, stages: { ...freshStages(), context: { status: 'processing' } } });

    try {
      let convId: string;
      try {
        convId = await ensureConversation();
      } catch (err) {
        const friendly = describeError(err);
        failProcess(friendly.title);
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
        failProcess(friendly.title);
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
        await runPipeline(text, convId, `${subject} — answered from policy records${understoodNote}`, true);
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
            failProcess(friendly.title);
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
      failProcess(friendly.title);
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

  /** Reopen a recorded conversation from the dashboard without asking anything again. */
  const loadConversation = async (convId: string) => {
    const conv = await getConversation(convId);
    setConversationId(conv.conversation_id);
    if (conv.policy_context) {
      setActivePolicy(await resolvePolicyContext(conv.policy_context.policy_id));
    }
    const records = await getConversationMessages(convId);
    const restored: ChatMessage[] = [];
    let last = null;
    for (const record of records) {
      restored.push({ kind: 'user', id: nextId('user'), time: timeOf(record.created_at), text: record.question });
      if (record.answer) {
        restored.push({ kind: 'answer', id: nextId('answer'), time: timeOf(record.created_at), result: record.answer });
        last = record.answer;
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
    setMessages(restored);
    if (last) {
      setProcess({
        phase: 'completed',
        stages: stagesFromResult(last, `${last.policy_context?.policy_number ?? ''} — restored from the Evidence Ledger`),
        result: last,
      });
    }
  };

  const startSession = async () => {
    const state = (location.state || {}) as { initialQuestion?: string; conversationId?: string };
    const initialQuestion = state.initialQuestion || searchParams.get('q');
    const passedConversation = state.conversationId || searchParams.get('conv');
    if (location.state) navigate(location.pathname, { replace: true, state: null });

    try {
      if (passedConversation) {
        await loadConversation(passedConversation);
      } else {
        await ensureConversation();
      }
      setInitError(null);
    } catch (err) {
      setInitError(describeError(err));
    }
    if (initialQuestion) handleAsk(initialQuestion);
  };

  useEffect(() => {
    if (initRef.current) return; // StrictMode mounts twice in development; start one session.
    initRef.current = true;
    startSession();
    loadRecent();
    return clearTimers;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    handleAsk(input);
  };

  const processLabel =
    process.phase === 'completed'
      ? process.result?.status === 'insufficient_evidence'
        ? 'Insufficient evidence'
        : `Completed · ${process.result?.confidence ?? ''} confidence`
      : process.phase === 'running'
      ? 'Processing'
      : process.phase === 'needs_input'
      ? 'Needs input'
      : process.phase === 'failed'
      ? 'Failed'
      : 'Idle';

  return (
    <div className="mx-auto flex h-[calc(100vh-6rem)] max-w-[88rem] flex-col gap-3 sm:h-[calc(100vh-7rem)] lg:h-[calc(100vh-8rem)]">
      {initError && (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-[12.5px] text-red-700">
          <span className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>
              <strong>{initError.title}.</strong> {initError.message}
            </span>
          </span>
          <button
            type="button"
            onClick={() => {
              setInitError(null);
              ensureConversation().catch((err) => setInitError(describeError(err)));
            }}
            className="inline-flex shrink-0 items-center gap-1 rounded-md border border-red-200 bg-white px-2.5 py-1 text-[11.5px] font-semibold text-red-700 hover:bg-red-100 cursor-pointer"
          >
            <RefreshCw className="h-3 w-3" /> Retry
          </button>
        </div>
      )}

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

      <div className="flex min-h-0 flex-1 gap-3">
        <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-[#E2E8F0] bg-white shadow-sm">
          <ConversationStream
            messages={messages}
            isWorking={isWorking}
            activePolicy={activePolicy}
            onAsk={handleAsk}
            onChooseCandidate={handleChooseCandidate}
            onOpenSource={openSource}
            onOpenTab={openTab}
          />

          {/* AI process on small screens: a status strip that expands in place */}
          <div className="border-t border-[#E2E8F0] lg:hidden">
            <button
              type="button"
              onClick={() => setShowMobileProcess(!showMobileProcess)}
              className="flex w-full items-center justify-between px-4 py-2 text-[11.5px] text-[#64748B] cursor-pointer"
              aria-expanded={showMobileProcess}
            >
              <span className="flex items-center gap-1.5">
                <Cpu className="h-3.5 w-3.5 text-[#F97316]" />
                <span className="font-semibold uppercase tracking-wider text-[#0F2A43]">AI process</span>
                <span>· {processLabel}</span>
              </span>
              {showMobileProcess ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            </button>
            {showMobileProcess && (
              <div className="max-h-[45vh] overflow-y-auto px-3 pb-3">
                <ExplainerRail
                  tab={railTab}
                  onTabChange={setRailTab}
                  process={process}
                  policyNumber={activePolicy?.policy_number}
                  recent={recent}
                  recentError={recentError}
                  recentLoading={recentLoading}
                  conversationId={conversationId}
                  busy={isWorking}
                  onOpenConversation={openConversation}
                  onNewConversation={newConversation}
                  onRefreshRecent={loadRecent}
                />
              </div>
            )}
          </div>

          <form onSubmit={onSubmit} className="flex items-center gap-2 border-t border-[#E2E8F0] bg-[#F8FAFC] p-3 sm:p-4">
            <QuestionInput
              value={input}
              onChange={setInput}
              disabled={isWorking}
              placeholder={activePolicy ? `Ask about ${activePolicy.customer_name}'s policy...` : 'Ask a policy question...'}
              inputRef={inputRef}
            />
            <button
              type="submit"
              disabled={!input.trim() || isWorking}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-[#EA580C] px-4 py-3 text-[13px] font-semibold text-white transition-colors hover:bg-[#C2410C] disabled:cursor-not-allowed disabled:opacity-50 sm:px-5 cursor-pointer"
            >
              <span className="hidden sm:inline">Send</span>
              <Send className="h-4 w-4" />
            </button>
          </form>
        </section>

        <div className="hidden shrink-0 overflow-y-auto lg:block">
          <ExplainerRail
                  tab={railTab}
                  onTabChange={setRailTab}
                  process={process}
                  policyNumber={activePolicy?.policy_number}
                  recent={recent}
                  recentError={recentError}
                  recentLoading={recentLoading}
                  conversationId={conversationId}
                  busy={isWorking}
                  onOpenConversation={openConversation}
                  onNewConversation={newConversation}
                  onRefreshRecent={loadRecent}
                />
        </div>
      </div>

      <SourceViewer target={sourceTarget} onClose={() => setSourceTarget(null)} />
      {conversationId && <span className="sr-only" data-conversation-id={conversationId} />}
    </div>
  );
}

export default ExplainerPage;
