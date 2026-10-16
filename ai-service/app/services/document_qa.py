"""Answers about a document the employee uploaded into the chat.

The document's text is stored page by page (PDF) or section by section (Word, text). It is split into
passages; a question is matched to passages by the same word match and meaning search used for policy
clauses; the language model answers from those passages only and cites them as [E#], which the chat
shows with the document's page or section. A broad question ("can this relate to a homeowners
policy?") also gets an overview of the whole document. When the conversation has a policy selected,
the most relevant wording of that policy on file is given too, labelled separately, so the two can be
compared. The model may add general insurance knowledge to explain, compare or relate, but only in
sentences that begin "In general," and never cited as the document or the policy. It says plainly when
a question has nothing to do with the document.

When the model is unavailable, the matching passages themselves are shown with their page numbers;
nothing is written that is not in the document.
"""

from __future__ import annotations

import logging
import re
import time
from types import SimpleNamespace
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document import UploadedDocument, UploadedDocumentPage
from app.services.llm.base import (
    citations_from_references,
    normalize_evidence_references,
    referenced_evidence_indexes,
)
from app.services.llm.exceptions import LLMConfigurationError, LLMProviderError
from app.services.llm.llm_service import LLMService
from app.services.retrieval.evidence_retriever import EvidenceItem, _tokenize
from app.services.retrieval.semantic_index import semantic_index

logger = logging.getLogger(__name__)

PASSAGE_CHARS = 900
MAX_PASSAGES = 6
SUMMARY_PASSAGES = 8
SUMMARY_CHARS = 7000
EVIDENCE_SCORE = 3.0  # as for policy clauses: below this a passage is not evidence
STRONG_EVIDENCE_SCORE = 12.0
MEANING_MIN_LIFT = 0.08  # one document is about one subject, so passages stand out less than clauses do
MEANING_FULL_LIFT = 0.18
TIMEOUT_SECONDS = 25.0
NOT_IN_DOCUMENT = "NOT_IN_DOCUMENT"

SUMMARY_PROMPT = """You explain a document that an insurance employee uploaded, in simple, plain language.

Use ONLY the numbered passages given. Do not add outside knowledge or assumptions.
Write:
1. One or two sentences saying what the document is and who it concerns.
2. "Key points:" then short bullet points with the important details actually present (for a policy: what is covered, limits, deductibles, exclusions, dates, conditions, obligations; for anything else: its main facts).
End every sentence or bullet that states a fact with the passage it comes from, as [E1], [E2].
Never say whether a particular claim or loss would be paid."""

GENERAL_MARKER = "In general,"

QUESTION_PROMPT = f"""You help an insurance employee with a document they uploaded. They may ask what it says, or ask you to explain it, compare it, relate it to other kinds of insurance or to the customer's policy on file, or reason about it.

The numbered sources are passages from the UPLOADED DOCUMENT and, when given, from the POLICY ON FILE (the customer's own policy in the carrier's records). Each is labelled.
Rules:
- What the document or the policy says must come from the sources, with the source cited at the end of the sentence as [E1], [E2]. Make clear which one you mean ("the uploaded document", "the policy on file").
- To explain, compare or relate you may use general insurance knowledge, but every such sentence must begin with "{GENERAL_MARKER}" and carry no citation. Never present general knowledge as what the document or the policy says.
- Answer in plain language, concisely.
- Never say whether a particular claim or loss would be paid.
- If the question has nothing to do with the document, the policy or insurance, reply with exactly: {NOT_IN_DOCUMENT}"""
OVERVIEW_WHEN_FEWER_THAN = 2
POLICY_PASSAGES = 4


