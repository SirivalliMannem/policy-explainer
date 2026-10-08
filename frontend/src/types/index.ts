import { ComponentType } from 'react';

export interface NavItem {
  title: string;
  href: string;
  icon: ComponentType<{ className?: string; size?: number | string }>;
  badge?: string;
}

export interface HealthCheckResponse {
  status: string;
  service?: string;
  database?: string;
}

export interface DashboardMetrics {
  questions_answered: number;
  total_questions: number;
  resolution_rate: number;
  evidence_coverage: number;
  low_confidence: number;
}

export interface ActivityDataPoint {
  label: string;
  timestamp: string;
  questions_asked: number;
  questions_answered: number;
  insufficient_evidence: number;
}

export interface EvidenceQualityBreakdown {
  high: number;
  medium: number;
  low: number;
  total: number;
}

export interface RecentQuestionItem {
  question_id: string;
  conversation_id: string;
  question: string;
  status: string;
  confidence?: string | null;
  customer_name: string;
  customer_id?: string | null;
  policy_number: string;
  policy_id?: string | null;
  created_at: string;
}

export interface DashboardResponse {
  metrics: DashboardMetrics;
  activity: ActivityDataPoint[];
  evidence_quality: EvidenceQualityBreakdown;
  recent_questions: RecentQuestionItem[];
}

// ==========================================
// Policy Entities & Feature Data Types
// ==========================================

export interface PolicyDetail {
  policy_id: string;
  policy_number: string;
  customer_id: string;
  customer_name: string;
  line_of_business: string;
  product_name?: string | null;
  status: string;
  effective_date: string;
  expiration_date: string;
  term_number: number;
  insured_location: string;
  annual_premium: number;
}

export interface CoverageItem {
  id: string;
  policy_id: string;
  name: string;
  pattern_code?: string | null;
  limit_text?: string | null;
  limit_amount?: number | null;
  deductible_text?: string | null;
  deductible_amount?: number | null;
  governing_form?: string | null;
  included: boolean;
  sort_order: number;
}

export interface FormItem {
  id: string;
  policy_id?: string | null;
  form_number: string;
  edition: string;
  title: string;
  kind: string;
  line_of_business: string;
  state?: string | null;
  page_count: number;
  effective_from?: string | null;
  effective_to?: string | null;
}

export interface ClaimItem {
  id: string;
  policy_id: string;
  claim_number: string;
  loss_date?: string | null;
  reported_date?: string | null;
  loss_cause?: string | null;
  loss_location?: string | null;
  description?: string | null;
  status: string;
  adjuster?: string | null;
  exposures?: unknown[];
  contacts?: unknown[];
}

export interface BillingItem {
  id: string;
  policy_id: string;
  account_number?: string | null;
  plan: string;
  status: string;
  next_due_date?: string | null;
  next_due_amount: number;
  past_due_amount: number;
  paid_to_date: number;
}

// ==========================================
// Policy Resolution & Conversation Types
// ==========================================

export interface PolicyContextCandidate {
  policy_id: string;
  policy_number: string;
  customer_id: string;
  customer_name: string;
  line_of_business: string;
  product_name?: string | null;
  status: string;
  effective_date: string;
  expiration_date: string;
}

export type ResolutionStatus = 'resolved' | 'ambiguous' | 'not_found' | 'no_reference';

/** How a loosely written question was understood before retrieval. */
export interface Interpretation {
  original: string;
  corrected: string;
  normalized: string;
  /** llm: rewritten by the language model; rules: spelling/names/synonyms only (no model call). */
  method: 'llm' | 'rules' | string;
  intent?: string | null;
  policyholders: string[];
  policy_numbers: string[];
  line_of_business?: string | null;
  search_terms: string[];
  corrections: { from: string; to: string }[];
  fallback_reason?: string | null;
  latency_ms: number;
}

export interface QuestionResolution {
  status: ResolutionStatus;
  /** "portfolio": counts or lists policies/customers; answered from policy records, no single-policy context needed. */
  intent: 'policy' | 'portfolio';
  matched_on?: 'policy_number' | 'customer_name' | 'surname' | 'first_name' | null;
  reference?: string | null;
  policy?: PolicyContextCandidate | null;
  candidates: PolicyContextCandidate[];
  message: string;
  interpretation?: Interpretation | null;
}

export interface CitationItem {
  source_id?: string | null;
  source_type?: string | null;
  evidence_index?: number | null;
  form_number?: string | null;
  edition?: string | null;
  page?: number | null;
  section?: string | null;
  heading?: string | null;
  citation_text?: string | null;
}

export type EvidenceScope = 'customer_form' | 'product_wording' | 'policy_record';

export interface EvidenceItem {
  source_type: string;
  source_id: string;
  title?: string | null;
  form_number?: string | null;
  edition?: string | null;
  page?: number | null;
  section?: string | null;
  heading?: string | null;
  content: string;
  plain_language?: string | null;
  relevance_score?: number | null;
  evidence_index?: number | null;
  scope?: EvidenceScope | string | null;
}

export type GuardrailCheckStatus = 'passed' | 'warning' | 'failed';

export interface GuardrailCheck {
  name: string;
  status: GuardrailCheckStatus | string;
  detail: string;
}

