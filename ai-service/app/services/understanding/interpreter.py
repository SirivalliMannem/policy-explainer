"""Understand a loosely written question before anything else runs.

Employees type the way people type: "hw many polcies does margret chen have", "whats the deductable",
"someone stole my wifes necklace". Every later step — policy resolution, intent, evidence retrieval —
works on exact words, so the question is first turned into a clean, canonical form.

Two layers:

  rules  always run, no network: shorthand expansion, spelling correction towards the policy
         library's own vocabulary, typo-tolerant policyholder names, policy-number normalisation and
         everyday-to-policy synonyms ("necklace" -> jewelry, "hotel" -> loss of use).
  llm    when a provider key is configured: one constrained call that rewrites the question and
         extracts structure as JSON. It only rewrites; it never answers. Any person it names is
         matched against real policyholders, and anything it returns that cannot be validated is
         dropped — the model cannot invent a customer or a policy.

Grounding is unchanged: answers still come only from retrieved evidence. The interpretation only
decides what to look for.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.llm.exceptions import LLMConfigurationError
from app.services.llm.llm_service import LLMService
from app.services.retrieval.evidence_retriever import STOP_WORDS
from app.services.understanding.vocabulary import (
    COMMON_WORDS,
    SHORTHAND,
    best_name_match,
    phrase_terms,
    policy_vocabulary,
    policyholder_names,
    word_terms,
)

logger = logging.getLogger(__name__)

TOKEN = re.compile(r"[A-Za-z][A-Za-z'\-]*|\d+|&|\S")
POLICY_NUMBER = re.compile(r"\b(ho|pa)\s*[-\s]?\s*(\d{4})(?:\s*[-\s]?\s*(\d{4}))?\b", re.IGNORECASE)

# Words that make a question depend on the one before it ("what endorsement provides *that*?").
FOLLOW_UP_REFERENCE = re.compile(
    r"\b(that|it|its|this coverage|this endorsement|those|they|them|same|above)\b", re.IGNORECASE
)

SPELLING_CUTOFF = 0.8
NAME_CUTOFF = 0.84  # high: a near-miss name must never become a different customer
MAX_SEARCH_TERMS = 10
INTERPRETER_TIMEOUT_SECONDS = 12.0

INTERPRET_SYSTEM_PROMPT = """You rewrite questions that insurance customer-service employees type into a policy explainer tool.
You NEVER answer the question. You return ONLY a JSON object with exactly these keys:

"corrected_question": the question rewritten as clear, correctly spelled English with the same meaning. Keep every
  person's name and policy number, fixing obvious misspellings of names. If the question refers back to the previous
  question ("that", "it", "this coverage"), make the subject explicit using the previous question.
"intent": "policy" for what a policy covers, says, limits, deductibles, forms, endorsements, claims or billing;
  "portfolio" for counting or listing policies, policyholders or customers; "definition" for what a term means;
  "other" otherwise.
"policyholder_name": the person named in the question, or null.
"policy_number": a policy number such as HO-1234-5678 or PA-1234-5678 if one is given, or null.
"line_of_business": "homeowners", "personal_auto", or null if not clear.
"search_terms": up to 8 short terms that homeowners or personal auto policy wording would use for this topic,
  for example "loss of use", "additional living expense", "theft", "jewelry", "special limits of liability",
  "accidental discharge or overflow of water", "water backup", "sewer", "windstorm or hail", "deductible",
  "transportation expenses", "public or livery conveyance", "uninsured motorists", "other than collision".

  Use only specific terms. Never use generic words such as "coverage", "damage", "perils", "exclusions", "limits"
  or "policy". Return an empty list when the topic is not something homeowners or auto policies address.

