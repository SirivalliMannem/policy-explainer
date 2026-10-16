"""Stored analysis of flagged questions, for the Needs attention Resolve box.

When an answer is recorded and flagged, the AI service analyses it once, in the background: it
classifies why the question went unanswered and returns only alternative questions that it verified
against the normal retrieval. The result is stored in the ledger entry's attention_analysis column,
which is added data: the recorded answer itself is never changed. The dashboard only reads what is
stored; the model is called again only when a person asks for it ("Analyze now").
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.database import SessionLocal
from app.models.ledger import EvidenceLedger
from app.services.ai_client import ai_client

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    # "off" stops the automatic analysis on flagging (tests use it, so they never call the model).
    return os.getenv("ATTENTION_ANALYSIS_ON_FLAG", "on").lower() not in ("off", "false", "0", "no")


def run_analysis(entry: EvidenceLedger, db: Session) -> Optional[dict]:
    """Analyse one flagged entry now and store the result (a failure is stored as such)."""
    from app.services.attention import flag_reason  # imported here: attention imports the ledger service

    reason = flag_reason(entry)
    if reason is None:
        return None
    result = local_analysis(entry, reason)
    if result is None:
        result = ai_client.attention_analysis(entry.question, entry.policy_id, entry.retrieval or {}, reason)
    if result is None:
        result = {"status": "failed", "reason": "The AI service is not reachable right now."}
    entry.attention_analysis = result
    flag_modified(entry, "attention_analysis")
    db.commit()
    return result


def local_analysis(entry: EvidenceLedger, reason: str) -> Optional[dict]:
    """The analysis for cases decided without the model: an unverified customer (no suggestions, no
    other customers or policies) and a question with no verified policy (nothing to ground them in)."""
    verification = (entry.retrieval or {}).get("customer_verification")
    status = verification.get("status") if isinstance(verification, dict) else None
    if reason == "customer_not_found" or status in ("not_found", "customer_not_found"):
        return {
            "status": "ready", "type": "customer_not_found", "category": "customer_not_found",
            "reason": "The customer asked about was not found in the customer records, so no policy context exists to suggest questions from.",
            "candidates": [], "missing": None,
        }
    if not entry.policy_id:
        return {
            "status": "ready", "type": "policy_context_missing", "category": "policy_context_missing",
            "reason": "No single policy was identified for this question, so suggestions cannot be grounded in policy wording.",
            "candidates": [], "missing": None,
        }
    return None


def _analyse_in_background(entry_id: str) -> None:
    db = SessionLocal()
    try:
        entry = db.get(EvidenceLedger, entry_id)
        if entry is not None and entry.attention_analysis is None:
            run_analysis(entry, db)
    except Exception:  # background work must never break the request that recorded the answer
        logger.exception("Attention analysis failed for ledger entry %s", entry_id)
    finally:
        db.close()


def schedule_analysis(entry: EvidenceLedger) -> None:
    """Analyse a newly recorded entry in the background when it is flagged."""
    from app.services.attention import flag_reason

    if not _enabled() or flag_reason(entry) is None:
        return
    threading.Thread(target=_analyse_in_background, args=(entry.id,), daemon=True).start()
