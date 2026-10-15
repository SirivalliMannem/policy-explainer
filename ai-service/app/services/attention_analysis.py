"""Analysis of a flagged question for the Needs attention Resolve box.

One language-model call classifies why the question went unanswered and proposes at most two
alternative questions. Everything after that is code:

- every candidate is run through the normal retrieval; only candidates that find a clause or a
  coverage scoring at least EVIDENCE_SCORE (the score at which retrieval keeps a passage as
  evidence) are kept, each with the passages it found, quoted from the stored wording and checked
  word for word against the source row;
- "What is missing" is built from the original search's own counts and terms, or from the form
  numbers and editions actually on the policy and in the form library, never from the model's prose.

When the model is unavailable the analysis is returned as failed and nothing is invented.
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
    "typo", "vague_wording", "definition", "coverage_no_evidence", "missing_form_or_edition", "out_of_scope"
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


SYSTEM_PROMPT = """You review an insurance question that a policy search could not answer well, for one specific policy.

Decide which one of these describes it:
- "typo": misspellings stop the search matching the policy wording.
- "vague_wording": the question is unclear or uses everyday words the policy does not use.
- "definition": it asks what a general insurance term means.
- "coverage_no_evidence": a clear coverage question about something this policy's forms do not address.
- "missing_form_or_edition": it names a form or an edition this policy does not have.
- "out_of_scope": it is not an insurance question about this policy at all.

Then propose at most 2 questions the employee could ask instead, written in the policy's own terms (use the coverage and form names given):
- "same": the rewritten question asks exactly the same thing (only for typo, vague_wording, definition).
- "related": a different question the policy can answer. Give a one-line "note" saying what it does NOT answer about the original.
For coverage_no_evidence, only propose "related" questions. For out_of_scope, propose none.

Reply with JSON only:
{"type": "...", "reason": "one short sentence", "candidates": [{"question": "...", "relation": "same|related", "note": "..."}]}"""


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


def analyze(question: str, policy_id: Optional[str], retrieval: dict, db: Session, flag_reason: str = "no_evidence") -> dict:
    """The stored analysis of one flagged question. Never raises; a failure is recorded as such."""
    base = {"version": ANALYSIS_VERSION, "analyzed_at": _utc_now(), "original_search": _original_search(retrieval or {})}
    policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first() if policy_id else None
    if policy is None:
        return {**base, "status": "ready", "type": None, "reason": "This question is not about a single policy, so there is no policy wording to search.",
                "candidates": [], "dropped_candidates": 0, "missing": None}

    context, forms = _policy_context(policy, db)
    try:
        provider = LLMService.get_provider()
        if not provider.is_configured:
            raise LLMConfigurationError(f"No API key configured for provider '{provider.name}'")
        search = base["original_search"]
        found_line = (
            f"The first search used the terms {', '.join(search.get('query_terms') or []) or 'none'} and searched "
            f"{search.get('coverages_searched', 0)} coverages, {search.get('forms_searched', 0)} forms and "
            f"{search.get('clauses_searched', 0)} clauses; {FLAG_LINES.get(flag_reason, FLAG_LINES['no_evidence'])}"
        )
        raw = provider.complete(
            SYSTEM_PROMPT, f"{context}\n\n{found_line}\n\nQuestion: {question.strip()}",
            max_tokens=700, json_mode=True, timeout_seconds=TIMEOUT_SECONDS, retry_rate_limit=False,
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
        # The question names no form or edition the policy lacks: treat it as a gap in coverage wording.
        kind = "coverage_no_evidence"

    candidates, dropped = [], 0
    if kind != "out_of_scope":
        for candidate in model.candidates[:MAX_CANDIDATES]:
            relation = candidate.relation
            if kind == "coverage_no_evidence" or kind == "missing_form_or_edition":
                relation = "related"  # rewording cannot answer a real gap
            if relation == "related" and not candidate.note:
                dropped += 1  # a related question must say what it does not answer
                continue
            passages, top = _passages(candidate.question, policy.id, db)
            if not passages:
                dropped += 1  # never shown: it did not find evidence
                continue
            candidates.append({
                "question": candidate.question,
                "relation": relation,
                "note": candidate.note if relation == "related" else None,
                "passages": passages,
                "top_score": top,
            })

    return {
        **base,
        "status": "ready",
        "type": kind,
        "category": "wrong_wording" if kind in WRONG_WORDING else "out_of_scope" if kind == "out_of_scope" else "evidence_missing",
        "reason": model.reason,
        "candidates": candidates,
        "dropped_candidates": dropped,
        "missing": _missing_text(kind, policy, base["original_search"], form),
        "missing_form": form,
        "policy_number": policy.policy_number,
        "model_used": provider.model,
        "provider": provider.name,
        "upload_available": False,  # no flow exists to add a form or edition
    }
