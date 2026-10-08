"""Question understanding: typos, names, policy numbers, paraphrases — rules layer and model layer."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

ai_service_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ai_service_dir not in sys.path:
    sys.path.insert(0, ai_service_dir)

from app.core.config import settings
from app.db.database import SessionLocal
from app.services.understanding import QueryInterpreter
from tests.messy_benchmark import run
from tests.messy_questions import NO_NAME_CASES


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def rules(question, db):
    return QueryInterpreter.interpret(question, db, mode="rules")


# ---- Rules layer (deterministic, no model call) --------------------------------------------

def test_messy_benchmark_rules_layer():
    """Typos and everyday wording find the right clause and customer without any model call."""
    scores = run(["raw", "rules"])
    hits, total = scores["rules"]["retrieval"]
    names, name_total = scores["rules"]["names"]
    assert hits >= 20, f"rules retrieval {hits}/{total}: {scores['rules']['rows']}"
    assert hits > scores["raw"]["retrieval"][0]
    assert names == name_total
    assert scores["rules"]["false_names"] == 0


def test_spelling_corrected_towards_policy_vocabulary(db):
    r = rules("whats the deductable", db)
    assert r.normalized == "what is the deductible"
    assert {"from": "deductable", "to": "deductible"} in r.corrections


def test_word_forms_are_not_mistaken_for_typos(db):
    assert rules("is he covered if he drives for uber", db).corrections == []
    assert rules("when does it renew", db).corrections == []


def test_policyholder_names_tolerate_typos_but_never_invent_customers(db):
    assert rules("does margret chen have water backup", db).policyholders == ["Margaret Chen"]
    assert "Margaret Chen's" in rules("is margaret chens house covered", db).normalized
    for question in NO_NAME_CASES:
        assert rules(question, db).policyholders == [], question


def test_policy_numbers_normalised(db):
    assert rules("deductible on ho 2847 1193", db).policy_numbers == ["HO-2847-1193"]
    assert rules("ho28471193", db).policy_numbers == ["HO-2847-1193"]


def test_everyday_words_mapped_to_policy_terms(db):
    assert {"jewelry", "theft"} <= set(rules("someone stole my necklace", db).search_terms)
    assert "loss of use" in rules("can we stay in a hotel", db).search_terms


# ---- Model layer (provider mocked) ------------------------------------------------------------

def _groq_reply(payload):
    resp = MagicMock(status_code=200, headers={})
    resp.json.return_value = {"choices": [{"message": {"content": payload}}]}
    return resp


def test_model_rewrite_is_used_and_validated(monkeypatch, db):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock")
    reply = json.dumps({
        "corrected_question": "Where would Margret Chen live if her house burned down?",
        "intent": "policy",
        "policyholder_name": "Margret Chen",
        "policy_number": "ho 2847 1193",
        "line_of_business": "homeowners",
        "search_terms": ["loss of use", "additional living expense", 42],
    })
    with patch("httpx.Client.post", return_value=_groq_reply(reply)):
        r = QueryInterpreter.interpret("where would margret live if her house burnt down", db, mode="auto")
    assert r.method == "llm"
    assert r.policyholders == ["Margaret Chen"]  # matched to the record on file
    assert "Margaret Chen" in r.normalized
    assert r.policy_numbers == ["HO-2847-1193"]
    assert "loss of use" in r.search_terms and 42 not in r.search_terms
    assert r.intent == "policy" and r.line_of_business == "homeowners"


def test_model_cannot_introduce_unknown_customer(monkeypatch, db):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    reply = json.dumps({"corrected_question": "Does John Smith have flood cover?", "intent": "policy",
                        "policyholder_name": "John Smith", "search_terms": ["flood"]})
    with patch("httpx.Client.post", return_value=_groq_reply(reply)):
        r = QueryInterpreter.interpret("does jon smith have flood cover", db, mode="auto")
    assert r.policyholders == []


def test_malformed_model_output_falls_back_to_rules(monkeypatch, db):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    with patch("httpx.Client.post", return_value=_groq_reply("Sure! The deductible is $500.")):
        r = QueryInterpreter.interpret("whats the deductable", db, mode="auto")
    assert r.method == "rules"
    assert r.normalized == "what is the deductible"
    assert r.fallback_reason


def test_rate_limited_model_falls_back_to_rules(monkeypatch, db):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    limited = MagicMock(status_code=429, headers={"retry-after": "60"})
    with patch("httpx.Client.post", return_value=limited):
        r = QueryInterpreter.interpret("does margret chen have water backup", db, mode="auto")
    assert r.method == "rules" and "429" in (r.fallback_reason or "")
    assert r.policyholders == ["Margaret Chen"]


def test_without_a_key_rules_are_used(monkeypatch, db):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    r = QueryInterpreter.interpret("hw many polcies", db, mode="auto")
    assert r.method == "rules" and "No API key" in (r.fallback_reason or "")
    assert r.normalized == "how many policies"


def test_generic_or_foreign_model_terms_are_dropped(monkeypatch, db):
    """Generic terms ("coverage", "exclusions") and words the forms never use ("UFO") must not make an
    off-topic question look answerable."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    reply = json.dumps({
        "corrected_question": "Does this policy cover damage from alien spacecraft?",
        "intent": "policy",
        "search_terms": ["damage", "coverage", "excluded perils", "policy limits", "UFO", "extraterrestrial", "loss of use"],
    })
    with patch("httpx.Client.post", return_value=_groq_reply(reply)):
        r = QueryInterpreter.interpret("does this cover damage from alien spacecraft", db, mode="auto")
    assert r.search_terms == ["loss of use"]


def test_previous_question_only_given_to_model_for_references(monkeypatch, db):
    """A general follow-up must not be narrowed to the previous topic; a referring one must use it."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    reply = json.dumps({"corrected_question": "What is the deductible?", "intent": "policy", "search_terms": ["deductible"]})
    with patch("httpx.Client.post", return_value=_groq_reply(reply)) as post:
        QueryInterpreter.interpret("whats the deductable", db, previous_question="Does she have water backup?", mode="auto")
        sent = post.call_args.kwargs["json"]["messages"][1]["content"]
        assert "Previous question" not in sent
        QueryInterpreter.interpret("which endorsement provides that", db, previous_question="Does she have water backup?", mode="auto")
        sent = post.call_args.kwargs["json"]["messages"][1]["content"]
        assert "Previous question: Does she have water backup?" in sent