def _passages(document: UploadedDocument, pages: list[UploadedDocumentPage]) -> list[dict]:
    """The document split into passages of about PASSAGE_CHARS, each keeping its page."""
    passages = []
    for page in pages:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page.text or "") if p.strip()]
        current = ""
        for paragraph in paragraphs:
            if current and len(current) + len(paragraph) > PASSAGE_CHARS:
                passages.append({"page": page, "text": current})
                current = ""
            current = f"{current}\n\n{paragraph}".strip()
            while len(current) > PASSAGE_CHARS * 1.5:  # one very long paragraph
                cut = current.rfind(". ", 0, PASSAGE_CHARS) + 1 or PASSAGE_CHARS
                passages.append({"page": page, "text": current[:cut].strip()})
                current = current[cut:].strip()
        if current:
            passages.append({"page": page, "text": current})
    for i, p in enumerate(passages):
        p["id"] = f"{p['page'].id}:{i}"
    return passages


def _score(question: str, passages: list[dict]) -> tuple[list[dict], dict]:
    """Word match plus meaning search, as for policy clauses. Returns passages scored as evidence."""
    q_tokens = _tokenize(question)
    as_clauses = [SimpleNamespace(id=p["id"], heading="", plain_language="", text=p["text"]) for p in passages]
    lifts = semantic_index.lifts(question, as_clauses, as_clauses) if passages else None
    meaning = {"status": "used" if lifts is not None else "unavailable", "model": semantic_index.model_name}
    scored = []
    for p in passages:
        words = len(q_tokens & _tokenize(p["text"])) * 3.0
        lift = (lifts or {}).get(p["id"])
        meaning_points = (
            round(min(STRONG_EVIDENCE_SCORE * lift / MEANING_FULL_LIFT, 15.0), 1)
            if lift is not None and lift >= MEANING_MIN_LIFT
            else 0.0
        )
        score = max(words, meaning_points) + (2.0 if words >= EVIDENCE_SCORE and meaning_points else 0.0)
        if score >= EVIDENCE_SCORE:
            scored.append({**p, "score": score,
                           "matched_by": "words and meaning" if words >= EVIDENCE_SCORE and meaning_points else "meaning" if meaning_points else "words"})
    scored.sort(key=lambda p: -p["score"])
    return scored[:MAX_PASSAGES], meaning


def _overview(passages: list[dict]) -> list[dict]:
    """Passages spread across the whole document, for the plain-language explanation."""
    if len(passages) <= SUMMARY_PASSAGES:
        chosen = passages
    else:
        step = len(passages) / SUMMARY_PASSAGES
        chosen = [passages[int(i * step)] for i in range(SUMMARY_PASSAGES)]
    total, kept = 0, []
    for p in chosen:
        if total + len(p["text"]) > SUMMARY_CHARS and kept:
            break
        kept.append({**p, "score": 0.0, "matched_by": None})
        total += len(p["text"])
    return kept


def _evidence(document: UploadedDocument, passages: list[dict]) -> list[EvidenceItem]:
    unit = "Page" if document.unit == "page" else "Section"
    return [
        EvidenceItem(
            source_type="document",
            source_id=p["page"].id,
            title=document.filename,
            content=p["text"],
            form_number=document.filename[:40],
            page=p["page"].page_number,
            heading=f"{unit} {p['page'].page_number}",
            relevance_score=p["score"],
            metadata={"scope": "uploaded_document", "matched_by": p.get("matched_by")},
        )
        for p in passages
    ]


def _evidence_dicts(items: list[EvidenceItem]) -> list[dict]:
    return [
        {
            "source_type": i.source_type, "source_id": i.source_id, "title": i.title, "content": i.content,
            "form_number": i.form_number, "edition": i.edition, "page": i.page, "section": i.section, "heading": i.heading,
            "relevance_score": i.relevance_score, "evidence_index": n,
            # The uploaded document, or the customer's policy on file given for comparison.
            "scope": (i.metadata or {}).get("scope", "uploaded_document"), "matched_by": (i.metadata or {}).get("matched_by"),
        }
        for n, i in enumerate(items, start=1)
    ]


