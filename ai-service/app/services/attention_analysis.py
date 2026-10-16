"""Analysis of a flagged question for the Needs attention Resolve box.

Decision order (each step stops the ones after it):

1. The actual flag reason decides first.
2. Customer verification: when the customer asked about is not on file, nothing is generated. No
   suggested questions, no other customers or policies, no model call: the Resolve box shows the
   verification failure and how to verify the customer instead.
3. Policy context: without a verified policy there is nothing to ground a suggestion in, so again
   nothing is generated; the employee is asked to identify the policy.
4. With a verified customer and policy, one model call classifies the question and returns exactly two
   distinct alternative questions in that policy's context: corrected wording for spelling or
   wording errors, related questions the policy can answer when evidence is missing. Code checks
   them (two, distinct, not a restatement of an unanswerable question); anything else is recorded
   as a failure and nothing is shown. Each suggestion is also run through the normal retrieval and
   the passages it finds are stored with it, quoted from the stored wording.

"What is missing" is built from the original search's own counts and terms, or from the form numbers
and editions actually on the policy and in the form library, never from the model's prose.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from app.models.policy import Clause, CoreCoverage, CoreForm, CorePolicy
from app.services.llm.exceptions import LLMConfigurationError, LLMProviderError
from app.services.llm.llm_service import LLMService
from app.services.retrieval.evidence_retriever import EvidenceRetriever

logger = logging.getLogger(__name__)

ANALYSIS_VERSION = 1
# The score at which retrieval keeps a clause as evidence (evidence_retriever: `if score >= 3.0`).
EVIDENCE_SCORE = 3.0
MAX_CANDIDATES = 2
MAX_PASSAGES = 3
QUOTE_CHARS = 600
TIMEOUT_SECONDS = 15.0

AnalysisType = Literal[
    "typo", "vague_wording", "definition", "coverage_no_evidence", "missing_form_or_edition", "customer_not_found", "out_of_scope", "other"
]
WRONG_WORDING = {"typo", "vague_wording", "definition"}


class Candidate(BaseModel):
    question: str = Field(..., min_length=3, max_length=300)
    relation: Literal["same", "related"]
    note: Optional[str] = Field(None, max_length=200)

    @field_validator("question", "note")
    @classmethod
    def _strip(cls, value: Optional[str]) -> Optional[str]:
        return " ".join(value.split()) if value else value


class ModelAnalysis(BaseModel):
    """The model's output; anything that does not fit is rejected."""

    type: AnalysisType
    reason: str = Field(..., min_length=3, max_length=300)
    candidates: list[Candidate] = Field(default_factory=list, max_length=MAX_CANDIDATES)


SYSTEM_PROMPT = """You review an insurance question that could not be answered or was flagged, for one specific policy.

Classify the issue into exactly one of these:
- "coverage_no_evidence": The policy search found no evidence for the requested coverage or condition.
- "typo": Misspellings or typographical errors prevented matching the policy terms.
- "vague_wording": The question is unclear, conversational, or uses terms the policy does not use.
- "definition": The question asks what a general insurance term means.
- "missing_form_or_edition": It names a specific form or edition that this policy does not have.
- "out_of_scope": It is not an insurance question about this policy, or represents another error.

Then write EXACTLY TWO different questions the employee could ask instead, for this policy only, using the coverage, form and endorsement names given:
1. "coverage_no_evidence" or "missing_form_or_edition": two questions that explore related information this policy's records and forms can answer (for example its listed coverages of that kind, or whether a relevant endorsement is attached). Do not restate the original question, and do not assume a coverage or endorsement exists unless it is listed. relation "related", with a one-line "note" saying what it does NOT answer about the original.
2. "typo", "vague_wording" or "definition": two corrected questions that keep the original meaning, with correct spelling and the policy's own terms. relation "same".
3. "out_of_scope": no questions (an empty list).

Reply with JSON only:
{"type": "...", "reason": "one short sentence", "candidates": [{"question": "...", "relation": "same|related", "note": "..."}, {"question": "...", "relation": "same|related", "note": "..."}]}"""

