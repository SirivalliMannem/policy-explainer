"""Needs attention: each flagged question offers actions that resolve it; resolving is recorded, never destructive."""

import uuid
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import app.api.routes.conversations as conversation_routes
from app.main import app
from app.schemas.explainer import AIServiceResponse
from app.services.ai_client import ai_client

client = TestClient(app)


@pytest.fixture
def session(monkeypatch):
    state = {"grounded": False}

    def explain(question, policy_id, **kwargs):
        if state["grounded"]:
            return AIServiceResponse(
                question=question, answer="Water back-up is covered by HO 04 95 [E1].", confidence="high", status="answered",
                evidence=[{"source_type": "clause", "source_id": "c-wb", "title": "Water back-up", "content": "...",
                           "relevance_score": 15.0, "form_number": "HO 04 95", "page": 1, "evidence_index": 1}],
                citations=[{"source_id": "c-wb", "source_type": "clause", "evidence_index": 1}],
                guardrail_status="passed",
                guardrail_checks=[{"name": "inline_citations", "status": "passed", "detail": ""}],
            )
        return AIServiceResponse(
            question=question, answer="Not enough policy evidence.", confidence="none", status="insufficient_evidence",
            evidence=[], citations=[], guardrail_status="no_evidence", guardrail_checks=[],
            retrieval={"query_terms": ["zorblax", "meteors"], "clauses_searched": 53, "coverages_searched": 7},
        )

    monkeypatch.setattr(ai_client, "explain", explain)
    monkeypatch.setattr(ai_client, "interpret", lambda *a, **k: None)
    monkeypatch.setattr(conversation_routes, "interpret_question", lambda *a, **k: None)
    headers = {"X-Employee-Id": f"EMP-RES-{uuid.uuid4().hex[:6]}", "X-Employee-Name": quote("Queue Reviewer"), "X-Employee-Role": "manager"}
    made: list[str] = []
    yield headers, made, state
    for conv in made:  # ledger entries are audit records: archive, never delete
        client.post(f"/api/conversations/{conv}/archive", headers=headers)


def ask(session, question: str) -> dict:
    headers, made, _ = session
    pid = client.post("/api/policy-resolution/from-question", json={"question": "HO-2847-1193"}, headers=headers).json()["policy"]["policy_id"]
    conv = client.post("/api/conversations", json={}, headers=headers).json()["conversation_id"]
    made.append(conv)
    res = client.post(f"/api/conversations/{conv}/questions", json={"question": question, "policy_id": pid}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def queue_item(marker: str):
    items = client.get("/api/dashboard/attention", params={"range": "today"}).json()["items"]
    return next((i for i in items if marker in i["question"]), None)


def flagged_question(session) -> tuple[str, dict, dict]:
    marker = uuid.uuid4().hex[:8]
    body = ask(session, f"Does this policy cover damage from zorblax meteors {marker}?")
    item = queue_item(marker)
    assert item is not None and item["reason"] == "no_evidence"
    return marker, body, item


def test_a_flagged_question_offers_a_suggestion_and_actions(session):
    _, _, item = flagged_question(session)
    assert [a["key"] for a in item["actions"]] == ["confirmed_not_covered", "referred_underwriting", "reasked"]
    assert [a["kind"] for a in item["actions"]] == ["resolve", "resolve", "reask"]
    assert "None of “zorblax”, “meteors” matched" in item["suggestion"]
    assert "HO-2847-1193" in item["suggestion"]


def test_resolving_records_who_and_why_and_removes_it_from_the_queue(session):
    headers, _, _ = session
    marker, body, item = flagged_question(session)
    res = client.post("/api/dashboard/attention/resolve", headers=headers, json={
        "entry_id": item["latest_entry_id"], "action": "confirmed_not_covered", "note": "Meteors are not a listed peril.",
    })
    assert res.status_code == 201, res.text
    resolution = res.json()
    assert resolution["action_label"] == "Confirm not covered by the policy wording"
    assert resolution["resolved_by_name"] == "Queue Reviewer" and resolution["resolved_by_role"] == "manager"
    assert queue_item(marker) is None

    # The ledger entry is unchanged and now shows how it was resolved.
    entry = client.get(f"/api/ledger/{body['ledger_id']}").json()
    assert entry["outcome"] == "insufficient_evidence"
    assert entry["resolution"]["note"] == "Meteors are not a listed peril."

    # Resolving twice is refused.
    again = client.post("/api/dashboard/attention/resolve", headers=headers,
                        json={"entry_id": item["latest_entry_id"], "action": "referred_underwriting"})
    assert again.status_code == 409


def test_asked_again_after_resolving_it_returns_to_the_queue(session):
    headers, _, _ = session
    marker, _, item = flagged_question(session)
    client.post("/api/dashboard/attention/resolve", headers=headers,
                json={"entry_id": item["latest_entry_id"], "action": "referred_underwriting"})
    assert queue_item(marker) is None
    ask(session, f"Does this policy cover damage from zorblax meteors {marker}?")
    returned = queue_item(marker)
    assert returned is not None and returned["times_asked"] == 1


def test_only_the_actions_for_the_flag_reason_are_accepted(session):
    headers, _, _ = session
    _, _, item = flagged_question(session)
    res = client.post("/api/dashboard/attention/resolve", headers=headers,
                      json={"entry_id": item["latest_entry_id"], "action": "approved_after_review"})
    assert res.status_code == 422


def test_asking_again_resolves_only_with_a_grounded_new_answer(session):
    headers, _, state = session
    marker, _, item = flagged_question(session)
    # Without the new answer, or with one that is flagged too, the question stays in the queue.
    assert client.post("/api/dashboard/attention/resolve", headers=headers,
                       json={"entry_id": item["latest_entry_id"], "action": "reasked"}).status_code == 422
    still_flagged = ask(session, f"Is meteor damage covered {marker}?")
    assert client.post("/api/dashboard/attention/resolve", headers=headers, json={
        "entry_id": item["latest_entry_id"], "action": "reasked", "new_entry_id": still_flagged["ledger_id"],
    }).status_code == 409

    state["grounded"] = True
    grounded = ask(session, f"Is sewer back-up covered {marker}?")
    res = client.post("/api/dashboard/attention/resolve", headers=headers, json={
        "entry_id": item["latest_entry_id"], "action": "reasked", "new_entry_id": grounded["ledger_id"],
    })
    assert res.status_code == 201, res.text
    assert grounded["ledger_id"] in res.json()["note"]
    assert queue_item(f"zorblax meteors {marker}") is None


def test_an_answer_that_is_not_flagged_has_nothing_to_resolve(session):
    headers, _, state = session
    state["grounded"] = True
    body = ask(session, f"Is sewer back-up covered {uuid.uuid4().hex[:6]}?")
    res = client.post("/api/dashboard/attention/resolve", headers=headers,
                      json={"entry_id": body["ledger_id"], "action": "confirmed_correct"})
    assert res.status_code == 409


def test_blocked_roles_cannot_resolve(session):
    _, _, item = flagged_question(session)
    blocked = {"X-Employee-Id": "EMP-BLOCKED", "X-Employee-Role": "suspended"}
    res = client.post("/api/dashboard/attention/resolve", headers=blocked,
                      json={"entry_id": item["latest_entry_id"], "action": "referred_underwriting"})
    assert res.status_code == 403
