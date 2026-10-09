"""Vocabulary, shorthand and synonyms used to understand loosely written questions.

The vocabulary is built from the carrier's own form library (clause headings and keywords, coverage
names, form titles), so spelling is corrected towards words the policies actually use.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.models.policy import Clause, CoreAccount, CoreCoverage, CoreForm

WORD = re.compile(r"[a-z]+")

# Words that are never "corrected": everyday English that is valid but absent from policy wording.
COMMON_WORDS = {
    "about", "above", "after", "again", "against", "also", "always", "another", "anything", "around",
    "asked", "away", "back", "because", "been", "before", "being", "below", "best", "better", "between",
    "both", "bring", "call", "came", "cannot", "case", "change", "check", "come", "could", "currently",
    "days", "does", "doing", "done", "down", "during", "each", "else", "enough", "even", "ever", "every",
    "find", "fine", "first", "from", "full", "gave", "gets", "getting", "give", "given", "goes", "going",
    "gone", "good", "great", "happen", "happened", "happens", "have", "having", "hear", "help", "here",
    "home", "house", "into", "just", "keep", "kind", "know", "last", "least", "left", "less", "like",
    "little", "live", "long", "look", "lost", "made", "make", "many", "maybe", "mean", "means", "might",
    "mine", "more", "most", "much", "must", "name", "need", "needs", "never", "next", "night", "nothing",
    "once", "only", "other", "over", "part", "past", "people", "place", "please", "pretty", "quite",
    "rather", "really", "right", "said", "same", "says", "see", "seem", "should", "show", "since", "some",
    "something", "still", "such", "sure", "take", "tell", "than", "thank", "thanks", "that", "their",
    "them", "then", "there", "these", "they", "thing", "things", "think", "this", "those", "though",
    "through", "time", "today", "told", "took", "total", "tried", "true", "under", "until", "upon",
    "used", "very", "want", "wants", "week", "well", "went", "were", "what", "when", "where", "which",
    "while", "will", "with", "within", "without", "work", "would", "year", "years", "your", "yours",
    "yesterday", "tomorrow", "kitchen", "bedroom", "garage", "wife", "husband", "kids", "child",
    "someone", "somebody", "anyone", "everyone", "stay", "staying", "fixed", "fix", "fixing", "broke",
    "broken", "stole", "stolen", "bought", "sold", "pay", "paid", "pays", "covered", "happening",
}

# Chat shorthand and frequent informal spellings, expanded before correction.
SHORTHAND = {
    "r": "are", "u": "you", "ur": "your", "y": "why", "hw": "how", "wat": "what", "wht": "what",
    "whats": "what is", "wats": "what is", "pls": "please", "plz": "please", "thx": "thanks",
    "dont": "do not", "doesnt": "does not", "isnt": "is not", "cant": "cannot", "wont": "will not",
    "im": "I am", "ive": "I have", "abt": "about", "b4": "before", "w": "with", "wo": "without",
    "&": "and", "n": "and", "gonna": "going to", "wanna": "want to", "gimme": "give me",
    "info": "information", "pol": "policy", "pols": "policies", "cust": "customer", "custs": "customers",
}

# Everyday words mapped to the terms policy wording uses. Values are added as search terms.
SYNONYMS: dict[str, list[str]] = {
    "necklace": ["jewelry", "theft"], "ring": ["jewelry"], "rings": ["jewelry"], "bracelet": ["jewelry"],
    "earrings": ["jewelry"], "watch": ["watches", "jewelry"], "jewellery": ["jewelry"], "jewels": ["jewelry"],
    "stole": ["theft"], "stolen": ["theft"], "steal": ["theft"], "robbed": ["theft"], "robbery": ["theft"],
    "burglary": ["theft"], "burgled": ["theft"], "break-in": ["theft"],
    "hotel": ["loss of use", "additional living expense"], "motel": ["loss of use", "additional living expense"],
    "airbnb": ["loss of use", "additional living expense"], "relocate": ["loss of use"],
    "pipe": ["accidental discharge or overflow of water"], "pipes": ["accidental discharge or overflow of water"],
    "burst": ["accidental discharge or overflow of water"], "leak": ["water damage", "accidental discharge"],
    "leaking": ["water damage", "accidental discharge"], "leaked": ["water damage", "accidental discharge"],
    "flooded": ["flood", "water damage"], "flooding": ["flood", "water damage"],
    "drain": ["sewer", "water backup"], "drains": ["sewer", "water backup"], "toilet": ["sewer", "water backup"],
    "sewage": ["sewer", "water backup"], "basement": ["water backup", "sump"],
    "tree": ["windstorm", "falling objects"], "storm": ["windstorm", "hail"], "hurricane": ["windstorm"],
    "tornado": ["windstorm"], "roof": ["windstorm", "hail", "dwelling"],
    "fire": ["fire"], "smoke": ["smoke", "fire"],
    "windshield": ["glass", "other than collision"], "windscreen": ["glass", "other than collision"],
    "deer": ["other than collision", "animal"], "crash": ["collision"], "crashed": ["collision"],
    "accident": ["collision"], "fender": ["collision"], "dent": ["collision"],
    "rental": ["transportation expenses"], "loaner": ["transportation expenses"],
    "uber": ["public or livery conveyance"], "lyft": ["public or livery conveyance"],
    "rideshare": ["public or livery conveyance"], "delivery": ["public or livery conveyance"],
    "uninsured": ["uninsured motorists"], "hit-and-run": ["uninsured motorists"],
    "bill": ["billing"], "bills": ["billing"], "payment": ["billing"], "owe": ["billing", "past due"],
    "overdue": ["past due", "billing"], "premium": ["premium", "billing"],
    "renew": ["renewal"], "renewed": ["renewal"], "cancel": ["cancellation"],
    "excess": ["deductible"], "out-of-pocket": ["deductible"],
}

# Multi-word everyday phrases mapped to policy terms.
PHRASE_SYNONYMS: dict[str, list[str]] = {
    "hit and run": ["uninsured motorists"],
    "no insurance": ["uninsured motorists"],
    "stay somewhere": ["loss of use", "additional living expense"],
    "live somewhere": ["loss of use", "additional living expense"],
    "can't live": ["loss of use"],
    "cannot live": ["loss of use"],
    "while they fix": ["loss of use"],
    "while it is fixed": ["loss of use"],
    "while my car is": ["transportation expenses"],
    "car is being repaired": ["transportation expenses"],
    "backed up": ["water backup", "sewer"],
    "sump pump": ["sump", "water backup"],
    "out of pocket": ["deductible"],
}

# Domain words every question may use even if no clause happens to contain them.
DOMAIN_WORDS = {
    "deductible", "deductibles", "coverage", "coverages", "covered", "cover", "covers", "policy", "policies",
    "policyholder", "policyholders", "customer", "customers", "insured", "insureds", "endorsement",
    "endorsements", "premium", "premiums", "claim", "claims", "billing", "payment", "limit", "limits",
    "exclusion", "exclusions", "dwelling", "liability", "collision", "comprehensive", "windstorm", "hail",
    "sewer", "backup", "sump", "jewelry", "theft", "rental", "transportation", "uninsured", "motorist",
    "motorists", "household", "households", "expired", "homeowners", "homeowner", "auto", "vehicle",
    "vehicles", "renewal", "flood", "water", "damage", "insurance", "account", "accounts", "form", "forms",
    "definition", "occurrence", "business", "property", "personal", "adjuster", "status", "open",
}

_CACHE_SECONDS = 300
_lock = threading.Lock()
_cache: dict[str, tuple[float, object]] = {}


def _cached(key: str, build):
    with _lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < _CACHE_SECONDS:
            return hit[1]
    value = build()
    with _lock:
        _cache[key] = (time.monotonic(), value)
    return value


def policy_vocabulary(db: Session) -> set[str]:
    """Words used by the form library and schedules, plus core domain words."""

    def build() -> set[str]:
        words: set[str] = set(DOMAIN_WORDS)
        for heading, keywords, section in db.query(Clause.heading, Clause.keywords, Clause.section).all():
            words |= set(WORD.findall((heading or "").lower()))
            words |= set(WORD.findall((section or "").lower()))
            for k in keywords or []:
                words |= set(WORD.findall(k.lower()))
        for (name,) in db.query(CoreCoverage.name).all():
            words |= set(WORD.findall((name or "").lower()))
        for (title,) in db.query(CoreForm.title).all():
            words |= set(WORD.findall((title or "").lower()))
        for terms in SYNONYMS.values():
            for term in terms:
                words |= set(WORD.findall(term))
        return {w for w in words if len(w) >= 3}

    return _cached("vocabulary", build)


def policyholder_names(db: Session) -> list[str]:
    """Full names of every policyholder on file."""
    return _cached("names", lambda: sorted({n for (n,) in db.query(CoreAccount.name).all() if n}))


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def phrase_terms(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for phrase, terms in PHRASE_SYNONYMS.items():
        if phrase in lowered:
            found.extend(terms)
    return found


def word_terms(words: list[str]) -> list[str]:
    found: list[str] = []
    for w in words:
        found.extend(SYNONYMS.get(w.lower(), []))
    return found


def best_name_match(candidate: str, names: list[str], cutoff: float) -> Optional[str]:
    """Closest full name to a written name, if close enough."""
    import difflib

    lowered = {n.lower(): n for n in names}
    match = difflib.get_close_matches(candidate.lower(), list(lowered), n=1, cutoff=cutoff)
    return lowered[match[0]] if match else None
