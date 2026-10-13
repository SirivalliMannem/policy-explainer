// The six pipeline steps shown in the AI process panel, built from the live run or a stored answer.
// Every value comes from the pipeline's own response or the evidence ledger; nothing is estimated
// except the token figure, which is labelled as an estimate. Kept free of runtime imports so
// `node --test` can load it directly.
import type { AskedBy, QuestionAnswerResponse } from '../types';
import type { StageKey, StageStatus } from './explainer';

export type StepStatus = 'pending' | 'running' | 'done' | 'warning' | 'failed' | 'skipped';

export type StepLine =
  | { kind: 'text'; text: string; mono?: string }
  | { kind: 'passage'; form: string; page?: number | null; score: number; ratio: number }
  | { kind: 'check'; ok: boolean; text: string }
  | { kind: 'warning'; text: string }
  | { kind: 'error'; text: string };

export interface ProcessStep {
  key: StageKey;
  label: string;
  status: StepStatus;
  ms?: number | null;
  lines: StepLine[];
}

export const STEP_LABELS: Record<StageKey, string> = {
  context: 'Identify policy context',
  retrieve: 'Retrieve relevant evidence',
  ground: 'Build grounding context',
  generate: 'Generate grounded answer',
  validate: 'Validate citations & guardrails',
  deliver: 'Deliver cited answer',
};

const ORDER: StageKey[] = ['context', 'retrieve', 'ground', 'generate', 'validate', 'deliver'];

/** A rough, widely used rule of thumb for English text: about four characters per token. */
export const CHARS_PER_TOKEN = 4;

