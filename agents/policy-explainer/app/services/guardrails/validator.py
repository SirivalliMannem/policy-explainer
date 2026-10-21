"""Guardrail and citation validation service."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.llm.base import EVIDENCE_REF_PATTERN, referenced_evidence_indexes
from app.services.retrieval.evidence_retriever import EvidenceItem

POLICY_NUMBER_PATTERN = re.compile(r"\b(?:HO|PA)-\d{4}-\d{4}\b", re.IGNORECASE)

# Language that promises pricing outcomes. An explainer may describe how premium is shown on a
# policy, but must never commit the carrier to a price change.
PREMIUM_PROMISE_PATTERNS = [
    re.compile(r"\b(?:we|i)(?:'ll| will| can| could)\s+(?:lower|reduce|decrease|cut|waive|refund|discount)\b", re.I),
    re.compile(r"\b(?:your\s+)?premium\s+(?:will|would)\s+(?:go down|decrease|drop|be lower|be reduced)\b", re.I),
    re.compile(r"\bguarantee[sd]?\b", re.I),
]

# Language that decides the outcome of a specific loss. Explaining what wording says is allowed;
# approving or paying a particular claim is a coverage determination reserved for adjusters.
COVERAGE_DETERMINATION_PATTERNS = [
    re.compile(r"\byour\s+(?:claim|loss)\s+(?:is|will be|would be)\s+(?:approved|paid|covered|accepted)\b", re.I),
    re.compile(r"\bwe(?:'ll| will)\s+(?:approve|pay)\s+(?:your|this|the)\s+(?:claim|loss)\b", re.I),
    re.compile(r"\b(?:claim|loss)\s+(?:is|has been)\s+approved\b", re.I),
]

# Checks whose failure means the answer must be reviewed by a person before it is relied on.
BLOCKING_CHECKS = {"premium_promise", "coverage_determination", "cross_policy_leak"}


@dataclass
class GuardrailValidationResult:
    """Result of guardrail validation checks."""

    is_valid: bool
    status: str  # passed | flagged | failed
    validated_answer: str
    validated_citations: list[dict] = field(default_factory=list)
    rejection_reason: Optional[str] = None
    checks: list[dict] = field(default_factory=list)


def _check(name: str, status: str, detail: str) -> dict:
    return {"name": name, "status": status, "detail": detail}


class GuardrailValidator:
    """Validates generated answers and citations against retrieved evidence."""

    @classmethod
    def validate(
        cls,
        answer: str,
        citations: list[dict],
        evidence: list[EvidenceItem],
        policy_number: Optional[str] = None,
    ) -> GuardrailValidationResult:
        """Execute deterministic guardrail checks on generated answer."""
        if not answer or not answer.strip():
            return GuardrailValidationResult(
                is_valid=False,
                status="failed",
                validated_answer="The available policy information could not establish an answer.",
                validated_citations=[],
                rejection_reason="Empty answer produced",
                checks=[_check("answer_present", "failed", "The model produced an empty answer.")],
            )

        checks: list[dict] = [_check("answer_present", "passed", "A non-empty answer was produced.")]
        working_answer = answer.strip()

        # Check for ungrounded answer when evidence was empty
        if not evidence:
            refused = any(
                phrase in working_answer.lower()
                for phrase in ["not find sufficient", "does not establish", "no specific", "couldn't find"]
            )
            if not refused:
                checks.append(_check("evidence_grounded", "failed", "An answer was attempted without retrieved evidence."))
                return GuardrailValidationResult(
                    is_valid=False,
                    status="failed",
                    validated_answer="The available policy information does not contain evidence to answer this question.",
                    validated_citations=[],
                    rejection_reason="Attempted ungrounded answer without supporting evidence",
                    checks=checks,
                )
            checks.append(_check("evidence_grounded", "passed", "No evidence was retrieved and the answer declines to guess."))
        else:
            checks.append(_check("evidence_grounded", "passed", f"Answer generated over {len(evidence)} retrieved evidence items."))

        # Inline evidence references must point at retrieved evidence; anything else is removed.
        references = referenced_evidence_indexes(working_answer)
        invalid = [i for i in references if not 1 <= i <= len(evidence)]
        if invalid:
            working_answer = EVIDENCE_REF_PATTERN.sub(
                lambda m: "" if int(m.group(1)) in invalid else m.group(0), working_answer
            ).strip()
        valid_count = len(references) - len(invalid)
        if invalid:
            checks.append(_check(
                "inline_citations", "failed",
                f"Removed {len(invalid)} reference(s) to evidence that was not retrieved.",
            ))
        elif valid_count:
            checks.append(_check("inline_citations", "passed", f"{valid_count} inline reference(s) to retrieved evidence."))
        elif evidence:
            checks.append(_check(
                "inline_citations", "warning",
                "The answer has no inline references; sources are attached from retrieved evidence.",
            ))

        # Build allowed source keys from retrieved evidence
        valid_form_numbers = {
            item.form_number.strip().lower() for item in evidence if item.form_number
        }
        valid_headings = {
            item.heading.strip().lower() for item in evidence if item.heading
        }

        # Filter citations to only those present in retrieved evidence
        verified_citations = []
        for cit in citations:
            form_num = (cit.get("form_number") or "").strip().lower()
            heading = (cit.get("heading") or "").strip().lower()

            if form_num and form_num in valid_form_numbers:
                verified_citations.append(cit)
            elif heading and heading in valid_headings:
                verified_citations.append(cit)

        dropped = len(citations) - len(verified_citations)
        if evidence and citations and not verified_citations:
            checks.append(_check("citations_verified", "failed", "None of the citations match retrieved evidence."))
        elif dropped:
            checks.append(_check(
                "citations_verified", "warning",
                f"{len(verified_citations)} of {len(citations)} citations verified; {dropped} unverifiable citation(s) removed.",
            ))
        else:
            checks.append(_check(
                "citations_verified", "passed",
                f"{len(verified_citations)} of {len(citations)} citations verified against retrieved evidence.",
            ))

        mentioned = {n.upper() for n in POLICY_NUMBER_PATTERN.findall(working_answer)}
        foreign = sorted(n for n in mentioned if not policy_number or n != policy_number.upper())
        if policy_number is None and not mentioned:
            checks.append(_check("cross_policy_leak", "passed", "No policy numbers are mentioned in the answer."))
        elif foreign:
            checks.append(_check("cross_policy_leak", "failed", f"Answer mentions another policy: {', '.join(foreign)}."))
        else:
            checks.append(_check("cross_policy_leak", "passed", "Answer references only the active policy."))

        promise = next((p.search(working_answer) for p in PREMIUM_PROMISE_PATTERNS if p.search(working_answer)), None)
        checks.append(
            _check("premium_promise", "failed", f"Promissory pricing language: \"{promise.group(0)}\".")
            if promise
            else _check("premium_promise", "passed", "No premium or pricing commitments.")
        )

        determination = next(
            (p.search(working_answer) for p in COVERAGE_DETERMINATION_PATTERNS if p.search(working_answer)), None
        )
        checks.append(
            _check("coverage_determination", "failed", f"Claim outcome language: \"{determination.group(0)}\".")
            if determination
            else _check("coverage_determination", "passed", "Explains wording without deciding a specific loss.")
        )

        blocking_failures = [c["name"] for c in checks if c["status"] == "failed" and c["name"] in BLOCKING_CHECKS]
        if blocking_failures:
            return GuardrailValidationResult(
                is_valid=False,
                status="flagged",
                validated_answer=working_answer,
                validated_citations=verified_citations,
                rejection_reason=f"Requires review: {', '.join(blocking_failures)}",
                checks=checks,
            )

        return GuardrailValidationResult(
            is_valid=True,
            status="passed",
            validated_answer=working_answer,
            validated_citations=verified_citations,
            rejection_reason=None,
            checks=checks,
        )
