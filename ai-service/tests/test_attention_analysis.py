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


def test_case_a_no_evidence_generates_two_alternative_questions(monkeypatch, db, policy_id):
    result = run(monkeypatch, db, policy_id, {
        "type": "coverage_no_evidence", "reason": "No clause addresses meteors.",
        "candidates": [
            {"question": "Is sewer back-up into the basement covered?", "relation": "related", "note": "Does not answer meteors."},
            {"question": "What is the deductible for water damage under this policy?", "relation": "related", "note": "Inquires about water damage coverage."},
        ],
    })
    assert result["status"] == "ready"
    assert len(result["candidates"]) == 2
    assert result["candidates"][0]["question"] == "Is sewer back-up into the basement covered?"
    assert result["candidates"][0]["relation"] == "related"
    assert result["candidates"][0]["note"] == "Does not answer meteors."
    assert result["candidates"][0]["passages"] and all(p["score"] >= attention_analysis.EVIDENCE_SCORE for p in result["candidates"][0]["passages"])
    assert all(p["quote_verified"] for p in result["candidates"][0]["passages"] if p["source_type"] == "clause")
    assert result["candidates"][1]["relation"] == "related"


def test_case_b_spelling_or_wording_error_generates_two_corrected_alternatives(monkeypatch, db, policy_id):
    result = run(monkeypatch, db, policy_id, {
        "type": "typo", "reason": "Typo in 'sewer' prevented retrieval match.",
        "candidates": [
            {"question": "Is sewer back-up into the basement covered?", "relation": "same"},
            {"question": "Does this policy cover sewer back-up damage?", "relation": "same"},
        ],
    }, question="Is suwer bak-up into basement covred?")
    assert result["status"] == "ready"
    assert len(result["candidates"]) == 2
    assert result["type"] == "typo"
    assert result["category"] == "wrong_wording"
    assert result["candidates"][0]["relation"] == "same"
    assert result["candidates"][1]["relation"] == "same"
    assert result["candidates"][0]["question"] == "Is sewer back-up into the basement covered?"


def test_case_c_other_errors_address_specific_issue(monkeypatch, db, policy_id):
    result = run(monkeypatch, db, policy_id, {
        "type": "out_of_scope", "reason": "Not a single policy coverage question.",
        "candidates": [
            {"question": "What coverage forms and endorsements apply to policy HO-2847-1193?", "relation": "related", "note": "Checks attached policy endorsements."},
            {"question": "What is the policy deductible and coverage limit?", "relation": "related", "note": "Checks basic policy terms."},
        ],
    }, question="What is the meaning of life?")
    assert result["status"] == "ready"
    assert len(result["candidates"]) == 2
    assert result["candidates"][0]["relation"] == "related"
    assert result["candidates"][1]["relation"] == "related"


def test_missing_policy_context_generates_two_suggestions_via_llm(monkeypatch, db):
    provider = FakeProvider({
        "type": "out_of_scope", "reason": "Customer and policy could not be identified.",
        "candidates": [
            {"question": "Could you provide the policy number (e.g. HO-XXXX-XXXX)?", "relation": "related", "note": "Clarifies policy number."},
            {"question": "Could you provide the customer's full name or account number?", "relation": "related", "note": "Clarifies customer."},
        ],
    })
    monkeypatch.setattr(attention_analysis.LLMService, "get_provider", classmethod(lambda cls, name=None: provider))
    result = attention_analysis.analyze("Does Margaret Chen have flood coverage?", None, STORED_SEARCH, db, flag_reason="customer_not_found")
    assert result["status"] == "ready"
    assert len(result["candidates"]) == 2
    assert result["candidates"][0]["question"].startswith("Could you provide the policy number")
    assert result["candidates"][1]["question"].startswith("Could you provide the customer's full name")


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
