"""Meaning-based clause search alongside word match: everyday wording finds the form's phrase."""

import os
import sys
from types import SimpleNamespace

import pytest

ai_service_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ai_service_dir not in sys.path:
    sys.path.insert(0, ai_service_dir)

from app.db.database import SessionLocal
from app.models.policy import CorePolicy
from app.services.retrieval import evidence_retriever
from app.services.retrieval.evidence_retriever import EvidenceRetriever, meaning_points
from app.services.retrieval.semantic_index import SemanticIndex, semantic_index


def _clause(cid, heading):
    return SimpleNamespace(id=cid, heading=heading, plain_language="", text="")


def test_only_clauses_that_stand_out_score_by_meaning():
    clauses = [_clause("a", "Discharge"), _clause("b", "Mold"), _clause("c", "Theft"), _clause("d", "Earth movement")]
    # a and b stand well above the baseline and close to the best; c is close to the best but too
    # weak on its own; d is far below the best.
    points = meaning_points({"a": 0.20, "b": 0.17, "c": 0.10, "d": 0.05}, clauses)
    assert set(points) == {"a", "b"}
    assert points["a"] == 13.3  # 12 x 0.20 / 0.18
    assert meaning_points({"a": 0.08}, clauses) == {}  # nothing stands out: nothing found by meaning


def test_a_clause_stored_for_several_policies_counts_once():
    copies = [_clause("x1", "Discharge"), _clause("x2", "Discharge"), _clause("y", "Mold"), _clause("z", "Vermin"), _clause("w", "Wear")]
    points = meaning_points({"x1": 0.20, "x2": 0.20, "y": 0.19, "z": 0.18, "w": 0.17}, copies)
    assert set(points) == {"x1", "x2", "y", "z"}  # three distinct clauses; both copies of the first


def _policy_id(number):
    db = SessionLocal()
    try:
        return db.query(CorePolicy).filter(CorePolicy.policy_number == number).order_by(CorePolicy.term_number.desc()).first().id
    finally:
        db.close()


def _search(number, question):
    db = SessionLocal()
    try:
        return EvidenceRetriever.retrieve_with_stats(question, _policy_id(number), db)
    finally:
        db.close()


needs_model = pytest.mark.skipif(not semantic_index.enabled, reason="meaning search switched off (SEMANTIC_SEARCH=off)")


@needs_model
def test_everyday_wording_finds_the_form_phrase():
    # No word in common with "Accidental Discharge Or Overflow Of Water Or Steam".
    items, stats = _search("HO-2847-1193", "My dishwasher hose leaked and soaked the floor")
    assert stats["meaning_search"]["status"] == "used"
    top = items[0]
    assert (top.form_number, top.heading) == ("HO 00 03", "Accidental Discharge Or Overflow Of Water Or Steam")
    assert top.metadata["matched_by"] == "meaning"
    assert top.relevance_score >= 12  # strong evidence


@needs_model
def test_word_and_meaning_matches_rank_together():
    items, stats = _search("HO-2847-1193", "A pipe burst in the kitchen, is it covered?")
    assert items[0].heading == "Accidental Discharge Or Overflow Of Water Or Steam"
    assert items[0].metadata["matched_by"] == "words and meaning"
    assert stats["meaning_search"]["words_and_meaning"] >= 1


@needs_model
def test_auto_wording_hitting_an_animal_finds_other_than_collision():
    items, _ = _search("PA-5518-0042", "I hit a deer on the highway")
    assert items[0].heading == "Other Than Collision"
    assert items[0].metadata["matched_by"] == "meaning"


@needs_model
def test_nothing_is_invented_when_no_clause_is_about_the_question():
    # The homeowners wording has no theft clause: meaning search must not force one in.
    items, stats = _search("HO-2847-1193", "Someone broke in and took my laptop")
    assert stats["meaning_search"]["found_by_meaning"] == 0
    assert not any(i.metadata.get("matched_by") == "meaning" for i in items)


def test_without_the_model_search_falls_back_to_word_match(monkeypatch):
    off = SemanticIndex("BAAI/bge-small-en-v1.5", None, enabled=False)
    monkeypatch.setattr(evidence_retriever, "semantic_index", off)
    items, stats = _search("HO-2847-1193", "A pipe burst in the kitchen, is it covered?")
    assert stats["meaning_search"]["status"] == "unavailable"
    assert "switched off" in stats["meaning_search"]["reason"]
    assert items[0].heading == "Accidental Discharge Or Overflow Of Water Or Steam"  # still found by words
    assert items[0].metadata["matched_by"] == "words"
