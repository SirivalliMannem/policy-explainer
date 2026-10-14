"""The current employee's conversation history, read only from stored rows.

Nothing here calls the AI service or a language model: titles are the first question,
truncated, and outcomes come from the evidence ledger.
"""

from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationQuestion
from app.models.ledger import EvidenceLedger
from app.models.policy import CoreAccount, CorePolicy
from app.schemas.conversation import AskedBy, ConversationListPage, ConversationSummary
from app.services.ledger.ledger_service import answer_outcome

TITLE_LENGTH = 40
POLICY_NUMBER_PATTERN = re.compile(r"\b((?:HO|PA)[-\s]?\d{3,4}(?:[-\s]\d{3,4})?)\b", re.IGNORECASE)
COVERAGE_PATTERN = re.compile(r"\b(Coverage\s+[A-Za-z0-9]+)\b", re.IGNORECASE)


def conversation_title(
    first_question: str,
    customer_name: Optional[str] = None,
    policy_number: Optional[str] = None,
) -> str:
    """Concise, human-readable conversation title based on initial question and policy context."""
    text = " ".join((first_question or "").split()).strip()
    if not text:
        return "New Conversation"

    # 1. Book-wide portfolio inquiries: "What policies do we have?" -> "Policy Overview"
    if (
        re.search(r"^\s*(?:what|which|list|show)\s+(?:kind\s+of\s+|type\s+of\s+)?(?:all\s+)?(?:our\s+)?policies\s+do\s+(?:we|i)\s+have[?.]*\s*$", text, re.I)
        or re.search(r"^\s*what\s+policies\s+do\s+(?:we|i)\s+have[?.]*\s*$", text, re.I)
        or re.search(r"^\s*(?:what|which)\s+policies\s+are\s+(?:in\s+force|on\s+file)[?.]*\s*$", text, re.I)
    ):
        return "Policy Overview"

    # 2. Customer policies:
    # "What policies does Elena Moreau have?" -> "Elena Moreau — Policies"
    # "What are David Chen's policies?" -> "David Chen — Policies"
    cust_match1 = re.search(r"\bwhat\s+policies\s+does\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)\s+have\b", text, re.I)
    if cust_match1:
        return f"{cust_match1.group(1).title()} — Policies"

    cust_match2 = re.search(r"\bwhat\s+are\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)(?:'s|’s)\s+policies\b", text, re.I)
    if cust_match2:
        return f"{cust_match2.group(1).title()} — Policies"

    cust_match3 = re.search(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)(?:'s|’s)\s+policies\b", text, re.I)
    if cust_match3:
        return f"{cust_match3.group(1).title()} — Policies"

    if customer_name and re.search(r"\bpolicies\b", text, re.I) and not re.search(r"\b(?:Coverage|HO|PA)\b", text, re.I):
        if re.search(rf"\b{re.escape(customer_name)}\b", text, re.I):
            return f"{customer_name} — Policies"

    # 3. Policy Number references (e.g. "What does HO-9021-4477 cover?", "HO-908-023 limits and deductibles"):
    pol_match = POLICY_NUMBER_PATTERN.search(text)
    pol_num = pol_match.group(1).upper().replace(" ", "-") if pol_match else (
        policy_number if (policy_number and policy_number.upper() in text.upper()) else None
    )
    if pol_num:
        if re.search(r"\b(?:limits?\s+and\s+deductibles?|deductibles?\s+and\s+limits?)\b", text, re.I):
            return f"{pol_num} — Limits & Deductibles"
        if re.search(r"\bdeductibles?\b", text, re.I):
            return f"{pol_num} — Deductible"
        if re.search(r"\blimits?\b", text, re.I):
            return f"{pol_num} — Limits"
        if re.search(r"\b(?:cover|covers|covered|coverage)\b", text, re.I):
            return f"{pol_num} — Coverage Details"
        if re.search(r"\bclaims?\b", text, re.I):
            return f"{pol_num} — Claims"
        if re.search(r"\b(?:forms?|endorsements?)\b", text, re.I):
            return f"{pol_num} — Forms & Endorsements"
        if re.search(r"\b(?:billing|premium)\b", text, re.I):
            return f"{pol_num} — Billing"
        return f"{pol_num} — Policy Details"

    # 4. Coverage letters / items: "What is the deductible for Coverage A?" -> "Coverage A — Deductible"
    cov_match = COVERAGE_PATTERN.search(text)
    if cov_match:
        cov_name = cov_match.group(1).title()
        if re.search(r"\b(?:limits?\s+and\s+deductibles?|deductibles?\s+and\s+limits?)\b", text, re.I):
            return f"{cov_name} — Limits & Deductibles"
        if re.search(r"\bdeductibles?\b", text, re.I):
            return f"{cov_name} — Deductible"
        if re.search(r"\blimits?\b", text, re.I):
            return f"{cov_name} — Limits"
        if re.search(r"\b(?:cover|covers|covered|coverage)\b", text, re.I):
            return f"{cov_name} — Coverage Details"
        return f"{cov_name} — Details"

    # 5. "Explain this policy" / "Explain the policy" -> "Policy Explanation"
    if (
        re.search(r"^\s*(?:please\s+)?(?:explain|summarize)\s+(?:this\s+|the\s+|our\s+)?policy[?.]*\s*$", text, re.I)
        or re.search(r"\bexplain\s+this\s+policy\b", text, re.I)
    ):
        return "Policy Explanation"

    # Default fallback: clean truncation at word boundary
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
    groups = [
        g for g in grouped.values()
        if not needle
        or (getattr(g["conv"], "title", None) and needle in g["conv"].title.lower())
        or needle in g["first"].question.lower()
        or needle in conversation_title(g["first"].question).lower()
    ]
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

        title = (
            conv.title.strip()
            if getattr(conv, "title", None) and conv.title.strip()
            else conversation_title(g["first"].question, customer_name, policy.policy_number if policy else None)
        )

        items.append(
            ConversationSummary(
                conversation_id=conv.id,
                title=title,
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
