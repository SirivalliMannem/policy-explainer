"""Answer several facts in one reply.

"What is the water backup deductible, which endorsement provides it, and is there an open claim?"
asks three things. The question is split into its parts, each part is answered from its own source
(schedule fields, claims and billing from the policy records; endorsements from the forms attached
to the policy; what wording means from clause search and the language model) and the parts are
combined into a single reply in which every fact cites its own source.

Splitting is deterministic. A part that names no coverage ("which endorsement provides it") borrows
the coverage named elsewhere in the question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.models.policy import CoreCoverage, CoreForm, CorePolicy
from app.schemas.explainer import CitationItem, EvidenceItemSchema
from app.services.factual_lookup import (
    COVERAGE_PATTERNS,
    FACTUAL_ADJUSTER_PATTERN,
    FACTUAL_BILLING_PATTERN,
    FACTUAL_CLAIM_STATUS_PATTERN,
    FACTUAL_DEDUCTIBLE_PATTERN,
    FACTUAL_LIMIT_PATTERN,
    FACTUAL_PREMIUM_PATTERN,
    execute_factual_lookup,
    find_matching_coverage,
    is_wording_query,
)

# Parts are separated by "?", ";", ", " (", and", ", also") or "and"/"also" before a new question.
_SPLIT = re.compile(
    r"\?+\s*|;\s*|,\s+(?:and\s+|also\s+|plus\s+)?|"
    r"\s+(?:and|also|plus|as\s+well\s+as)\s+(?=(?:what|which|who|when|where|is|are|was|were|does|do|did|has|have|how|"
    r"can|any|the|its|his|her|their|an?|if|whether)\b)",
    re.IGNORECASE,
)
ENDORSEMENT = re.compile(r"\b(?:endorsements?|riders?|attached\s+forms?|forms?\s+attached|which\s+forms?|what\s+forms?)\b", re.IGNORECASE)
CLAIM_MENTION = re.compile(r"\bclaims?\b", re.IGNORECASE)
PRONOUN = re.compile(r"\b(?:it|that|this|they|them)\b", re.IGNORECASE)

RECORD_KINDS = ("deductible", "limit", "premium", "billing", "claim", "adjuster")
LABELS = {
    "deductible": "Deductible",
    "limit": "Limit",
    "premium": "Premium",
    "billing": "Next bill",
    "claim": "Claims",
    "adjuster": "Assigned adjuster",
    "endorsement": "Endorsement",
    "wording": "What the policy wording says",
}


@dataclass
class Part:
    text: str  # the part as asked, completed with the coverage it refers to when needed
    kinds: list[str]
    source: str = ""  # records | forms | wording

    @property
    def label(self) -> str:
        names = [LABELS[k] for k in self.kinds]
        if len(names) <= 2:
            return " and ".join(names)
        return ", ".join(names[:-1]) + " and " + names[-1]


@dataclass
class PartAnswer:
    part: Part
    text: str
    evidence: list[EvidenceItemSchema] = field(default_factory=list)
    citations: list[CitationItem] = field(default_factory=list)
    found: bool = True


def _record_kinds(text: str) -> list[str]:
    kinds = []
    if FACTUAL_DEDUCTIBLE_PATTERN.search(text):
        kinds.append("deductible")
    if FACTUAL_LIMIT_PATTERN.search(text):
        kinds.append("limit")
    if FACTUAL_PREMIUM_PATTERN.search(text):
        kinds.append("premium")
    if FACTUAL_BILLING_PATTERN.search(text):
        kinds.append("billing")
    if FACTUAL_ADJUSTER_PATTERN.search(text):
        kinds.append("adjuster")
    elif FACTUAL_CLAIM_STATUS_PATTERN.search(text) or CLAIM_MENTION.search(text):
        kinds.append("claim")
    return kinds


def _coverage_phrase(question: str) -> Optional[str]:
    """The coverage the question names ("water backup", "dwelling"), to complete parts that only say "it"."""
    for pattern, _ in COVERAGE_PATTERNS:
        if m := pattern.search(question):
            return m.group(0)
    return None


def _names_coverage(text: str) -> bool:
    return any(pattern.search(text) for pattern, _ in COVERAGE_PATTERNS)


def split_question(question: str) -> list[Part]:
    """The question's parts, each with what it asks. Fewer than two parts: not a multi-part question."""
    fragments = [f.strip(" ,.") for f in _SPLIT.split(question or "") if f and f.strip(" ,.")]
    grouped: list[list[str]] = []
    for fragment in fragments:
        endorsement = bool(ENDORSEMENT.search(fragment))
        kinds = [] if endorsement else _record_kinds(fragment)
        wording = not endorsement and is_wording_query(fragment)
        if not (endorsement or kinds or wording) and grouped:
            grouped[-1].append(fragment)  # a fragment asking nothing on its own continues the previous part
        else:
            grouped.append([fragment])

    coverage = _coverage_phrase(question)
    parts: list[Part] = []
    for group in grouped:
        text = " ".join(group)
        if coverage and not _names_coverage(text):
            text = f"{text} for {coverage}" if not PRONOUN.search(text) else PRONOUN.sub(coverage, text, count=1)
        if ENDORSEMENT.search(text):
            parts.append(Part(text, ["endorsement"], "forms"))
            continue
        kinds = _record_kinds(text)
        if kinds:
            parts.append(Part(text, kinds, "records"))
        if is_wording_query(text) and not (kinds and not _wording_beyond_fact(text)):
            parts.append(Part(text, ["wording"], "wording"))

    # Wording parts are one question to the language model ("does it cover mold, wear and tear, or
    # vermin?" is a single question listing perils), so they count as one part.
    wording = [p for p in parts if p.source == "wording"]
    if len(wording) > 1:
        merged = Part(", ".join(p.text for p in wording), ["wording"], "wording")
        first = parts.index(wording[0])
        parts = [p for p in parts if p.source != "wording"]
        parts.insert(first, merged)
    return parts if len(parts) >= 2 else []