def _checks(answer: str, evidence: list[EvidenceItem]) -> list[dict]:
    refs = referenced_evidence_indexes(answer)
    valid = [r for r in refs if 1 <= r <= len(evidence)]
    general = GENERAL_MARKER.lower() in answer.lower()
    if valid:
        inline = {"name": "inline_citations", "status": "passed", "detail": f"{len(valid)} inline reference(s) to the sources."}
    elif general:
        # Only general knowledge, clearly marked as such: reported, not blocked.
        inline = {"name": "inline_citations", "status": "warning",
                  "detail": "The answer uses general insurance knowledge only (marked “In general”); nothing in the document is cited."}
    else:
        inline = {"name": "inline_citations", "status": "failed", "detail": "The answer cites no passage of the document."}
    return [
        {"name": "answer_present", "status": "passed" if answer.strip() else "failed",
         "detail": "A non-empty answer was produced." if answer.strip() else "No answer was produced."},
        inline,
        {"name": "citations_verified", "status": "passed" if len(valid) == len(refs) else "failed",
         "detail": f"{len(valid)} of {len(refs)} references point to passages of the document."},
    ]


def _fallback_answer(lead: str, evidence: list[EvidenceItem]) -> str:
    lines = [lead]
    for n, item in enumerate(evidence, start=1):
        snippet = " ".join(item.content.split())
        snippet = snippet[:220].rsplit(" ", 1)[0] + "…" if len(snippet) > 220 else snippet
        lines.append(f"- {item.heading}: “{snippet}” [E{n}]")
    return "\n".join(lines)


def _policy_evidence(question: str, policy_id: Optional[str], db: Session) -> list[EvidenceItem]:
    """The policy on file's most relevant wording for the question, for comparison with the document."""
    if not policy_id:
        return []
    from app.services.retrieval.evidence_retriever import EvidenceRetriever

    items = EvidenceRetriever.retrieve(question, policy_id, db)
    kept = [i for i in items if i.source_type in ("clause", "coverage")][:POLICY_PASSAGES]
    for item in kept:
        item.metadata = {**(item.metadata or {}), "scope": "policy_on_file"}
    return kept