# Evidence-missing types: a suggestion that only restates the unanswerable question is not shown.
EVIDENCE_MISSING = {"coverage_no_evidence", "missing_form_or_edition"}
# Content-word overlap at or above which a suggestion restates the original question.
RESTATEMENT_OVERLAP = 0.75
_STOP = {"the", "a", "an", "is", "are", "does", "do", "my", "this", "that", "on", "of", "for", "to", "in", "it",
         "policy", "covered", "cover", "coverage", "what", "under", "be", "by", "any", "there", "can", "i"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _parse(raw: str) -> dict:
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"\{.*\}", raw or "", re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _policy_context(policy: CorePolicy, db: Session) -> tuple[str, list[CoreForm]]:
    coverages = db.query(CoreCoverage).filter(CoreCoverage.policy_id == policy.id).order_by(CoreCoverage.sort_order).all()
    forms = db.query(CoreForm).filter(CoreForm.policy_id == policy.id).order_by(CoreForm.form_number).all()
    lines = [
        f"Policy {policy.policy_number}: {policy.product_name or policy.line_of_business}, state {policy.state or 'n/a'}.",
        "Coverages: " + "; ".join(
            f"{c.name} (limit {c.limit_text or 'n/a'}, deductible {c.deductible_text or 'none'}, form {c.governing_form or 'n/a'})"
            for c in coverages
        ),
        "Forms and endorsements: " + "; ".join(f"{f.form_number} edition {f.edition} {f.title} ({f.kind})" for f in forms),
    ]
    return "\n".join(lines), forms


def _original_search(retrieval: dict) -> dict:
    """What the first search found, from the flagged answer's stored retrieval stats."""
    keys = ("query_terms", "coverages_searched", "forms_searched", "clauses_searched")
    return {k: retrieval.get(k) for k in keys if retrieval.get(k) is not None}


def _passages(question: str, policy_id: str, db: Session) -> tuple[list[dict], float]:
    """Run the normal retrieval and keep the clauses and coverages that count as evidence."""
    items, _ = EvidenceRetriever.retrieve_with_stats(question, policy_id, db)
    found = [i for i in items if i.source_type in ("clause", "coverage") and i.relevance_score >= EVIDENCE_SCORE]
    passages = []
    for item in found[:MAX_PASSAGES]:
        quote = (item.content or "").strip()[:QUOTE_CHARS]
        source_text = item.content or ""
        if item.source_type == "clause":
            row = db.query(Clause).filter(Clause.id == item.source_id).first()
            source_text = row.text if row else ""
        passages.append({
            "source_type": item.source_type,
            "source_id": item.source_id,
            "form_number": item.form_number,
            "edition": item.edition,
            "page": item.page,
            "section": item.section,
            "heading": item.heading or item.title,
            "quote": quote,
            "score": round(item.relevance_score, 1),
            # Clauses only: the quote is the stored wording, confirmed against the source row. A coverage
            # line is built from schedule fields, so there is no wording to check it against.
            "quote_verified": (bool(quote) and quote in (source_text or "")) if item.source_type == "clause" else None,
        })
    top = max((p["score"] for p in passages), default=0.0)
    return passages, top


# A policy number ("HO-2847-1193") identifies the policy; it is never a form reference.
_POLICY_NUMBER = re.compile(r"\b(?:HO|PA)[-\s]?\d{4}[-\s]?\d{4}\b", re.IGNORECASE)
_FORM_REF = re.compile(r"\b([A-Z]{2})[\s-]?(\d{2})[\s-]?(\d{2})\b", re.IGNORECASE)
_EDITION_REF = re.compile(r"\b(?:edition|ed\.?)\s*(\d{2})[\s/-]?(\d{2})\b", re.IGNORECASE)


def _form_facts(question: str, policy: CorePolicy, forms: list[CoreForm], db: Session) -> Optional[dict]:
    """The form or edition the question names that the policy does not have, from the stored forms."""
    text = _POLICY_NUMBER.sub(" ", question or "")
    match = _FORM_REF.search(text)
    if not match:
        return None
    number = f"{match.group(1).upper()} {match.group(2)} {match.group(3)}"
    edition_match = _EDITION_REF.search(text)
    edition = f"{edition_match.group(1)} {edition_match.group(2)}" if edition_match else None
    attached = [f for f in forms if f.form_number == number]
    library = sorted({c.edition for c in db.query(Clause).filter(Clause.form_number == number).all()})
    if attached and (edition is None or any(f.edition == edition for f in attached)):
        return None  # the policy has exactly what was asked for: nothing is missing
    return {
        "form_number": number,
        "edition_asked": edition,
        "policy_editions": sorted({f.edition for f in attached}),
        "library_editions": library,
    }


def _missing_text(kind: str, policy: CorePolicy, search: dict, form: Optional[dict]) -> Optional[str]:
    """'What is missing', built only from stored facts."""
    if kind == "missing_form_or_edition" and form:
        number, edition = form["form_number"], form["edition_asked"]
        asked = f"{number} edition {edition}" if edition else number
        if form["policy_editions"]:
            return f"{asked} is not on {policy.policy_number}; the policy has {number} edition {', '.join(form['policy_editions'])}."
        on_file = f" The form library has edition {', '.join(form['library_editions'])}." if form["library_editions"] else " It is not in the form library either."
        return f"{asked} is not attached to {policy.policy_number}.{on_file}"
    if kind == "coverage_no_evidence":
        terms = search.get("query_terms") or []
        counts = (
            f"Searched {search.get('coverages_searched', 0)} coverages, {search.get('forms_searched', 0)} forms "
            f"and {search.get('clauses_searched', 0)} clauses on {policy.policy_number}"
        )
        if terms:
            return counts + "; none mention " + ", ".join(f"“{t}”" for t in terms) + "."
        return counts + "; none matched the question."
    return None


FLAG_LINES = {
    "no_evidence": "it found no evidence it could answer from.",
    "guardrail_flagged": "an answer was written but a safety check failed.",
    "low_confidence": "it was answered on weak evidence.",
}


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 2 and w not in _STOP}


