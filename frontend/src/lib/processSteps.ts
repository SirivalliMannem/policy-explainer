// The pipeline steps shown in the AI process panel, built from the live run or a stored answer.
// Every value comes from the pipeline's own response or the evidence ledger; nothing is estimated
// except the token figure, which is labelled as an estimate. Imports only pure modules so
// `node --test` can load it directly.
import type {
  AskedBy,
  CompanyGuidance,
  CustomerVerification,
  GuardrailCheck,
  MeaningSearch,
  QuestionAnswerResponse,
} from '../types';
import type { StageKey, StageStatus } from './explainer';
import { evidencePercent, isRecordAnswer, searchedEvidence, topEvidencePercent } from './confidence.ts';

export type StepStatus = 'pending' | 'running' | 'done' | 'warning' | 'failed' | 'skipped';

export type StepLine =
  | { kind: 'text'; text: string; mono?: string }
  | { kind: 'passage'; form: string; page?: number | null; score: number; percent: number; matchedBy?: string | null }
  | { kind: 'check'; ok: boolean; text: string }
  | { kind: 'result'; tone: 'passed' | 'failed' | 'attention'; text: string }
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
  verify: 'Verify customer',
  context: 'Identify policy context',
  retrieve: 'Retrieve relevant evidence',
  ground: 'Build grounding context',
  generate: 'Generate grounded answer',
  citations: 'Verify citations',
  validate: 'Check guardrails',
  deliver: 'Deliver cited answer',
};

const ORDER: StageKey[] = ['verify', 'context', 'retrieve', 'ground', 'generate', 'citations', 'validate', 'deliver'];

/** Checks about citations; every other check is a guardrail. */
const CITATION_CHECKS = new Set(['inline_citations', 'citations_verified']);

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

function checkLine(c: GuardrailCheck): StepLine {
  return { kind: 'check', ok: c.status === 'passed', text: checkText(c.name, c.detail) };
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
  /** The customer verification made for the question in progress (live runs). */
  verification?: CustomerVerification | null;
}

/** What a customer was matched on, in words. */
const MATCHED_ON: Record<string, string> = {
  customer_name: 'customer name',
  surname: 'surname',
  first_name: 'first name',
  policy_number: 'policy number',
  claim_number: 'claim number',
  account_number: 'account number',
  email: 'email address',
  phone: 'phone number',
  vin: 'VIN',
  plate: 'license plate',
  address: 'address',
  vehicle: 'vehicle',
  loss_date: 'date of loss',
  selected_policy: 'the selected policy',
  conversation: 'the customer already selected in this conversation',
};

