"""How the backend uses the AI service's understanding of a question.

The interpretation is computed once, when the frontend asks which policy a question is about, and
reused when the same question is submitted moments later — one language-model call per question,
not two. The cache is per-process and short-lived; a miss simply interprets again.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.models.conversation import ConversationQuestion
from app.services.ai_client import ai_client
from app.services.portfolio import CONTENT_TERMS, is_portfolio_question

_TTL_SECONDS = 600
_MAX_ENTRIES = 500
_lock = threading.Lock()
_cache: dict[tuple[str, str], tuple[float, dict]] = {}


def _key(conversation_id: Optional[str], question: str) -> tuple[str, str]:
    return (conversation_id or "", question.strip())


def remember(conversation_id: Optional[str], question: str, interpretation: Optional[dict]) -> None:
    if not interpretation:
        return
    with _lock:
        if len(_cache) >= _MAX_ENTRIES:
            for stale in sorted(_cache, key=lambda k: _cache[k][0])[: _MAX_ENTRIES // 5]:
                _cache.pop(stale, None)
        _cache[_key(conversation_id, question)] = (time.monotonic(), interpretation)


def recall(conversation_id: Optional[str], question: str) -> Optional[dict]:
    with _lock:
        hit = _cache.pop(_key(conversation_id, question), None)
    if hit and time.monotonic() - hit[0] < _TTL_SECONDS:
        return hit[1]
    return None


def previous_question(conversation_id: Optional[str], policy_id: Optional[str], db: Session) -> Optional[str]:
    """Most recent answered question in the conversation (on the same policy when one is set)."""
    if not conversation_id:
        return None
    query = db.query(ConversationQuestion).filter(
        ConversationQuestion.conversation_id == conversation_id,
        ConversationQuestion.status == "answered",
    )
    if policy_id:
        query = query.filter(ConversationQuestion.policy_id == policy_id)
    last = query.order_by(ConversationQuestion.created_at.desc()).first()
    return last.question if last else None


def interpret(conversation_id: Optional[str], question: str, previous: Optional[str]) -> Optional[dict]:
    """Cached interpretation for this question, or a fresh one from the AI service."""
    cached = recall(conversation_id, question)
    if cached is not None:
        return cached
    return ai_client.interpret(question, previous)


def understood_text(question: str, interpretation: Optional[dict]) -> str:
    """The canonical wording (corrected spelling, exact policyholder names, normalised policy numbers)."""
    normalized = (interpretation or {}).get("normalized")
    return normalized.strip() if isinstance(normalized, str) and normalized.strip() else question


def asks_about_portfolio(question: str, interpretation: Optional[dict]) -> bool:
    """Portfolio when the canonical wording reads as one, or the model judged it one and it is not about wording."""
    text = understood_text(question, interpretation)
    if is_portfolio_question(text) or is_portfolio_question(question):
        return True
    return (interpretation or {}).get("intent") == "portfolio" and not CONTENT_TERMS.search(text)