export function formatDuration(ms?: number | null): string {
  if (ms === null || ms === undefined) return '';
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

function asker(askedBy?: AskedBy | null): StepLine {
  if (!askedBy) return { kind: 'text', text: 'Asked by: not recorded' };
  return { kind: 'text', text: `Asked by ${askedBy.name || 'name not recorded'} · `, mono: askedBy.employee_id };
}

function checkText(name: string, detail: string): string {
  return detail || name.replace(/_/g, ' ');
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString()} ${n === 1 ? one : many}`;
}

export interface LiveStage {
  status: StageStatus;
  detail?: string;
}

export interface ProcessInput {
  /** The answer, live or stored. When present every step is built from it. */
  result?: QuestionAnswerResponse | null;
  /** Live stage states while a question is in flight (no result yet). */
  stages?: Record<StageKey, LiveStage> | null;
  askedBy?: AskedBy | null;
  /** How the policy was identified in this session ("matched on policy number"), when known. */
  contextDetail?: string | null;
}

const LIVE_STATUS: Record<StageStatus, StepStatus> = {
  waiting: 'pending',
  processing: 'running',
  completed: 'done',
  failed: 'failed',
  attention: 'warning',
  skipped: 'skipped',
};

/** Steps while the request is in flight: statuses only, plus what is genuinely known so far. */
function liveSteps(stages: Record<StageKey, LiveStage>, input: ProcessInput): ProcessStep[] {
  const steps = ORDER.map((key): ProcessStep => {
    const stage = stages[key];
    const status = LIVE_STATUS[stage.status];
    const lines: StepLine[] = [];
    if (key === 'context' && status === 'done') {
      if (stage.detail) lines.push({ kind: 'text', text: stage.detail });
      lines.push(asker(input.askedBy));
    } else if (status === 'failed') {
      lines.push({ kind: 'error', text: stage.detail || 'This step failed.' });
    } else if (status === 'warning' && stage.detail) {
      lines.push({ kind: 'warning', text: stage.detail });
    } else if (status === 'skipped' && stage.detail) {
      lines.push({ kind: 'text', text: stage.detail });
    }
    return { key, label: STEP_LABELS[key], status, lines };
  });
  // Once a step has failed nothing after it runs: never leave a spinner going.
  const failedAt = steps.findIndex((s) => s.status === 'failed');
  if (failedAt >= 0) {
    for (const step of steps.slice(failedAt + 1)) {
      if (step.status === 'running' || step.status === 'pending') {
        step.status = 'skipped';
        step.lines = [{ kind: 'text', text: 'Not run: an earlier step failed.' }];
      }
    }
  }
  return steps;
}

function contextLines(result: QuestionAnswerResponse, input: ProcessInput): StepLine[] {
  const lines: StepLine[] = [];
  if (input.contextDetail) {
    lines.push({ kind: 'text', text: input.contextDetail });
  } else if (result.answer_type === 'portfolio') {
    lines.push({ kind: 'text', text: 'Portfolio lookup · answered from policy records' });
  } else if (result.policy_context) {
    lines.push({
      kind: 'text',
      text: `Policy ${result.policy_context.policy_number} · ${result.policy_context.customer_name}`,
    });
  } else {
    lines.push({ kind: 'text', text: 'Policy: not recorded' });
  }
  lines.push(asker(input.askedBy ?? result.asked_by));
  return lines;
}

function deliverStep(result: QuestionAnswerResponse, input: ProcessInput): ProcessStep {
  const who = input.askedBy ?? result.asked_by;
  const lines: StepLine[] = result.ledger_id
    ? [
        { kind: 'text', text: 'Ledger reference ', mono: result.ledger_id },
        who
          ? { kind: 'text', text: `Recorded under ${who.name || 'name not recorded'} · `, mono: who.employee_id }
          : { kind: 'text', text: 'Recorded under: not recorded' },
      ]
    : [{ kind: 'warning', text: 'No ledger reference was recorded for this answer.' }];
  if (result.latency_ms !== null && result.latency_ms !== undefined) {
    lines.push({ kind: 'text', text: `Total time for the question: ${formatDuration(result.latency_ms)}` });
  }
  return { key: 'deliver', label: STEP_LABELS.deliver, status: 'done', lines };
}

function portfolioSteps(result: QuestionAnswerResponse, input: ProcessInput): ProcessStep[] {
  const t = result.timings_ms || {};
  const found = result.portfolio?.scope !== 'not_found';
  const count = result.portfolio?.policies.length ?? 0;
  return [
    { key: 'context', label: STEP_LABELS.context, status: 'done', ms: t.interpretation ?? result.interpretation?.latency_ms, lines: contextLines(result, input) },
    {
      key: 'retrieve',
      label: STEP_LABELS.retrieve,
      status: found ? 'done' : 'warning',
      ms: t.retrieval,
      lines: [
        found
          ? { kind: 'text', text: `${plural(count, 'policy record')} matched in the policy system` }
          : { kind: 'warning', text: 'No matching policyholder on file.' },
      ],
    },
    { key: 'ground', label: STEP_LABELS.ground, status: 'skipped', lines: [{ kind: 'text', text: 'Skipped: answered from policy records, not policy wording.' }] },
    { key: 'generate', label: STEP_LABELS.generate, status: 'skipped', lines: [{ kind: 'text', text: 'Skipped: no language model is used for record lookups.' }] },
    { key: 'validate', label: STEP_LABELS.validate, status: 'skipped', lines: [{ kind: 'text', text: 'Skipped: guardrails apply to generated answers.' }] },
    deliverStep(result, input),
  ];
}

/** Steps for a finished answer, from the pipeline's response or the stored ledger entry. */
function resultSteps(result: QuestionAnswerResponse, input: ProcessInput): ProcessStep[] {
  if (result.answer_type === 'portfolio') return portfolioSteps(result, input);

  const t = result.timings_ms || {};
  const r = result.retrieval || {};
  const noEvidence = result.status === 'insufficient_evidence' || result.evidence.length === 0;

  const retrieveLines: StepLine[] = [];
  if (r.clauses_searched !== undefined || r.forms_searched !== undefined) {
    const passages = (r.clauses_searched ?? 0) + (r.coverages_searched ?? 0) + (r.claims_searched ?? 0) + (r.billing_searched ?? 0);
    retrieveLines.push({
      kind: 'text',
      text: `Searched ${plural(passages, 'passage')} across ${plural(r.forms_searched ?? 0, 'form')}`,
    });
  } else {
    retrieveLines.push({ kind: 'text', text: 'Search counts not recorded for this answer.' });
  }
  if (noEvidence) {
    retrieveLines.push({ kind: 'warning', text: 'No passage matched the question.' });
  } else {
    const scores = result.evidence.map((e) => e.relevance_score ?? 0);
    const top = Math.max(...scores, 0);
    for (const item of result.evidence) {
      if (item.relevance_score === null || item.relevance_score === undefined) continue;
      retrieveLines.push({
        kind: 'passage',
        form: item.form_number || item.title || item.source_type,
        page: item.page,
        score: item.relevance_score,
        ratio: top > 0 ? item.relevance_score / top : 0,
      });
    }
  }

  const steps: ProcessStep[] = [
    { key: 'context', label: STEP_LABELS.context, status: 'done', ms: t.interpretation ?? result.interpretation?.latency_ms, lines: contextLines(result, input) },
    { key: 'retrieve', label: STEP_LABELS.retrieve, status: noEvidence ? 'warning' : 'done', ms: t.retrieval, lines: retrieveLines },
  ];

  if (noEvidence) {
    steps.push(
      { key: 'ground', label: STEP_LABELS.ground, status: 'skipped', lines: [{ kind: 'text', text: 'Skipped: no evidence to ground an answer in.' }] },
      { key: 'generate', label: STEP_LABELS.generate, status: 'skipped', lines: [{ kind: 'text', text: 'Skipped: not enough evidence to draft an answer.' }] },
      {
        key: 'validate',
        label: STEP_LABELS.validate,
        status: 'warning',
        ms: t.validation,
        lines: [
          ...result.guardrail_checks.map((c): StepLine => ({ kind: 'check', ok: c.status === 'passed', text: checkText(c.name, c.detail) })),
          { kind: 'warning', text: 'Answer withheld and flagged for specialist review.' },
        ],
      }
    );
  } else {
    const chars = result.grounding_context_chars;
    steps.push(
      {
        key: 'ground',
        label: STEP_LABELS.ground,
        status: 'done',
        ms: t.grounding,
        lines: [
          { kind: 'text', text: `${plural(result.evidence.length, 'passage')} kept in the grounding context` },
          chars
            ? {
                kind: 'text',
                text: `≈ ${Math.round(chars / CHARS_PER_TOKEN).toLocaleString()} tokens (estimated from ${chars.toLocaleString()} characters)`,
              }
            : { kind: 'text', text: 'Context size not recorded for this answer.' },
        ],
      },
      {
        key: 'generate',
        label: STEP_LABELS.generate,
        status: result.is_fallback ? 'warning' : 'done',
        ms: t.generation,
        lines: [
          !result.model_used || result.model_used === 'unknown'
            ? { kind: 'text', text: 'Model: not recorded' }
            : { kind: 'text', text: 'Model ', mono: result.model_used },
          { kind: 'text', text: 'Drafts the answer from the supplied passages only.' },
          ...(result.is_fallback
            ? [{ kind: 'warning', text: `Fallback engine used${result.fallback_reason ? `: ${result.fallback_reason}` : '.'}` } as StepLine]
            : []),
        ],
      },
      {
        key: 'validate',
        label: STEP_LABELS.validate,
        status: result.guardrail_status === 'passed' ? 'done' : 'warning',
        ms: t.validation,
        lines: result.guardrail_checks.length
          ? result.guardrail_checks.map((c): StepLine => ({ kind: 'check', ok: c.status === 'passed', text: checkText(c.name, c.detail) }))
          : [{ kind: 'text', text: 'Guardrail checks not recorded for this answer.' }],
      }
    );
  }
  steps.push(deliverStep(result, input));
  return steps;
}

export function buildProcessSteps(input: ProcessInput): ProcessStep[] {
  if (input.result) return resultSteps(input.result, input);
  if (input.stages) return liveSteps(input.stages, input);
  return ORDER.map((key) => ({ key, label: STEP_LABELS[key], status: 'pending', lines: [] }));
}
