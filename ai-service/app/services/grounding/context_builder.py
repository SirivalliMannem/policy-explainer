"""Grounding context builder for LLM prompting."""

from __future__ import annotations

from app.models.policy import CoreAccount, CorePolicy
from app.services.retrieval.evidence_retriever import EvidenceItem


class GroundingContextBuilder:
    """Builds structured, grounded context distinguishing policy, customer, and evidence sources."""

    @staticmethod
    def build(
        question: str,
        policy: CorePolicy,
        customer: CoreAccount,
        evidence: list[EvidenceItem],
        previous_question: str | None = None,
    ) -> str:
        """Construct prompt context clearly separating sections."""
        lines = []

        lines.append("=== POLICY CONTEXT ===")
        lines.append(f"Policy Number: {policy.policy_number}")
        lines.append(f"Term Number: {policy.term_number}")
        lines.append(f"Line of Business: {policy.line_of_business}")
        lines.append(f"Product Name: {policy.product_name or 'N/A'}")
        lines.append(f"Status: {policy.status}")
        lines.append(f"Effective Period: {policy.effective_date} to {policy.expiration_date}")
        lines.append(f"Insured Location: {policy.insured_location or 'N/A'}")
        lines.append(f"Annual Premium: ${policy.annual_premium:,.2f}")
        lines.append("")

        lines.append("=== CUSTOMER CONTEXT ===")
        lines.append(f"Customer Name: {customer.name if customer else 'N/A'}")
        lines.append(f"Email: {customer.email or 'N/A' if customer else 'N/A'}")
        lines.append(f"Phone: {customer.phone or 'N/A' if customer else 'N/A'}")
        if customer:
            lines.append(f"Address: {customer.address_line}, {customer.city} {customer.state} {customer.postal_code}".strip())
        else:
            lines.append("Address: N/A")
        lines.append("")

        lines.append("=== RETRIEVED POLICY EVIDENCE ===")
        if not evidence:
            lines.append("No specific policy evidence retrieved for this question.")
        else:
            for i, item in enumerate(evidence, start=1):
                lines.append(f"[E{i}]")
                lines.append(f"Source Type: {item.source_type.upper()}")
                if item.source_type == "clause":
                    scope = item.metadata.get("scope")
                    lines.append(
                        "Applies To: generic product wording (not specific to this policy)"
                        if scope == "product_wording"
                        else "Applies To: this policy's own attached form"
                    )
                lines.append(f"Title: {item.title}")

                # Format source metadata
                meta_parts = []
                if item.form_number:
                    meta_parts.append(f"Form: {item.form_number}")
                if item.edition:
                    meta_parts.append(f"Edition: {item.edition}")
                if item.page:
                    meta_parts.append(f"Page: {item.page}")
                if item.section:
                    meta_parts.append(f"Section: {item.section}")
                if item.heading:
                    meta_parts.append(f"Heading: {item.heading}")

                if meta_parts:
                    lines.append(f"Source Metadata: {' | '.join(meta_parts)}")

                lines.append(f"Content: {item.content}")
                if item.plain_language:
                    lines.append(f"Approved Explanation: {item.plain_language}")
                lines.append("")

        if previous_question:
            lines.append("=== PREVIOUS QUESTION IN THIS CONVERSATION (for resolving references only) ===")
            lines.append(previous_question.strip())
            lines.append("")

        lines.append("=== USER QUESTION ===")
        lines.append(question.strip())

        return "\n".join(lines)
