"""Confidence percentage in the Evidence Ledger: the same criteria as the chat's confidence badge."""

import uuid
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import app.api.routes.conversations as conversation_routes
from app.main import app
from app.schemas.explainer import AIServiceResponse
from app.services.ai_client import ai_client
from app.services.confidence import confidence_percent

client = TestClient(app)

CHECKS = [{"name": "inline_citations", "status": "passed"}, {"name": "cross_policy_leak", "status": "passed"}]


def clause(score):
    return {"source_type": "clause", "relevance_score": score, "scope": "customer_form"}


def test_a_generated_answer_meeting_every_criterion_is_100():
    assert confidence_percent("high", "policy_explanation", [clause(15), clause(4)], [{}, {}], CHECKS, "passed") == 100


def test_each_missed_criterion_lowers_the_percentage():
    # One citation (misses "two or more") and weak evidence (misses the strong-evidence threshold).
    assert confidence_percent("medium", "policy_explanation", [clause(8)], [{}], CHECKS, "passed") == 67
    # Also no inline citations.
    no_inline = [{"name": "inline_citations", "status": "failed"}]
    assert confidence_percent("low", "policy_explanation", [clause(8)], [{}], no_inline, "passed") == 50


def test_record_answers_use_the_record_criteria():
    record = {"source_type": "coverage", "scope": "policy_record"}
    assert confidence_percent("high", "factual_lookup", [record], [{}], [], "passed") == 100
    assert confidence_percent("high", "factual_lookup", [record, record], [{}], [], "passed") == 67


@pytest.mark.parametrize(
    "confidence, answer_type, checks",
    [("high", "portfolio", CHECKS), ("none", "policy_explanation", CHECKS), ("medium", "policy_explanation", [])],
)
def test_no_percentage_where_it_does_not_apply(confidence, answer_type, checks):
    assert confidence_percent(confidence, answer_type, [clause(15)], [{}], checks, "passed") is None


@pytest.fixture
def headers(monkeypatch):
    monkeypatch.setattr(ai_client, "interpret", lambda *a, **k: None)
    monkeypatch.setattr(conversation_routes, "interpret_question", lambda *a, **k: None)
    h = {"X-Employee-Id": f"EMP-CONF-{uuid.uuid4().hex[:6]}", "X-Employee-Name": quote("Confidence Tester"), "X-Employee-Role": "csr"}
    made: list[str] = []
    yield h, made
    for conv in made:  # ledger entries are audit records: archive, never delete
        client.post(f"/api/conversations/{conv}/archive", headers=h)


def test_ledger_rows_and_detail_carry_the_percentage(headers, monkeypatch):
    h, made = headers
    monkeypatch.setattr(ai_client, "explain", lambda question, policy_id, **k: AIServiceResponse(
        question=question, answer="Sewer back-up is covered by HO 04 95 [E1].", confidence="medium", status="answered",
        evidence=[{"source_type": "clause", "source_id": "c-wb", "title": "Water back-up", "content": "...",
                   "relevance_score": 8.0, "form_number": "HO 04 95", "page": 1, "evidence_index": 1}],
        citations=[{"source_id": "c-wb", "source_type": "clause", "evidence_index": 1}],
        guardrail_status="passed",
        guardrail_checks=[{"name": "inline_citations", "status": "passed", "detail": ""}],
    ))
    pid = client.post("/api/policy-resolution/from-question", json={"question": "HO-2847-1193"}, headers=h).json()["policy"]["policy_id"]
    conv = client.post("/api/conversations", json={}, headers=h).json()["conversation_id"]
    made.append(conv)
    marker = uuid.uuid4().hex[:8]
    body = client.post(f"/api/conversations/{conv}/questions",
                       json={"question": f"Does the sewer backup wording apply {marker}?", "policy_id": pid}, headers=h).json()
    row = next(r for r in client.get("/api/ledger", params={"search": marker}).json()["items"] if r["id"] == body["ledger_id"])
    # Evidence, guardrails, one citation and inline citations met; two citations and strong evidence missed.
    assert (row["confidence"], row["confidence_percent"]) == ("medium", 67)
    assert client.get(f"/api/ledger/{body['ledger_id']}").json()["confidence_percent"] == 67
