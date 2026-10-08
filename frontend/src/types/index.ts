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
