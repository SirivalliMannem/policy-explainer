"""Analysis of a flagged question: the model classifies and proposes; code verifies and states facts."""

import json
import os
import sys

import pytest

ai_service_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ai_service_dir not in sys.path:
    sys.path.insert(0, ai_service_dir)

from app.db.database import SessionLocal
from app.models.policy import CorePolicy
from app.services import attention_analysis
from app.services.llm.exceptions import LLMProviderError

STORED_SEARCH = {"query_terms": ["meteors", "zorblax"], "coverages_searched": 6, "forms_searched": 4, "clauses_searched": 47}


class FakeProvider:
    name, model, is_configured = "groq", "openai/gpt-oss-120b", True

    def __init__(self, reply=None, error=None):
        self.reply, self.error = reply, error

    def complete(self, system, user, **kwargs):
        if self.error:
            raise self.error
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def policy_id(db):
    return db.query(CorePolicy).filter(CorePolicy.policy_number == "HO-2847-1193").order_by(CorePolicy.term_number.desc()).first().id


def run(monkeypatch, db, policy_id, reply, question="Does this policy cover damage from zorblax meteors?", error=None):
    provider = FakeProvider(reply, error)
    monkeypatch.setattr(attention_analysis.LLMService, "get_provider", classmethod(lambda cls, name=None: provider))
    return attention_analysis.analyze(question, policy_id, STORED_SEARCH, db)


def test_candidates_that_find_no_evidence_are_dropped(monkeypatch, db, policy_id):
    result = run(monkeypatch, db, policy_id, {
        "type": "coverage_no_evidence", "reason": "No clause addresses meteors.",
        "candidates": [
            {"question": "Is sewer back-up into the basement covered?", "relation": "related", "note": "Does not answer meteors."},
            {"question": "Does it cover zorblax quux frobnication?", "relation": "related", "note": "Does not answer meteors."},
        ],
    })
    assert result["status"] == "ready"
    assert [c["question"] for c in result["candidates"]] == ["Is sewer back-up into the basement covered?"]
    assert result["dropped_candidates"] == 1
    kept = result["candidates"][0]
    assert kept["passages"] and all(p["score"] >= attention_analysis.EVIDENCE_SCORE for p in kept["passages"])
    assert all(p["quote_verified"] for p in kept["passages"] if p["source_type"] == "clause")


def test_a_real_gap_is_never_presented_as_the_same_question(monkeypatch, db, policy_id):
    result = run(monkeypatch, db, policy_id, {
        "type": "coverage_no_evidence", "reason": "No clause addresses meteors.",
        "candidates": [
            {"question": "Is sewer back-up into the basement covered?", "relation": "same"},  # no note: cannot be shown
            {"question": "Is water back-up from a sewer covered?", "relation": "same", "note": "Does not answer meteors."},
        ],
    })
    assert [c["relation"] for c in result["candidates"]] == ["related"]
    assert result["candidates"][0]["note"] == "Does not answer meteors."


def test_what_is_missing_is_built_from_the_stored_search(monkeypatch, db, policy_id):
    result = run(monkeypatch, db, policy_id, {"type": "coverage_no_evidence", "reason": "The policy is silent on meteors entirely.", "candidates": []})
    assert result["missing"] == (
        "Searched 6 coverages, 4 forms and 47 clauses on HO-2847-1193; none mention “meteors”, “zorblax”."
    )
    assert "silent" not in result["missing"]  # the model's wording is not used


def test_a_missing_edition_is_stated_from_the_policy_forms(monkeypatch, db, policy_id):
    result = run(monkeypatch, db, policy_id, {"type": "typo", "reason": "Wrong edition.", "candidates": []},
                 question="Is HO 04 95 edition 05 11 on this policy?")
    assert result["type"] == "missing_form_or_edition"  # the stored forms decide, not the model
    assert result["missing"] == "HO 04 95 edition 05 11 is not on HO-2847-1193; the policy has HO 04 95 edition 10 00."
    assert result["upload_available"] is False


def test_out_of_scope_offers_no_suggestions(monkeypatch, db, policy_id):
    result = run(monkeypatch, db, policy_id, {
        "type": "out_of_scope", "reason": "Not an insurance question.",
        "candidates": [{"question": "Is sewer back-up covered?", "relation": "related", "note": "x"}],
    }, question="What is the capital of France?")
    assert result["category"] == "out_of_scope" and result["candidates"] == []


def test_a_reply_that_does_not_match_the_schema_is_rejected(monkeypatch, db, policy_id):
    result = run(monkeypatch, db, policy_id, {"type": "made_up_type", "reason": "x", "candidates": []})
    assert result["status"] == "failed" and "format" in result["reason"]


def test_without_the_model_the_analysis_fails_and_invents_nothing(monkeypatch, db, policy_id):
    result = run(monkeypatch, db, policy_id, None, error=LLMProviderError("HTTP 429"))
    assert result["status"] == "failed" and "candidates" not in result


def test_a_policy_number_is_never_read_as_a_missing_form(monkeypatch, db, policy_id):
    result = run(monkeypatch, db, policy_id, {"type": "coverage_no_evidence", "reason": "No clause on meteors.", "candidates": []},
                 question="Does this policy cover damage from meteors on HO-2847-1193?")
    assert result["type"] == "coverage_no_evidence"
    assert result["missing"].startswith("Searched 6 coverages, 4 forms and 47 clauses on HO-2847-1193")
