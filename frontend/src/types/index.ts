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

export interface CitationItem {
  source_id?: string | null;
  form_number?: string | null;
  edition?: string | null;
  page?: number | null;
  section?: string | null;
  heading?: string | null;
  citation_text?: string | null;
}

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
}

export interface QuestionAnswerResponse {
  conversation_id: string;
  question_id: string;
  question: string;
  answer: string;
  policy_context?: PolicyContextCandidate | null;
  evidence: EvidenceItem[];
  citations: CitationItem[];
  confidence: string;
  status: string;
  suggested_questions: string[];
}

export interface ConversationResponse {
  conversation_id: string;
  employee_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  policy_context?: PolicyContextCandidate | null;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  confidence?: string;
  evidence?: EvidenceItem[];
  citations?: CitationItem[];
  suggestedQuestions?: string[];
  status?: string;
  isAnalyzing?: boolean;
  policyContext?: PolicyContextCandidate | null;
}

