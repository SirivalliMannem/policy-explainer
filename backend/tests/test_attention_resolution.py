"""Needs attention: suggestion-based closing. A flagged item is closed by asking a verified suggestion
or an edited question as a NEW question, or by dismissing it with a reason. The flagged ledger record
is never modified; a re-asked question flagged again becomes a new item linked to the original."""

import uuid
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import app.api.routes.conversations as conversation_routes
from app.db.database import SessionLocal
from app.main import app
from app.models.ledger import EvidenceLedger
from app.schemas.explainer import AIServiceResponse
from app.services.ai_client import ai_client

client = TestClient(app)

GROUNDED = "Is sewer back-up covered by the water back-up endorsement?"


@pytest.fixture
def session(monkeypatch):
    def explain(question, policy_id, **kwargs):
        if "sewer" in question.lower():
            return AIServiceResponse(
                question=question, answer="Sewer back-up is covered by HO 04 95 [E1].", confidence="high", status="answered",
                evidence=[{"source_type": "clause", "source_id": "c-wb", "title": "Water back-up", "content": "...",
                           "relevance_score": 15.0, "form_number": "HO 04 95", "page": 1, "evidence_index": 1}],
                citations=[{"source_id": "c-wb", "source_type": "clause", "evidence_index": 1}],
                guardrail_status="passed",
                guardrail_checks=[{"name": "inline_citations", "status": "passed", "detail": ""}],
            )
        return AIServiceResponse(
            question=question, answer="Not enough policy evidence.", confidence="none", status="insufficient_evidence",
            evidence=[], citations=[], guardrail_status="no_evidence", guardrail_checks=[],
            retrieval={"query_terms": ["zorblax", "meteors"], "clauses_searched": 47, "coverages_searched": 6, "forms_searched": 4},
        )

    monkeypatch.setattr(ai_client, "explain", explain)
    monkeypatch.setattr(ai_client, "interpret", lambda *a, **k: None)
    monkeypatch.setattr(conversation_routes, "interpret_question", lambda *a, **k: None)
    headers = {"X-Employee-Id": f"EMP-RES-{uuid.uuid4().hex[:6]}", "X-Employee-Name": quote("Queue Worker"), "X-Employee-Role": "csr"}
    made: list[str] = []
    yield headers, made
    for conv in made:  # ledger entries are audit records: archive, never delete
        client.post(f"/api/conversations/{conv}/archive", headers=headers)


