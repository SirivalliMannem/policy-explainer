export interface AgentRecord {
  id: string; // e.g., 'A02'
  name: string; // e.g., 'Policy Explainer'
  streamId: string; // e.g., 'S2'
  streamName: string; // e.g., 'Customer Service & Experience'
  executive: string; // e.g., 'VP Customer Care / Chief Customer Officer'
  status: 'live' | 'preview' | 'coming_soon';
  route?: string; // e.g., '/app/explainer'
  description: string;
  capabilities: string[];
}

export interface ValueStream {
  id: string; // 'S1' to 'S6'
  name: string;
  shortName: string;
  executive: string;
  icon: string;
  tagColor: string;
  accentColor: string;
  agents: AgentRecord[];
}

export const VALUE_STREAMS: ValueStream[] = [
  {
    id: 'S1',
    name: 'Claims Operations',
    shortName: 'Claims',
    executive: 'Chief Claims Officer',
    icon: '🛡️',
    tagColor: '#FFE9DC',
    accentColor: '#F97316',
    agents: [
      {
        id: 'A14',
        name: 'First Notice of Loss Intake',
        streamId: 'S1',
        streamName: 'Claims Operations',
        executive: 'Chief Claims Officer',
        status: 'coming_soon',
        description:
          'Conversational FNOL intake capturing incident details, loss date, damaged property, and photos directly into carrier claims systems with zero re-keying.',
        capabilities: [
          'Omnichannel incident fact extraction',
          'Automated loss-date verification',
          'Damage photo triage and initial categorization',
        ],
      },
      {
        id: 'A15',
        name: 'Coverage & Triage',
        streamId: 'S1',
        streamName: 'Claims Operations',
        executive: 'Chief Claims Officer',
        status: 'coming_soon',
        description:
          'Instantly matches FNOL facts against policy endorsements, deductibles, and triage severity tiers for automated routing.',
        capabilities: [
          'Immediate policy coverage verification',
          'Fast-track vs complex desk-adjuster routing',
          'Loss-date policy term matching',
        ],
      },
      {
        id: 'A16',
        name: 'Claim Flow Control',
        streamId: 'S1',
        streamName: 'Claims Operations',
        executive: 'Chief Claims Officer',
        status: 'coming_soon',
        description:
          'Monitors milestone lifecycles, orchestrates adjuster tasks, statutory deadlines, and SLA escalations across active claims.',
        capabilities: [
          'SLA countdown and regulatory alerts',
          'Adjuster workload balancing',
          'Vendor and independent appraiser handoffs',
        ],
      },
      {
        id: 'A17',
        name: 'Reserve & Settlement',
        streamId: 'S1',
        streamName: 'Claims Operations',
        executive: 'Chief Claims Officer',
        status: 'coming_soon',
        description:
          'Recommends initial and ultimate reserves based on comparable historical losses and calculates net settlement drafts.',
        capabilities: [
          'Data-driven initial reserve recommendations',
          'Deductible netting and depreciation calculations',
          'Settlement agreement and release package generation',
        ],
      },
      {
        id: 'A18',
        name: 'Adjuster Copilot & Surge',
        streamId: 'S1',
        streamName: 'Claims Operations',
        executive: 'Chief Claims Officer',
        status: 'coming_soon',
        description:
          'Supports field and desk adjusters during catastrophic storm surges with draft correspondence, repair scoping, and line-item notes.',
        capabilities: [
          'Automated catastrophe surge document drafting',
          'Estimate review copilot and guideline validation',
          'Policyholder status update broadcast system',
        ],
      },
    ],
  },
  {
    id: 'S2',
    name: 'Customer Service & Experience',
    shortName: 'Customer',
    executive: 'VP Customer Care / Chief Customer Officer',
    icon: '💬',
    tagColor: '#E3EDFF',
    accentColor: '#2563EB',
    agents: [
      {
        id: 'A01',
        name: 'Service Front Door',
        streamId: 'S2',
        streamName: 'Customer Service & Experience',
        executive: 'VP Customer Care / Chief Customer Officer',
        status: 'coming_soon',
        description:
          'Multi-channel AI front door handling policyholder inquiries, billing verifications, ID card requests, and policy changes.',
        capabilities: [
          'Auto-ID card and certificate generation',
          'Billing schedule and payment inquiry resolution',
          'Endorsement change request collection',
        ],
      },
      {
        id: 'A02',
        name: 'Policy Explainer',
        streamId: 'S2',
        streamName: 'Customer Service & Experience',
        executive: 'VP Customer Care / Chief Customer Officer',
        status: 'live',
        route: '/app/explainer',
        description:
          'Production-ready enterprise policy intelligence. Answers coverage, deductible, exclusion, and endorsement questions grounded in verified policy wording with audit-trailed citations.',
        capabilities: [
          'Real-time customer & policy context resolution',
          'Exact sentence citations and page-level evidence ledger',
          'Anti-hallucination guardrails and conflict detection',
          'Multi-policy portfolio comparison and timeline analysis',
        ],
      },
      {
        id: 'A03',
        name: 'Live Agent Assist & Quality',
        streamId: 'S2',
        streamName: 'Customer Service & Experience',
        executive: 'VP Customer Care / Chief Customer Officer',
        status: 'coming_soon',
        description:
          'Real-time suggestion engine for CSRs during customer calls, evaluating sentiment, accuracy, and compliance on the fly.',
        capabilities: [
          'In-call knowledge retrieval suggestions',
          'Real-time tone and compliance monitoring',
          'Automated post-call summary and disposition tagging',
        ],
      },
      {
        id: 'A04',
        name: 'Complaint & Grievance Manager',
        streamId: 'S2',
        streamName: 'Customer Service & Experience',
        executive: 'VP Customer Care / Chief Customer Officer',
        status: 'coming_soon',
        description:
          'Identifies escalated sentiment across all touchpoints, logs formal complaints, and drafts prompt, compliant resolution responses.',
        capabilities: [
          'Early escalation warning and sentiment tracking',
          'DOI and regulatory complaint timeline compliance',
          'Root-cause reporting for operational leaders',
        ],
      },
      {
        id: 'A05',
        name: 'Customer Retention & Outreach',
        streamId: 'S2',
        streamName: 'Customer Service & Experience',
        executive: 'VP Customer Care / Chief Customer Officer',
        status: 'coming_soon',
        description:
          'Predicts churn risk ahead of renewals, surfacing proactive discount reviews and tailored policy recommendations.',
        capabilities: [
          'Pre-renewal lapse risk score modeling',
          'Proactive discount and bundled savings advisor',
          'Personalized policy review outreach automation',
        ],
      },
    ],
  },
  {
    id: 'S3',
    name: 'Document & Data Intelligence',
    shortName: 'Documents',
    executive: 'Head of Operations / Chief Underwriting Officer',
    icon: '📄',
    tagColor: '#FFE9DC',
    accentColor: '#F97316',
    agents: [
      {
        id: 'A06',
        name: 'Submission Document Reader',
        streamId: 'S3',
        streamName: 'Document & Data Intelligence',
        executive: 'Head of Operations / Chief Underwriting Officer',
        status: 'coming_soon',
        description:
          'Ingests ACORD forms, SOVs (Statements of Values), and loss runs, extracting structured data with audit trails.',
        capabilities: [
          'SOV table parsing and geo-coding',
          'ACORD 125/126/140 key-value extraction',
          'Loss run normalization across prior carriers',
        ],
      },
      {
        id: 'A07',
        name: 'Claims Document Reader',
        streamId: 'S3',
        streamName: 'Document & Data Intelligence',
        executive: 'Head of Operations / Chief Underwriting Officer',
        status: 'coming_soon',
        description:
          'Parses police reports, medical invoices, repair estimates, and proof of loss documents with handwriting and table recognition.',
        capabilities: [
          'Medical bill and CPT code extraction',
          'Police crash report diagram & citation reading',
          'Contractor repair estimate verification',
        ],
      },
      {
        id: 'A08',
        name: 'Evidence Chaser',
        streamId: 'S3',
        streamName: 'Document & Data Intelligence',
        executive: 'Head of Operations / Chief Underwriting Officer',
        status: 'coming_soon',
        description:
          'Automatically tracks missing documentation, chasing insureds and third parties via email and SMS reminders.',
        capabilities: [
          'Checklist audit for complete claim / bind files',
          'Automated multi-channel polite reminders',
          'Secure upload portal integration',
        ],
      },
    ],
  },
  {
    id: 'S4',
    name: 'Submission & Underwriting',
    shortName: 'Underwriting',
    executive: 'Chief Underwriting Officer',
    icon: '🏢',
    tagColor: '#E3EDFF',
    accentColor: '#2563EB',
    agents: [
      {
        id: 'A09',
        name: 'Submission Intake & Clearance',
        streamId: 'S4',
        streamName: 'Submission & Underwriting',
        executive: 'Chief Underwriting Officer',
        status: 'coming_soon',
        description:
          'Verifies broker appointments, checks duplicate submissions, and cross-references clearance guidelines.',
        capabilities: [
          'Broker authorization & appointment verification',
          'Duplicate submission prevention',
          'Appetite guide automated pre-clearance',
        ],
      },
      {
        id: 'A10',
        name: 'Risk Assembly',
        streamId: 'S4',
        streamName: 'Submission & Underwriting',
        executive: 'Chief Underwriting Officer',
        status: 'coming_soon',
        description:
          'Synthesizes third-party aerial imagery, flood maps, business registers, and credit scores into a single risk dossier.',
        capabilities: [
          'Aerial roof and property condition scoring',
          'FEMA flood zone and wildfire risk enrichment',
          'Secretary of State & OSHA record aggregation',
        ],
      },
      {
        id: 'A11',
        name: 'Hazard & Accumulation',
        streamId: 'S4',
        streamName: 'Submission & Underwriting',
        executive: 'Chief Underwriting Officer',
        status: 'coming_soon',
        description:
          'Models geographic catastrophe accumulations, wildfire zones, and coastal windstorm exposures across the portfolio.',
        capabilities: [
          'PML (Probable Maximum Loss) cluster analysis',
          'Real-time capacity and underwriting authority caps',
          'Coastal setback and storm surge zone mapping',
        ],
      },
      {
        id: 'A12',
        name: 'Quote & Bind',
        streamId: 'S4',
        streamName: 'Submission & Underwriting',
        executive: 'Chief Underwriting Officer',
        status: 'coming_soon',
        description:
          'Evaluates rating rules, applies underwriting guidelines, calculates premiums, and prepares formal binder packages.',
        capabilities: [
          'Underwriter authority limit verification',
          'Automated subjective debits/credits documentation',
          'Binding package & policy jacket generation',
        ],
      },
      {
        id: 'A13',
        name: 'Portfolio & Renewal',
        streamId: 'S4',
        streamName: 'Submission & Underwriting',
        executive: 'Chief Underwriting Officer',
        status: 'coming_soon',
        description:
          'Tracks rate adequacy, loss trends, and book performance to recommend renewal terms and account re-pricing.',
        capabilities: [
          'Account-level loss ratio and loss trend tracking',
          'Renewal target rate calculation',
          'Non-renewal notice compliance tracking',
        ],
      },
    ],
  },
  {
    id: 'S5',
    name: 'Legal, Compliance & Regulatory',
    shortName: 'Compliance',
    executive: 'General Counsel / Chief Compliance Officer',
    icon: '⚖️',
    tagColor: '#FFE9DC',
    accentColor: '#F97316',
    agents: [
      {
        id: 'A23',
        name: 'Litigation Predictor',
        streamId: 'S5',
        streamName: 'Legal, Compliance & Regulatory',
        executive: 'General Counsel / Chief Compliance Officer',
        status: 'coming_soon',
        description:
          'Analyzes disputed claims to forecast attorney representation likelihood, trial outcomes, and recommended ADR settlements.',
        capabilities: [
          'Plaintiff attorney propensity scoring',
          'Venue and jurisdiction verdict benchmarking',
          'Early neutral evaluation and mediation strategy',
        ],
      },
      {
        id: 'A24',
        name: 'Coverage Position Drafting',
        streamId: 'S5',
        streamName: 'Legal, Compliance & Regulatory',
        executive: 'General Counsel / Chief Compliance Officer',
        status: 'coming_soon',
        description:
          'Drafts legally sound Reservation of Rights (ROR) and coverage declination letters grounded in cited policy clauses.',
        capabilities: [
          'State-specific ROR statutory language generation',
          'Exclusion cross-referencing to verified policy forms',
          'Counsel review workflow with versioned audit trail',
        ],
      },
      {
        id: 'A25',
        name: 'Fair-Claims Compliance',
        streamId: 'S5',
        streamName: 'Legal, Compliance & Regulatory',
        executive: 'General Counsel / Chief Compliance Officer',
        status: 'coming_soon',
        description:
          'Continuously audits claims handling against state-by-state unfair claims practices acts and statutory timelines.',
        capabilities: [
          'Acknowledgment and payment deadline monitoring',
          'Audit sampling for market conduct readiness',
          'State insurance department complaint response packs',
        ],
      },
      {
        id: 'A26',
        name: 'Litigation Management',
        streamId: 'S5',
        streamName: 'Legal, Compliance & Regulatory',
        executive: 'General Counsel / Chief Compliance Officer',
        status: 'coming_soon',
        description:
          'Manages outside defense counsel budgets, invoices, court dates, and discovery filings with billing guideline validation.',
        capabilities: [
          'LEDES electronic legal invoice audit against guidelines',
          'Court filing and responsive pleading tracking',
          'Trial calendar and expert witness fee tracking',
        ],
      },
    ],
  },
  {
    id: 'S6',
    name: 'Fraud, Leakage & Recovery',
    shortName: 'Fraud',
    executive: 'SIU Director / Chief Claims Officer / CFO',
    icon: '🔍',
    tagColor: '#E3EDFF',
    accentColor: '#2563EB',
    agents: [
      {
        id: 'A19',
        name: 'Fraud & Media Integrity',
        streamId: 'S6',
        streamName: 'Fraud, Leakage & Recovery',
        executive: 'SIU Director / Chief Claims Officer / CFO',
        status: 'coming_soon',
        description:
          'Detects metadata tampering, AI-generated synthetic images, staging anomalies, and cross-carrier claim duplicates.',
        capabilities: [
          'EXIF metadata and digital tampering detection',
          'AI-generated generative image detection',
          'Cross-claim duplicate invoice and photo identification',
        ],
      },
      {
        id: 'A20',
        name: 'Estimate Review',
        streamId: 'S6',
        streamName: 'Fraud, Leakage & Recovery',
        executive: 'SIU Director / Chief Claims Officer / CFO',
        status: 'coming_soon',
        description:
          'Scrutinizes body shop and contractor line-item estimates against regional benchmarks, spotting duplicate or inflated labor.',
        capabilities: [
          'Collision & property repair labor rate benchmarking',
          'Unnecessary line-item overlap and markup detection',
          'OEM vs aftermarket parts compliance checking',
        ],
      },
      {
        id: 'A21',
        name: 'Payment & Recovery',
        streamId: 'S6',
        streamName: 'Fraud, Leakage & Recovery',
        executive: 'SIU Director / Chief Claims Officer / CFO',
        status: 'coming_soon',
        description:
          'Identifies subrogation opportunities against negligent third parties, automated salvage routing, and deductible recovery.',
        capabilities: [
          'Subrogation liability opportunity scoring',
          'Inter-company arbitration document pack preparation',
          'Policyholder deductible reimbursement tracking',
        ],
      },
      {
        id: 'A22',
        name: 'Leakage & Quality Audit',
        streamId: 'S6',
        streamName: 'Fraud, Leakage & Recovery',
        executive: 'SIU Director / Chief Claims Officer / CFO',
        status: 'coming_soon',
        description:
          'Conducts closed-claim audits measuring indemnity leakage, guideline compliance, and settlement consistency.',
        capabilities: [
          'Indemnity and expense leakage estimation',
          'Adjuster authority compliance benchmarking',
          'Actionable claims operational quality dashboards',
        ],
      },
    ],
  },
];

export const ALL_AGENTS: AgentRecord[] = VALUE_STREAMS.flatMap((s) => s.agents);

export const VALUE_STREAM_COLORS = [
  '#F97316',
  '#2563EB',
  '#FB923C',
  '#60A5FA',
  '#EA580C',
  '#1D4ED8',
];
