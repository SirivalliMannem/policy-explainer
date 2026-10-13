"""Find the policy a question refers to by something other than a policy number or a name.

Employees often start from what the customer gives them: a claim number, an account number, an
email, a phone number, a vehicle (VIN, plate, or make and model) or an address. Each finder returns
the policies that identifier points to, with what was matched and the text that matched it. They
are exact lookups against policy records; nothing is guessed.

Strong identifiers (claim, account number, email, phone, VIN, plate) belong to one customer or one
policy and decide on their own. Weak ones (address, make/model) can be shared, so the resolver
checks them against any name in the question before trusting them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from app.models.policy import CoreAccount, CoreClaim, CorePolicy


@dataclass
class IdentifierMatch:
    policies: list[CorePolicy]
    matched_on: str  # claim_number | account_number | email | phone | vin | plate | address | vehicle
    reference: str
    # A claim belongs to one policy term: that term is the answer, not the customer's current one.
    exact_term: bool = False


CLAIM_NUMBER = re.compile(r"\bCLM[-\s]?(\d{4})[-\s]?(\d{3,6})\b", re.IGNORECASE)
ACCOUNT_NUMBER = re.compile(r"\bACCT[-\s]?(\d{4,8})\b", re.IGNORECASE)
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# (512) 555-0142, 512-555-0142, 512.555.0142, +1 512 555 0142, 5125550142; or the local part 555-0142.
PHONE = re.compile(r"(?<![\w-])(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?![\w-])")
LOCAL_PHONE = re.compile(r"(?<![\w-])\d{3}[\s.-]\d{4}(?![\w-])")
VIN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b", re.IGNORECASE)
# State prefix and plate, as stored ("TX-KLM4418"), typed with a space, or the plate alone.
PLATE = re.compile(r"\b(?:[A-Z]{2}[-\s])?[A-Z0-9]{2,4}[-\s]?\d{2,5}[A-Z0-9]{0,2}\b", re.IGNORECASE)
# A house number followed by a street word: "1408 Wilshire", "4 Alderbrook Court".
STREET = re.compile(r"\b(\d{1,6})\s+([A-Za-z][A-Za-z.'-]{2,})\b")

# Words after a number that are amounts or counts, never a street.
NOT_STREETS = {
    "policies", "policy", "claims", "claim", "forms", "form", "days", "day", "months", "month", "years", "year",
    "dollars", "percent", "cars", "vehicles", "vehicle", "drivers", "people", "times", "questions", "deductible",
    "deductibles", "limit", "limits", "coverage", "coverages", "and", "or", "of", "to", "in", "on", "at", "for",
}


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _policies_of(db: Session, account_ids: list[str]) -> list[CorePolicy]:
    if not account_ids:
        return []
    return db.query(CorePolicy).filter(CorePolicy.account_id.in_(account_ids)).all()


def by_claim_number(text: str, db: Session) -> Optional[IdentifierMatch]:
    match = CLAIM_NUMBER.search(text)
    if not match:
        return None
    year, serial = match.group(1), match.group(2)
    claims = db.query(CoreClaim).filter(func.upper(CoreClaim.claim_number).like(f"CLM-{year}-%{serial}")).all()
    claims = [c for c in claims if c.claim_number.split("-")[-1].lstrip("0") == serial.lstrip("0")]
    policies = [p for p in (db.get(CorePolicy, c.policy_id) for c in claims) if p is not None]
    return IdentifierMatch(policies, "claim_number", match.group(0), exact_term=True)


def by_account_number(text: str, db: Session) -> Optional[IdentifierMatch]:
    match = ACCOUNT_NUMBER.search(text)
    if not match:
        return None
    accounts = db.query(CoreAccount).filter(func.upper(CoreAccount.account_number) == f"ACCT-{match.group(1)}").all()
    return IdentifierMatch(_policies_of(db, [a.id for a in accounts]), "account_number", match.group(0))


def by_email(text: str, db: Session) -> Optional[IdentifierMatch]:
    match = EMAIL.search(text)
    if not match:
        return None
    accounts = db.query(CoreAccount).filter(func.lower(CoreAccount.email) == match.group(0).lower()).all()
    return IdentifierMatch(_policies_of(db, [a.id for a in accounts]), "email", match.group(0))


def by_phone(text: str, db: Session) -> Optional[IdentifierMatch]:
    match = PHONE.search(text)
    local = None if match else LOCAL_PHONE.search(text)
    if not match and not local:
        return None
    typed = (match or local).group(0)
    digits = _digits(typed)
    # Compare the last ten digits (or the seven of a local number) of every stored phone number.
    wanted = digits[-10:] if match else digits
    accounts = [a for a in db.query(CoreAccount).filter(CoreAccount.phone != "").all() if _digits(a.phone).endswith(wanted)]
    return IdentifierMatch(_policies_of(db, [a.id for a in accounts]), "phone", typed)


def _vehicle_policies(db: Session, needles: list[str]) -> list[CorePolicy]:
    """Auto policies whose stored vehicles mention any of the needles (narrowed in Python after)."""
    if not needles:
        return []
    text = cast(CorePolicy.vehicles, String)
    return (
        db.query(CorePolicy)
        .filter(CorePolicy.line_of_business == "personal_auto", or_(*[text.ilike(f"%{n}%") for n in needles]))
        .all()
    )


def by_vin_or_plate(text: str, db: Session) -> Optional[IdentifierMatch]:
    vins = [m.group(0).upper() for m in VIN.finditer(text) if re.search(r"\d", m.group(0)) and re.search(r"[A-Za-z]", m.group(0))]
    if vins:
        policies = [p for p in _vehicle_policies(db, vins) if any(v.get("vin", "").upper() in vins for v in p.vehicles or [])]
        return IdentifierMatch(policies, "vin", vins[0])

    for m in PLATE.finditer(text):
        typed = m.group(0)
        key = _compact(typed)
        if not re.search(r"\d", key) or not re.search(r"[a-z]", key) or len(key) < 5:
            continue
        policies = []
        for policy in _vehicle_policies(db, [key[-4:]]):
            for v in policy.vehicles or []:
                plate = _compact(v.get("plate", ""))
                # "TX-KLM4418" matches "TX KLM4418", "TX-KLM4418" and the plate alone "KLM4418".
                if plate and (plate == key or plate[2:] == key):
                    policies.append(policy)
                    break
        if policies:
            return IdentifierMatch(policies, "plate", typed)
    return None


def by_address(text: str, db: Session) -> Optional[IdentifierMatch]:
    for m in STREET.finditer(text):
        number, word = m.group(1), m.group(2)
        if word.lower() in NOT_STREETS:
            continue
        prefix = f"{number} {word}%"
        located = db.query(CorePolicy).filter(CorePolicy.insured_location.ilike(prefix)).all()
        accounts = db.query(CoreAccount).filter(CoreAccount.address_line.ilike(prefix)).all()
        policies = {p.id: p for p in located + _policies_of(db, [a.id for a in accounts])}
        if policies:
            reference = (located[0].insured_location if located else accounts[0].address_line).split(",")[0]
            return IdentifierMatch(list(policies.values()), "address", reference)
    return None


def _words(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split()


def by_vehicle(text: str, db: Session) -> Optional[IdentifierMatch]:
    """A vehicle by model ("RAV4", "RX 350", "F-150"), else by make ("Toyota"), narrowed by year."""
    words = _words(text)
    if not words:
        return None
    # Single words and adjacent pairs joined, so "RX 350" and "F 150" read as "rx350" and "f150".
    keys = set(words) | {a + b for a, b in zip(words, words[1:])}
    needles = [w for w in words if len(w) >= 3 and not w.isdigit()] + [f"{a} {b}" for a, b in zip(words, words[1:])]
    candidates = _vehicle_policies(db, needles[:40])
    years = {w for w in words if re.fullmatch(r"(19|20)\d{2}", w)}

    def matches(field: str) -> list[tuple[CorePolicy, dict]]:
        found = []
        for policy in candidates:
            for v in policy.vehicles or []:
                if _compact(str(v.get(field, ""))) in keys and (not years or str(v.get("year")) in years):
                    found.append((policy, v))
        return found

    found = matches("model") or matches("make")
    if not found:
        return None
    policies = {p.id: p for p, _ in found}
    v = found[0][1]
    reference = " ".join(str(part) for part in (v.get("year"), v.get("make"), v.get("model")) if part)
    return IdentifierMatch(list(policies.values()), "vehicle", reference)


# Strong identifiers, tried in this order; each belongs to one policy or one customer.
STRONG_FINDERS: list[Callable[[str, Session], Optional[IdentifierMatch]]] = [
    by_claim_number,
    by_account_number,
    by_email,
    by_phone,
    by_vin_or_plate,
]
# Weak identifiers: shared by households and fleets, so checked against any name in the question.
WEAK_FINDERS: list[Callable[[str, Session], Optional[IdentifierMatch]]] = [by_address, by_vehicle]
