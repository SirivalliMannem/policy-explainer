import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, ArrowLeft, ArrowUp, FileText, Loader2, Plus, X } from 'lucide-react';
import type {
  AskedBy,
  DocumentInfo,
  EvidenceItem,
  PolicyContextCandidate,
  QuestionResolution,
  SourceTarget,
} from '../types';
import {
  ApiError,
  clearConversationContext,
  createConversation,
  detachDocument,
  explainDocument,
  getConversation,
  listDocuments,
  uploadDocument,
  getConversationMessages,
  resolvePolicyContext,
  resolvePolicyFromQuestion,
  setConversationContext,
  submitQuestion,
} from '../services/api';
import { currentEmployee } from '../services/auth';
import { PolicyContextBanner } from '../components/explainer/PolicyContextBanner';
import { PolicyFeaturesPanel, PolicyFeatureTab } from '../components/explainer/PolicyFeaturesPanel';
import { ChatMessage, ConversationStream, PendingCustomerSwitch } from '../components/explainer/ConversationStream';
import { PolicySwitcherModal } from '../components/explainer/PolicySwitcherModal';
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
  lineLabel,
} from '../lib/explainer';
import { notifyConversationsChanged } from '../lib/conversations';
import { groupPolicyAnswers } from '../lib/answerGroups';

/** Most policies one question is answered for at once; more than this, the employee chooses. */
const MAX_ANSWER_ALL = 4;

const MATCH_LABEL: Record<string, string> = {
  policy_number: 'policy number',
  customer_name: 'policyholder name',
  surname: 'surname',
  first_name: 'first name',
  claim_number: 'claim number',
  account_number: 'account number',
  email: 'email address',
  phone: 'phone number',
  vin: 'VIN',
  plate: 'license plate',
  address: 'address',
  vehicle: 'vehicle',
  loss_date: 'date of loss',
};