def _restates(candidate: str, original: str) -> bool:
    a, b = _content_words(candidate), _content_words(original)
    return bool(a and b) and len(a & b) / len(a | b) >= RESTATEMENT_OVERLAP


def _customer_not_found(flag_reason: str, retrieval: dict) -> bool:
    verification = (retrieval or {}).get("customer_verification")
    status = verification.get("status") if isinstance(verification, dict) else None
    return flag_reason == "customer_not_found" or status in ("not_found", "customer_not_found")


def analyze(question: str, policy_id: Optional[str], retrieval: dict, db: Session, flag_reason: str = "no_evidence") -> dict:
    """The stored analysis of one flagged question. Never raises; a failure is recorded as such."""
    base = {"version": ANALYSIS_VERSION, "analyzed_at": _utc_now(), "original_search": _original_search(retrieval or {})}

    # 2. Customer verification comes first: an unverified customer gets no suggestions at all.
    if _customer_not_found(flag_reason, retrieval):
        return {
            **base, "status": "ready", "type": "customer_not_found", "category": "customer_not_found",
            "reason": "The customer asked about was not found in the customer records, so no policy context exists to suggest questions from.",
            "candidates": [], "missing": None,
        }
    # 3. Without a verified policy there is nothing to ground a suggestion in.
    policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first() if policy_id else None
    if policy is None:
        return {
            **base, "status": "ready", "type": "policy_context_missing", "category": "policy_context_missing",
            "reason": "No single policy was identified for this question, so suggestions cannot be grounded in policy wording.",
            "candidates": [], "missing": None,
        }

    # 4. Verified customer and policy: one model call, then code checks.
    context, forms = _policy_context(policy, db)
    try:
        provider = LLMService.get_provider()
        if not provider.is_configured:
            raise LLMConfigurationError(f"No API key configured for provider '{provider.name}'")
        search = base["original_search"]
        found_line = (
            f"The first search used the terms {', '.join(search.get('query_terms') or []) or 'none'} and searched "
            f"{search.get('coverages_searched', 0)} coverages, {search.get('forms_searched', 0)} forms and "
            f"{search.get('clauses_searched', 0)} clauses; {FLAG_LINES.get(flag_reason, f'flagged with reason: {flag_reason}.')}"
        )
        raw = provider.complete(
            SYSTEM_PROMPT, f"{context}\n\n{found_line}\n\nActual flag reason: {flag_reason}\nOriginal question: {question.strip()}",
            max_tokens=700, json_mode=True, timeout_seconds=TIMEOUT_SECONDS, retry_rate_limit=True,
        )
        model = ModelAnalysis.model_validate(_parse(raw))
    except (LLMConfigurationError, LLMProviderError) as exc:
        logger.warning("Attention analysis unavailable: %s", type(exc).__name__)
        return {**base, "status": "failed", "reason": "The language model is not available right now (it may be busy)."}
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Attention analysis rejected: the model's reply did not match the schema (%s)", type(exc).__name__)
        return {**base, "status": "failed", "reason": "The language model's reply did not match the required format."}

    # The stored forms decide whether a form or edition is missing, whatever the model called it.
    kind = model.type
    form = _form_facts(question, policy, forms, db) if kind != "out_of_scope" else None
    if form is not None:
        kind = "missing_form_or_edition"
    elif kind == "missing_form_or_edition":
        kind = "coverage_no_evidence"  # names no form the policy lacks: a gap in coverage wording
    if kind in ("customer_not_found", "other"):
        kind = "out_of_scope" if kind == "other" else kind

    result = {
        **base,
        "status": "ready",
        "type": kind,
        "category": "wrong_wording" if kind in WRONG_WORDING else "out_of_scope" if kind == "out_of_scope" else "evidence_missing",
        "reason": model.reason,
        "candidates": [],
        "missing": _missing_text(kind, policy, base["original_search"], form),
        "missing_form": form,
        "policy_number": policy.policy_number,
        "model_used": provider.model,
        "provider": provider.name,
        "upload_available": False,  # no flow exists to add a form or edition
    }
    if kind == "out_of_scope":
        return result

    # Exactly two distinct, usable suggestions, or none at all: nothing is padded or made up.
    proposed, seen = [], set()
    for candidate in model.candidates:
        key = " ".join(_content_words(candidate.question)) or candidate.question.lower()
        if key in seen or candidate.question.strip().lower() == question.strip().lower():
            continue
        if kind in EVIDENCE_MISSING and _restates(candidate.question, question):
            continue  # restating an unanswerable question would imply it can be answered
        seen.add(key)
        proposed.append(candidate)
    if len(proposed) != MAX_CANDIDATES:
        logger.warning("Attention analysis: the model gave %d usable suggestions, not %d", len(proposed), MAX_CANDIDATES)
        return {**base, "status": "failed",
                "reason": "The language model did not return two distinct, usable suggestions. Try again."}

    for candidate in proposed:
        relation = "related" if kind in EVIDENCE_MISSING else "same" if kind in WRONG_WORDING else candidate.relation
        note = (candidate.note or None) if relation == "related" else None
        if relation == "related" and not note:
            note = "A related question; it does not answer the original question itself."
        passages, top = _passages(candidate.question, policy.id, db)
        result["candidates"].append({
            "question": candidate.question,
            "relation": relation,
            "note": note,
            "passages": passages,
            "top_score": top,
        })
    return result
