"""The current employee's conversation history, read only from stored rows.

Nothing here calls the AI service or a language model: titles are the first question,
truncated, and outcomes come from the evidence ledger.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationQuestion
from app.models.ledger import EvidenceLedger
from app.models.policy import CoreAccount, CorePolicy
from app.schemas.conversation import AskedBy, ConversationListPage, ConversationSummary
from app.services.ledger.ledger_service import answer_outcome

TITLE_LENGTH = 40


def conversation_title(first_question: str) -> str:
    """The first question, cut at a word boundary to about 40 characters."""
    text = " ".join(first_question.split())
    if len(text) <= TITLE_LENGTH:
        return text
    cut = text[:TITLE_LENGTH].rsplit(" ", 1)[0] or text[:TITLE_LENGTH]
    return cut.rstrip(",.;:-") + "…"


def ledger_outcome(entry: EvidenceLedger, question_status: Optional[str] = None) -> str:
    if entry.outcome:
        return entry.outcome
    status = question_status or ("insufficient_evidence" if entry.confidence == "none" else "answered")
    return answer_outcome(status, entry.guardrail_status)


def asked_by(employee_id: str, entry: Optional[EvidenceLedger]) -> AskedBy:
    return AskedBy(
        employee_id=(entry.employee_id if entry and entry.employee_id else employee_id),
        name=entry.employee_name if entry else None,
        role=entry.employee_role if entry else None,
    )


def list_conversations(
    db: Session,
    employee_id: str,
    search: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> ConversationListPage:
    """The employee's own conversations that have at least one question, newest activity first.

    Archived conversations are excluded. ``search`` matches the conversation title (its first question).
    """
    rows = (
        db.query(ConversationQuestion, Conversation)
        .join(Conversation, Conversation.id == ConversationQuestion.conversation_id)
        .filter(Conversation.employee_id == employee_id, Conversation.is_archived.is_(False))
        .order_by(ConversationQuestion.created_at.asc())
        .all()
    )

    grouped: dict[str, dict] = {}
    for question, conv in rows:
        group = grouped.get(conv.id)
        if group is None:
            group = grouped[conv.id] = {"conv": conv, "first": question, "questions": []}
        group["questions"].append(question)

    needle = (search or "").strip().lower()
    groups = [g for g in grouped.values() if not needle or needle in g["first"].question.lower()]
    groups.sort(key=lambda g: g["questions"][-1].created_at, reverse=True)
    page = groups[offset:offset + limit]

    question_ids = [q.id for g in page for q in g["questions"]]
    entries = {
        e.question_id: e
        for e in db.query(EvidenceLedger).filter(EvidenceLedger.question_id.in_(question_ids)).all()
    } if question_ids else {}

    policy_ids = {
        pid
        for g in page
        for pid in [g["conv"].policy_id, *[q.policy_id for q in g["questions"]]]
        if pid
    }
    policies = {
        policy.id: (policy, account)
        for policy, account in db.query(CorePolicy, CoreAccount)
        .join(CoreAccount, CoreAccount.id == CorePolicy.account_id)
        .filter(CorePolicy.id.in_(policy_ids))
        .all()
    } if policy_ids else {}

    items: list[ConversationSummary] = []
    for g in page:
        conv: Conversation = g["conv"]
        questions: list[ConversationQuestion] = g["questions"]
        latest = questions[-1]
        latest_entry = entries.get(latest.id)
        # The newest ledger entry that recorded the asker's name, for the identity line.
        named_entry = next(
            (entries[q.id] for q in reversed(questions) if q.id in entries and entries[q.id].employee_name),
            latest_entry,
        )

        policy_id = next((q.policy_id for q in reversed(questions) if q.policy_id), None) or conv.policy_id
        policy, account = policies.get(policy_id, (None, None)) if policy_id else (None, None)
        customer_name = account.name if account else None
        if not policy and latest_entry and (latest_entry.retrieval or {}).get("answer_type") == "portfolio":
            customers = ((latest_entry.retrieval or {}).get("portfolio") or {}).get("customers") or []
            customer_name = ", ".join(customers) or None

        items.append(
            ConversationSummary(
                conversation_id=conv.id,
                title=conversation_title(g["first"].question),
                created_at=conv.created_at,
                last_activity_at=latest.created_at,
                question_count=len(questions),
                asked_by=asked_by(conv.employee_id, named_entry),
                policy_number=policy.policy_number if policy else None,
                customer_name=customer_name,
                latest_outcome=ledger_outcome(latest_entry, latest.status) if latest_entry else None,
            )
        )

    return ConversationListPage(items=items, total=len(groups), limit=limit, offset=offset)