def ask(session, question: str) -> dict:
    headers, made = session
    pid = client.post("/api/policy-resolution/from-question", json={"question": "HO-2847-1193"}, headers=headers).json()["policy"]["policy_id"]
    conv = client.post("/api/conversations", json={}, headers=headers).json()["conversation_id"]
    made.append(conv)
    res = client.post(f"/api/conversations/{conv}/questions", json={"question": question, "policy_id": pid}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def queue():
    return client.get("/api/dashboard/attention", params={"range": "today"}).json()["items"]


def queue_item(marker: str):
    return next((i for i in queue() if marker in i["question"]), None)


def store_analysis(entry_id: str, candidates: list[str]):
    """What the background analysis stores (the model is never called in tests)."""
    db = SessionLocal()
    try:
        entry = db.get(EvidenceLedger, entry_id)
        entry.attention_analysis = {
            "status": "ready", "type": "coverage_no_evidence", "category": "evidence_missing",
            "reason": "No clause addresses meteors.",
            "missing": "Searched 6 coverages, 4 forms and 47 clauses on HO-2847-1193; none mention “meteors”.",
            "candidates": [{"question": q, "relation": "related", "note": "Does not answer meteors.",
                            "passages": [{"form_number": "HO 04 95", "page": 1, "score": 15.0, "quote": "...", "quote_verified": True}],
                            "top_score": 15.0} for q in candidates],
        }
        db.commit()
    finally:
        db.close()


def snapshot(entry_id: str) -> dict:
    db = SessionLocal()
    try:
        e = db.get(EvidenceLedger, entry_id)
        return {k: getattr(e, k) for k in ("question", "final_answer", "outcome", "confidence", "guardrail_status",
                                           "citations", "retrieved_evidence", "retrieval", "created_at")}
    finally:
        db.close()


def flagged(session) -> tuple[str, dict]:
    marker = uuid.uuid4().hex[:8]
    body = ask(session, f"Does this policy cover damage from zorblax meteors {marker}?")
    assert queue_item(marker) is not None
    return marker, body


def test_the_queue_reads_the_stored_analysis(session):
    marker, body = flagged(session)
    assert queue_item(marker)["analysis"] is None  # not analysed yet: nothing is computed on load
    store_analysis(body["ledger_id"], [GROUNDED])
    item = queue_item(marker)
    assert item["analysis"]["missing"].startswith("Searched 6 coverages")
    assert item["analysis"]["candidates"][0]["question"] == GROUNDED


def test_asking_a_suggestion_closes_the_item_and_leaves_the_original_record_untouched(session):
    headers, _ = session
    marker, body = flagged(session)
    store_analysis(body["ledger_id"], [GROUNDED])
    before = snapshot(body["ledger_id"])
    res = client.post("/api/dashboard/attention/resolve", headers=headers, json={
        "entry_id": body["ledger_id"], "action": "asked_suggestion", "question": GROUNDED,
    })
    assert res.status_code == 201, res.text
    out = res.json()
    assert out["new_answer"]["outcome"] == "answered" and out["new_answer"]["flagged"] is False
    assert out["resolution"]["new_question"] == GROUNDED
    assert out["resolution"]["new_entry_id"] == out["new_answer"]["ledger_id"] != body["ledger_id"]
    assert out["resolution"]["resolved_by_name"] == "Queue Worker"
    assert queue_item(marker) is None
    assert snapshot(body["ledger_id"]) == before  # the flagged record is unchanged
    # The new answer is its own entry, linked to the original it re-runs.
    new_entry = client.get(f"/api/ledger/{out['new_answer']['ledger_id']}").json()
    assert new_entry["retrieval"]["rerun_of"]["entry_id"] == body["ledger_id"]


def test_only_a_verified_suggestion_can_be_asked_as_one(session):
    headers, _ = session
    _, body = flagged(session)
    store_analysis(body["ledger_id"], [GROUNDED])
    res = client.post("/api/dashboard/attention/resolve", headers=headers, json={
        "entry_id": body["ledger_id"], "action": "asked_suggestion", "question": "Something the analysis never verified?",
    })
    assert res.status_code == 422


def test_a_rerun_that_is_flagged_again_is_a_new_linked_item_and_the_original_stays_closed(session):
    headers, _ = session
    marker, body = flagged(session)
    edited = f"Are meteor strikes covered {marker}?"  # still no evidence
    res = client.post("/api/dashboard/attention/resolve", headers=headers, json={
        "entry_id": body["ledger_id"], "action": "edited_and_asked", "question": edited,
    })
    assert res.status_code == 201, res.text
    assert res.json()["new_answer"]["flagged"] is True
    items = [i for i in queue() if marker in i["question"]]
    assert [i["question"] for i in items] == [edited]  # the original is not reopened
    assert items[0]["rerun_of"] == {"entry_id": body["ledger_id"], "question": body["question"]}


def test_dismiss_requires_a_reason(session):
    headers, _ = session
    marker, body = flagged(session)
    bad = client.post("/api/dashboard/attention/resolve", headers=headers,
                      json={"entry_id": body["ledger_id"], "action": "dismissed", "reason": "  "})
    assert bad.status_code == 422
    ok = client.post("/api/dashboard/attention/resolve", headers=headers,
                     json={"entry_id": body["ledger_id"], "action": "dismissed", "reason": "Not an insurance question."})
    assert ok.status_code == 201
    assert ok.json()["resolution"]["note"] == "Not an insurance question." and ok.json()["new_answer"] is None
    assert queue_item(marker) is None
    log = client.get("/api/dashboard/attention/resolutions", params={"range": "today"}).json()
    assert any(r["action"] == "dismissed" and r["question"] == body["question"] for r in log)


def test_closing_clears_every_repeat(session):
    headers, _ = session
    marker = uuid.uuid4().hex[:8]
    question = f"Does this policy cover damage from zorblax meteors {marker}?"
    first = ask(session, question)
    ask(session, question)
    assert queue_item(marker)["times_asked"] == 2
    client.post("/api/dashboard/attention/resolve", headers=headers,
                json={"entry_id": first["ledger_id"], "action": "dismissed", "reason": "Out of scope."})
    assert queue_item(marker) is None


def test_adding_an_edition_is_refused_without_an_upload_flow(session):
    headers, _ = session
    _, body = flagged(session)
    res = client.post("/api/dashboard/attention/resolve", headers=headers,
                      json={"entry_id": body["ledger_id"], "action": "added_edition"})
    assert res.status_code == 422 and "No flow exists" in res.json()["detail"]


def test_blocked_roles_cannot_work_the_queue(session):
    _, body = flagged(session)
    blocked = {"X-Employee-Id": "EMP-BLOCKED", "X-Employee-Role": "suspended"}
    res = client.post("/api/dashboard/attention/resolve", headers=blocked,
                      json={"entry_id": body["ledger_id"], "action": "dismissed", "reason": "x"})
    assert res.status_code == 403