def answer_from_document(
    document_id: str, question: str, mode: str, db: Session, policy_id: Optional[str] = None
) -> Optional[dict]:
    """A grounded answer (or the plain-language explanation, mode "summary") from one uploaded document."""
    started = time.perf_counter()
    document = db.query(UploadedDocument).filter(UploadedDocument.id == document_id).first()
    if document is None:
        return None
    pages = (
        db.query(UploadedDocumentPage)
        .filter(UploadedDocumentPage.document_id == document.id)
        .order_by(UploadedDocumentPage.page_number)
        .all()
    )
    passages = _passages(document, pages)
    policy_items: list[EvidenceItem] = []
    matched = 0  # passages that matched the question (the rest, if any, are the document's overview)
    if mode == "summary":
        chosen, meaning = _overview(passages), None
    else:
        chosen, meaning = _score(question, passages)
        matched = len(chosen)
        # A broad question matches few passages: give the whole document's overview as well, so it can
        # still be explained, compared or related.
        if len(chosen) < OVERVIEW_WHEN_FEWER_THAN:
            seen = {p["id"] for p in chosen}
            chosen = chosen + [p for p in _overview(passages) if p["id"] not in seen][: MAX_PASSAGES - len(chosen)]
        policy_items = _policy_evidence(question, policy_id, db)
    evidence = _evidence(document, chosen) + policy_items
    retrieval = {
        "answer_type": "document",
        "mode": mode,
        "document": {"id": document.id, "filename": document.filename, "unit": document.unit, "page_count": document.page_count},
        "passages_searched": len(passages),
        "policy_passages": len(policy_items),
        **({"meaning_search": meaning} if meaning else {}),
    }
    base = {"question": question, "suggested_questions": [], "retrieval": retrieval, "evidence": _evidence_dicts(evidence)}
    retrieval_ms = int((time.perf_counter() - started) * 1000)

    if not evidence:
        return {
            **base, "answer": "The uploaded document does not appear to cover this question.", "confidence": "none",
            "status": "insufficient_evidence", "citations": [], "guardrail_status": "no_evidence", "guardrail_checks": [],
            "model_used": "none", "provider": "none", "timings_ms": {"retrieval": retrieval_ms},
        }

    def label(item: EvidenceItem) -> str:
        if item.source_type == "document":
            return f"UPLOADED DOCUMENT, {item.heading}"
        return f"POLICY ON FILE, {item.form_number or ''} p.{item.page or '-'} {item.heading or item.title}".strip()

    numbered = "\n\n".join(f"[E{n}] ({label(item)})\n{item.content}" for n, item in enumerate(evidence, start=1))
    grounding = f"Uploaded document: {document.filename}\n\n{numbered}"
    generation_started = time.perf_counter()
    try:
        provider = LLMService.get_provider()
        if not provider.is_configured:
            raise LLMConfigurationError(f"No API key configured for provider '{provider.name}'")
        prompt = SUMMARY_PROMPT if mode == "summary" else QUESTION_PROMPT
        user = grounding + ("" if mode == "summary" else f"\n\nQuestion: {question.strip()}")
        raw = provider.complete(prompt, user, max_tokens=900, timeout_seconds=TIMEOUT_SECONDS, retry_rate_limit=True)
        answer = normalize_evidence_references((raw or "").strip())
        model_used, provider_name, is_fallback, fallback_reason = provider.model, provider.name, False, None
    except (LLMConfigurationError, LLMProviderError) as exc:
        logger.warning("Document answer: language model unavailable (%s)", type(exc).__name__)
        lead = (
            "The language model is not available right now, so here are passages from across the document:"
            if mode == "summary"
            else "The language model is not available right now. These passages of the document match the question:"
            if matched
            else "The language model is not available right now, so the question cannot be answered. Nothing in the document matched it; here is an overview of the document:"
        )
        answer = _fallback_answer(lead, evidence)
        model_used, provider_name, is_fallback, fallback_reason = "none", "none", True, type(exc).__name__
    generation_ms = int((time.perf_counter() - generation_started) * 1000)

    if answer.strip() == NOT_IN_DOCUMENT or answer.strip().startswith(NOT_IN_DOCUMENT):
        return {
            **base, "evidence": [], "answer": "The uploaded document does not say anything that answers this question.",
            "confidence": "none", "status": "insufficient_evidence", "citations": [], "guardrail_status": "no_evidence",
            "guardrail_checks": [], "model_used": model_used, "provider": provider_name, "grounding_context": grounding,
            "raw_llm_response": raw if not is_fallback else "",
            "timings_ms": {"retrieval": retrieval_ms, "generation": generation_ms},
        }

    checks = _checks(answer, evidence)
    passed = not any(c["status"] == "failed" for c in checks)
    retrieval["general_knowledge"] = GENERAL_MARKER.lower() in answer.lower()
    cited = len({r for r in referenced_evidence_indexes(answer) if 1 <= r <= len(evidence)})
    top = max((i.relevance_score for i in evidence), default=0.0)
    confidence = "low" if is_fallback or not passed else "high" if cited >= 2 and (mode == "summary" or top >= STRONG_EVIDENCE_SCORE) else "medium"
    return {
        **base,
        "answer": answer,
        "confidence": confidence,
        "status": "answered",
        "citations": citations_from_references(answer, evidence),
        "guardrail_status": "passed" if passed else "flagged",
        "guardrail_checks": checks,
        "grounding_context": grounding,
        "raw_llm_response": "" if is_fallback else raw,
        "model_used": model_used,
        "provider": provider_name,
        "is_fallback": is_fallback,
        "fallback_reason": fallback_reason,
        "timings_ms": {"retrieval": retrieval_ms, "generation": generation_ms},
    }