/** Verified: the customer, then where they were found in the records, then their account ID. */
function verificationLines(v: CustomerVerification): StepLine[] {
  if (v.status !== 'verified' || !v.customers.length) {
    return [{ kind: 'result', tone: v.status === 'not_found' ? 'failed' : 'attention', text: v.message }];
  }
  const customer = v.customers[0];
  const on = MATCHED_ON[v.matched_on ?? ''] ?? (v.matched_on ? v.matched_on.replace(/_/g, ' ') : 'the question');
  const showReference = v.reference && v.matched_on !== 'conversation' && v.reference !== customer.name;
  return [
    { kind: 'result', tone: 'passed', text: `Verified: ${customer.name}` },
    { kind: 'text', text: `Found in the customer records, matched on ${on}${showReference ? ` (${v.reference})` : ''}` },
    { kind: 'text', text: 'Account ID ', mono: customer.account_number || customer.customer_id },
  ];
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
    if (key === 'verify' && status === 'done') {
      if (input.verification?.status === 'verified') lines.push(...verificationLines(input.verification));
      else if (stage.detail) lines.push({ kind: 'result', tone: 'passed', text: `Verified: ${stage.detail}` });
    } else if (key === 'context' && status === 'done') {
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

/** Step 1 from the verification recorded with the answer. */
function verifyStep(result: QuestionAnswerResponse): ProcessStep {
  const v: CustomerVerification | null | undefined = result.retrieval?.customer_verification;
  if (!v && result.retrieval?.answer_type === 'document') {
    return {
      key: 'verify',
      label: STEP_LABELS.verify,
      status: 'skipped',
      lines: [{ kind: 'text', text: 'Not needed: answered from the uploaded document.' }],
    };
  }
  if (!v) {
    return {
      key: 'verify',
      label: STEP_LABELS.verify,
      status: 'skipped',
      lines: [{ kind: 'text', text: 'Customer verification was not recorded for this answer.' }],
    };
  }
  return { key: 'verify', label: STEP_LABELS.verify, status: v.status === 'verified' ? 'done' : 'warning', lines: verificationLines(v) };
}

function contextLines(result: QuestionAnswerResponse, input: ProcessInput): StepLine[] {
  const lines: StepLine[] = [];
  const doc = result.retrieval?.document;
  if (result.answer_type === 'portfolio') {
    lines.push({ kind: 'text', text: 'Portfolio lookup · answered from policy records' });
  } else if (result.retrieval?.answer_type === 'document' && doc) {
    const unit = doc.unit === 'page' ? 'page' : 'section';
    lines.push({ kind: 'text', text: `Uploaded document: ${doc.filename} · ${doc.page_count} ${unit}${doc.page_count === 1 ? '' : 's'}` });
  } else if (result.policy_context) {
    lines.push({
      kind: 'text',
      text: `Policy ${result.policy_context.policy_number} · ${result.policy_context.customer_name}`,
    });
  } else if (input.contextDetail) {
    lines.push({ kind: 'text', text: input.contextDetail });
  } else {
    lines.push({ kind: 'text', text: 'Policy: not recorded' });
  }
  // The term in force on the question's date of loss (or why none was).
  const term = result.retrieval?.term_selection;
  if (term && !input.contextDetail?.includes(term.message)) {
    lines.push(
      term.status === 'matched'
        ? { kind: 'result', tone: 'passed', text: term.message }
        : { kind: 'result', tone: 'attention', text: term.message }
    );
  }
  lines.push(asker(input.askedBy ?? result.asked_by));
  return lines;
}

/** Whether the answer reached the employee, was delivered flagged for review, or was withheld. */
function deliverStep(result: QuestionAnswerResponse, input: ProcessInput): ProcessStep {
  const who = input.askedBy ?? result.asked_by;
  const withheld = result.status === 'insufficient_evidence' || result.outcome === 'insufficient_evidence';
  const flagged = !withheld && result.outcome === 'needs_review';
  const lines: StepLine[] = [
    withheld
      ? { kind: 'result', tone: 'failed', text: 'Withheld: no answer was delivered. The question is flagged for specialist review.' }
      : flagged
      ? { kind: 'result', tone: 'attention', text: 'Delivered with a review flag: a guardrail failed, so a specialist must review this answer.' }
      : { kind: 'result', tone: 'passed', text: 'Delivered: the cited answer was shown to the employee.' },
  ];
  if (result.ledger_id) {
    lines.push({ kind: 'text', text: 'Ledger reference ', mono: result.ledger_id });
    lines.push(
      who
        ? { kind: 'text', text: `Recorded under ${who.name || 'name not recorded'} · `, mono: who.employee_id }
        : { kind: 'text', text: 'Recorded under: not recorded' }
    );
  } else {
    lines.push({ kind: 'warning', text: 'No ledger reference was recorded for this answer.' });
  }
  if (result.latency_ms !== null && result.latency_ms !== undefined) {
    lines.push({ kind: 'text', text: `Total time for the question: ${formatDuration(result.latency_ms)}` });
  }
  return { key: 'deliver', label: STEP_LABELS.deliver, status: withheld || flagged ? 'warning' : 'done', lines };
}

/** Citation verification, kept apart from the guardrails. */
function citationsStep(result: QuestionAnswerResponse, noAnswer: boolean): ProcessStep {
  if (noAnswer) {
    return { key: 'citations', label: STEP_LABELS.citations, status: 'skipped', lines: [{ kind: 'text', text: 'Skipped: no answer to cite.' }] };
  }
  const checks = result.guardrail_checks.filter((c) => CITATION_CHECKS.has(c.name));
  const verified = result.citations.length;
  const lines: StepLine[] = checks.map(checkLine);
  if (!checks.length) {
    lines.push({
      kind: 'text',
      text: verified ? `${plural(verified, 'citation')} to the policy records` : 'Citation checks not recorded for this answer.',
    });
  }
  const ok = checks.every((c) => c.status === 'passed') && verified > 0;
  lines.unshift({
    kind: 'result',
    tone: ok ? 'passed' : verified ? 'attention' : 'failed',
    text: ok
      ? `Verified: ${plural(verified, 'citation')} ${verified === 1 ? 'matches' : 'match'} the retrieved evidence.`
      : verified
      ? `Needs attention: ${plural(verified, 'citation')} verified, but not every citation check passed.`
      : 'Failed: no citation could be matched to the retrieved evidence.',
  });
  return { key: 'citations', label: STEP_LABELS.citations, status: ok ? 'done' : verified ? 'warning' : 'failed', lines };
}

/** The guardrail checks and their overall result: passed, failed (flagged or withheld) or needs attention. */
function guardrailsStep(result: QuestionAnswerResponse, ms: number | undefined, noAnswer: boolean): ProcessStep {
  const checks = result.guardrail_checks.filter((c) => !CITATION_CHECKS.has(c.name));
  if (!checks.length) {
    return {
      key: 'validate',
      label: STEP_LABELS.validate,
      status: 'skipped',
      ms,
      lines: [{ kind: 'text', text: 'Guardrail checks not recorded for this answer.' }],
    };
  }
  const failed = checks.filter((c) => c.status === 'failed');
  const attention = checks.filter((c) => c.status === 'warning');
  const names = (list: GuardrailCheck[]) => list.map((c) => c.name.replace(/_/g, ' ')).join(', ');
  let result_line: StepLine;
  let status: StepStatus;
  // Only blocking failures flag an answer for review (outcome "needs_review"); others are reported.
  const flagged = result.outcome === 'needs_review';
  if (noAnswer || flagged) {
    status = 'failed';
    result_line = {
      kind: 'result',
      tone: 'failed',
      text: noAnswer
        ? `Failed: ${names(failed) || 'evidence check'}. The answer was withheld and flagged for specialist review.`
        : `Failed: ${names(failed) || 'a blocking guardrail'}. The answer is flagged for specialist review.`,
    };
  } else if (failed.length) {
    status = 'warning';
    result_line = {
      kind: 'result',
      tone: 'attention',
      text: `Needs attention: ${names(failed)} failed. It is not a blocking check, so the answer was delivered.`,
    };
  } else if (attention.length) {
    status = 'warning';
    result_line = { kind: 'result', tone: 'attention', text: `Needs attention: ${names(attention)}.` };
  } else {
    status = 'done';
    result_line = {
      kind: 'result',
      tone: 'passed',
      text: checks.length === 1 ? 'Passed: the guardrail check passed.' : `Passed: all ${plural(checks.length, 'guardrail check')} passed.`,
    };
  }
  return { key: 'validate', label: STEP_LABELS.validate, status, ms, lines: [result_line, ...checks.map(checkLine)] };
}

/** Meaning-based search alongside word match: what it added, or why it did not run. */
export function meaningLines(meaning?: MeaningSearch | null): StepLine[] {
  if (!meaning) return []; // answers recorded before meaning search existed
  if (meaning.status !== 'used') {
    return [{ kind: 'warning', text: `Meaning search unavailable${meaning.reason ? ` (${meaning.reason})` : ''}: word match only` }];
  }
  const byMeaning = meaning.found_by_meaning ?? 0;
  const both = meaning.words_and_meaning ?? 0;
  if (!byMeaning && !both) return [{ kind: 'text', text: 'Meaning search: no passage stood out by meaning' }];
  const parts = [
    byMeaning ? `${plural(byMeaning, 'passage')} found by meaning only` : '',
    both ? `${plural(both, 'passage')} matched by words and meaning` : '',
  ].filter(Boolean);
  return [{ kind: 'text', text: `Meaning search: ${parts.join(', ')}` }];
}

/** Company guidance searched next to the policy wording: which articles matched, and on which words. */
export function guidanceLines(guidance?: CompanyGuidance | null): StepLine[] {
  if (!guidance) return []; // answers recorded before guidance was searched
  if (!guidance.searched) {
    return [{ kind: 'text', text: 'Company guidance: not shown, because no policy answer was delivered' }];
  }
  if (!guidance.articles.length) return [{ kind: 'text', text: 'Company guidance: no article on this topic' }];
  return [
    { kind: 'text', text: `Company guidance: ${plural(guidance.articles.length, 'article')} matched` },
    ...guidance.articles.map(
      (a): StepLine => ({ kind: 'text', text: `${a.ref} · ${a.title} (matched: ${a.matched_on.join(', ')})` })
    ),
  ];
}

function portfolioSteps(result: QuestionAnswerResponse, input: ProcessInput): ProcessStep[] {
  const t = result.timings_ms || {};
  const found = result.portfolio?.scope !== 'not_found';
  const count = result.portfolio?.policies.length ?? 0;
  return [
    verifyStep(result),
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
    { key: 'citations', label: STEP_LABELS.citations, status: 'skipped', lines: [{ kind: 'text', text: 'Skipped: record lookups list the records themselves.' }] },
    { key: 'validate', label: STEP_LABELS.validate, status: 'skipped', lines: [{ kind: 'text', text: 'Skipped: guardrails apply to generated answers.' }] },
    deliverStep(result, input),
  ];
}

/** Steps for a finished answer, from the pipeline's response or the stored ledger entry. */
function resultSteps(result: QuestionAnswerResponse, input: ProcessInput): ProcessStep[] {
  if (result.answer_type === 'portfolio') return portfolioSteps(result, input);

  const t = result.timings_ms || {};
  const r = result.retrieval || {};
  const records = isRecordAnswer(result);
  const noEvidence = result.status === 'insufficient_evidence' || result.evidence.length === 0;

  const retrieveLines: StepLine[] = [];
  // A several-facts question: each part and where it was answered from.
  const PART_SOURCE: Record<string, string> = {
    records: 'read from the policy records',
    forms: 'read from the attached forms',
    wording: 'clause search and the language model',
  };
  (r.parts ?? []).forEach((part, i) => {
    retrieveLines.push({
      kind: 'text',
      text: `Part ${i + 1} · ${part.label}: ${PART_SOURCE[part.source] ?? part.source}${part.found ? '' : ' (not found)'}`,
    });
  });
  if (records) {
    retrieveLines.push({ kind: 'result', tone: 'passed', text: 'Evidence confidence: exact record match. Values were read from the policy’s own records.' });
  } else if (r.answer_type === 'document' && r.document) {
    retrieveLines.push({
      kind: 'text',
      text:
        r.mode === 'summary'
          ? `Read ${plural(r.passages_searched ?? 0, 'passage')} across ${r.document.filename} for the explanation`
          : `Searched ${plural(r.passages_searched ?? 0, 'passage')} of ${r.document.filename}`,
    });
  } else if (r.clauses_searched !== undefined || r.forms_searched !== undefined) {
    const passages = (r.clauses_searched ?? 0) + (r.coverages_searched ?? 0) + (r.claims_searched ?? 0) + (r.billing_searched ?? 0);
    retrieveLines.push({
      kind: 'text',
      text: `Searched ${plural(passages, 'passage')} across ${plural(r.forms_searched ?? 0, 'form')}`,
    });
    retrieveLines.push(...meaningLines(r.meaning_search));
  } else {
    retrieveLines.push({ kind: 'text', text: 'Search counts not recorded for this answer.' });
  }
  if (noEvidence) {
    retrieveLines.push({ kind: 'warning', text: 'No passage matched the question.' });
  } else {
    const top = topEvidencePercent(result);
    // The whole-document explanation reads passages across the document; it scores none of them.
    const unscored = r.answer_type === 'document' && r.mode === 'summary';
    if (!records && !unscored && top !== null) {
      retrieveLines.push({
        kind: 'result',
        tone: top >= 100 ? 'passed' : 'attention',
        text: `Evidence confidence: ${top}%`,
      });
    }
    for (const item of searchedEvidence(result.evidence)) {
      if (records || unscored || item.relevance_score === null || item.relevance_score === undefined) continue;
      retrieveLines.push({
        kind: 'passage',
        form: item.form_number || item.title || item.source_type,
        page: item.page,
        score: item.relevance_score,
        percent: evidencePercent(item.relevance_score) ?? 0,
        ...(item.matched_by ? { matchedBy: item.matched_by } : {}),
      });
    }
  }

  retrieveLines.push(...guidanceLines(r.company_guidance));

  const steps: ProcessStep[] = [
    verifyStep(result),
    { key: 'context', label: STEP_LABELS.context, status: 'done', ms: t.interpretation ?? result.interpretation?.latency_ms, lines: contextLines(result, input) },
    { key: 'retrieve', label: STEP_LABELS.retrieve, status: noEvidence ? 'warning' : 'done', ms: t.retrieval, lines: retrieveLines },
  ];

  if (noEvidence) {
    steps.push(
      { key: 'ground', label: STEP_LABELS.ground, status: 'skipped', lines: [{ kind: 'text', text: 'Skipped: no evidence to ground an answer in.' }] },
      { key: 'generate', label: STEP_LABELS.generate, status: 'skipped', lines: [{ kind: 'text', text: 'Skipped: not enough evidence to draft an answer.' }] }
    );
  } else if (records) {
    steps.push(
      { key: 'ground', label: STEP_LABELS.ground, status: 'skipped', lines: [{ kind: 'text', text: 'Skipped: values are read directly from the records.' }] },
      { key: 'generate', label: STEP_LABELS.generate, status: 'skipped', lines: [{ kind: 'text', text: 'Skipped: answered straight from the policy records; no language model was used.' }] }
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
      }
    );
  }
  steps.push(citationsStep(result, noEvidence), guardrailsStep(result, t.validation, noEvidence), deliverStep(result, input));
  return steps;
}

export function buildProcessSteps(input: ProcessInput): ProcessStep[] {
  if (input.result) return resultSteps(input.result, input);
  if (input.stages) return liveSteps(input.stages, input);
  return ORDER.map((key) => ({ key, label: STEP_LABELS[key], status: 'pending', lines: [] }));
}
