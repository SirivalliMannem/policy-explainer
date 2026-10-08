import { ApiError } from '../services/api';
import type { CitationItem, EvidenceItem, Interpretation, QuestionAnswerResponse } from '../types';

// ==========================================
// Labels & formatting
// ==========================================

export function lineLabel(line?: string | null): string {
  if (line === 'homeowners') return 'Homeowners';
  if (line === 'personal_auto') return 'Personal Auto';
  return line ? line.replace(/_/g, ' ') : '—';
}

export function statusLabel(status?: string | null): string {
  if (status === 'in_force') return 'In Force';
  return status ? status.replace(/_/g, ' ') : '—';
}

export function outcomeLabel(outcome?: string | null): string {
  switch (outcome) {
    case 'answered':
      return 'Answered';
    case 'needs_review':
      return 'Needs review';
    case 'insufficient_evidence':
      return 'Insufficient evidence';
    default:
      return outcome || '—';
  }
}

export function formatDate(value?: string | null): string {
  if (!value) return '—';
  const d = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  if (isNaN(d.getTime())) return value;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '—';
  // The backend stores naive UTC timestamps.
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
  if (isNaN(d.getTime())) return value;
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export function formatMs(ms?: number | null): string {
  if (ms === null || ms === undefined) return '—';
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

/** Human-readable name for a guardrail check identifier such as `cross_policy_leak`. */
export function checkLabel(name: string): string {
  return name.replace(/_/g, ' ');
}

export function modelLabel(result: Pick<QuestionAnswerResponse, 'model_used' | 'provider' | 'is_fallback'>): string {
  if (!result.model_used || result.model_used === 'none') return 'No model call';
  if (result.is_fallback) return 'Deterministic grounded engine';
  const provider = result.provider && result.provider !== 'none' ? result.provider : '';
  return provider ? `${provider[0].toUpperCase()}${provider.slice(1)} · ${result.model_used}` : result.model_used;
}

// ==========================================
// Citations
// ==========================================

/** Short label shown on an orange source chip, e.g. "HO 04 95 · p.1". */
export function evidenceChipLabel(item: Pick<EvidenceItem, 'form_number' | 'page' | 'source_type' | 'title'>): string {
  if (item.form_number) return item.page ? `${item.form_number} · p.${item.page}` : item.form_number;
  return item.title || item.source_type;
}

/** Full citation metadata line, e.g. "HO 04 95 · Ed. 10 00 · p.1 · Water Back-Up". */
export function citationLine(c: CitationItem | EvidenceItem): string {
  const parts = [c.form_number, c.edition ? `Ed. ${c.edition}` : null, c.page ? `p.${c.page}` : null, c.heading];
  return parts.filter(Boolean).join(' · ');
}

export function evidenceByIndex(evidence: EvidenceItem[], index: number): EvidenceItem | undefined {
  return evidence.find((e) => e.evidence_index === index) ?? evidence[index - 1];
}

// ==========================================
// Question understanding
// ==========================================

function comparable(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

/** The understood wording, when it differs from what was typed in a way worth showing. */
export function interpretedText(interpretation?: Interpretation | null): string | null {
  if (!interpretation) return null;
  const understood = interpretation.method === 'llm' ? interpretation.corrected : interpretation.normalized;
  if (!understood || comparable(understood) === comparable(interpretation.original)) return null;
  return understood;
}

export function interpretationMethodLabel(interpretation: Interpretation): string {
  return interpretation.method === 'llm' ? 'AI-normalised' : 'Spelling & names corrected';
}

// ==========================================
// Errors
// ==========================================

export interface FriendlyError {
  title: string;
  message: string;
}

/** Turn a failed request into an enterprise-friendly explanation of what broke. */
export function describeError(err: unknown): FriendlyError {
  if (err instanceof ApiError) {
    const detail = err.detail;
    switch (err.status) {
      case 0:
        return {
          title: 'Backend unavailable',
          message: 'The Policy Explainer backend (port 8000) could not be reached. Check that it is running and try again.',
        };
      case 408:
        return {
          title: 'Request timed out',
          message: 'No response arrived within 60 seconds. The AI service or the language model may be overloaded; try again shortly.',
        };
      case 503:
        return { title: 'AI service unavailable', message: detail || 'The AI service (port 8001) is not reachable from the backend.' };
      case 504:
        return { title: 'AI service timed out', message: detail || 'The AI service took too long to answer.' };
      case 502:
        return { title: 'AI service error', message: detail || 'The AI service returned an error.' };
      case 404:
        return { title: 'Not found', message: detail || 'The requested policy or conversation no longer exists.' };
      case 400:
        return { title: 'Cannot answer yet', message: detail || 'The request was not valid.' };
      default:
        return {
          title: 'Backend error',
          message: detail || `The backend returned status ${err.status}. This is often a database connectivity problem.`,
        };
    }
  }
  return { title: 'Unexpected error', message: err instanceof Error ? err.message : 'Something went wrong.' };
}

// ==========================================
// AI process stages
// ==========================================

export type StageKey = 'context' | 'retrieve' | 'ground' | 'generate' | 'validate' | 'deliver';
export type StageStatus = 'waiting' | 'processing' | 'completed' | 'failed' | 'attention' | 'skipped';

export interface StageState {
  status: StageStatus;
  detail?: string;
  ms?: number | null;
}

export const STAGES: { key: StageKey; label: string }[] = [
  { key: 'context', label: 'Identify policy context' },
  { key: 'retrieve', label: 'Retrieve relevant evidence' },
  { key: 'ground', label: 'Build grounding context' },
  { key: 'generate', label: 'Generate grounded answer' },
  { key: 'validate', label: 'Validate citations & guardrails' },
  { key: 'deliver', label: 'Deliver cited answer' },
];

export type ProcessPhase = 'idle' | 'running' | 'completed' | 'needs_input' | 'failed';

export interface ProcessState {
  phase: ProcessPhase;
  stages: Record<StageKey, StageState>;
  result: QuestionAnswerResponse | null;
}

export function freshStages(): Record<StageKey, StageState> {
  return {
    context: { status: 'waiting' },
    retrieve: { status: 'waiting' },
    ground: { status: 'waiting' },
    generate: { status: 'waiting' },
    validate: { status: 'waiting' },
    deliver: { status: 'waiting' },
  };
}

export const IDLE_PROCESS: ProcessState = { phase: 'idle', stages: freshStages(), result: null };

/** Final stage states derived from what the AI service actually returned and measured. */
export function stagesFromResult(result: QuestionAnswerResponse, contextDetail: string): Record<StageKey, StageState> {
  const t = result.timings_ms || {};
  const r = result.retrieval || {};
  const searched = `${r.clauses_searched ?? 0} clauses, ${r.coverages_searched ?? 0} coverages, ${r.forms_searched ?? 0} forms`;
  const stages = freshStages();
  stages.context = { status: 'completed', detail: contextDetail };

  if (result.answer_type === 'portfolio') {
    const portfolio = result.portfolio;
    const found = portfolio?.scope !== 'not_found';
    stages.retrieve = {
      status: found ? 'completed' : 'failed',
      detail: found
        ? `${portfolio?.policies.length ?? 0} policy records matched in the policy system`
        : 'No matching policyholder on file',
      ms: t.retrieval,
    };
    stages.ground = { status: 'skipped', detail: 'Not needed — answered from policy records, not policy wording' };
    stages.generate = { status: 'skipped', detail: 'No language model used' };
    stages.validate = { status: 'skipped', detail: 'Guardrails apply to generated answers, not record lookups' };
    stages.deliver = { status: 'completed', detail: 'Policy list returned to the browser', ms: result.latency_ms };
    return stages;
  }

  if (result.status === 'insufficient_evidence') {
    stages.retrieve = { status: 'failed', detail: `No matching evidence (searched ${searched})`, ms: t.retrieval };
    stages.ground = { status: 'skipped', detail: 'Nothing to ground' };
    stages.generate = { status: 'skipped', detail: 'No answer generated without evidence' };
    stages.validate = { status: 'skipped' };
    stages.deliver = { status: 'completed', detail: 'Insufficient-evidence response delivered', ms: result.latency_ms };
    return stages;
  }

  const failed = result.guardrail_checks.filter((c) => c.status === 'failed').length;
  const passed = result.guardrail_checks.filter((c) => c.status === 'passed').length;
  stages.retrieve = { status: 'completed', detail: `${result.evidence.length} evidence items from ${searched}`, ms: t.retrieval };
  stages.ground = { status: 'completed', detail: 'Policy, customer and evidence sections assembled', ms: t.grounding };
  stages.generate = {
    status: result.is_fallback ? 'attention' : 'completed',
    detail: result.is_fallback
      ? `Fallback engine used${result.fallback_reason ? ` — ${result.fallback_reason}` : ''}`
      : modelLabel(result),
    ms: t.generation,
  };
  stages.validate = {
    status: result.guardrail_status === 'passed' ? 'completed' : 'attention',
    detail:
      result.guardrail_status === 'passed'
        ? `${passed}/${result.guardrail_checks.length} checks passed · ${result.citations.length} citations verified`
        : `${failed} check(s) failed — flagged for review`,
    ms: t.validation,
  };
  stages.deliver = { status: 'completed', detail: 'Answer returned to the browser', ms: result.latency_ms };
  return stages;
}
