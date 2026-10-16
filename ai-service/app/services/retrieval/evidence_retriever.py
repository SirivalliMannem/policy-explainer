"""Evidence retrieval service grounded in resolved policy database entities."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy.orm import Session

from app.services.retrieval.semantic_index import clause_text, semantic_index
from app.models.policy import (
    Clause,
    CoreBilling,
    CoreClaim,
    CoreCoverage,
    CoreForm,
    CorePolicy,
)


@dataclass
class EvidenceItem:
    """Structured evidence element retrieved from policy database."""

    source_type: str  # clause | coverage | form | claim | billing | policy_meta
    source_id: str
    title: str
    content: str
    form_number: Optional[str] = None
    edition: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    heading: Optional[str] = None
    plain_language: Optional[str] = None
    relevance_score: float = 1.0
    metadata: dict = field(default_factory=dict)


STOP_WORDS = {
    "a", "about", "an", "and", "are", "as", "at", "be", "by", "can",
    "cause", "caused", "causing", "could", "did", "do", "does", "for",
    "from", "had", "has", "have", "how", "i", "if", "in", "is", "it",
    "its", "me", "much", "my", "no", "not", "of", "on", "or", "our",
    "ours", "please", "policy", "tell", "that", "the", "their", "then",
    "there", "these", "they", "this", "those", "to", "under", "us",
    "was", "we", "were", "what", "when", "where", "which", "who", "will",
    "with", "would", "you", "your", "cover", "coverage", "covered",
    "damage", "damages", "loss", "losses",
}


# Meaning-based search (see semantic_index.py). A clause counts as a meaning match when its
# similarity to the question stands at least MEANING_MIN_LIFT above the question's baseline and
# within MEANING_BAND of the best match; at most MEANING_MAX distinct clauses are taken this way.
# Its score scales with that lift: MEANING_FULL_LIFT scores the strong-evidence threshold.
MEANING_MIN_LIFT = 0.12
MEANING_BAND = 0.05
MEANING_MAX = 3
MEANING_FULL_LIFT = 0.18
STRONG_EVIDENCE_SCORE = 12.0  # the same threshold as explainer_pipeline.STRONG_EVIDENCE_SCORE
MEANING_SCORE_CAP = 15.0
BOTH_BONUS = 2.0


def meaning_points(lifts: dict[str, float], clauses: list) -> dict[str, float]:
    """Scores for the clauses whose meaning stands out for the question, by clause id."""
    if not lifts:
        return {}
    by_text: dict[str, float] = {}
    for clause in clauses:
        lift = lifts.get(clause.id)
        if lift is not None:
            text = clause_text(clause)
            by_text[text] = max(lift, by_text.get(text, lift))
    best = max(by_text.values(), default=0.0)
    chosen = sorted(
        (t for t, lift in by_text.items() if lift >= MEANING_MIN_LIFT and lift >= best - MEANING_BAND),
        key=lambda t: -by_text[t],
    )[:MEANING_MAX]
    points: dict[str, float] = {}
    for clause in clauses:
        text = clause_text(clause)
        if text in chosen:
            points[clause.id] = round(
                min(STRONG_EVIDENCE_SCORE * by_text[text] / MEANING_FULL_LIFT, MEANING_SCORE_CAP), 1
            )
    return points


# Words that ask for a kind of clause, by the clause_type stored on each clause.
CLAUSE_TYPE_TERMS: dict[str, set[str]] = {
    "exclusion": {"exclusion", "exclusions", "exclude", "excludes", "excluded"},
    "condition": {"condition", "conditions"},
    "definition": {"definition", "definitions", "define", "defined", "defines"},
}
# Enough on its own to count as evidence (with the customer's-own-form bonus it reaches the strong level).
CLAUSE_TYPE_SCORE = 8.0
# With a topic in the question: a nudge that needs a topic match too to reach the evidence threshold.
CLAUSE_TYPE_TOPIC_SCORE = 2.0
# Words that name no topic ("what are the exclusions on this policy", "list all of them").
GENERIC_TERMS = {"list", "all", "any", "main", "key", "apply", "applies", "listed"}


POLICY_NUMBER_REFERENCE = re.compile(r"\b(?:HO|PA)[-\s]?\d{4}(?:[-\s]\d{4})?\b", re.IGNORECASE)

POLICY_IDENTIFICATION_PATTERN = re.compile(
    r"\b(?:what\s+(?:kind\s+of\s+|type\s+of\s+)?policy|which\s+policy|what\s+is\s+(?:this|that|the|our|my)\s+policy|"
    r"what\s+do\s+we\s+have|what\s+policy\s+do\s+(?:we|i)\s+have|"
    r"policy\s+summary|summarize\s+(?:this\s+|the\s+)?policy|policy\s+overview|"
    r"who\s+is\s+(?:the\s+)?(?:insured|policyholder|named\s+insured)|who\s+is\s+this\s+policy\s+for|"
    r"policy\s+number|policy\s*#|number\s+of\s+(?:this|the)\s+policy|"
    r"(?:effective|expiration)\s+(?:dates?|period)|when\s+does\s+(?:this|the)\s+policy\s+expire|"
    r"policy\s+status|status\s+of\s+(?:this|the)\s+policy|is\s+(?:this|the)\s+policy\s+(?:in\s+force|active)|"
    r"product\s+(?:name|type)|line\s+of\s+business)\b",
    re.IGNORECASE,
)


def _tokenize(text: str) -> set[str]:
    """Extract lowercased alphanumeric words and normalized tokens from text."""
    if not text:
        return set()
    raw = re.findall(r"[a-zA-Z0-9_\-]+", text.lower())
    toks = set()
    for w in raw:
        clean = w.strip("-_")
        if len(clean) >= 2 and clean not in STOP_WORDS:
            toks.add(clean)
            if "-" in clean:
                toks.add(clean.replace("-", ""))
                for p in clean.split("-"):
                    if len(p) >= 2 and p not in STOP_WORDS:
                        toks.add(p)
            elif clean == "backup":
                toks.add("back-up")
            elif clean == "back":
                toks.add("backup")
                toks.add("back-up")
    return toks


class EvidenceRetriever:
    """Retrieves structured evidence grounded in a specific resolved policy."""

    @staticmethod
    def retrieve(
        question: str,
        policy_id: str,
        db: Session,
        limit: int = 8,
    ) -> list[EvidenceItem]:
        """Retrieve relevant evidence items for a given question and policy."""
        items, _ = EvidenceRetriever.retrieve_with_stats(question, policy_id, db, limit)
        return items

    @staticmethod
    def retrieve_with_stats(
        question: str,
        policy_id: str,
        db: Session,
        limit: int = 8,
    ) -> tuple[list[EvidenceItem], dict]:
        """Retrieve evidence plus a summary of what was searched (for audit and insufficient-evidence UX)."""
        stats: dict = {
            "query_terms": [],
            "coverages_searched": 0,
            "forms_searched": 0,
            "clauses_searched": 0,
            "claims_searched": 0,
            "billing_searched": 0,
            "candidates_scored": 0,
            "duplicates_removed": 0,
        }
        policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
        if not policy:
            return [], stats

        # A policy number says *which* policy to search, not *what* to search for. Left in, its
        # "HO"/"PA" prefix overlaps every form number and surfaces unrelated forms as evidence.
        q_clean = POLICY_NUMBER_REFERENCE.sub(" ", question).strip()
        q_lower = q_clean.lower()
        q_tokens = _tokenize(q_clean)
        # The policyholder's name identifies the policy; it is never something its wording says.
        holder_tokens = _tokenize(policy.account.name) if policy.account else set()
        q_tokens -= holder_tokens

        # When broad policy questions yield no remaining tokens due to stop words,
        # capture the identified inquiry terms so valid questions do not become empty queries.
        if not q_tokens:
            raw_words = re.findall(r"[a-zA-Z0-9_\-]+", q_clean.lower())
            preserved = [w.strip("-_") for w in raw_words if len(w.strip("-_")) >= 2]
            intent_terms = [
                w for w in preserved if w in ["policy", "summary", "number", "dates", "status", "effective"] or len(w) >= 4
            ]
            stats["query_terms"] = sorted(set(intent_terms or preserved[:3]))
        else:
            stats["query_terms"] = sorted(q_tokens)

        evidence_items: list[EvidenceItem] = []

        # ── 1. Match Policy Coverages ──────────────────────────────────────────
        coverages = db.query(CoreCoverage).filter(CoreCoverage.policy_id == policy_id).all()
        stats["coverages_searched"] = len(coverages)
        matched_coverage_patterns: set[str] = set()

        is_general_coverage_q = bool(
            re.search(
                r"\b(?:what\s+does\s+.*?\bcover\b|what\s+is\s+covered\b|what\s+are\s+the\s+coverages\b|what\s+coverages?\s+(?:are|do|does)\b|what\s+do\s+we\s+cover\b|list\s+(?:the\s+)?coverages?\b|coverages?\s+(?:on|for)\b|what\s+about\s+.*?\bpolicy\b|how\s+about\s+.*?\bpolicy\b)\b",
                q_lower,
            )
            or (not q_tokens and re.search(r"\b(?:cover|covers|covered|coverage)\b", q_lower))
        )

        for cov in coverages:
            cov_tokens = _tokenize(cov.name) | _tokenize(cov.pattern_code)
            overlap = q_tokens & cov_tokens
            has_deductible = bool(cov.deductible_text) and cov.deductible_text.strip().lower() not in ("none", "")
            is_deductible_q = "deductible" in q_tokens and ("deductible" in cov.name.lower() or has_deductible)
            is_limit_q = "limit" in q_tokens and cov.limit_text

            score = 0.0
            if overlap:
                score += len(overlap) * 4.0
            if is_general_coverage_q and cov.included:
                score += 8.0
            if is_deductible_q:
                # The declarations schedule is the policy-specific source of truth for amounts,
                # so it must outrank generic clause wording that merely mentions deductibles.
                score += 10.0
            if is_limit_q:
                score += 2.0

            # Special domain coverage associations
            if any(k in q_tokens for k in ["backup", "back-up", "sewer", "sump"]) and "water" in cov.name.lower():
                score += 15.0
            if any(k in q_tokens for k in ["wind", "hail", "storm"]) and "wind" in cov.name.lower():
                score += 8.0
            if any(k in q_tokens for k in ["jewel", "jewelry", "jewellery", "theft"]) and "scheduled" in cov.name.lower():
                score += 8.0
            if any(k in q_tokens for k in ["collision", "crash"]) and "collision" in cov.name.lower():
                score += 8.0
            if any(k in q_tokens for k in ["rental", "transportation"]) and (
                "rental" in cov.name.lower() or "transportation" in cov.name.lower() or "rental" in cov.pattern_code.lower()
            ):
                score += 8.0

            if score >= 3.0:
                matched_coverage_patterns.add(cov.pattern_code)
                limit_info = f"Limit: {cov.limit_text}" if cov.limit_text else "Limit: N/A"
                deductible_info = f"Deductible: {cov.deductible_text}" if cov.deductible_text else "Deductible: None"
                gov_info = f"Governing Form: {cov.governing_form}" if cov.governing_form else ""
                content = f"{cov.name} - {limit_info}, {deductible_info}. {gov_info}".strip()

                evidence_items.append(
                    EvidenceItem(
                        source_type="coverage",
                        source_id=cov.id,
                        title=f"Coverage: {cov.name}",
                        content=content,
                        form_number=cov.governing_form or None,
                        relevance_score=score,
                        metadata={
                            "pattern_code": cov.pattern_code,
                            "included": cov.included,
                            "limit_amount": cov.limit_amount,
                            "deductible_amount": cov.deductible_amount,
                        },
                    )
                )

        # ── 2. Match Policy Attached Forms ─────────────────────────────────────
        forms = db.query(CoreForm).filter(CoreForm.policy_id == policy_id).all()
        stats["forms_searched"] = len(forms)
        for form in forms:
            form_tokens = _tokenize(form.form_number) | _tokenize(form.title) | _tokenize(form.kind)
            form_overlap = q_tokens & form_tokens

            form_num_normalized = form.form_number.lower().replace(" ", "")
            q_num_normalized = q_lower.replace(" ", "")
            exact_number_match = form_num_normalized in q_num_normalized or form.form_number.lower() in q_lower

            score = 0.0
            if exact_number_match:
                score += 10.0
            elif form_overlap:
                score += len(form_overlap) * 3.0

            # Direct endorsement / form keywords
            if any(k in q_tokens for k in ["backup", "back-up", "sewer", "sump"]) and "04 95" in form.form_number:
                score += 10.0
            if "wind" in q_tokens and "03 12" in form.form_number:
                score += 8.0

            if score >= 3.0:
                content = (
                    f"Form {form.form_number} (Edition: {form.edition}) - Title: '{form.title}', "
                    f"Kind: {form.kind}, State: {form.state or 'Standard'}, Pages: {form.page_count}."
                )
                evidence_items.append(
                    EvidenceItem(
                        source_type="form",
                        source_id=form.id,
                        title=f"Form: {form.form_number} - {form.title}",
                        content=content,
                        form_number=form.form_number,
                        edition=form.edition,
                        page=1,
                        relevance_score=score,
                        metadata={"kind": form.kind, "state": form.state},
                    )
                )

        # ── 3. Match Policy Clauses (Customer's Own Forms + Product Guidance) ──
        customer_clauses = db.query(Clause).filter(Clause.policy_id == policy_id).all()
        product_clauses = (
            db.query(Clause)
            .filter(
                Clause.scope == "product_wording",
                Clause.line_of_business == policy.line_of_business,
            )
            .all()
        )

        all_candidate_clauses = [(c, True) for c in customer_clauses] + [(c, False) for c in product_clauses]
        asked_types = {kind for kind, words in CLAUSE_TYPE_TERMS.items() if q_tokens & words}
        # "What are the exclusions?" asks for all of them; "is flood excluded?" asks about flood, so a
        # clause of that kind still has to match the topic to count.
        topic_terms = q_tokens - set().union(*CLAUSE_TYPE_TERMS.values()) - GENERIC_TERMS
        type_score = CLAUSE_TYPE_SCORE if not topic_terms else CLAUSE_TYPE_TOPIC_SCORE
        stats["clauses_searched"] = len(all_candidate_clauses)

        # Meaning-based search over the same clauses, alongside the word match below.
        candidate_clauses = [c for c, _ in all_candidate_clauses]
        lifts = semantic_index.lifts(q_clean, candidate_clauses, db.query(Clause).all()) if q_clean else None
        meaning = meaning_points(lifts or {}, candidate_clauses)
        stats["meaning_search"] = {
            "status": "used" if lifts is not None else "unavailable",
            "model": semantic_index.model_name,
            **({} if lifts is not None else {"reason": semantic_index.unavailable_reason or "no question text"}),
        }

        for clause, is_customer_form in all_candidate_clauses:
            clause_keywords = set(k.lower() for k in (clause.keywords or []))
            heading_tokens = _tokenize(clause.heading)
            section_tokens = _tokenize(clause.section)
            text_tokens = _tokenize(clause.text)

            score = 0.0

            # Direct keyword hits (from curated domain indexing)
            # Curated keywords are often phrases ("rental car", "living expenses"); a phrase hits
            # when every one of its words is in the question.
            kw_hits = {k for k in clause_keywords if (kw_tokens := _tokenize(k)) and kw_tokens <= q_tokens}
            if kw_hits:
                score += len(kw_hits) * 3.0

            # Heading hits
            h_hits = q_tokens & heading_tokens
            if h_hits:
                score += len(h_hits) * 4.0

            # Section & body hits
            body_hits = q_tokens & (section_tokens | text_tokens)
            if body_hits:
                score += min(len(body_hits) * 0.5, 2.0)

            # Direct form number reference
            if clause.form_number.lower() in q_lower or clause.form_number.replace(" ", "").lower() in q_lower:
                score += 6.0

            # Governing pattern alignment
            if clause.pattern_code and clause.pattern_code in matched_coverage_patterns:
                score += 5.0

            # A question about a kind of clause ("what are the exclusions?") matches the clauses stored
            # as that kind, whatever their heading says: exclusions are often headed by their subject
            # ("Water Damage", "Earth Movement") and only the section says "Exclusions".
            if clause.clause_type in asked_types:
                score += type_score

            # Specific question terms: deductible, sewer, backup, flood
            if "deductible" in q_tokens and ("deductible" in clause.heading.lower() or "deductible" in clause_keywords):
                score += 8.0
            if any(k in q_tokens for k in ["backup", "back-up", "sewer", "sump"]):
                if any(k in clause.heading.lower() for k in ["backup", "back-up", "sump", "overflow"]):
                    score += 15.0
                elif clause.pattern_code == "HOWaterBackupCov":
                    score += 12.0
                elif "04 95" in clause.form_number:
                    score += 8.0

            # Meaning match: the clause is about what the question describes, whatever words it uses.
            word_score = score
            meaning_score = meaning.get(clause.id, 0.0)
            if meaning_score:
                score = max(word_score, meaning_score) + (BOTH_BONUS if word_score >= 3.0 else 0.0)
            matched_by = (
                "words and meaning" if meaning_score and word_score >= 3.0 else "meaning" if meaning_score else "words"
            )

            # PE-02 Ranking Rule: customer's own form outranks generic product wording
            if score >= 3.0:
                if is_customer_form:
                    score += 4.0

                evidence_items.append(
                    EvidenceItem(
                        source_type="clause",
                        source_id=clause.id,
                        title=f"Clause: {clause.heading}",
                        content=clause.text,
                        form_number=clause.form_number,
                        edition=clause.edition,
                        page=clause.page,
                        section=clause.section,
                        heading=clause.heading,
                        plain_language=clause.plain_language,
                        relevance_score=score,
                        metadata={
                            "scope": clause.scope,
                            "clause_type": clause.clause_type,
                            "pattern_code": clause.pattern_code,
                            "matched_by": matched_by,
                            **({"meaning_lift": round(lifts[clause.id], 3)} if lifts and clause.id in lifts and meaning_score else {}),
                        },
                    )
                )

        # ── 4. Match Claims (if loss / claim inquiry) ──────────────────────────
        if any(term in q_tokens for term in ["claim", "loss", "accident", "damage", "adjuster", "open"]):
            claims = db.query(CoreClaim).filter(CoreClaim.policy_id == policy_id).all()
            stats["claims_searched"] = len(claims)
            for claim in claims:
                content = (
                    f"Claim Number: {claim.claim_number}, Status: {claim.status}, Loss Cause: {claim.loss_cause}, "
                    f"Loss Date: {claim.loss_date}, Location: {claim.loss_location}, Description: {claim.description}, "
                    f"Adjuster: {claim.adjuster}."
                )
                evidence_items.append(
                    EvidenceItem(
                        source_type="claim",
                        source_id=claim.id,
                        title=f"Claim: {claim.claim_number}",
                        content=content,
                        relevance_score=3.0,
                        metadata={"status": claim.status, "claim_number": claim.claim_number},
                    )
                )

        # ── 5. Match Billing (if billing / payment inquiry) ────────────────────
        if any(term in q_tokens for term in ["bill", "billing", "payment", "due", "premium", "pay"]):
            billing_records = db.query(CoreBilling).filter(CoreBilling.policy_id == policy_id).all()
            stats["billing_searched"] = len(billing_records)
            for bill in billing_records:
                content = (
                    f"Billing Plan: {bill.plan}, Status: {bill.status}, Next Due: {bill.next_due_date}, "
                    f"Next Due Amount: ${bill.next_due_amount:.2f}, Past Due: ${bill.past_due_amount:.2f}."
                )
                evidence_items.append(
                    EvidenceItem(
                        source_type="billing",
                        source_id=bill.id,
                        title="Billing Record",
                        content=content,
                        relevance_score=3.0,
                        metadata={"status": bill.status, "plan": bill.plan},
                    )
                )

        # ── 6. Match Policy Metadata (Identification, Summary, Status, Dates) ──
        has_specific_coverage_inquiry = bool(
            re.search(r"\b(?:cover|covers|covered|coverage|exclu\w*|peril\w*|damage|loss|losses)\b", q_lower)
            and not re.search(
                r"\b(?:what\s+(?:kind\s+of\s+|type\s+of\s+)?policy|which\s+policy|what\s+policy\s+do|policy\s+summary|summarize)\b",
                q_lower,
            )
        )
        is_policy_id_q = not has_specific_coverage_inquiry and bool(
            POLICY_IDENTIFICATION_PATTERN.search(question)
            or POLICY_IDENTIFICATION_PATTERN.search(q_clean)
            or any(t in q_tokens for t in ["number", "effective", "expiration", "status"])
        )

        meta_score = 0.0
        if is_policy_id_q:
            meta_score += 12.0
            if "summary" in q_tokens or "summarize" in q_lower:
                meta_score += 3.0
            if "number" in q_tokens and "policy" in q_lower:
                meta_score += 3.0
            if any(k in q_tokens for k in ["effective", "expiration", "dates", "period"]):
                meta_score += 3.0
        elif is_general_coverage_q:
            meta_score += 6.0

        if meta_score >= 3.0:
            status_desc = "in force" if policy.status == "in_force" else policy.status.replace("_", " ")
            line_desc = (policy.line_of_business or "").replace("_", " ").title()
            named_insured = policy.account.name if policy.account else "N/A"
            location_info = f"Insured Location: {policy.insured_location}. " if policy.insured_location else ""
            premium_info = f"Annual Premium: ${policy.annual_premium:,.2f}. " if policy.annual_premium else ""

            content = (
                f"Policy Number: {policy.policy_number}. "
                f"Product: {policy.product_name or line_desc}. "
                f"Line of Business: {line_desc}. "
                f"Status: {status_desc}. "
                f"Effective Period: {policy.effective_date} to {policy.expiration_date} (Term {policy.term_number}). "
                f"Named Insured: {named_insured}. "
                f"State: {policy.state or 'N/A'}. "
                f"{location_info}"
                f"{premium_info}"
            ).strip()

            evidence_items.append(
                EvidenceItem(
                    source_type="policy_meta",
                    source_id=policy.id,
                    title=f"Policy Record: {policy.policy_number} — {policy.product_name or line_desc}",
                    content=content,
                    heading=f"Policy Record ({policy.policy_number})",
                    relevance_score=meta_score,
                    metadata={
                        "policy_number": policy.policy_number,
                        "line_of_business": policy.line_of_business,
                        "product_name": policy.product_name,
                        "status": policy.status,
                        "effective_date": str(policy.effective_date),
                        "expiration_date": str(policy.expiration_date),
                        "term_number": policy.term_number,
                        "named_insured": named_insured,
                        "scope": "policy_record",
                    },
                )
            )

        # Filter items with meaningful score (threshold >= 1.5)
        filtered = [item for item in evidence_items if item.relevance_score >= 1.5]

        stats["candidates_scored"] = len(filtered)

        # Sort descending by score, deduplicate by source_id and by citation identity:
        # product wording is stored once per seeded policy, so identical clauses must not
        # crowd out other evidence.
        filtered.sort(key=lambda x: x.relevance_score, reverse=True)

        seen_ids = set()
        seen_citations = set()
        deduped = []
        for item in filtered:
            citation_key = (
                (item.source_type, item.form_number, item.edition, item.page, item.heading)
                if item.source_type == "clause"
                else None
            )
            if item.source_id in seen_ids or (citation_key and citation_key in seen_citations):
                stats["duplicates_removed"] += 1
                continue
            seen_ids.add(item.source_id)
            if citation_key:
                seen_citations.add(citation_key)
            deduped.append(item)
            if len(deduped) >= limit:
                break

        if "meaning_search" in stats:
            kinds = [item.metadata.get("matched_by") for item in deduped if item.source_type == "clause"]
            stats["meaning_search"]["found_by_meaning"] = kinds.count("meaning")
            stats["meaning_search"]["words_and_meaning"] = kinds.count("words and meaning")
        return deduped, stats
