"""The most recently asked policy questions, for the dashboard API and the Explainer's Recent list."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationQuestion
from app.models.ledger import EvidenceLedger
from app.models.policy import CoreAccount, CorePolicy
from app.schemas.dashboard import RecentQuestionItem


def recent_questions(db: Session, limit: int = 10, employee_id: Optional[str] = None) -> list[RecentQuestionItem]:
    """Newest questions first, with the policyholder, policy and recorded confidence.

    With ``employee_id``, only that employee's questions in conversations they have not archived.
    """
    query = (
        db.query(
            ConversationQuestion,
            CorePolicy,
            CoreAccount,
            EvidenceLedger.confidence,
            EvidenceLedger.retrieval,
        )
        .outerjoin(CorePolicy, CorePolicy.id == ConversationQuestion.policy_id)
        .outerjoin(CoreAccount, CoreAccount.id == CorePolicy.account_id)
        .outerjoin(EvidenceLedger, EvidenceLedger.question_id == ConversationQuestion.id)
    )
    if employee_id is not None:
        query = query.join(Conversation, Conversation.id == ConversationQuestion.conversation_id).filter(
            Conversation.employee_id == employee_id, Conversation.is_archived.is_(False)
        )
    rows = query.order_by(ConversationQuestion.created_at.desc()).limit(limit).all()

    items: list[RecentQuestionItem] = []
    for cq, policy, account, conf, retrieval in rows:
        cust_name = account.name if (account and account.name) else "Context pending"
        pol_num = policy.policy_number if (policy and policy.policy_number) else "Context pending"
        if (retrieval or {}).get("answer_type") == "portfolio":
            # Customer / portfolio answers are about many policies, not a pending context.
            customers = ((retrieval or {}).get("portfolio") or {}).get("customers") or []
            cust_name = ", ".join(customers) or "All policyholders"
            pol_num = "Portfolio"
        final_conf = conf if conf else ("none" if cq.status == "insufficient_evidence" else None)
        items.append(
            RecentQuestionItem(
                question_id=cq.id,
                conversation_id=cq.conversation_id,
                question=cq.question,
                status=cq.status,
                confidence=final_conf,
                customer_name=cust_name,
                customer_id=account.id if account else None,
                policy_number=pol_num,
                policy_id=policy.id if policy else None,
                created_at=cq.created_at.isoformat(),
            )
        )
    return items
