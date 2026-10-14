"""Customer verification: the first step of answering a question.

Before any policy information is retrieved, the customer the question refers to must exist in the
customer records and be identified uniquely. The result is one of:

- verified   exactly one customer, by name, an identifier (email, phone, claim, account, VIN, ...),
             a policy number, or the customer already selected in the conversation
- ambiguous  more than one customer matches; the employee is asked which one
- not_found  a customer or identifier is named but is not in the records; the employee is asked
- not_named  the question names no customer and the conversation has none selected yet

The result is cached for the conversation and question so the answer, when it is given, records
how its customer was verified.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.models.policy import CoreAccount, CorePolicy
from app.schemas.policy_resolution import CustomerVerification, VerifiedCustomer
from app.services.policy_resolver import NON_NAME_WORDS, STATE_WORDS, ResolutionResult, find_accounts

# Two capitalised words in a row ("John Smith") or a capitalised possessive ("Smith's").
_FULL_NAME = re.compile(r"\b([A-Z][a-z]{1,})\s+([A-Z][a-z]{1,})\b")
_POSSESSIVE = re.compile(r"\b([A-Z][a-z]{2,})(?:'s|’s)\b")

_TTL_SECONDS = 600
_cache: dict[tuple[str, str], tuple[float, dict]] = {}
_lock = threading.Lock()


def _key(conversation_id: str, question: str) -> tuple[str, str]:
    return conversation_id, " ".join(question.lower().split())


def remember(conversation_id: Optional[str], question: str, verification: CustomerVerification) -> None:
    if not conversation_id:
        return
    with _lock:
        if len(_cache) > 500:
            for stale in sorted(_cache, key=lambda k: _cache[k][0])[:100]:
                _cache.pop(stale, None)
        _cache[_key(conversation_id, question)] = (time.monotonic(), verification.model_dump())


def recall(conversation_id: str, question: str) -> Optional[dict]:
    # Not removed on read: one question may be answered for several of a customer's policies.
    with _lock:
        hit = _cache.get(_key(conversation_id, question))
    if hit and time.monotonic() - hit[0] < _TTL_SECONDS:
        return hit[1]
    return None


def _customer(account: CoreAccount) -> VerifiedCustomer:
    return VerifiedCustomer(customer_id=account.id, name=account.name, account_number=account.account_number or None)


def _named_people(question: str, interpretation: Optional[dict]) -> list[str]:
    """People the question names: from the interpreter when it ran, else capitalised full names."""
    names = [n for n in (interpretation or {}).get("policyholders") or [] if isinstance(n, str) and n.strip()]
    if names:
        return names
    found = []
    for first, last in _FULL_NAME.findall(question):
        if not {first.lower(), last.lower()} & (NON_NAME_WORDS | STATE_WORDS):
            found.append(f"{first} {last}")
    for word in _POSSESSIVE.findall(question):
        if word.lower() not in NON_NAME_WORDS | STATE_WORDS and not any(word in n for n in found):
            found.append(word)
    return found


def verify_customer(
    result: ResolutionResult,
    question: str,
    interpretation: Optional[dict],
    active: Optional[CorePolicy],
    db: Session,
) -> CustomerVerification:
    """Verify the customer a question refers to, from the policy resolution and the customer records."""
    if result.status == "resolved" and result.policy and result.policy.account:
        return CustomerVerification(
            status="verified",
            matched_on=result.matched_on,
            reference=result.reference,
            customers=[_customer(result.policy.account)],
            message=f"{result.policy.account.name} is in the customer records, matched on "
            f"{(result.matched_on or 'reference').replace('_', ' ')}.",
        )

    if result.status == "ambiguous":
        accounts = {p.account_id: p.account for p in result.candidates if p.account}
        if len(accounts) == 1:
            account = next(iter(accounts.values()))
            return CustomerVerification(
                status="verified",
                matched_on=result.matched_on,
                reference=result.reference,
                customers=[_customer(account)],
                message=f"{account.name} is in the customer records and has more than one matching policy.",
            )
        # The customer already selected in this conversation is one of them: keep with that customer.
        if active and active.account_id in accounts:
            return CustomerVerification(
                status="verified",
                matched_on="conversation",
                reference=result.reference,
                customers=[_customer(accounts[active.account_id])],
                message=f"Several customers match; continuing with {accounts[active.account_id].name}, "
                "the customer already selected in this conversation.",
            )
        names = sorted(a.name for a in accounts.values())
        return CustomerVerification(
            status="ambiguous",
            matched_on=result.matched_on,
            reference=result.reference,
            customers=[_customer(a) for a in sorted(accounts.values(), key=lambda a: a.name)],
            message=f"{len(names)} customers in the records match: {', '.join(names[:-1])} and {names[-1]}.",
        )

    if result.status == "not_found":
        return CustomerVerification(
            status="not_found",
            matched_on=result.matched_on,
            reference=result.reference,
            message=result.message or f"No customer in the records matches {result.reference}.",
        )

    # no_reference: was a person named who is not in the records?
    unknown = [name for name in _named_people(question, interpretation) if not find_accounts(name, db)[0]]
    if unknown:
        return CustomerVerification(
            status="not_found",
            matched_on="customer_name",
            reference=unknown[0],
            message=f"No customer named {unknown[0]} is in the customer records.",
        )
    if active and active.account:
        return CustomerVerification(
            status="verified",
            matched_on="conversation",
            reference=active.account.name,
            customers=[_customer(active.account)],
            message=f"{active.account.name}, the customer already selected in this conversation.",
        )
    return CustomerVerification(status="not_named", message="The question does not name a customer yet.")


def verification_for_answer(conversation_id: str, question: str, policy: Optional[CorePolicy]) -> Optional[dict]:
    """How the customer of an answer was verified: the cached result, else the answered policy's customer."""
    cached = recall(conversation_id, question)
    if cached and cached.get("status") == "verified":
        return cached
    if policy is not None and policy.account is not None:
        return CustomerVerification(
            status="verified",
            matched_on="selected_policy",
            reference=policy.policy_number,
            customers=[_customer(policy.account)],
            message=f"{policy.account.name} is the customer on policy {policy.policy_number}.",
        ).model_dump()
    return cached
