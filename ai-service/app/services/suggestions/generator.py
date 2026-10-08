"""Suggested follow-up question generator service."""

from __future__ import annotations

from typing import Optional
from app.models.policy import CorePolicy
from app.services.retrieval.evidence_retriever import EvidenceItem


class SuggestionGenerator:
    """Generates at most 3 contextual follow-up questions based on evidence and inquiry."""

    @classmethod
    def generate(
        cls,
        question: str,
        policy: CorePolicy,
        evidence: list[EvidenceItem],
    ) -> list[str]:
        """Produce up to 3 relevant suggested follow-up questions."""
        q_lower = question.lower()
        suggestions: list[str] = []

        # Category 1: Water backup / drain / sump
        if any(w in q_lower for w in ["water", "backup", "back-up", "sewer", "sump"]):
            suggestions = [
                "What is the water backup limit on this policy?",
                "What deductible applies to water backup and sump overflow?",
                "Which endorsement form provides the water backup coverage?",
            ]

        # Category 2: Wind / hail / deductible
        elif any(w in q_lower for w in ["wind", "hail", "storm"]):
            suggestions = [
                "What percentage deductible applies to windstorm and hail?",
                "How does the percentage deductible calculate against Coverage A?",
                "What is the standard all-other-perils deductible?",
            ]

        # Category 3: General deductible inquiry
        elif "deductible" in q_lower:
            if policy.line_of_business == "homeowners":
                suggestions = [
                    "What is my wind and hail deductible?",
                    "Does water backup have a separate endorsement deductible?",
                    "What is the base deductible on Coverage A dwelling?",
                ]
            else:
                suggestions = [
                    "What is my collision deductible?",
                    "What is my comprehensive (other than collision) deductible?",
                    "Does comprehensive cover windshield glass replacement?",
                ]

        # Category 4: Jewellery / scheduled property
        elif any(w in q_lower for w in ["jewelry", "jewellery", "fur", "silverware", "theft"]):
            suggestions = [
                "What is the special limit of liability for theft of unscheduled jewelry?",
                "Is scheduled personal property subject to a deductible?",
                "Does scheduled jewelry coverage provide worldwide protection?",
            ]

        # Category 5: Auto collision / damage / rental
        elif any(w in q_lower for w in ["collision", "car", "auto", "vehicle", "crash", "rental"]):
            suggestions = [
                "Am I covered for a rental car while my vehicle is being repaired?",
                "What are the daily and total limits for transportation expenses?",
                "Does my personal auto policy cover me when driving for Uber or rideshare?",
            ]

        # Category 6: Claims
        elif any(w in q_lower for w in ["claim", "loss", "adjuster", "accident"]):
            suggestions = [
                "What is the status and assigned adjuster on my open claim?",
                "What is the reported loss cause and date?",
                "What vehicle exposures are currently open?",
            ]

        # Category 7: Renewal / comparison
        elif any(w in q_lower for w in ["renewal", "changed", "prior", "increase"]):
            suggestions = [
                "What changed in my coverages between expiring and renewal terms?",
                "Did my annual premium increase at renewal?",
                "Were any endorsement limits or deductibles adjusted at renewal?",
            ]

        # Fallback based on retrieved evidence items
        if not suggestions:
            for item in evidence:
                if item.source_type == "coverage" and len(suggestions) < 3:
                    suggestions.append(f"What limit and deductible apply to {item.title}?")
                elif item.source_type == "form" and item.form_number and len(suggestions) < 3:
                    suggestions.append(f"What provisions does form {item.form_number} govern?")

        # Default fallback if still empty
        if not suggestions:
            if policy.line_of_business == "homeowners":
                suggestions = [
                    "What are the Coverage A dwelling and Coverage C personal property limits?",
                    "What is the deductible on this policy?",
                    "Which endorsements are attached to this homeowners policy?",
                ]
            else:
                suggestions = [
                    "What are the liability limits on this auto policy?",
                    "What are my collision and comprehensive deductibles?",
                    "Does this policy have extended transportation expenses?",
                ]

        return suggestions[:3]
