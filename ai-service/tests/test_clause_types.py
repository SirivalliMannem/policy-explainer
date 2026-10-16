"""A question about a kind of clause (exclusions, conditions) finds the clauses stored as that kind,
whatever their heading says, on each policy separately."""

import os
import sys

import pytest

ai_service_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ai_service_dir not in sys.path:
    sys.path.insert(0, ai_service_dir)

from app.db.database import SessionLocal
from app.models.policy import Clause, CorePolicy
from app.services.retrieval.evidence_retriever import EvidenceRetriever


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def search(db, number, question):
    policy = db.query(CorePolicy).filter(CorePolicy.policy_number == number).order_by(CorePolicy.term_number.desc()).first()
    items, _ = EvidenceRetriever.retrieve_with_stats(question, policy.id, db)
    return policy, items


def clause_types(db, items):
    return {db.get(Clause, i.source_id).clause_type for i in items if i.source_type == "clause"}


def test_exclusions_headed_by_their_subject_are_found(db):
    # Elena Moreau's homeowners exclusions are headed "Water Damage", "Earth Movement" ...: only the
    # section says "Exclusions". They used to score below the evidence threshold.
    _, items = search(db, "HO-9021-4477", "What are the exclusions of Elena's policy?")
    assert items and clause_types(db, items) == {"exclusion"}
    assert {"Water Damage", "Earth Movement"} <= {i.heading for i in items}
    assert items[0].relevance_score >= 12  # strong evidence


def test_each_of_a_customers_policies_gets_its_own_exclusions(db):
    ho, ho_items = search(db, "HO-9021-4477", "What are the exclusions of Elena's policy?")
    pa, pa_items = search(db, "PA-8830-2215", "What are the exclusions of Elena's policy?")
    assert {i.form_number for i in ho_items} <= {"HO 00 03", "HO 04 61", "HO 04 95", "HO 01 41", "HO 03 12"}
    assert {i.form_number for i in pa_items} == {"PP 00 01"}  # nothing from the homeowners policy


def test_a_named_topic_still_has_to_match(db):
    # The auto policy has no flood wording: its unrelated livery exclusion is not evidence about flood.
    _, items = search(db, "PA-8830-2215", "Is flood excluded?")
    assert items == []
    _, items = search(db, "HO-9021-4477", "Is flood excluded?")
    assert items and items[0].heading == "Water Damage"


def test_conditions_are_found_by_their_kind(db):
    _, items = search(db, "HO-9021-4477", "What conditions apply after a loss?")
    assert "condition" in clause_types(db, items)
