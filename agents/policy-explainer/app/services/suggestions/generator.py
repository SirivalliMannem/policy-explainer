"""Suggested follow-up question generator service."""

from __future__ import annotations

import re

from app.models.policy import CorePolicy
from app.services.retrieval.evidence_retriever import EvidenceItem

MAX_SUGGESTIONS = 3


# Two questions this alike (word overlap) read as the same question: "my car" vs "my vehicle".
SIMILARITY_THRESHOLD = 0.75


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _similar(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= SIMILARITY_THRESHOLD


class SuggestionGenerator:
    """Generates at most 3 follow-up questions that fit the question asked and the policy's own contents.

    Topic suggestions are only offered when the policy actually carries the coverage they ask about,
    and anything the employee just asked is never suggested back to them.
    """

    @classmethod
    def generate(
        cls,
        question: str,
        policy: CorePolicy,
        evidence: list[EvidenceItem],
    ) -> list[str]:
        """Produce up to 3 relevant suggested follow-up questions."""
        q_lower = question.lower()
        forms = {f.form_number: f for f in (policy.forms or [])}
        coverages = sorted(policy.coverages or [], key=lambda c: (c.sort_order, c.name))
        patterns = {c.pattern_code for c in coverages}

        has_backup = "HO 04 95" in forms or "HOWaterBackupCov" in patterns
        has_wind = "HO 03 12" in forms
        has_scheduled = "HO 04 61" in forms or "HOScheduledPropertyCov" in patterns
        has_rental = "PP 03 06" in forms or "PARentalCov" in patterns
        is_home = policy.line_of_business == "homeowners"

        topic: list[str] = []

        # Category 1: Water backup / drain / sump
        if any(w in q_lower for w in ["water", "backup", "back-up", "sewer", "sump", "flood"]):
            topic = (
                [
                    "What is the water backup limit on this policy?",
                    "What deductible applies to water backup and sump overflow?",
                    "Which endorsement form provides the water backup coverage?",
                ]
                if has_backup
                else [
                    "What does the base policy say about water damage?",
                    "Which endorsements are attached to this policy?",
                    "What is the deductible on this policy?",
                ]
            )

        # Category 2: Wind / hail / deductible
        elif any(w in q_lower for w in ["wind", "hail", "storm"]) and has_wind:
            topic = [
                "What percentage deductible applies to windstorm and hail?",
                "How does the percentage deductible calculate against Coverage A?",
                "What is the standard all-other-perils deductible?",
            ]

        # Category 3: General deductible inquiry
        elif "deductible" in q_lower:
            if is_home:
                topic = [
                    "What is my wind and hail deductible?" if has_wind else "What is the base deductible on Coverage A dwelling?",
                    "Does water backup have a separate endorsement deductible?" if has_backup else "What does the base policy say about water damage?",
                    "What is the base deductible on Coverage A dwelling?" if has_wind else "Which endorsements are attached to this policy?",
                ]
            else:
                topic = [
                    "What is my collision deductible?",
                    "What is my comprehensive (other than collision) deductible?",
                    "Does comprehensive cover windshield glass replacement?",
                ]

        # Category 4: Jewellery / scheduled property
        elif any(w in q_lower for w in ["jewelry", "jewellery", "fur", "silverware", "theft"]) and is_home:
            topic = [
                "What is the special limit of liability for theft of unscheduled jewelry?",
                "Is scheduled personal property subject to a deductible?" if has_scheduled else "Which endorsements are attached to this policy?",
                "Does scheduled jewelry coverage provide worldwide protection?" if has_scheduled else "What are the Coverage C personal property limits?",
            ]

        # Category 5: Auto collision / damage / rental
        elif any(w in q_lower for w in ["collision", "car", "auto", "vehicle", "crash", "rental"]) and not is_home:
            topic = [
                "Am I covered for a rental car while my vehicle is being repaired?",
                "What are the daily and total limits for transportation expenses?" if has_rental else "What are my collision and comprehensive deductibles?",
                "Does my personal auto policy cover me when driving for Uber or rideshare?",
            ]

        # Category 6: Claims
        elif any(w in q_lower for w in ["claim", "loss", "adjuster", "accident"]):
            topic = [
                "What is the status and assigned adjuster on my open claim?",
                "What is the reported loss cause and date?",
                "What vehicle exposures are currently open?" if not is_home else "What deductible would apply to this loss?",
            ]

        # Category 7: Renewal / comparison
        elif any(w in q_lower for w in ["renewal", "changed", "prior", "increase"]):
            topic = [
                "What changed in my coverages between expiring and renewal terms?",
                "Did my annual premium increase at renewal?",
                "Were any endorsement limits or deductibles adjusted at renewal?",
            ]

        return cls._finish(question, topic + cls._from_policy(question, coverages, forms, evidence))

    @staticmethod
    def _from_policy(question: str, coverages: list, forms: dict, evidence: list[EvidenceItem]) -> list[str]:
        """Questions about this policy's own coverages and endorsements, most relevant first."""
        q_lower = question.lower()
        suggestions: list[str] = []

        # Coverages surfaced by retrieval first, then the rest of the schedule.
        retrieved_ids = [e.source_id for e in evidence if e.source_type == "coverage"]
        ordered = sorted(coverages, key=lambda c: (c.id not in retrieved_ids, c.sort_order))
        for cov in ordered:
            if cov.name.lower() in q_lower:
                continue
            if cov.limit_text and cov.deductible_text:
                suggestions.append(f"What are the limit and deductible for {cov.name}?")
            elif cov.deductible_text:
                suggestions.append(f"How does the {cov.name} work?")
            else:
                suggestions.append(f"What is the limit for {cov.name}?")

        for form in forms.values():
            if form.kind == "endorsement" and form.form_number.lower() not in q_lower:
                suggestions.append(f"What does the {form.title} endorsement ({form.form_number}) provide?")
        return suggestions

    @staticmethod
    def _finish(question: str, candidates: list[str]) -> list[str]:
        """Drop near-repeats of the question just asked and of each other; keep the first three."""
        kept_words = [_words(question)]
        result: list[str] = []
        for suggestion in candidates:
            words = _words(suggestion)
            if any(_similar(words, other) for other in kept_words):
                continue
            kept_words.append(words)
            result.append(suggestion)
            if len(result) == MAX_SUGGESTIONS:
                break
        return result