Do not add facts. Do not guess amounts. Output JSON only."""

# Words too general to steer retrieval: they match broad clauses on every policy.
GENERIC_SEARCH_WORDS = set(STOP_WORDS) | {
    "peril", "perils", "exclusion", "exclusions", "excluded", "limit", "limits", "property", "insurance",
    "policies", "coverages", "damage", "damages", "loss", "losses", "protection", "general", "standard",
    "terms", "conditions", "provisions", "unusual", "event", "events", "risk", "risks", "physical", "direct",
    "covered", "claim", "claims", "benefit", "benefits", "amount", "amounts", "applicable",
}


@dataclass
class Interpretation:
    original: str
    corrected: str
    normalized: str
    method: str  # llm | rules
    intent: Optional[str] = None
    policyholders: list[str] = field(default_factory=list)
    policy_numbers: list[str] = field(default_factory=list)
    line_of_business: Optional[str] = None
    search_terms: list[str] = field(default_factory=list)
    corrections: list[dict] = field(default_factory=list)
    fallback_reason: Optional[str] = None
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def search_text(self) -> str:
        """Everything retrieval should match against: original wording, corrected wording, policy terms."""
        parts = [self.original]
        if _comparable(self.corrected) != _comparable(self.original):
            parts.append(self.corrected)
        parts.extend(self.search_terms)
        return " ".join(parts)


def _comparable(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _normalize_policy_numbers(text: str) -> tuple[str, list[str]]:
    found: list[str] = []

    def repl(m: re.Match) -> str:
        number = f"{m.group(1).upper()}-{m.group(2)}" + (f"-{m.group(3)}" if m.group(3) else "")
        found.append(number)
        return number

    return POLICY_NUMBER.sub(repl, text), found


def _join_tokens(tokens: list[str]) -> str:
    text = ""
    for tok in tokens:
        if not text or re.fullmatch(r"[.,!?;:)\]]", tok) or text.endswith(("(", "[")):
            text += tok
        else:
            text += " " + tok
    return text


class QueryInterpreter:
    """Turns a raw question into a corrected, canonical, search-ready form."""

    @classmethod
    def interpret(
        cls,
        question: str,
        db: Session,
        previous_question: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> Interpretation:
        started = time.perf_counter()
        mode = (mode or settings.QUERY_INTERPRETER or "auto").lower()
        result = cls._rules(question, db)

        if mode == "auto":
            # The previous question is context only for questions that refer back to it. Given to
            # every follow-up, the model narrows general questions ("what is the deductible?") to
            # the previous topic.
            context = previous_question if previous_question and FOLLOW_UP_REFERENCE.search(question) else None
            try:
                llm = cls._llm(question, context, db)
            except Exception as exc:  # provider errors carry only status codes / class names
                result.fallback_reason = str(exc)
                logger.info("Question interpretation fell back to rules: %s", exc)
            else:
                result = cls._merge(result, llm)

        result.latency_ms = int(round((time.perf_counter() - started) * 1000))
        return result

    # ── Layer 1: rules (no network) ─────────────────────────────────────────

    @classmethod
    def _rules(cls, question: str, db: Session) -> Interpretation:
        original = (question or "").strip()
        vocabulary = policy_vocabulary(db)
        vocab_list = sorted(vocabulary)
        names = policyholder_names(db)
        name_parts = {part.lower() for n in names for part in n.split()}

        tokens = TOKEN.findall(original)
        corrected_tokens: list[str] = []
        corrections: list[dict] = []
        for tok in tokens:
            low = tok.lower()
            bare = low[:-2] if low.endswith("'s") else low
            if low in SHORTHAND:
                corrected_tokens.append(SHORTHAND[low])
                continue
            # Plural typed with -ys ("policys") when the vocabulary has -ies ("policies").
            if bare.endswith("ys") and bare not in vocabulary and bare[:-2] + "ies" in vocabulary:
                corrections.append({"from": tok, "to": bare[:-2] + "ies"})
                corrected_tokens.append(bare[:-2] + "ies")
                continue
            if (
                not re.fullmatch(r"[a-z][a-z\-]*", bare)
                or len(bare) < 4
                or bare in vocabulary
                or bare in COMMON_WORDS
                or bare in STOP_WORDS
                or bare in name_parts
                or bare.rstrip("s") in vocabulary
                or bare.rstrip("s") in COMMON_WORDS
            ):
                corrected_tokens.append(tok)
                continue
            match = difflib.get_close_matches(bare, vocab_list, n=1, cutoff=SPELLING_CUTOFF)
            if match and not _looks_like_name(bare, names) and not _same_word_other_form(bare, match[0]):
                corrections.append({"from": tok, "to": match[0]})
                corrected_tokens.append(match[0])
            else:
                corrected_tokens.append(tok)

        corrected = _join_tokens(corrected_tokens)
        corrected, numbers = _normalize_policy_numbers(corrected)
        normalized, holders = cls._canonical_names(corrected, names, vocabulary)

        words = re.findall(r"[a-z][a-z\-]*", normalized.lower())
        terms = phrase_terms(normalized) + word_terms(words)
        return Interpretation(
            original=original,
            corrected=corrected,
            normalized=normalized,
            method="rules",
            policyholders=holders,
            policy_numbers=numbers,
            search_terms=_dedupe(terms)[:MAX_SEARCH_TERMS],
            corrections=corrections,
        )

    @staticmethod
    def _canonical_names(text: str, names: list[str], vocabulary: set[str]) -> tuple[str, list[str]]:
        """Replace near-miss policyholder names with the exact name on file.

        Ordinary words are never turned into names: a word already in the policy vocabulary or in
        everyday English only counts when it is exactly a name on file.
        """
        if not names:
            return text, []
        exact_parts = {part.lower() for n in names for part in n.split()}

        def ordinary(word: str) -> bool:
            return word not in exact_parts and (
                word in vocabulary or word in COMMON_WORDS or word in STOP_WORDS or word.rstrip("s") in COMMON_WORDS
            )
        tokens = re.findall(r"\S+", text)
        out: list[str] = []
        holders: list[str] = []
        firsts = {n.split()[0].lower(): n for n in names}
        lasts: dict[str, list[str]] = {}
        for n in names:
            lasts.setdefault(n.split()[-1].lower(), []).append(n)

        def clean(tok: str) -> tuple[str, str]:
            m = re.match(r"^(.*?)('s|’s|s'|[.,!?;:]+)?$", tok)
            core, tail = m.group(1), m.group(2) or ""
            return core, tail

        i = 0
        while i < len(tokens):
            core, tail = clean(tokens[i])
            # Full name across two words ("margret chen", "Margaret Chens").
            if i + 1 < len(tokens):
                core2, tail2 = clean(tokens[i + 1])
                pair = f"{core} {core2}"
                if re.fullmatch(r"[A-Za-z]+ [A-Za-z]+", pair):
                    full = best_name_match(pair, names, NAME_CUTOFF)
                    if full:
                        # Keep a possessive the writer typed without an apostrophe ("chens house").
                        last = full.split()[-1].lower()
                        if not tail2 and core2.lower().endswith("s") and core2.lower()[:-1] == last:
                            tail2 = "'s"
                        out.append(full + tail2)
                        holders.append(full)
                        i += 2
                        continue
            low = core.lower()
            if re.fullmatch(r"[a-z]{3,}", low) and not ordinary(low):
                surname = difflib.get_close_matches(low, list(lasts), n=1, cutoff=NAME_CUTOFF) if len(low) >= 4 or low in lasts else []
                if surname and (low == surname[0] or len(low) >= 4):
                    out.append(surname[0].capitalize() + tail)
                    holders.extend(lasts[surname[0]])
                    i += 1
                    continue
                first = difflib.get_close_matches(low, list(firsts), n=1, cutoff=NAME_CUTOFF) if len(low) >= 4 else []
                if first:
                    out.append(first[0].capitalize() + tail)
                    holders.append(firsts[first[0]])
                    i += 1
                    continue
            out.append(tokens[i])
            i += 1
        return " ".join(out), _dedupe(holders)

    # ── Layer 2: language model (constrained rewrite) ───────────────────────

    @classmethod
    def _llm(cls, question: str, previous_question: Optional[str], db: Session) -> Interpretation:
        provider = LLMService.get_provider()
        if not provider.is_configured:
            raise LLMConfigurationError(f"No API key configured for provider '{provider.name}'")

        user = (f"Previous question: {previous_question.strip()}\n" if previous_question else "") + f"Question: {question.strip()}"
        raw = provider.complete(
            INTERPRET_SYSTEM_PROMPT, user, max_tokens=700, json_mode=True,
            timeout_seconds=INTERPRETER_TIMEOUT_SECONDS,
        )
        data = _parse_json(raw)

        corrected = _text(data.get("corrected_question"), 400) or question.strip()
        corrected, numbers = _normalize_policy_numbers(corrected)
        names = policyholder_names(db)
        normalized, holders = cls._canonical_names(corrected, names, policy_vocabulary(db))

        stated = _text(data.get("policyholder_name"), 120)
        if stated:
            full = best_name_match(stated, names, NAME_CUTOFF)
            if full and full not in holders:
                holders.append(full)

        number = _text(data.get("policy_number"), 20)
        if number:
            _, extra = _normalize_policy_numbers(number)
            numbers.extend(n for n in extra if n not in numbers)

        intent = data.get("intent") if data.get("intent") in ("policy", "portfolio", "definition", "other") else None
        line = data.get("line_of_business") if data.get("line_of_business") in ("homeowners", "personal_auto") else None
        raw_terms = [t for t in (_text(x, 60) for x in (data.get("search_terms") or [])[:8] if isinstance(x, str)) if t]
        terms = _policy_terms(raw_terms, policy_vocabulary(db))

        return Interpretation(
            original=question.strip(),
            corrected=corrected,
            normalized=normalized,
            method="llm",
            intent=intent,
            policyholders=holders,
            policy_numbers=numbers,
            line_of_business=line,
            search_terms=terms,
        )

    @staticmethod
    def _merge(rules: Interpretation, llm: Interpretation) -> Interpretation:
        """The model's rewrite leads; the rules layer's validated names, numbers and terms are kept."""
        return Interpretation(
            original=rules.original,
            corrected=llm.corrected,
            normalized=llm.normalized,
            method="llm",
            intent=llm.intent,
            policyholders=_dedupe(llm.policyholders + rules.policyholders),
            policy_numbers=_dedupe(llm.policy_numbers + rules.policy_numbers),
            line_of_business=llm.line_of_business,
            search_terms=_dedupe(llm.search_terms + rules.search_terms)[:MAX_SEARCH_TERMS],
            corrections=rules.corrections,
        )


WORD_ENDINGS = {"", "s", "es", "e", "d", "ed", "r", "er", "ers", "ing", "al", "ly", "ion", "ions"}


def _same_word_other_form(word: str, candidate: str) -> bool:
    """True for "drives"/"driver" or "renew"/"renewal": a different form of a correctly spelled word."""
    stem = 0
    while stem < min(len(word), len(candidate)) and word[stem] == candidate[stem]:
        stem += 1
    return stem >= 4 and word[stem:] in WORD_ENDINGS and candidate[stem:] in WORD_ENDINGS


def _policy_terms(terms: list[str], vocabulary: set[str]) -> list[str]:
    """Keep model search terms that use the policy library's own words and say something specific.

    A term the forms never use ("UFO") cannot find real evidence, and a generic one ("coverage",
    "exclusions") finds the same broad clauses for every question — both would let an off-topic
    question look answerable.
    """
    kept = []
    for term in terms:
        words = re.findall(r"[a-z]+", term.lower())
        if not words or not all(w in vocabulary or w in STOP_WORDS for w in words):
            continue
        if all(w in GENERIC_SEARCH_WORDS for w in words):
            continue
        kept.append(term)
    return kept


def _looks_like_name(word: str, names: list[str]) -> bool:
    parts = [p.lower() for n in names for p in n.split()]
    return bool(difflib.get_close_matches(word, parts, n=1, cutoff=NAME_CUTOFF))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _text(value, limit: int) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:limit] if value else None


def _parse_json(raw: str) -> dict:
    """Parse the model's JSON, tolerating code fences or text around the object."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("Interpreter returned no JSON object")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Interpreter returned JSON that is not an object")
    return data
