"""Analysis of a flagged question, in its decision order: customer verification, then policy context,
then exactly two suggestions from the model in that verified context. Nothing is padded or made up."""

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

TWO_RELATED = [
    {"question": "Which water-damage coverages are listed on this policy?", "relation": "related", "note": "Does not answer meteors."},
    {"question": "Is a water back-up endorsement attached to this policy?", "relation": "related", "note": "Does not answer meteors."},
]


class FakeProvider:
    name, model, is_configured = "groq", "openai/gpt-oss-120b", True

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, 0

    def complete(self, system, user, **kwargs):
        self.calls += 1
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


def run(monkeypatch, db, policy_id, reply=None, question="Does this policy cover damage from zorblax meteors?", error=None,
        flag_reason="no_evidence", retrieval=None):
    provider = FakeProvider(reply, error)
    monkeypatch.setattr(attention_analysis.LLMService, "get_provider", classmethod(lambda cls, name=None: provider))
    result = attention_analysis.analyze(question, policy_id, retrieval if retrieval is not None else STORED_SEARCH, db, flag_reason)
    return result, provider


def test_customer_not_found_gets_no_suggestions_and_no_model_call(monkeypatch, db):
    result, provider = run(monkeypatch, db, None, reply={"type": "typo", "reason": "x", "candidates": TWO_RELATED},
                           question="What are the policies of Sirivalli?", flag_reason="customer_not_found")
    assert result["status"] == "ready" and result["type"] == "customer_not_found"
    assert result["candidates"] == []
    assert provider.calls == 0  # no suggestion is generated before the customer is verified


def test_a_failed_customer_verification_stops_even_with_another_flag_reason(monkeypatch, db, policy_id):
    result, provider = run(monkeypatch, db, policy_id, reply={"type": "typo", "reason": "x", "candidates": TWO_RELATED},
                           retrieval={**STORED_SEARCH, "customer_verification": {"status": "not_found"}})
    assert result["type"] == "customer_not_found" and result["candidates"] == [] and provider.calls == 0


def test_no_verified_policy_gets_no_policy_specific_suggestions(monkeypatch, db):
    result, provider = run(monkeypatch, db, None, reply={"type": "typo", "reason": "x", "candidates": TWO_RELATED})
    assert result["type"] == "policy_context_missing" and result["candidates"] == []
    assert provider.calls == 0


def test_evidence_missing_with_a_verified_policy_gives_exactly_two_related_suggestions(monkeypatch, db, policy_id):
    result, provider = run(monkeypatch, db, policy_id, reply={"type": "coverage_no_evidence", "reason": "No clause on meteors.", "candidates": TWO_RELATED})
    assert provider.calls == 1
    assert result["status"] == "ready" and result["category"] == "evidence_missing"
    assert [c["question"] for c in result["candidates"]] == [c["question"] for c in TWO_RELATED]
    assert all(c["relation"] == "related" and c["note"] for c in result["candidates"])
    # Each is run through the normal retrieval; what it found is stored with it.
    assert all("passages" in c and "top_score" in c for c in result["candidates"])
    assert result["missing"].startswith("Searched 6 coverages, 4 forms and 47 clauses on HO-2847-1193")


def test_a_suggestion_that_restates_an_unanswerable_question_is_not_accepted(monkeypatch, db, policy_id):
    result, _ = run(monkeypatch, db, policy_id, reply={"type": "coverage_no_evidence", "reason": "No clause.", "candidates": [
        {"question": "Does this policy cover damage from zorblax meteors?", "relation": "related", "note": "x"},
        TWO_RELATED[0],
    ]})
    # One usable suggestion is not two: nothing is padded, the analysis fails and nothing is shown.
    assert result["status"] == "failed" and "candidates" not in result


def test_spelling_errors_give_two_corrected_suggestions(monkeypatch, db, policy_id):
    result, _ = run(monkeypatch, db, policy_id, question="is sewr bakup coverd", reply={"type": "typo", "reason": "Misspelled.", "candidates": [
        {"question": "Is sewer backup covered?", "relation": "same"},
        {"question": "Does the policy cover water backing up through a sewer or drain?", "relation": "same"},
    ]})
    assert result["category"] == "wrong_wording"
    assert len(result["candidates"]) == 2 and all(c["relation"] == "same" and c["note"] is None for c in result["candidates"])


def test_duplicate_suggestions_do_not_count_as_two(monkeypatch, db, policy_id):
    result, _ = run(monkeypatch, db, policy_id, question="is sewr bakup coverd", reply={"type": "typo", "reason": "x", "candidates": [
        {"question": "Is sewer backup covered?", "relation": "same"},
        {"question": "Is sewer backup covered", "relation": "same"},
    ]})
    assert result["status"] == "failed"


def test_out_of_scope_offers_no_suggestions(monkeypatch, db, policy_id):
    result, _ = run(monkeypatch, db, policy_id, question="What is the capital of France?",
                    reply={"type": "out_of_scope", "reason": "Not an insurance question.", "candidates": []})
    assert result["category"] == "out_of_scope" and result["candidates"] == []


def test_a_missing_edition_is_stated_from_the_policy_forms(monkeypatch, db, policy_id):
    result, _ = run(monkeypatch, db, policy_id, question="Is HO 04 95 edition 05 11 on this policy?",
                    reply={"type": "typo", "reason": "Wrong edition.", "candidates": TWO_RELATED})
    assert result["type"] == "missing_form_or_edition"  # the stored forms decide, not the model
    assert result["missing"] == "HO 04 95 edition 05 11 is not on HO-2847-1193; the policy has HO 04 95 edition 10 00."


def test_a_policy_number_is_never_read_as_a_missing_form(monkeypatch, db, policy_id):
    result, _ = run(monkeypatch, db, policy_id, question="Does this policy cover damage from meteors on HO-2847-1193?",
                    reply={"type": "coverage_no_evidence", "reason": "No clause on meteors.", "candidates": TWO_RELATED})
    assert result["type"] == "coverage_no_evidence"


def test_a_reply_that_does_not_match_the_schema_is_rejected(monkeypatch, db, policy_id):
    result, _ = run(monkeypatch, db, policy_id, reply={"type": "made_up_type", "reason": "x", "candidates": []})
    assert result["status"] == "failed" and "format" in result["reason"]


def test_without_the_model_the_analysis_fails_and_invents_nothing(monkeypatch, db, policy_id):
    result, _ = run(monkeypatch, db, policy_id, error=LLMProviderError("HTTP 429"))
    assert result["status"] == "failed" and "candidates" not in result