def _wording_beyond_fact(text: str) -> bool:
    """A fact question such as "what is covered for the dwelling limit" is not also a wording question."""
    return bool(re.search(r"\b(?:exclu\w*|why|how\s+(?:does|do|would|will)|mean|condition\w*|cover(?:ed|s)?\b(?!\s*age))", text, re.IGNORECASE))


def _form_evidence(form: CoreForm, index: int) -> tuple[EvidenceItemSchema, CitationItem]:
    evidence = EvidenceItemSchema(
        source_type="form",
        source_id=form.id,
        title=f"Form: {form.form_number} - {form.title}",
        form_number=form.form_number,
        edition=form.edition,
        content=f"{form.form_number} (edition {form.edition}): {form.title}. Attached as {form.kind} form.",
        relevance_score=1.0,
        evidence_index=index,
        scope="policy_record",
    )
    citation = CitationItem(
        source_id=form.id,
        source_type="form",
        evidence_index=index,
        form_number=form.form_number,
        edition=form.edition,
        heading=form.title,
        citation_text=f"Attached form {form.form_number}",
    )
    return evidence, citation


def answer_endorsement(part: Part, policy: CorePolicy, db: Session) -> PartAnswer:
    """Which endorsement grants a named coverage, or which endorsements are attached, from the policy's forms."""
    forms = db.query(CoreForm).filter(CoreForm.policy_id == policy.id).order_by(CoreForm.form_number).all()
    coverages = db.query(CoreCoverage).filter(CoreCoverage.policy_id == policy.id).all()
    coverage = find_matching_coverage(part.text, coverages)
    if coverage and coverage.governing_form:
        form = next((f for f in forms if f.form_number == coverage.governing_form), None)
        if form:
            evidence, citation = _form_evidence(form, 1)
            what = "endorsement" if form.kind == "endorsement" else f"{form.kind} form"
            return PartAnswer(
                part,
                f"{coverage.name} is provided by {what} {form.form_number} ({form.title}) [E1].",
                [evidence],
                [citation],
            )
    endorsements = [f for f in forms if f.kind == "endorsement"]
    if not endorsements:
        return PartAnswer(part, f"No endorsements are attached to policy {policy.policy_number} in the records.", found=False)
    lines, evidence, citations = [f"The endorsements attached to policy {policy.policy_number} are:"], [], []
    for i, form in enumerate(endorsements, start=1):
        ev, cit = _form_evidence(form, i)
        evidence.append(ev)
        citations.append(cit)
        lines.append(f"- {form.form_number}: {form.title} [E{i}]")
    return PartAnswer(part, "\n".join(lines), evidence, citations)


def answer_records(part: Part, policy: CorePolicy, db: Session) -> PartAnswer:
    """Schedule fields, billing, claims and adjusters for this part, from the policy records."""
    result = execute_factual_lookup(part.text, policy, db)
    if result is None:
        return PartAnswer(part, f"The records for policy {policy.policy_number} do not answer this part.", found=False)
    for i, item in enumerate(result.evidence, start=1):
        item.evidence_index = i
        item.scope = "policy_record"
    return PartAnswer(part, result.answer, list(result.evidence), list(result.citations), found=result.found)


def renumber(text: str, offset: int) -> str:
    """Shift [E#] references so each part's sources keep their own numbers in the combined reply."""
    if not offset:
        return text
    return re.sub(r"\[E(\d+)\]", lambda m: f"[E{int(m.group(1)) + offset}]", text)


def combine(answers: list[PartAnswer]) -> tuple[str, list[EvidenceItemSchema], list[CitationItem]]:
    """One reply: each part under its own label, every fact citing its own source."""
    blocks = [f"Your question has {len(answers)} parts; each is answered from its own source."]
    evidence: list[EvidenceItemSchema] = []
    citations: list[CitationItem] = []
    for answer in answers:
        offset = len(evidence)
        for item in answer.evidence:
            item.evidence_index = (item.evidence_index or 0) + offset
            evidence.append(item)
        for citation in answer.citations:
            citation.evidence_index = (citation.evidence_index or 0) + offset
            citations.append(citation)
        body = renumber(answer.text, offset).strip()
        first, _, rest = body.partition("\n")
        blocks.append(f"**{answer.part.label}:** {first}" + (f"\n{rest}" if rest else ""))
    return "\n\n".join(blocks), evidence, citations