export interface RetrievalSummary {
  query_terms?: string[];
  coverages_searched?: number;
  forms_searched?: number;
  clauses_searched?: number;
  claims_searched?: number;
  billing_searched?: number;
  candidates_scored?: number;
  duplicates_removed?: number;
  used_previous_question?: boolean;
  interpretation?: Interpretation | null;
}

export type AnswerOutcome = 'answered' | 'needs_review' | 'insufficient_evidence';

export interface PortfolioPolicy {
  policy_id: string;
  policy_number: string;
  customer_id: string;
  customer_name: string;
  line_of_business: string;
  product_name?: string | null;
  status: string;
  state?: string | null;
  term_number: number;
  effective_date: string;
  expiration_date: string;
  earlier_terms: number;
}

export interface PortfolioAnswer {
  scope: 'customer' | 'household' | 'book' | 'not_found' | string;
  customers: string[];
  filters: Record<string, string>;
  policies: PortfolioPolicy[];
}

export interface QuestionAnswerResponse {
  conversation_id: string;
  question_id: string;
  question: string;
  answer: string;
  /** policy_explanation: grounded answer about one policy; portfolio: facts read from policy records. */
  answer_type: 'policy_explanation' | 'portfolio' | string;
  portfolio?: PortfolioAnswer | null;
  policy_context?: PolicyContextCandidate | null;
  evidence: EvidenceItem[];
  citations: CitationItem[];
  confidence: string;
  status: string;
  suggested_questions: string[];
  guardrail_status: string;
  guardrail_checks: GuardrailCheck[];
  outcome: AnswerOutcome | string;
  model_used: string;
  provider: string;
  is_fallback: boolean;
  fallback_reason?: string | null;
  retrieval: RetrievalSummary;
  timings_ms: Partial<Record<'retrieval' | 'grounding' | 'generation' | 'validation', number>>;
  latency_ms?: number | null;
  ledger_id?: string | null;
  interpretation?: Interpretation | null;
}

export interface ConversationResponse {
  conversation_id: string;
  employee_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  policy_context?: Pick<
    PolicyContextCandidate,
    'policy_id' | 'policy_number' | 'customer_id' | 'customer_name' | 'line_of_business' | 'product_name' | 'status'
  > | null;
}

export interface ConversationMessageRecord {
  question_id: string;
  question: string;
  status: string;
  policy_id?: string | null;
  created_at: string;
  answer?: QuestionAnswerResponse | null;
}

// ==========================================
// Source Viewer
// ==========================================

export interface SourcePassage {
  source_id: string;
  page?: number | null;
  section?: string | null;
  heading?: string | null;
  text: string;
  plain_language?: string | null;
  is_cited: boolean;
}

export interface SourceDocument {
  source_type: string;
  source_id: string;
  representation: string;
  pdf_available: boolean;
  scope?: string | null;
  policy_id?: string | null;
  policy_number?: string | null;
  form_number?: string | null;
  form_title?: string | null;
  form_kind?: string | null;
  edition?: string | null;
  page?: number | null;
  page_count?: number | null;
  section?: string | null;
  heading?: string | null;
  text: string;
  plain_language?: string | null;
  record_fields: Record<string, string>;
  passages: SourcePassage[];
}

/** What the source viewer is asked to open: a stored source, optionally with the evidence row it came from. */
export interface SourceTarget {
  sourceType: string;
  sourceId: string;
  evidence?: EvidenceItem | null;
}

// ==========================================
// Evidence Ledger ("The Record")
// ==========================================

export interface LedgerSummary {
  answers_recorded: number;
  carrier_source_count: number;
  carrier_source_pct: number;
  resolved_without_person_count: number;
  resolved_without_person_pct: number;
  p95_response_ms?: number | null;
  waiting_on_person: number;
  model_answers: number;
  fallback_answers: number;
}

export interface LedgerRow {
  id: string;
  created_at: string;
  conversation_id: string;
  question_id: string;
  agent?: string | null;
  insured?: string | null;
  customer_id?: string | null;
  policy_id?: string | null;
  answer_type: 'policy_explanation' | 'portfolio' | string;
  policy_number?: string | null;
  policy_term?: number | null;
  policy_effective?: string | null;
  policy_expiration?: string | null;
  state?: string | null;
  line_of_business?: string | null;
  question: string;
  sources: string[];
  source_count: number;
  model_used?: string | null;
  provider?: string | null;
  is_fallback?: boolean | null;
  confidence: string;
  guardrail_status: string;
  outcome: AnswerOutcome | string;
  reviewer?: string | null;
  latency_ms?: number | null;
}

export interface LedgerPage {
  items: LedgerRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface LedgerFilters {
  insureds: { value: string; label: string }[];
  states: string[];
  lines: string[];
  outcomes: string[];
}

export interface LedgerDetail extends LedgerRow {
  answer: string;
  product_name?: string | null;
  evidence: EvidenceItem[];
  citations: CitationItem[];
  guardrail_checks: GuardrailCheck[];
  suggested_questions: string[];
  fallback_reason?: string | null;
  retrieval: RetrievalSummary;
  timings_ms: Partial<Record<'retrieval' | 'grounding' | 'generation' | 'validation', number>>;
}

export interface LedgerQuery {
  search?: string;
  insured?: string;
  state?: string;
  line?: string;
  outcome?: string;
  date_from?: string;
  date_to?: string;
  sort?: 'newest' | 'oldest' | 'slowest' | 'fastest';
  limit?: number;
  offset?: number;
}
