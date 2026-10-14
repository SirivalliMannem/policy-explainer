"""Direct factual lookups for policy schedule fields from database records.

Answers clear factual questions straight from PostgreSQL without calling an LLM:
- Deductibles and policy limits from CoreCoverage
- Annual premium from CorePolicy
- Next bill due date and amount from CoreBilling
- Claim status and assigned adjuster from CoreClaim
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.policy import CoreBilling, CoreClaim, CoreCoverage, CorePolicy
from app.schemas.explainer import CitationItem, EvidenceItemSchema

# ── 1. Classification Patterns ───────────────────────────────────────────────

# Each pattern also covers the everyday ways employees ask ("out of pocket", "max payout", "past due",
# "still open", "who is handling the claim").
FACTUAL_DEDUCTIBLE_PATTERN = re.compile(r"\b(?:deduct[ia]bles?|out[\s-]of[\s-]pocket)\b", re.IGNORECASE)
FACTUAL_LIMIT_PATTERN = re.compile(
    r"\b(?:(?:policy\s+)?limits?|how\s+much\s+(?:coverage|cover)\b|max(?:imum)?\s+(?:payout|pay[\s-]?out|benefit|amount)"
    r"|coverage\s+amounts?|amount\s+of\s+coverage)",
    re.IGNORECASE,
)
FACTUAL_PREMIUM_PATTERN = re.compile(
    r"\b(?:premiums?|annual\s+premium|policy\s+premium|cost\s+of\s+(?:this|the)\s+policy"
    r"|how\s+much\s+(?:does|is)\s+(?:this|the|my|our|their|his|her)\s+(?:policy|insurance)\s+(?:cost|costing)"
    r"|(?:annual|yearly|monthly)\s+cost|cost\s+(?:per|a|each)\s+(?:year|month))\b",
    re.IGNORECASE,
)
FACTUAL_BILLING_PATTERN = re.compile(
    r"\b(?:bill\w*|due\s+date|payment\s+due|next\s+payment|amount\s+due|when\s+is\s+(?:the\s+|my\s+)?payment\s+due"
    r"|when\s+do\s+i\s+have\s+to\s+pay|past[\s-]due|overdue|outstanding\s+balance|balance\s+due|amount\s+owed"
    r"|behind\s+on\s+(?:payments?|the\s+bill)|paid\s+up|payment\s+status)\b",
    re.IGNORECASE,
)
FACTUAL_CLAIM_STATUS_PATTERN = re.compile(
    r"\b(?:claim\s+status|status\s+of\s+(?:the\s+|my\s+)?claim|is\s+(?:the\s+|my\s+)?claim\s+open|is\s+(?:the\s+|my\s+)?claim\s+closed"
    r"|claim\b[^.?!]{0,40}\b(?:still\s+)?(?:open|closed|settled|pending|resolved)"
    r"|where\s+(?:is|are)\s+(?:the\s+|my\s+|this\s+)?claims?)\b",
    re.IGNORECASE,
)
FACTUAL_ADJUSTER_PATTERN = re.compile(
    r"\b(?:adjusters?|assigned\s+adjuster|adjuster\s+assigned|who\s+is\s+(?:the\s+|my\s+)?adjuster"
    r"|who(?:'s|\s+is)\s+(?:handling|working\s+on|managing)\s+(?:the\s+|my\s+|this\s+|that\s+)?claim"
    r"|who(?:'s|\s+is)\s+assigned\s+to\s+(?:the\s+|my\s+|this\s+|that\s+)?claim|claims?\s+handler)\b",
    re.IGNORECASE,
)

# Wording inquiry patterns (exclusions, conditions, endorsements, perils, coverage interpretation)
WORDING_INDICATORS = [
    re.compile(r"\b(?:exclu\w*|except\w*)\b", re.IGNORECASE),
    re.compile(r"\b(?:condition\w*|provision\w*|clause\w*|wording|plain\s+language)\b", re.IGNORECASE),
    re.compile(r"\b(?:what\s+endorsement|endorsement\s+wording|attached\s+forms?|what\s+form)\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+.*?\s+covered|does\s+.*?\s+cover|are\s+.*?\s+covered|is\s+there\s+coverage\s+for|what\s+is\s+covered|what\s+does\s+.*?\s+cover)\b", re.IGNORECASE),
    re.compile(r"\b(?:peril\w*|cause\s+of\s+loss|wear\s+and\s+tear|mold|mould|termites?|vermin|vandalism)\b", re.IGNORECASE),
    re.compile(r"\b(?:why\s+is|how\s+does\s+(?:the\s+)?coverage\s+apply|explain\s+(?:the|how))\b", re.IGNORECASE),
    # "...and how does it apply?", "how does that work", "what does it mean", "when does it apply"
    re.compile(
        r"\b(?:how\s+(?:does|do|would|will)\s+(?:it|this|that|they|these|those|the\s+\w+(?:\s+\w+)?)\s+(?:apply|work)"
        r"|what\s+does\s+(?:it|this|that)\s+mean|when\s+does\s+(?:it|this|that)\s+apply)\b",
        re.IGNORECASE,
    ),
]

COVERAGE_PATTERNS = [
    (re.compile(r"\b(?:coverage\s*a|dwelling)\b", re.IGNORECASE), ["dwelling", "coverage a", "hodwellingcov"]),
    (re.compile(r"\b(?:coverage\s*b|other\s+structures?)\b", re.IGNORECASE), ["other structures", "coverage b", "hootherstructurescov"]),
    (re.compile(r"\b(?:coverage\s*c|personal\s+property|contents)\b", re.IGNORECASE), ["personal property", "coverage c", "hopersonalpropertycov"]),
    (re.compile(r"\b(?:coverage\s*d|loss\s+of\s+use|additional\s+living)\b", re.IGNORECASE), ["loss of use", "coverage d", "holossofusecov"]),
    (re.compile(r"\b(?:coverage\s*e|personal\s+liability)\b", re.IGNORECASE), ["personal liability", "coverage e", "hopersonalliabilitycov"]),
    (re.compile(r"\b(?:coverage\s*f|medical\s+payments?)\b", re.IGNORECASE), ["medical payments", "coverage f", "homedicalpaymentscov"]),
    (re.compile(r"\b(?:water\s+back-?up|sewer\s+back-?up|sump)\b", re.IGNORECASE), ["water back", "water", "howaterbackupcov"]),
    (re.compile(r"\b(?:jewel\w*|scheduled\s+personal\s+property)\b", re.IGNORECASE), ["jewel", "scheduled", "hoscheduledjewelrycov"]),
    (re.compile(r"\b(?:wind|hail|windstorm)\b", re.IGNORECASE), ["wind", "hail", "howindhaildedcov"]),
    (re.compile(r"\b(?:collision|crash)\b", re.IGNORECASE), ["collision", "pacollisioncov"]),
    (re.compile(r"\b(?:comprehensive|other\s+than\s+collision)\b", re.IGNORECASE), ["other than collision", "comprehensive", "pacomprehensivecov"]),
    (re.compile(r"\b(?:bodily\s+injury|bi)\b", re.IGNORECASE), ["bodily injury"]),
    (re.compile(r"\b(?:property\s+damage|pd)\b", re.IGNORECASE), ["property damage"]),
    (re.compile(r"\b(?:uninsured\s+motorist\w*|um|uim)\b", re.IGNORECASE), ["uninsured"]),
    (re.compile(r"\b(?:rental|transportation)\b", re.IGNORECASE), ["transportation", "rental", "parentalcov"]),
]


@dataclass
class FactualLookupResult:
    answer: str
    evidence: list[EvidenceItemSchema]
    citations: list[CitationItem]
    fields_matched: list[str]
    found: bool
    suggestions: list[str] = field(default_factory=list)
    grounding_context: str = ""


def is_factual_query(question: str) -> bool:
    """True when the question asks about one of the six schedule factual fields."""
    text = (question or "").strip()
    if not text:
        return False
    return bool(
        FACTUAL_DEDUCTIBLE_PATTERN.search(text)
        or FACTUAL_LIMIT_PATTERN.search(text)
        or FACTUAL_PREMIUM_PATTERN.search(text)
        or FACTUAL_BILLING_PATTERN.search(text)
        or FACTUAL_CLAIM_STATUS_PATTERN.search(text)
        or FACTUAL_ADJUSTER_PATTERN.search(text)
    )


def is_wording_query(question: str) -> bool:
    """True when the question includes a policy wording, coverage scope, or exclusion inquiry."""
    text = (question or "").strip()
    if not text:
        return False
    return any(p.search(text) for p in WORDING_INDICATORS)


def find_matching_coverage(question: str, coverages: list[CoreCoverage]) -> Optional[CoreCoverage]:
    """Find a specific named coverage within the question text."""
    for pattern, search_keys in COVERAGE_PATTERNS:
        if pattern.search(question):
            for cov in coverages:
                cov_name = cov.name.lower()
                cov_code = (cov.pattern_code or "").lower()
                if any(k in cov_name or k in cov_code for k in search_keys):
                    return cov
    return None


# ── 2. Field-Specific Answer Builders ────────────────────────────────────────


def _answer_deductible(
    question: str,
    policy: CorePolicy,
    coverages: list[CoreCoverage],
    start_index: int = 1,
) -> Tuple[str, list[EvidenceItemSchema], list[CitationItem]]:
    specific_cov = find_matching_coverage(question, coverages)
    if specific_cov:
        ded_str = (specific_cov.deductible_text or "").strip()
        if not ded_str or ded_str.lower() in ("none", "0", "$0"):
            ans = (
                f"For policy {policy.policy_number}, {specific_cov.name} has no separate deductible on file (None) "
                f"[E{start_index}]."
            )
        else:
            ans = f"For policy {policy.policy_number}, the deductible for {specific_cov.name} is {ded_str} [E{start_index}]."

        ev = [
            EvidenceItemSchema(
                source_type="coverage",
                source_id=specific_cov.id,
                title=f"Coverage: {specific_cov.name}",
                content=f"{specific_cov.name} — Limit: {specific_cov.limit_text or 'N/A'}, Deductible: {specific_cov.deductible_text or 'None'}.",
                form_number=specific_cov.governing_form or None,
                relevance_score=1.0,
                metadata={
                    "pattern_code": specific_cov.pattern_code,
                    "limit_amount": specific_cov.limit_amount,
                    "deductible_amount": specific_cov.deductible_amount,
                },
            )
        ]
        cit = [
            CitationItem(
                source_id=specific_cov.id,
                source_type="coverage",
                evidence_index=start_index,
                heading=specific_cov.name,
                citation_text=f"Policy schedule: {specific_cov.name}",
            )
        ]
        return ans, ev, cit

    # No specific coverage named: list all scheduled coverages with deductibles
    covs_with_ded = [
        c for c in coverages if c.deductible_text and c.deductible_text.strip().lower() not in ("none", "", "0", "$0")
    ]
    if covs_with_ded:
        lines = [f"The deductibles on record for policy {policy.policy_number} are:"]
        ev_items = []
        cit_items = []
        for i, c in enumerate(covs_with_ded, start=start_index):
            lines.append(f"• {c.name}: {c.deductible_text} [E{i}]")
            ev_items.append(
                EvidenceItemSchema(
                    source_type="coverage",
                    source_id=c.id,
                    title=f"Coverage: {c.name}",
                    content=f"{c.name} — Limit: {c.limit_text or 'N/A'}, Deductible: {c.deductible_text}.",
                    form_number=c.governing_form or None,
                    relevance_score=1.0,
                    metadata={"pattern_code": c.pattern_code, "deductible_amount": c.deductible_amount},
                )
            )
            cit_items.append(
                CitationItem(
                    source_id=c.id,
                    source_type="coverage",
                    evidence_index=i,
                    heading=c.name,
                    citation_text=f"Policy schedule: {c.name}",
                )
            )
        other_count = len(coverages) - len(covs_with_ded)
        if other_count > 0:
            lines.append("Other scheduled coverages on this policy do not have a separate deductible.")
        return "\n".join(lines), ev_items, cit_items

    if coverages:
        return (
            f"For policy {policy.policy_number}, no separate deductibles are listed in the available schedule records.",
            [],
            [],
        )
    return (
        f"The available records do not contain coverage or deductible information for policy {policy.policy_number}.",
        [],
        [],
    )


def _answer_limit(
    question: str,
    policy: CorePolicy,
    coverages: list[CoreCoverage],
    also_include_deductible: bool = False,
    start_index: int = 1,
) -> Tuple[str, list[EvidenceItemSchema], list[CitationItem]]:
    specific_cov = find_matching_coverage(question, coverages)
    if specific_cov:
        lim_str = specific_cov.limit_text or "N/A"
        ded_str = specific_cov.deductible_text or "None"
        if also_include_deductible:
            ans = (
                f"For policy {policy.policy_number}, {specific_cov.name} has a limit of {lim_str} and a deductible of {ded_str} "
                f"[E{start_index}]."
            )
        else:
            ans = f"For policy {policy.policy_number}, the limit for {specific_cov.name} is {lim_str} [E{start_index}]."

        ev = [
            EvidenceItemSchema(
                source_type="coverage",
                source_id=specific_cov.id,
                title=f"Coverage: {specific_cov.name}",
                content=f"{specific_cov.name} — Limit: {lim_str}, Deductible: {ded_str}.",
                form_number=specific_cov.governing_form or None,
                relevance_score=1.0,
                metadata={
                    "pattern_code": specific_cov.pattern_code,
                    "limit_amount": specific_cov.limit_amount,
                    "deductible_amount": specific_cov.deductible_amount,
                },
            )
        ]
        cit = [
            CitationItem(
                source_id=specific_cov.id,
                source_type="coverage",
                evidence_index=start_index,
                heading=specific_cov.name,
                citation_text=f"Policy schedule: {specific_cov.name}",
            )
        ]
        return ans, ev, cit

    # No specific coverage named: list all scheduled coverage limits
    if coverages:
        lines = [f"The coverage limits on record for policy {policy.policy_number} are:"]
        ev_items = []
        cit_items = []
        for i, c in enumerate(coverages, start=start_index):
            lim = c.limit_text or "N/A"
            if also_include_deductible and c.deductible_text and c.deductible_text.lower() != "none":
                lines.append(f"• {c.name}: limit {lim}, deductible {c.deductible_text} [E{i}]")
            else:
                lines.append(f"• {c.name}: {lim} [E{i}]")
            ev_items.append(
                EvidenceItemSchema(
                    source_type="coverage",
                    source_id=c.id,
                    title=f"Coverage: {c.name}",
                    content=f"{c.name} — Limit: {lim}, Deductible: {c.deductible_text or 'None'}.",
                    form_number=c.governing_form or None,
                    relevance_score=1.0,
                    metadata={"pattern_code": c.pattern_code, "limit_amount": c.limit_amount},
                )
            )
            cit_items.append(
                CitationItem(
                    source_id=c.id,
                    source_type="coverage",
                    evidence_index=i,
                    heading=c.name,
                    citation_text=f"Policy schedule: {c.name}",
                )
            )
        return "\n".join(lines), ev_items, cit_items

    return (
        f"The available records do not contain coverage limits for policy {policy.policy_number}.",
        [],
        [],
    )


def _answer_premium(
    policy: CorePolicy,
    start_index: int = 1,
) -> Tuple[str, list[EvidenceItemSchema], list[CitationItem]]:
    if policy.annual_premium and policy.annual_premium > 0:
        ans = f"The annual premium for policy {policy.policy_number} is ${policy.annual_premium:,.2f} [E{start_index}]."
        ev = [
            EvidenceItemSchema(
                source_type="policy_meta",
                source_id=policy.id,
                title=f"Policy Record: {policy.policy_number}",
                content=f"Policy {policy.policy_number} — Annual Premium: ${policy.annual_premium:,.2f}, Status: {policy.status}.",
                relevance_score=1.0,
                metadata={"policy_number": policy.policy_number, "annual_premium": policy.annual_premium},
            )
        ]
        cit = [
            CitationItem(
                source_id=policy.id,
                source_type="policy_meta",
                evidence_index=start_index,
                heading=f"Policy Record ({policy.policy_number})",
                citation_text=f"Policy record {policy.policy_number}",
            )
        ]
        return ans, ev, cit

    return (
        f"The available records do not contain an annual premium for policy {policy.policy_number}.",
        [],
        [],
    )


def _answer_billing(
    policy: CorePolicy,
    billing_records: list[CoreBilling],
    start_index: int = 1,
) -> Tuple[str, list[EvidenceItemSchema], list[CitationItem]]:
    if not billing_records:
        return (
            f"The available records do not contain billing or payment due date information for policy {policy.policy_number}.",
            [],
            [],
        )

    bill = billing_records[0]
    date_str = bill.next_due_date.isoformat() if bill.next_due_date else "not scheduled"
    amount_str = f"${bill.next_due_amount:,.2f}"
    status_str = bill.status or "current"
    plan_str = bill.plan or "Monthly"

    past_due = bill.past_due_amount or 0.0
    past_due_str = f"${past_due:,.2f} is past due" if past_due > 0 else "nothing is past due"
    ans = (
        f"For policy {policy.policy_number}, the next payment of {amount_str} is due on {date_str}, and "
        f"{past_due_str} (Plan: {plan_str}, Status: {status_str}) [E{start_index}]."
    )
    ev = [
        EvidenceItemSchema(
            source_type="billing",
            source_id=bill.id,
            title="Billing Record",
            content=f"Billing Plan: {plan_str}, Status: {status_str}, Next Due: {date_str}, Next Due Amount: {amount_str}, Past Due: ${bill.past_due_amount:,.2f}.",
            relevance_score=1.0,
            metadata={"status": status_str, "plan": plan_str},
        )
    ]
    cit = [
        CitationItem(
            source_id=bill.id,
            source_type="billing",
            evidence_index=start_index,
            heading="Billing Record",
            citation_text=f"Billing schedule ({plan_str})",
        )
    ]
    return ans, ev, cit


def _answer_claim(
    question: str,
    policy: CorePolicy,
    claims: list[CoreClaim],
    wants_status: bool,
    wants_adjuster: bool,
    start_index: int = 1,
) -> Tuple[str, list[EvidenceItemSchema], list[CitationItem]]:
    if not claims:
        return (
            f"The available records do not contain any claims on file for policy {policy.policy_number}.",
            [],
            [],
        )

    # Check for specific claim number reference in question
    claim_match = re.search(r"\b(CLM[-\s]?\d{4}[-\s]?\d{3,5})\b", question, re.IGNORECASE)
    matched_claim = None
    if claim_match:
        norm_q = claim_match.group(1).upper().replace(" ", "").replace("-", "")
        for c in claims:
            if c.claim_number.upper().replace(" ", "").replace("-", "") == norm_q:
                matched_claim = c
                break

    if matched_claim is None and len(claims) == 1:
        matched_claim = claims[0]

    if matched_claim:
        c = matched_claim
        adj = c.adjuster.strip() if c.adjuster else "Unassigned"
        st = c.status or "open"
        loss_info = f" (Loss Date: {c.loss_date}, {c.loss_cause})" if c.loss_date else ""

        if wants_status and wants_adjuster:
            ans = (
                f"For claim {c.claim_number} on policy {policy.policy_number}, the status is {st} "
                f"and the assigned adjuster is {adj}{loss_info} [E{start_index}]."
            )
        elif wants_adjuster:
            if adj and adj.lower() != "unassigned":
                ans = f"The assigned adjuster for claim {c.claim_number} on policy {policy.policy_number} is {adj} (Status: {st}){loss_info} [E{start_index}]."
            else:
                ans = f"For claim {c.claim_number} on policy {policy.policy_number}, no adjuster is currently assigned in the available records (Status: {st}){loss_info} [E{start_index}]."
        else:
            ans = f"Claim {c.claim_number} on policy {policy.policy_number} is currently {st}{loss_info} [E{start_index}]."

        ev = [
            EvidenceItemSchema(
                source_type="claim",
                source_id=c.id,
                title=f"Claim: {c.claim_number}",
                content=f"Claim Number: {c.claim_number}, Status: {st}, Adjuster: {adj}, Loss Cause: {c.loss_cause}, Loss Date: {c.loss_date}.",
                relevance_score=1.0,
                metadata={"claim_number": c.claim_number, "status": st, "adjuster": adj},
            )
        ]
        cit = [
            CitationItem(
                source_id=c.id,
                source_type="claim",
                evidence_index=start_index,
                heading=f"Claim {c.claim_number}",
                citation_text=f"Claim record {c.claim_number}",
            )
        ]
        return ans, ev, cit

    # Multiple claims on file, none specified
    lines = [f"There are {len(claims)} claims on record for policy {policy.policy_number}:"]
    ev_items = []
    cit_items = []
    for i, c in enumerate(claims, start=start_index):
        adj = c.adjuster.strip() if c.adjuster else "Unassigned"
        st = c.status or "open"
        loss_info = f" · Loss Date: {c.loss_date} ({c.loss_cause})" if c.loss_date else ""
        lines.append(f"• Claim {c.claim_number}: Status: {st} · Adjuster: {adj}{loss_info} [E{i}]")
        ev_items.append(
            EvidenceItemSchema(
                source_type="claim",
                source_id=c.id,
                title=f"Claim: {c.claim_number}",
                content=f"Claim Number: {c.claim_number}, Status: {st}, Adjuster: {adj}, Loss Cause: {c.loss_cause}, Loss Date: {c.loss_date}.",
                relevance_score=1.0,
                metadata={"claim_number": c.claim_number, "status": st, "adjuster": adj},
            )
        )
        cit_items.append(
            CitationItem(
                source_id=c.id,
                source_type="claim",
                evidence_index=i,
                heading=f"Claim {c.claim_number}",
                citation_text=f"Claim record {c.claim_number}",
            )
        )
    return "\n".join(lines), ev_items, cit_items


# ── 3. Main Factual Lookup Execution ─────────────────────────────────────────


def execute_factual_lookup(
    question: str,
    policy: CorePolicy,
    db: Session,
) -> Optional[FactualLookupResult]:
    """Execute direct database lookup for factual schedule fields.

    Returns FactualLookupResult if the question asks about any of the 6 factual fields,
    or None if the question is not a factual lookup.
    """
    text = question.strip()
    if not is_factual_query(text):
        return None

    wants_deductible = bool(FACTUAL_DEDUCTIBLE_PATTERN.search(text))
    wants_limit = bool(FACTUAL_LIMIT_PATTERN.search(text))
    wants_premium = bool(FACTUAL_PREMIUM_PATTERN.search(text))
    wants_billing = bool(FACTUAL_BILLING_PATTERN.search(text))
    wants_status = bool(FACTUAL_CLAIM_STATUS_PATTERN.search(text))
    wants_adjuster = bool(FACTUAL_ADJUSTER_PATTERN.search(text))

    # If the question asks for claims generally, e.g. "What claims are on this policy?"
    if not wants_status and not wants_adjuster and re.search(r"\bclaims?\b", text, re.IGNORECASE):
        wants_status = True

    answers: list[str] = []
    all_evidence: list[EvidenceItemSchema] = []
    all_citations: list[CitationItem] = []
    fields_matched: list[str] = []

    # 1. Coverages: Deductible and / or Limit
    coverages: list[CoreCoverage] = []
    if wants_deductible or wants_limit:
        coverages = (
            db.query(CoreCoverage)
            .filter(CoreCoverage.policy_id == policy.id)
            .order_by(CoreCoverage.sort_order.asc(), CoreCoverage.name.asc())
            .all()
        )

        if wants_limit and wants_deductible:
            fields_matched.extend(["limit", "deductible"])
            ans, ev, cit = _answer_limit(
                text,
                policy,
                coverages,
                also_include_deductible=True,
                start_index=len(all_evidence) + 1,
            )
            answers.append(ans)
            all_evidence.extend(ev)
            all_citations.extend(cit)
        elif wants_limit:
            fields_matched.append("limit")
            ans, ev, cit = _answer_limit(
                text,
                policy,
                coverages,
                also_include_deductible=False,
                start_index=len(all_evidence) + 1,
            )
            answers.append(ans)
            all_evidence.extend(ev)
            all_citations.extend(cit)
        elif wants_deductible:
            fields_matched.append("deductible")
            ans, ev, cit = _answer_deductible(
                text,
                policy,
                coverages,
                start_index=len(all_evidence) + 1,
            )
            answers.append(ans)
            all_evidence.extend(ev)
            all_citations.extend(cit)

    # 2. Annual Premium
    if wants_premium:
        fields_matched.append("premium")
        ans, ev, cit = _answer_premium(policy, start_index=len(all_evidence) + 1)
        answers.append(ans)
        all_evidence.extend(ev)
        all_citations.extend(cit)

    # 3. Next Bill Due Date and Amount
    if wants_billing:
        fields_matched.append("billing")
        billing_records = db.query(CoreBilling).filter(CoreBilling.policy_id == policy.id).all()
        ans, ev, cit = _answer_billing(policy, billing_records, start_index=len(all_evidence) + 1)
        answers.append(ans)
        all_evidence.extend(ev)
        all_citations.extend(cit)

    # 4. Claim Status and / or Assigned Adjuster
    if wants_status or wants_adjuster:
        if wants_status:
            fields_matched.append("claim_status")
        if wants_adjuster:
            fields_matched.append("assigned_adjuster")
        claims = (
            db.query(CoreClaim)
            .filter(CoreClaim.policy_id == policy.id)
            .order_by(CoreClaim.loss_date.desc().nullslast())
            .all()
        )
        ans, ev, cit = _answer_claim(
            text,
            policy,
            claims,
            wants_status=wants_status,
            wants_adjuster=wants_adjuster,
            start_index=len(all_evidence) + 1,
        )
        answers.append(ans)
        all_evidence.extend(ev)
        all_citations.extend(cit)

    if not answers:
        return None

    full_answer = "\n\n".join(answers)
    found = len(all_evidence) > 0

    # Helpful suggestions tailored to the fields queried
    suggestions: list[str] = []
    if "deductible" in fields_matched or "limit" in fields_matched:
        suggestions.extend(["When is my next bill due?", "What is my annual premium?"])
    elif "premium" in fields_matched:
        suggestions.extend(["When is my bill due?", "What are my policy limits?"])
    elif "billing" in fields_matched:
        suggestions.extend(["What is my annual premium?", "What are my coverage limits?"])
    elif "claim_status" in fields_matched or "assigned_adjuster" in fields_matched:
        suggestions.extend(["What are my coverage limits?", "What is my deductible?"])

    grounding_context = (
        f"Answered directly from policy records in PostgreSQL for {policy.policy_number} "
        f"({', '.join(fields_matched)}); no language model involved."
    )

    return FactualLookupResult(
        answer=full_answer,
        evidence=all_evidence,
        citations=all_citations,
        fields_matched=fields_matched,
        found=found,
        suggestions=suggestions,
        grounding_context=grounding_context,
    )
