"""One question, several matching policies: answered for each when they belong to one customer."""

import uuid
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import app.api.routes.conversations as conversation_routes
from app.db.database import SessionLocal
from app.main import app
from app.models.conversation import Conversation
from app.models.ledger import EvidenceLedger
from app.schemas.explainer import AIServiceResponse
from app.services.ai_client import ai_client

client = TestClient(app)


def headers(emp: str) -> dict:
    return {"X-Employee-Id": emp, "X-Employee-Name": quote("Test Agent"), "X-Employee-Role": "csr"}


@pytest.fixture
def no_interpreter(monkeypatch):
    # Resolution and answering must not depend on the language model in these tests.
    monkeypatch.setattr(ai_client, "interpret", lambda *a, **k: None)
    monkeypatch.setattr(conversation_routes, "interpret_question", lambda *a, **k: None)


def resolve(question: str, emp: str = "EMP-ALL-01", conversation_id=None) -> dict:
    body = {"question": question}
    if conversation_id:
        body["conversation_id"] = conversation_id
    res = client.post("/api/policy-resolution/from-question", json=body, headers=headers(emp))
    assert res.status_code == 200, res.text
    return res.json()


def test_one_customers_policies_are_answered_together(no_interpreter):
    body = resolve("Does Margaret Chen have a deductible?")
    assert body["status"] == "ambiguous"
    assert body["answer_all"] is True
    numbers = sorted(c["policy_number"] for c in body["candidates"])
    assert numbers == ["HO-2847-1193", "PA-6120-7742"]
    assert len({c["customer_id"] for c in body["candidates"]}) == 1


def test_different_customers_are_still_asked_about(no_interpreter):
    # "Chen" is Margaret Chen and David Chen: answering both would mix two customers.
    body = resolve("What is Chen's deductible?")
    assert body["status"] == "ambiguous"
    assert len({c["customer_id"] for c in body["candidates"]}) > 1
    assert body["answer_all"] is False


def test_a_line_hint_still_picks_one_policy(no_interpreter):
    body = resolve("Does Margaret Chen's car policy have a deductible?")
    assert body["status"] == "resolved" and body["policy"]["policy_number"] == "PA-6120-7742"
    assert body["answer_all"] is False


def _answer_for_each(question: str, emp: str) -> tuple[str, list[dict], list[dict]]:
    """Resolve the question, then answer it for each of the customer's policies, as the chat does."""
    me = headers(emp)
    resolution = resolve(question, emp)
    assert resolution["answer_all"] is True, resolution
    candidates = resolution["candidates"]
    conv = client.post("/api/conversations", json={}, headers=me).json()["conversation_id"]
    answers = []
    for c in candidates:
        res = client.post(
            f"/api/conversations/{conv}/questions", json={"question": question, "policy_id": c["policy_id"]}, headers=me
        )
        assert res.status_code == 201, res.text
        answers.append(res.json())
    return conv, candidates, answers


def _assert_recorded_per_policy(conv: str, candidates: list[dict], answers: list[dict], emp: str) -> None:
    assert [a["policy_context"]["policy_number"] for a in answers] == [c["policy_number"] for c in candidates]
    db = SessionLocal()
    try:
        # One ledger entry per policy answered, and the conversation's context is left unset.
        entries = db.query(EvidenceLedger).filter(EvidenceLedger.conversation_id == conv).all()
        assert sorted(e.policy_id for e in entries) == sorted(c["policy_id"] for c in candidates)
        assert db.get(Conversation, conv).policy_id is None
    finally:
        db.close()
    # Reopening returns each, with its own policy.
    messages = client.get(f"/api/conversations/{conv}/messages", headers=headers(emp)).json()
    assert [m["policy_id"] for m in messages] == [c["policy_id"] for c in candidates]
    # Ledger entries are permanent audit records: archive the test conversation instead of deleting it.
    client.post(f"/api/conversations/{conv}/archive", headers=headers(emp))


def test_a_wording_question_is_explained_for_each_policy(no_interpreter, monkeypatch):
    explained: list[str] = []

    def explain(question, policy_id, **kwargs):
        explained.append(policy_id)
        return AIServiceResponse(question=question, answer=f"Answer for {policy_id}", confidence="high", status="answered")

    monkeypatch.setattr(ai_client, "explain", explain)
    emp = f"EMP-ALL-{uuid.uuid4().hex[:6]}"
    conv, candidates, answers = _answer_for_each("What exclusions apply to Margaret Chen?", emp)
    assert explained == [c["policy_id"] for c in candidates]
    _assert_recorded_per_policy(conv, candidates, answers, emp)


def test_a_simple_fact_is_read_from_each_policys_records(no_interpreter, monkeypatch):
    def explain(*args, **kwargs):
        raise AssertionError("a deductible is read from the records, not the language model")

    monkeypatch.setattr(ai_client, "explain", explain)
    emp = f"EMP-ALL-{uuid.uuid4().hex[:6]}"
    conv, candidates, answers = _answer_for_each("Does Margaret Chen have a deductible?", emp)
    # Each answer is about its own policy's deductibles.
    assert answers[0]["answer"] != answers[1]["answer"]
    _assert_recorded_per_policy(conv, candidates, answers, emp)
