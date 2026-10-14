"""Use the policy term that was in force on the date of loss.

A policy number covers several terms (renewals), each with its own limits, deductibles, forms and
premium. When a question gives a date ("the basement flooded on 3 November 2025"), the answer must
come from the term in force that day, not today's term, and must say which term it used.

Dates are read from what the employee typed: ISO (2025-11-03), US numeric (11/3/2025, 11-3-25),
written (November 3, 2025 / 3 Nov 2025 / Nov. 3rd, 2025), "today" and "yesterday". A written date
without a year means its most recent occurrence. A term runs from its effective date up to, but not
including, its expiration date (the renewal starts that day).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.policy import CorePolicy

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MONTH = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
_DAY = r"(\d{1,2})(?:st|nd|rd|th)?"

ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
US_NUMERIC = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4}|\d{2})\b")
MONTH_DAY_YEAR = re.compile(rf"\b{_MONTH}\s+{_DAY}(?:,?\s+(\d{{4}}))?\b", re.IGNORECASE)
DAY_MONTH_YEAR = re.compile(rf"\b{_DAY}\s+(?:of\s+)?{_MONTH}(?:,?\s+(\d{{4}}))?\b", re.IGNORECASE)
RELATIVE = re.compile(r"\b(today|yesterday)\b", re.IGNORECASE)

# Words that make a date a date of loss rather than, say, a billing date.
LOSS_CUES = re.compile(
    r"\b(?:loss|lost|damage\w*|accident\w*|happen\w*|occur\w*|stolen|theft|broke\w*|burst|fire|storm\w*|hail\w*|"
    r"flood\w*|leak\w*|collision|crash\w*|incident|claim\w*|injur\w*|vandal\w*|hit|struck|fell|collapsed?)\b",
    re.IGNORECASE,
)
# Questions about when something is due are about billing dates, not a loss.
BILLING_DATE = re.compile(r"\b(?:due|bill\w*|payment|pay|paid|premium|renew\w*|expir\w*|effective)\b", re.IGNORECASE)


@dataclass
class LossDate:
    value: date
    text: str  # as typed
    year_assumed: bool = False
    is_loss: bool = True  # a loss cue was present ("flooded on ..."); otherwise just the date asked about


def _safe(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _most_recent(month: int, day: int, today: date) -> Optional[date]:
    candidate = _safe(today.year, month, day)
    if candidate and candidate > today:
        candidate = _safe(today.year - 1, month, day)
    return candidate


def extract_loss_date(question: str, today: Optional[date] = None) -> Optional[LossDate]:
    """The date a question asks about, when it gives one and is not a billing-date question."""
    text = question or ""
    today = today or date.today()
    is_loss = bool(LOSS_CUES.search(text))
    if not is_loss and BILLING_DATE.search(text):
        return None

    found: Optional[LossDate] = None
    if m := ISO.search(text):
        if d := _safe(int(m.group(1)), int(m.group(2)), int(m.group(3))):
            found = LossDate(d, m.group(0))
    if not found and (m := US_NUMERIC.search(text)):
        year = int(m.group(3))
        year += 2000 if year < 100 else 0
        if d := _safe(year, int(m.group(1)), int(m.group(2))):
            found = LossDate(d, m.group(0))
    if not found:
        for pattern, month_group, day_group in ((MONTH_DAY_YEAR, 1, 2), (DAY_MONTH_YEAR, 2, 1)):
            if m := pattern.search(text):
                month = MONTHS[m.group(month_group).lower().rstrip(".")]
                day = int(m.group(day_group))
                if m.group(3):
                    d = _safe(int(m.group(3)), month, day)
                    if d:
                        found = LossDate(d, m.group(0))
                else:
                    d = _most_recent(month, day, today)
                    if d:
                        found = LossDate(d, m.group(0), year_assumed=True)
                if found:
                    break
    if not found and (m := RELATIVE.search(text)) and is_loss:
        d = today if m.group(1).lower() == "today" else today - timedelta(days=1)
        found = LossDate(d, m.group(0))
    if found:
        found.is_loss = is_loss
    return found


def term_in_force(policy_number: str, on: date, db: Session) -> Optional[CorePolicy]:
    """The term of a policy number in force on a date: effective on or before it, expiring after it."""
    return (
        db.query(CorePolicy)
        .filter(CorePolicy.policy_number == policy_number, CorePolicy.effective_date <= on, CorePolicy.expiration_date > on)
        .order_by(CorePolicy.term_number.desc())
        .first()
    )


def terms_of(policy_number: str, db: Session) -> list[CorePolicy]:
    return db.query(CorePolicy).filter(CorePolicy.policy_number == policy_number).order_by(CorePolicy.term_number).all()


def _when(d: date) -> str:
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def describe_term(term: CorePolicy) -> str:
    return f"term {term.term_number} of {term.policy_number} ({_when(term.effective_date)} – {_when(term.expiration_date)})"


def term_selection(policy_number: str, loss: LossDate, db: Session) -> dict:
    """Which term answers a question about a date, as stored with the answer and shown to the employee."""
    label = "loss date" if loss.is_loss else "date in the question"
    assumed = f" (no year was given, so {loss.value.year} is assumed)" if loss.year_assumed else ""
    term = term_in_force(policy_number, loss.value, db)
    base = {
        "loss_date": loss.value.isoformat(),
        "date_text": loss.text,
        "is_loss": loss.is_loss,
        "year_assumed": loss.year_assumed,
        "policy_number": policy_number,
    }
    if term is None:
        periods = "; ".join(
            f"term {t.term_number}: {_when(t.effective_date)} – {_when(t.expiration_date)}" for t in terms_of(policy_number, db)
        )
        return {
            **base,
            "status": "no_term",
            "message": f"No term of {policy_number} was in force on the {label}, {_when(loss.value)}{assumed}. "
            f"Its terms on file: {periods}.",
        }
    return {
        **base,
        "status": "matched",
        "policy_id": term.id,
        "term_number": term.term_number,
        "effective_date": term.effective_date.isoformat(),
        "expiration_date": term.expiration_date.isoformat(),
        "term_status": term.status,
        "message": f"Using {describe_term(term)}, the term in force on the {label}, {_when(loss.value)}{assumed}.",
    }
