"""Company guidance: the carrier's approved how-to articles, searched next to the policy wording.

Articles come from the knowledge library (published collections, active documents) and are shown
exactly as approved, labelled [G1], [G2] and kept apart from the policy answer. They are never given
to the language model and never replace the form: the policy answer cites only forms and records
([E#]), and a guardrail check confirms that no coverage statement leans on guidance.

Matching is deterministic: an article matches when at least two of its keywords appear in the
question. Collections limited to a line of business, a state or a date range apply only to policies
and dates inside them.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeCollection, KnowledgeDocument
from app.models.policy import CorePolicy
from app.schemas.explainer import GuardrailCheck

MIN_KEYWORD_HITS = 2
MAX_ARTICLES = 2
CHECK_NAME = "guidance_not_overriding_form"
GUIDANCE_REF = re.compile(r"\[G\d+\]")

# "the sewer backed up" asks about a backup.
_PHRASES = ((re.compile(r"\bback(?:ed|s|ing)?[\s-]+up\b"), "backup"),)


def _normalise(question: str) -> str:
    text = (question or "").lower()
    for pattern, replacement in _PHRASES:
        text = pattern.sub(replacement, text)
    return text


def _keyword_pattern(keyword: str) -> re.Pattern:
    words = re.escape(keyword.lower().strip()).replace(r"\ ", r"[\s-]+")
    return re.compile(rf"\b{words}(?:s|es|ed|ing|d)?\b")


def matched_keywords(question: str, keywords: list[str]) -> list[str]:
    """The article keywords that appear in the question. A keyword inside a longer matched one
    ("covered" in "is it covered") is the same evidence, so it is not counted again."""
    text = _normalise(question)
    hits = [k for k in keywords or [] if k.strip() and _keyword_pattern(k).search(text)]
    return [k for k in hits if not any(k != other and k.lower() in other.lower() for other in hits)]


def _applies(collection: KnowledgeCollection, policy: CorePolicy, today: date) -> bool:
    if collection.status != "published":
        return False
    if collection.effective_from and collection.effective_from > today:
        return False
    if collection.effective_to and collection.effective_to < today:
        return False
    if collection.line_of_business and collection.line_of_business != policy.line_of_business:
        return False
    if collection.state and collection.state != policy.state:
        return False
    return True


def find_guidance(question: str, policy: CorePolicy, db: Session, today: Optional[date] = None) -> list[dict]:
    """The approved articles that match the question, best match first, numbered G1, G2."""
    today = today or date.today()
    rows = (
        db.query(KnowledgeDocument, KnowledgeCollection)
        .join(KnowledgeCollection, KnowledgeDocument.collection_id == KnowledgeCollection.id)
        .filter(KnowledgeDocument.active.is_(True), KnowledgeCollection.org_id == policy.org_id)
        .all()
    )
    scored = []
    for document, collection in rows:
        if not _applies(collection, policy, today):
            continue
        hits = matched_keywords(question, document.keywords)
        if len(hits) >= MIN_KEYWORD_HITS:
            scored.append((len(hits), document, collection, hits))
    scored.sort(key=lambda s: (-s[0], s[1].title))
    return [
        {
            "ref": f"G{i}",
            "document_id": document.id,
            "title": document.title,
            "collection": collection.name,
            "kind": collection.kind,
            "body": document.body,
            "spoken": document.spoken,
            "matched_on": hits,
            "version": document.version,
            "approved_by": document.approved_by,
        }
        for i, (_, document, collection, hits) in enumerate(scored[:MAX_ARTICLES], start=1)
    ]


def guidance_for_answer(
    question: str, policy: CorePolicy, answer_text: str, delivered: bool, db: Session
) -> tuple[dict, Optional[GuardrailCheck]]:
    """The guidance shown beside an answer, and the check that it did not override the form.

    Withheld answers get no guidance: on its own it could be read as the answer.
    """
    if not delivered:
        return {"searched": False, "articles": [], "reason": "No policy answer was delivered."}, None
    articles = find_guidance(question, policy, db)
    payload = {"searched": True, "articles": articles}
    if not articles:
        return payload, None
    if GUIDANCE_REF.search(answer_text or ""):
        check = GuardrailCheck(
            name=CHECK_NAME,
            status="failed",
            detail="Guidance does not override the form: the policy answer cites a guidance article.",
        )
    else:
        check = GuardrailCheck(
            name=CHECK_NAME,
            status="passed",
            detail=(
                "Guidance does not override the form: the policy answer cites only policy forms and records; "
                f"{len(articles)} guidance article{'s are' if len(articles) != 1 else ' is'} shown separately."
            ),
        )
    return payload, check


def with_guidance_status(guardrail_status: str, check: Optional[GuardrailCheck]) -> str:
    """A failed guidance check flags the answer for review."""
    if check is not None and check.status == "failed" and guardrail_status not in ("flagged", "failed"):
        return "flagged"
    return guardrail_status