function detectQuestionEntityConflict(
  question: string,
  targetPolicy: PolicyContextCandidate
): { hasConflict: boolean; entity?: string } {
  const q = question.trim();
  if (!q) return { hasConflict: false };

  // 1. Explicit policy number in question
  const policyNumMatch = q.match(/\b(HO|PA)[-\s]?\d{4}(?:[-\s]?\d{4})?\b/i);
  if (policyNumMatch) {
    const rawNum = policyNumMatch[0].replace(/[-\s]/g, '').toUpperCase();
    const targetNum = targetPolicy.policy_number.replace(/[-\s]/g, '').toUpperCase();
    if (rawNum !== targetNum) {
      return { hasConflict: true, entity: `policy ${policyNumMatch[0]}` };
    }
  }

  // 2. Explicit person name in question
  const nonNames = new Set([
    'does', 'do', 'did', 'what', 'which', 'who', 'whose', 'when', 'where', 'why', 'how', 'is', 'are',
    'can', 'could', 'would', 'will', 'should', 'the', 'this', 'that', 'these', 'those', 'and', 'for',
    'with', 'under', 'policy', 'coverage', 'coverages', 'endorsement', 'form', 'forms', 'deductible',
    'water', 'backup', 'homeowners', 'auto', 'personal', 'special', 'texas', 'new', 'york', 'section',
    'part', 'show', 'tell', 'explain', 'list', 'please', 'has', 'have', 'any', 'all', 'give', 'display',
    'name', 'there', 'we', 'our', 'us', 'me', 'my', 'was', 'were', 'home', 'customer', 'policyholder',
    'insured', 'policies', 'procedure', 'filing', 'claim', 'dwelling', 'damage', 'peril', 'flood',
    'limits', 'limit', 'exclusions', 'exclusion', 'about', 'regarding', 'both', 'either', 'neither',
    'each', 'every', 'other', 'another', 'first', 'second', 'third', 'last', 'premium', 'deductibles',
  ]);

  const targetParts = targetPolicy.customer_name.toLowerCase().split(/\s+/);

  const prepMatch = q.match(/\b(?:of|for|about|with|under|regarding)\s+([A-Za-z\-]+(?:\s+[A-Za-z\-]+)?)\b/i);
  if (prepMatch) {
    const candidate = prepMatch[1].trim();
    const words = candidate.toLowerCase().split(/\s+/);
    if (!words.some((w) => nonNames.has(w)) && !candidate.match(/\b(?:HO|PA|CLM)[-\s]?\d+/i)) {
      if (!words.some((w) => targetParts.includes(w))) {
        return { hasConflict: true, entity: candidate };
      }
    }
  }

  const possMatch = q.match(/\b([A-Za-z\-]+(?:\s+[A-Za-z\-]+)?)(?:['’]s)\b/i);
  if (possMatch) {
    const candidate = possMatch[1].trim();
    const words = candidate.toLowerCase().split(/\s+/);
    if (!words.some((w) => nonNames.has(w)) && !candidate.match(/\b(?:HO|PA|CLM)[-\s]?\d+/i)) {
      if (!words.some((w) => targetParts.includes(w))) {
        return { hasConflict: true, entity: candidate };
      }
    }
  }

  const verbMatch = q.match(/\b(?:does|is|has)\s+([A-Za-z\-]+(?:\s+[A-Za-z\-]+)?)\s+(?:have|covered|own|insured)\b/i);
  if (verbMatch) {
    const candidate = verbMatch[1].trim();
    const words = candidate.toLowerCase().split(/\s+/);
    if (!words.some((w) => nonNames.has(w)) && !candidate.match(/\b(?:HO|PA|CLM)[-\s]?\d+/i)) {
      if (!words.some((w) => targetParts.includes(w))) {
        return { hasConflict: true, entity: candidate };
      }
    }
  }

  const fullMatch = q.match(/\b([A-Z][a-z]{1,}\s+[A-Z][a-z]{1,})\b/);
  if (fullMatch) {
    const candidate = fullMatch[1].trim();
    const words = candidate.toLowerCase().split(/\s+/);
    if (!words.some((w) => nonNames.has(w))) {
      if (!words.some((w) => targetParts.includes(w))) {
        return { hasConflict: true, entity: candidate };
      }
    }
  }

  const singleMatch = q.match(/\b([A-Z][a-zA-Z\-]{2,})\b/);
  if (singleMatch) {
    const candidate = singleMatch[1].trim();
    if (!nonNames.has(candidate.toLowerCase()) && !candidate.match(/\b(?:HO|PA|CLM)[-\s]?\d+/i)) {
      if (!targetParts.includes(candidate.toLowerCase())) {
        return { hasConflict: true, entity: candidate };
      }
    }
  }

  return { hasConflict: false };
}

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

  // Safe Customer and Policy Switching state (inline confirmation card)
  const [pendingSwitch, setPendingSwitch] = useState<PendingCustomerSwitch | null>(null);
  const [policySwitcherOpen, setPolicySwitcherOpen] = useState(false);

  // Refs mirror state for async flows that must not read stale closures.
  const conversationRef = useRef<string | null>(null);
  const policyRef = useRef<PolicyContextCandidate | null>(null);
  // A document uploaded into this chat: while attached, questions are answered from it alone.
  const [attachedDoc, setAttachedDocState] = useState<DocumentInfo | null>(null);
  const attachedDocRef = useRef<DocumentInfo | null>(null);
  const setAttachedDoc = (doc: DocumentInfo | null) => {
    attachedDocRef.current = doc;
    setAttachedDocState(doc);
  };
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
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
  const ensureConversation = async (targetPolicyId?: string): Promise<string> => {
    if (conversationRef.current) return conversationRef.current;
    const pid = targetPolicyId || policyRef.current?.policy_id;
    const conv = await createConversation(pid);
    conversationRef.current = conv.conversation_id;
    navigate(`/app/explainer/c/${conv.conversation_id}`, { replace: true });
    return conv.conversation_id;
  };

  /** Stages 2–6: submit to the backend, which answers it (AI service or policy records) and records the Evidence Ledger. */
  // The backend answers in one request, so stages 2–6 are reported together when it returns: step 2
  // shows as in progress until then, and every value shown afterwards is the one the pipeline measured.
  // `forPolicy` answers for one of a customer's matching policies (labelled), leaving the context as it is.
  // `verified` is how the customer was confirmed when the employee chose them (a candidate or a switch).
  const runPipeline = async (
    question: string,
    convId: string,
    contextDetail: string,
    forPolicy?: PolicyContextCandidate,
    verified?: string
  ) => {
    // A question that runs the pipeline opens the AI process panel without taking focus from the composer.
    openPanel({ mode: 'live' }, null);
    setProcess((prev) => ({
      ...prev,
      phase: 'running',
      result: null,
      question,
      contextDetail,
      stages: {
        ...freshStages(),
        verify: verified ? { status: 'completed', detail: verified } : prev.stages.verify,
        context: { status: 'completed', detail: contextDetail },
        retrieve: { status: 'processing' },
      },
    }));

    try {
      const targetPolicy = forPolicy || policyRef.current;
      const result = await submitQuestion(convId, question, targetPolicy?.policy_id);
      setProcess((prev) => ({
        ...prev,
        phase: 'completed',
        result,
        askedBy: result.asked_by ?? prev.askedBy,
        askedAt: result.asked_at ?? prev.askedAt,
      }));
      push({ kind: 'answer', id: nextId('answer'), time: nowTime(), question, result, labelled: Boolean(forPolicy) });
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
    setPendingSwitch(null);
    setPolicySwitcherOpen(false);
    setAttachedDoc(null);
  };

  const unitLabel = (doc: DocumentInfo) => `${doc.page_count} ${doc.unit === 'page' ? 'page' : 'section'}${doc.page_count === 1 ? '' : 's'}`;

  /** A question about the attached document: answered from the document only, with its page references. */
  const runDocumentQuestion = async (question: string, convId: string, doc: DocumentInfo) => {
    openPanel({ mode: 'live' }, null);
    setProcess((prev) => ({
      ...prev,
      phase: 'running',
      result: null,
      question,
      contextDetail: `Uploaded document: ${doc.filename} · ${unitLabel(doc)}`,
      stages: {
        ...freshStages(),
        verify: { status: 'skipped', detail: 'Not needed: answered from the uploaded document.' },
        context: { status: 'completed', detail: `Uploaded document: ${doc.filename} · ${unitLabel(doc)}` },
        retrieve: { status: 'processing' },
      },
    }));
    try {
      const result = await submitQuestion(convId, question, undefined, doc.document_id);
      setProcess((prev) => ({ ...prev, phase: 'completed', result, askedBy: result.asked_by ?? prev.askedBy, askedAt: result.asked_at ?? prev.askedAt }));
      push({ kind: 'answer', id: nextId('answer'), time: nowTime(), question, result });
    } catch (err) {
      const friendly = describeError(err);
      failProcess(friendly);
      push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
    }
    notifyConversationsChanged();
  };

  /** Upload a document into the chat, then explain it in plain language. */
  const handleUpload = async (file: File) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setIsWorking(true);
    setIsUploading(true);
    const askedAt = new Date().toISOString();
    push({ kind: 'user', id: nextId('user'), time: nowTime(), text: `Uploaded “${file.name}”`, askedBy: me(), askedAt });
    try {
      const convId = await ensureConversation();
      const doc = await uploadDocument(convId, file);
      setAttachedDoc(doc);
      setIsUploading(false);
      push({
        kind: 'assistant',
        id: nextId('assistant'),
        time: nowTime(),
        text: `I've read “${doc.filename}” (${unitLabel(doc)}). Here it is in plain language. Ask me anything about it: my answers will come from this document only, with its ${doc.unit === 'page' ? 'page' : 'section'} numbers.`,
        suggestions: [],
      });
      const question = `Explain the uploaded document “${doc.filename}” in simple language`;
      openPanel({ mode: 'live' }, null);
      setProcess({
        phase: 'running', result: null, question, askedBy: me(), askedAt, contextDetail: `Uploaded document: ${doc.filename} · ${unitLabel(doc)}`,
        verification: null,
        stages: {
          ...freshStages(),
          verify: { status: 'skipped', detail: 'Not needed: answered from the uploaded document.' },
          context: { status: 'completed', detail: `Uploaded document: ${doc.filename} · ${unitLabel(doc)}` },
          retrieve: { status: 'processing' },
        },
      });
      try {
        const result = await explainDocument(convId, doc.document_id);
        setProcess((prev) => ({ ...prev, phase: 'completed', result }));
        push({ kind: 'answer', id: nextId('answer'), time: nowTime(), question, result });
      } catch (err) {
        const friendly = describeError(err);
        failProcess(friendly);
        push({ kind: 'error', id: nextId('error'), time: nowTime(), title: 'Could not explain the document', text: friendly.message });
      }
      notifyConversationsChanged();
    } catch (err) {
      const friendly = describeError(err);
      push({ kind: 'error', id: nextId('error'), time: nowTime(), title: 'Upload failed', text: friendly.message });
    } finally {
      setIsUploading(false);
      busyRef.current = false;
      setIsWorking(false);
      inputRef.current?.focus();
    }
  };

  /** Stop answering from the document; the chat answers from the policy again. */
  const handleDetach = async () => {
    const doc = attachedDocRef.current;
    const convId = conversationRef.current;
    if (!doc || !convId) return;
    try {
      await detachDocument(convId, doc.document_id);
      setAttachedDoc(null);
      push({
        kind: 'assistant',
        id: nextId('assistant'),
        time: nowTime(),
        text: `“${doc.filename}” is detached. Questions are answered from the policy wording again.`,
        suggestions: [],
      });
    } catch (err) {
      const friendly = describeError(err);
      push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
    }
  };

  const askForPolicy = (text: string, candidates: PolicyContextCandidate[], stageDetail: string, candidatesLabel?: string) => {
    push({ kind: 'clarify', id: nextId('clarify'), time: nowTime(), text, candidates, candidatesLabel });
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
      verification: null,
      stages: { ...freshStages(), verify: { status: 'processing' } },
    });
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

      // A document is attached: answer from it alone, without resolving a policy or customer.
      const doc = attachedDocRef.current;
      if (doc) {
        await runDocumentQuestion(text, convId, doc);
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

      // Greetings, thanks, "what can you do?" and off-topic messages get a conversational reply;
      // nothing is retrieved or recorded for them.
      if ((resolution.intent === 'conversation' || resolution.intent === 'off_topic') && resolution.reply) {
        push({
          kind: 'assistant',
          id: nextId('assistant'),
          time: nowTime(),
          text: resolution.reply,
          suggestions: resolution.suggestions ?? [],
        });
        setProcess(IDLE_PROCESS);
        return;
      }

      // Step 1: verify the customer before any policy information is retrieved. A customer who is not
      // in the records, or a name several customers share, stops here and the employee is asked.
      const verification = resolution.customer_verification;
      if (verification && (verification.status === 'not_found' || verification.status === 'ambiguous')) {
        const notFound = verification.status === 'not_found';
        const pending = pendingQuestionRef.current;
        pendingQuestionRef.current = pending && looksLikeReply(text) ? pending : text;
        setProcess((prev) => ({
          ...prev,
          phase: notFound ? 'failed' : 'needs_input',
          stages: (() => {
            // Not found: nothing after verification runs. Ambiguous: the rest waits for the employee's choice.
            const after = notFound
              ? { status: 'skipped' as const, detail: 'Skipped: customer verification failed.' }
              : { status: 'waiting' as const };
            return {
              ...freshStages(),
              verify: { status: notFound ? ('failed' as const) : ('attention' as const), detail: verification.message },
              context: after,
              retrieve: after,
              ground: after,
              generate: after,
              citations: after,
              validate: after,
              deliver: after,
            };
          })(),
        }));
        push({
          kind: 'assistant',
          id: nextId('assistant'),
          time: nowTime(),
          text: notFound
            ? verification.message
            : `${verification.message} Which customer did you mean?`,
          suggestions: notFound ? [] : verification.customers.map((c) => c.name),
        });
        openPanel({ mode: 'live' }, null);
        if (notFound) {
          // Recorded, so it stays flagged in Needs attention: the backend verifies the customer again,
          // records the failed verification in the ledger and answers nothing about any policy.
          ensureConversation()
            .then((convId) => submitQuestion(convId, text))
            .then(() => notifyConversationsChanged())
            .catch(() => undefined);
        }
        return;
      }
      setProcess((prev) => ({
        ...prev,
        verification: verification ?? null,
        stages: {
          ...prev.stages,
          verify:
            verification?.status === 'verified'
              ? { status: 'completed', detail: verification.message }
              : resolution.intent === 'portfolio'
              ? { status: 'skipped', detail: 'Not needed: the question is about the book of business, not one customer.' }
              : { status: 'attention', detail: verification?.message || 'The question does not name a customer yet.' },
          context: { status: 'processing' },
        },
      }));

      // A date of loss when no term of the policy was in force that day: say so and ask, rather
      // than answer from a term that did not cover the loss.
      const term = resolution.term_selection;
      if (term?.status === 'no_term') {
        const pending = pendingQuestionRef.current;
        pendingQuestionRef.current = pending && looksLikeReply(text) ? pending : text;
        setProcess((prev) => ({
          ...prev,
          phase: 'needs_input',
          stages: { ...prev.stages, context: { status: 'attention', detail: term.message } },
        }));
        push({
          kind: 'assistant',
          id: nextId('assistant'),
          time: nowTime(),
          text: `${term.message} Please check the date of loss.`,
          suggestions: [],
        });
        openPanel({ mode: 'live' }, null);
        return;
      }
      const termNote = term?.status === 'matched' ? ` · ${term.message}` : '';

      const understood = interpretedText(resolution.interpretation);
      const understoodNote = understood ? ` · understood as “${understood}”` : '';

      // Customer / portfolio questions are answered from policy records. They need no single-policy
      // context, and they neither change the active context nor ask which policy to check.
      if (resolution.intent === 'portfolio') {
        const subject = resolution.reference ? `Customer question · ${resolution.reference}` : 'Portfolio question · whole book';
        await runPipeline(text, convId, `Portfolio lookup · ${subject} — answered from policy records`);
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

        // Scenario C: If switching to an unrelated customer, require explicit confirmation via inline card
        if (current && current.customer_id && resolved.customer_id && current.customer_id !== resolved.customer_id) {
          setPendingSwitch({
            currentPolicy: current,
            targetPolicy: resolved,
            pendingQuestion: question,
            matchedOn: resolution.matched_on || null,
          });
          setProcess(IDLE_PROCESS);
          return;
        }

        pendingQuestionRef.current = null;
        const isDifferentPolicy = !current || current.policy_id !== resolved.policy_id;
        const isSwitch = Boolean(current && current.policy_id !== resolved.policy_id);
        try {
          await setConversationContext(convId, resolved.policy_id, {
            customerId: resolved.customer_id,
          });
        } catch (err) {
          const friendly = describeError(err);
          failProcess(friendly);
          push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
          return;
        }
        setActivePolicy(resolved);
        setFeatureTab(null);
        if (isDifferentPolicy) {
          push({
            kind: 'context',
            id: nextId('context'),
            time: nowTime(),
            policy: resolved,
            matchedOn: resolution.matched_on,
            switched: isSwitch,
            switchType: isSwitch ? 'same_customer_different_policy' : 'initial_selection',
            answering: question !== text ? question : undefined,
          });
        }
        contextDetail = `Policy ${resolved.policy_number} · ${resolved.customer_name}`;
      } else if (
        resolution.status === 'ambiguous' &&
        resolution.answer_all &&
        resolution.candidates.length <= MAX_ANSWER_ALL &&
        // Another customer's policies still go through the switch confirmation below.
        (!current || resolution.candidates.every((c) => c.customer_id === current.customer_id))
      ) {
        // Several policies of one customer: answer the question for each, labelled by policy number.
        const pending = pendingQuestionRef.current;
        if (pending && isBareReference(text, resolution)) question = pending;
        pendingQuestionRef.current = null;
        const policies = resolution.candidates;
        push({
          kind: 'assistant',
          id: nextId('assistant'),
          time: nowTime(),
          text: `${policies[0].customer_name} has ${policies.length} policies that match: ${policies
            .map((c) => `${c.policy_number} (${lineLabel(c.line_of_business)})`)
            .join(' and ')}. Here is the answer for each.`,
          suggestions: [],
        });
        for (const policy of policies) {
          await runPipeline(
            question,
            convId,
            `Policy ${policy.policy_number} · ${policy.customer_name}`,
            policy
          );
        }
        return;
      } else if (resolution.status === 'ambiguous') {
        if (current && resolution.candidates.some((c) => c.policy_id === current.policy_id)) {
          contextDetail = `Policy ${current.policy_number} · ${current.customer_name}`;
          try {
            await setConversationContext(convId, current.policy_id, {
              customerId: current.customer_id,
            });
          } catch (err) {
            const friendly = describeError(err);
            failProcess(friendly);
            push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
            return;
          }
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
        contextDetail = `Policy ${current.policy_number} · ${current.customer_name}`;
        try {
          await setConversationContext(convId, current.policy_id, {
            customerId: current.customer_id,
          });
        } catch (err) {
          const friendly = describeError(err);
          failProcess(friendly);
          push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
          return;
        }
      } else {
        pendingQuestionRef.current = text;
        const recent = resolution.suggested_policies ?? [];
        askForPolicy(
          recent.length
            ? 'Happy to help with that. Which policy should I check? Pick one you looked at recently, or give me a policy number or policyholder name.'
            : 'Happy to help with that. Which policy should I check? Give me a policy number or the policyholder’s name.',
          recent,
          'No policy named and no active context',
          recent.length ? 'Your recent policies' : undefined
        );
        return;
      }

      const targetPolicy = (resolution.status === 'resolved' && resolution.policy) ? resolution.policy : (current || undefined);
      await runPipeline(question, convId, contextDetail, targetPolicy);
    } finally {
      busyRef.current = false;
      setIsWorking(false);
      inputRef.current?.focus();
    }
  };

  const handleChooseCandidate = async (candidate: PolicyContextCandidate) => {
    if (busyRef.current) return;
    setPolicySwitcherOpen(false);
    const current = policyRef.current;
    const pending = pendingQuestionRef.current;

    // Scenario C: If selecting a policy belonging to a different customer, require confirmation via inline card
    if (current && current.customer_id && candidate.customer_id && current.customer_id !== candidate.customer_id) {
      setPendingSwitch({
        currentPolicy: current,
        targetPolicy: candidate,
        pendingQuestion: pending || null,
        matchedOn: null,
      });
      return;
    }

    // Scenario A: Same customer, same policy
    if (current && current.policy_id === candidate.policy_id) {
      pendingQuestionRef.current = null;
      if (pending) {
        const conflict = detectQuestionEntityConflict(pending, candidate);
        if (conflict.hasConflict && conflict.entity) {
          push({
            kind: 'assistant',
            id: nextId('assistant'),
            time: nowTime(),
            text: `The original question refers to ${conflict.entity}, but the selected policy belongs to ${candidate.customer_name}. Would you like to rephrase the question for ${candidate.customer_name}’s policy?`,
            suggestions: [
              `What are the exclusions for policy ${candidate.policy_number}?`,
              `What are the exclusions of ${candidate.customer_name}?`,
            ],
          });
          setInput(pending);
          setProcess(IDLE_PROCESS);
          inputRef.current?.focus();
          return;
        }
        busyRef.current = true;
        setIsWorking(true);
        try {
          const convId = await ensureConversation(candidate.policy_id);
          await setConversationContext(convId, candidate.policy_id, {
            customerId: candidate.customer_id,
          });
          await runPipeline(
            pending,
            convId,
            `Policy ${candidate.policy_number} · ${candidate.customer_name}`,
            candidate,
            `${candidate.customer_name}, chosen by the employee.`
          );
        } catch (err) {
          const friendly = describeError(err);
          failProcess(friendly);
          push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
        } finally {
          busyRef.current = false;
          setIsWorking(false);
        }
      }
      return;
    }

    // Scenario B: Same customer, different policy (or initial policy selection)
    busyRef.current = true;
    setIsWorking(true);
    try {
      const convId = await ensureConversation(candidate.policy_id);
      const isSwitch = Boolean(current);
      await setConversationContext(convId, candidate.policy_id, {
        customerId: candidate.customer_id,
      });
      setActivePolicy(candidate);
      setFeatureTab(null);
      pendingQuestionRef.current = null;
      push({
        kind: 'context',
        id: nextId('context'),
        time: nowTime(),
        policy: candidate,
        matchedOn: null,
        switched: isSwitch,
        switchType: isSwitch ? 'same_customer_different_policy' : 'initial_selection',
        answering: pending ?? undefined,
      });
      notifyConversationsChanged();
      if (pending) {
        const conflict = detectQuestionEntityConflict(pending, candidate);
        if (conflict.hasConflict && conflict.entity) {
          push({
            kind: 'assistant',
            id: nextId('assistant'),
            time: nowTime(),
            text: `The original question refers to ${conflict.entity}, but the selected policy belongs to ${candidate.customer_name}. Would you like to rephrase the question for ${candidate.customer_name}’s policy?`,
            suggestions: [
              `What are the exclusions for policy ${candidate.policy_number}?`,
              `What are the exclusions of ${candidate.customer_name}?`,
            ],
          });
          setInput(pending);
          setProcess(IDLE_PROCESS);
          inputRef.current?.focus();
        } else {
          await runPipeline(
            pending,
            convId,
            `Policy ${candidate.policy_number} · ${candidate.customer_name}`,
            candidate,
            `${candidate.customer_name}, chosen by the employee.`
          );
        }
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

  /** Scenario D: Start a new conversation with the newly selected customer/policy. */
  const handleConfirmStartNew = async () => {
    if (!pendingSwitch) return;
    const { targetPolicy, pendingQuestion } = pendingSwitch;
    setPendingSwitch(null);

    try {
      const newConv = await createConversation(targetPolicy.policy_id);
      notifyConversationsChanged();
      const conflict = pendingQuestion ? detectQuestionEntityConflict(pendingQuestion, targetPolicy) : { hasConflict: false };
      if (conflict.hasConflict && conflict.entity) {
        navigate(`/app/explainer/c/${newConv.conversation_id}`, {
          state: {
            policyId: targetPolicy.policy_id,
            conflictNotice: {
              entity: conflict.entity,
              customerName: targetPolicy.customer_name,
              policyNumber: targetPolicy.policy_number,
              pendingQuestion,
            },
          },
        });
      } else {
        navigate(`/app/explainer/c/${newConv.conversation_id}`, {
          state: pendingQuestion ? { initialQuestion: pendingQuestion, policyId: targetPolicy.policy_id } : { policyId: targetPolicy.policy_id },
        });
      }
    } catch (err) {
      const friendly = describeError(err);
      push({ kind: 'error', id: nextId('error'), time: nowTime(), title: friendly.title, text: friendly.message });
    }
  };

  /** Scenario C action 2: Switch the existing conversation to the newly selected customer. */
  const handleConfirmSwitchExisting = async () => {
    if (!pendingSwitch) return;
    const { targetPolicy, pendingQuestion, matchedOn } = pendingSwitch;
    setPendingSwitch(null);

    busyRef.current = true;
    setIsWorking(true);
    try {
      const convId = await ensureConversation(targetPolicy.policy_id);
      await setConversationContext(convId, targetPolicy.policy_id, {
        customerId: targetPolicy.customer_id,
        confirmDifferentCustomer: true,
      });
      setActivePolicy(targetPolicy);
      setFeatureTab(null);
      pendingQuestionRef.current = null;
      push({
        kind: 'context',
        id: nextId('context'),
        time: nowTime(),
        policy: targetPolicy,
        matchedOn,
        switched: true,
        switchType: 'different_customer',
        answering: pendingQuestion ?? undefined,
      });
      notifyConversationsChanged();
      if (pendingQuestion) {
        const conflict = detectQuestionEntityConflict(pendingQuestion, targetPolicy);
        if (conflict.hasConflict && conflict.entity) {
          push({
            kind: 'assistant',
            id: nextId('assistant'),
            time: nowTime(),
            text: `The original question refers to ${conflict.entity}, but the selected policy belongs to ${targetPolicy.customer_name}. Would you like to rephrase the question for ${targetPolicy.customer_name}’s policy?`,
            suggestions: [
              `What are the exclusions for policy ${targetPolicy.policy_number}?`,
              `What are the exclusions of ${targetPolicy.customer_name}?`,
            ],
          });
          setInput(pendingQuestion);
          setProcess(IDLE_PROCESS);
          inputRef.current?.focus();
        } else {
          await runPipeline(
            pendingQuestion,
            convId,
            `Policy ${targetPolicy.policy_number} · ${targetPolicy.customer_name}`,
            targetPolicy,
            `${targetPolicy.customer_name}, confirmed by the employee when switching customers.`
          );
        }
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

  /** Scenario C action 3: Cancel customer switch, retaining existing conversation context. */
  const handleCancelCustomerSwitch = () => {
    setPendingSwitch(null);
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

  // The header's "AI process" button: the question in progress (or just answered), else the latest answer.
  const lastAnswer = [...messages].reverse().find((m): m is Extract<ChatMessage, { kind: 'answer' }> => m.kind === 'answer');
  const liveAvailable = process.phase !== 'idle' && Boolean(process.question);
  const toggleProcess = (opener: HTMLElement) => {
    if (panel) {
      closePanel();
    } else if (liveAvailable) {
      showProcess(opener);
    } else if (lastAnswer) {
      showAudit(
        { question: lastAnswer.question, result: lastAnswer.result, askedBy: lastAnswer.result.asked_by, askedAt: lastAnswer.result.asked_at },
        opener
      );
    }
  };

  const prefill = (text: string) => {
    setInput(text);
    requestAnimationFrame(() => {
      const el = inputRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    });
  };

  /** Reopen a recorded conversation from stored answers; nothing is asked again. */
  const loadConversation = async (convId: string) => {
    const conv = await getConversation(convId);
    if (conv.policy_context && conversationRef.current === convId) {
      setActivePolicy(await resolvePolicyContext(conv.policy_context.policy_id));
    }
    const records = await getConversationMessages(convId);
    const restored: ChatMessage[] = [];
    // A question answered for each of a customer's policies shows once, with its labelled answers.
    for (const { record, startsQuestion, inGroup } of groupPolicyAnswers(records)) {
      if (startsQuestion) {
        restored.push({
          kind: 'user',
          id: nextId('user'),
          time: timeOf(record.created_at),
          text: record.question,
          askedBy: record.asked_by,
          askedAt: record.created_at,
        });
      }
      if (record.answer) {
        restored.push({
          kind: 'answer',
          id: nextId('answer'),
          time: timeOf(record.created_at),
          question: record.question,
          result: record.answer,
          labelled: inGroup,
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
    // The document still attached to this conversation, if any.
    const docs = await listDocuments(convId).catch(() => [] as DocumentInfo[]);
    if (conversationRef.current === convId) setAttachedDoc(docs.find((d) => d.is_active) ?? null);
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
      const state = (location.state || {}) as {
        initialQuestion?: string;
        policyId?: string;
        conflictNotice?: { entity: string; customerName: string; policyNumber: string; pendingQuestion: string };
      };
      if (state.conflictNotice) {
        navigate(location.pathname, { replace: true, state: null });
        const cn = state.conflictNotice;
        push({
          kind: 'assistant',
          id: nextId('assistant'),
          time: nowTime(),
          text: `The original question refers to ${cn.entity}, but the selected policy belongs to ${cn.customerName}. Would you like to rephrase the question for ${cn.customerName}’s policy?`,
          suggestions: [
            `What are the exclusions for policy ${cn.policyNumber}?`,
            `What are the exclusions of ${cn.customerName}?`,
          ],
        });
        setInput(cn.pendingQuestion);
        setProcess(IDLE_PROCESS);
        inputRef.current?.focus();
        return;
      }
      if (state.policyId && !policyRef.current) {
        resolvePolicyContext(state.policyId)
          .then((p) => {
            setActivePolicy(p);
            if (state.initialQuestion) {
              navigate(location.pathname, { replace: true, state: null });
              const conflict = detectQuestionEntityConflict(state.initialQuestion, p);
              if (conflict.hasConflict && conflict.entity) {
                push({
                  kind: 'assistant',
                  id: nextId('assistant'),
                  time: nowTime(),
                  text: `The original question refers to ${conflict.entity}, but the selected policy belongs to ${p.customer_name}. Would you like to rephrase the question for ${p.customer_name}’s policy?`,
                  suggestions: [
                    `What are the exclusions for policy ${p.policy_number}?`,
                    `What are the exclusions of ${p.customer_name}?`,
                  ],
                });
                setInput(state.initialQuestion);
                setProcess(IDLE_PROCESS);
                inputRef.current?.focus();
              } else {
                handleAsk(state.initialQuestion);
              }
            }
          })
          .catch(() => {
            if (state.initialQuestion) {
              navigate(location.pathname, { replace: true, state: null });
              handleAsk(state.initialQuestion);
            }
          });
        return;
      }
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
      .then(() => {
        if (load !== loadIdRef.current) return;
        const state = (location.state || {}) as {
          initialQuestion?: string;
          policyId?: string;
          conflictNotice?: { entity: string; customerName: string; policyNumber: string; pendingQuestion: string };
        };
        if (state.conflictNotice) {
          navigate(location.pathname, { replace: true, state: null });
          const cn = state.conflictNotice;
          push({
            kind: 'assistant',
            id: nextId('assistant'),
            time: nowTime(),
            text: `The original question refers to ${cn.entity}, but the selected policy belongs to ${cn.customerName}. Would you like to rephrase the question for ${cn.customerName}’s policy?`,
            suggestions: [
              `What are the exclusions for policy ${cn.policyNumber}?`,
              `What are the exclusions of ${cn.customerName}?`,
            ],
          });
          setInput(cn.pendingQuestion);
          setProcess(IDLE_PROCESS);
          inputRef.current?.focus();
          return;
        }
        if (state.policyId && !policyRef.current) {
          resolvePolicyContext(state.policyId)
            .then((p) => {
              setActivePolicy(p);
              if (state.initialQuestion) {
                navigate(location.pathname, { replace: true, state: null });
                const conflict = detectQuestionEntityConflict(state.initialQuestion, p);
                if (conflict.hasConflict && conflict.entity) {
                  push({
                    kind: 'assistant',
                    id: nextId('assistant'),
                    time: nowTime(),
                    text: `The original question refers to ${conflict.entity}, but the selected policy belongs to ${p.customer_name}. Would you like to rephrase the question for ${p.customer_name}’s policy?`,
                    suggestions: [
                      `What are the exclusions for policy ${p.policy_number}?`,
                      `What are the exclusions of ${p.customer_name}?`,
                    ],
                  });
                  setInput(state.initialQuestion);
                  setProcess(IDLE_PROCESS);
                  inputRef.current?.focus();
                } else {
                  handleAsk(state.initialQuestion);
                }
              }
            })
            .catch(() => {
              if (state.initialQuestion) {
                navigate(location.pathname, { replace: true, state: null });
                handleAsk(state.initialQuestion);
              }
            });
          return;
        }
        if (state.initialQuestion) {
          navigate(location.pathname, { replace: true, state: null });
          const pol = policyRef.current;
          if (pol) {
            const conflict = detectQuestionEntityConflict(state.initialQuestion, pol);
            if (conflict.hasConflict && conflict.entity) {
              push({
                kind: 'assistant',
                id: nextId('assistant'),
                time: nowTime(),
                text: `The original question refers to ${conflict.entity}, but the selected policy belongs to ${pol.customer_name}. Would you like to rephrase the question for ${pol.customer_name}’s policy?`,
                suggestions: [
                  `What are the exclusions for policy ${pol.policy_number}?`,
                  `What are the exclusions of ${pol.customer_name}?`,
                ],
              });
              setInput(state.initialQuestion);
              setProcess(IDLE_PROCESS);
              inputRef.current?.focus();
              return;
            }
          }
          handleAsk(state.initialQuestion);
        }
      })
      .catch((err) => {
        if (load !== loadIdRef.current) return; // the employee has moved on
        conversationRef.current = null;
        const state = (location.state || {}) as { initialQuestion?: string; policyId?: string };
        if (state.initialQuestion) {
          navigate('/app/explainer', {
            replace: true,
            state: {
              initialQuestion: state.initialQuestion,
              policyId: state.policyId,
            },
          });
          return;
        }
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
    <div className="flex h-full min-h-0 w-full flex-1 bg-white overflow-hidden">
      <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <PolicyContextBanner
          policy={activePolicy}
          isResolving={isResolving}
          openTab={featureTab}
          onOpenTab={(tab) => openTab(tab)}
          onClear={handleClearContext}
          onOpenSwitcher={() => setPolicySwitcherOpen(true)}
          processAvailable={liveAvailable || Boolean(lastAnswer)}
          processOpen={Boolean(panel)}
          onToggleProcess={toggleProcess}
        />

        {activePolicy && featureTab && (
          <div className="max-h-[45%] shrink-0 overflow-y-auto border-b border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3 sm:px-6">
            <div className="mx-auto w-full max-w-[780px]">
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
            </div>
          </div>
        )}

        <section aria-label="Conversation" className="flex min-h-0 flex-1 flex-col bg-[#FBFCFD] overflow-hidden">
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
              onPrefill={prefill}
              firstName={me()?.name?.split(/\s+/)[0]}
              activePolicy={activePolicy}
              onAsk={handleAsk}
              onChooseCandidate={handleChooseCandidate}
              onOpenSource={openSource}
              onOpenTab={openTab}
              pendingSwitch={pendingSwitch}
              onConfirmSwitchContext={handleConfirmSwitchExisting}
              onConfirmStartNew={handleConfirmStartNew}
              onCancelSwitch={handleCancelCustomerSwitch}
            />
          )}

          <div className="shrink-0 px-4 pb-4 pt-2 sm:px-6">
            <form onSubmit={onSubmit} className="mx-auto w-full max-w-[780px]">
              {(attachedDoc || isUploading) && (
                <div className="mb-2 flex items-center gap-2 rounded-xl border border-[#BFDBFE] bg-[#F0F7FF] px-3 py-1.5 text-[12.5px] text-[#1E3A5F]">
                  {isUploading ? (
                    <>
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[#1D4ED8]" aria-hidden="true" />
                      <span>Reading the document…</span>
                    </>
                  ) : (
                    attachedDoc && (
                      <>
                        <FileText className="h-4 w-4 shrink-0 text-[#1D4ED8]" aria-hidden="true" />
                        <span className="min-w-0 truncate font-semibold" title={attachedDoc.filename}>
                          {attachedDoc.filename}
                        </span>
                        <span className="shrink-0 text-[#475569]">· {unitLabel(attachedDoc)} · answering from this document</span>
                        <button
                          type="button"
                          onClick={handleDetach}
                          disabled={isWorking}
                          aria-label={`Detach ${attachedDoc.filename}`}
                          title="Detach: answer from the policy again"
                          className="ml-auto rounded p-0.5 text-[#475569] hover:bg-white hover:text-[#0F2A43] disabled:opacity-50 cursor-pointer"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </>
                    )
                  )}
                </div>
              )}
              <div className="flex items-center gap-2 rounded-2xl border border-[#CBD5E1] bg-white py-1.5 pl-1.5 pr-1.5 shadow-[0_4px_16px_rgba(15,42,67,0.06)] transition-colors focus-within:border-[#F97316] focus-within:ring-2 focus-within:ring-[#F97316]/20">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
                  className="sr-only"
                  tabIndex={-1}
                  aria-hidden="true"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = '';
                    if (file) handleUpload(file);
                  }}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isWorking || isLoadingHistory || Boolean(loadError)}
                  aria-label="Upload a document (PDF, Word or text)"
                  title="Upload a document (PDF, Word or text, up to 10 MB)"
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[#475569] transition-colors hover:bg-[#F1F5F9] hover:text-[#0F2A43] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
                >
                  <Plus className="h-5 w-5" strokeWidth={2.25} />
                </button>
                <QuestionInput
                  variant="bare"
                  value={input}
                  onChange={setInput}
                  disabled={isWorking || isLoadingHistory || Boolean(loadError)}
                  placeholder={
                    attachedDoc
                      ? `Ask about ${attachedDoc.filename}…`
                      : activePolicy
                      ? `Ask about ${activePolicy.customer_name}'s policy, or another one…`
                      : 'Message Policy Explainer…'
                  }
                  inputRef={inputRef}
                />
                <button
                  type="submit"
                  aria-label="Send"
                  disabled={!input.trim() || isWorking || Boolean(loadError)}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#EA580C] text-white transition-colors hover:bg-[#C2410C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#EA580C] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#E2E8F0] disabled:text-[#94A3B8] cursor-pointer"
                >
                  <ArrowUp className="h-4 w-4" strokeWidth={2.5} />
                </button>
              </div>
              <p className="mt-2 text-center text-[11px] text-[#94A3B8]">
                {attachedDoc
                  ? 'Answers come from the uploaded document, cite its pages and are recorded in the Audit Log.'
                  : 'Answers come from the policy wording, cite their sources and are recorded in the Audit Log.'}
              </p>
            </form>
          </div>
        </section>
      </div>

      <AIProcessPanel content={panel} process={process} docked={docked} autoFocus={panelAutoFocus} onClose={closePanel} />
      <SourceViewer target={sourceTarget} onClose={() => setSourceTarget(null)} />

      {/* Policy and Customer Selection Modal */}
      <PolicySwitcherModal
        isOpen={policySwitcherOpen}
        onClose={() => setPolicySwitcherOpen(false)}
        currentPolicy={activePolicy}
        onSelectPolicy={handleChooseCandidate}
      />

      {routeConversationId && <span className="sr-only" data-conversation-id={routeConversationId} />}
    </div>
  );
}

export default ExplainerPage;
