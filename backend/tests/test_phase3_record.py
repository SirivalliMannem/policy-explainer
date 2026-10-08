"""Phase 3: policy resolution from questions, audit fields, The Record, sources and failure handling.

Requires the seeded database and a running AI service (test_phase2_explainer starts one for the
session when none is running).
"""

import os
import sys
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.db.database import engine
from app.db.migrations import ensure_ledger_columns
from app.main import app
from app.services.ai_client import ai_client

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def require_ai_service():
    try:
        httpx.get(f"{ai_client.base_url}/health", timeout=2).raise_for_status()
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.fail(f"AI service is not reachable at {ai_client.base_url}: {exc}")


def resolve(question: str) -> dict:
    r = client.post("/api/policy-resolution/from-question", json={"question": question})
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def answered():
    """Ask one question through the full Backend -> AI Service path and return the response."""
    res = resolve("Does Margaret Chen have water backup coverage?")
    conv = client.post("/api/conversations", json={"policy_id": res["policy"]["policy_id"]}).json()
    marker = f"water backup coverage {uuid.uuid4().hex[:8]}"
    r = client.post(
        f"/api/conversations/{conv['conversation_id']}/questions",
        json={"question": f"Does this policy have {marker}?"},
    )
    assert r.status_code == 201
    return {"conversation_id": conv["conversation_id"], "marker": marker, "data": r.json()}


def test_resolution_by_customer_name():
    d = resolve("Does Margaret Chen have water backup coverage?")
    assert d["status"] == "resolved"
    assert d["matched_on"] == "customer_name"
    assert d["policy"]["policy_number"] == "HO-2847-1193"
    assert d["policy"]["status"] == "in_force"  # the current term, not the expired one


def test_resolution_by_policy_number():
    d = resolve("What is the deductible for HO-2847-1193?")
    assert d["status"] == "resolved" and d["matched_on"] == "policy_number"
    assert d["policy"]["policy_number"] == "HO-2847-1193"


def test_resolution_without_reference():
    assert resolve("What is the deductible?")["status"] == "no_reference"


def test_resolution_ambiguous_surname_returns_candidates():
    d = resolve("Does Chen have collision coverage?")
    assert d["status"] == "ambiguous"
    assert {c["customer_name"] for c in d["candidates"]} == {"Margaret Chen", "David Chen"}


def test_resolution_unknown_policy_number():
    assert resolve("Is HO-9999-0000 in force?")["status"] == "not_found"


def test_answer_carries_audit_fields(answered):
    d = answered["data"]
    assert d["status"] == "answered" and d["outcome"] == "answered"
    assert d["guardrail_status"] == "passed"
    assert {c["name"] for c in d["guardrail_checks"]} >= {"citations_verified", "cross_policy_leak", "premium_promise"}
    assert d["model_used"] and d["provider"]
    assert d["latency_ms"] is not None and d["ledger_id"]
    assert all(c["evidence_index"] for c in d["citations"])
    assert {"retrieval", "generation"} <= set(d["timings_ms"])


def test_conversation_messages_restore_recorded_answers(answered):
    r = client.get(f"/api/conversations/{answered['conversation_id']}/messages")
    assert r.status_code == 200
    messages = r.json()
    assert len(messages) == 1
    assert messages[0]["answer"]["answer"] == answered["data"]["answer"]
    assert messages[0]["answer"]["ledger_id"] == answered["data"]["ledger_id"]


def test_record_lists_and_details_the_entry(answered):
    page = client.get("/api/ledger", params={"search": answered["marker"]}).json()
    assert page["total"] == 1
    row = page["items"][0]
    assert row["id"] == answered["data"]["ledger_id"]
    assert row["insured"] == "Margaret Chen" and row["policy_number"] == "HO-2847-1193"
    assert row["policy_term"] == 2 and row["state"] == "TX" and row["line_of_business"] == "homeowners"
    assert row["outcome"] == "answered" and row["sources"]

    detail = client.get(f"/api/ledger/{row['id']}").json()
    assert detail["answer"] == answered["data"]["answer"]
    assert detail["guardrail_checks"] == answered["data"]["guardrail_checks"]
    assert len(detail["evidence"]) == len(answered["data"]["evidence"])


def test_record_filters_and_summary(answered):
    assert client.get("/api/ledger", params={"search": answered["marker"], "outcome": "needs_review"}).json()["total"] == 0
    assert client.get("/api/ledger", params={"search": answered["marker"], "line": "personal_auto"}).json()["total"] == 0
    summary = client.get("/api/ledger/summary").json()
    assert summary["answers_recorded"] >= 1
    assert summary["p95_response_ms"] is not None
    filters = client.get("/api/ledger/filters").json()
    assert "TX" in filters["states"] and "homeowners" in filters["lines"]
    assert client.get("/api/ledger/does-not-exist").status_code == 404


def test_source_viewer_returns_cited_clause(answered):
    clause_cite = next(c for c in answered["data"]["citations"] if c["source_type"] == "clause")
    doc = client.get(f"/api/sources/clause/{clause_cite['source_id']}").json()
    assert doc["form_number"] == clause_cite["form_number"]
    assert doc["form_title"]
    assert doc["pdf_available"] is False
    assert any(p["is_cited"] and p["source_id"] == clause_cite["source_id"] for p in doc["passages"])


def test_source_viewer_returns_coverage_schedule(answered):
    coverage = next(e for e in answered["data"]["evidence"] if e["source_type"] == "coverage")
    doc = client.get(f"/api/sources/coverage/{coverage['source_id']}").json()
    assert doc["record_fields"]["Limit"]
    assert client.get("/api/sources/clause/nope").status_code == 404
    assert client.get("/api/sources/unknown/x").status_code == 400


def test_ai_service_down_marks_question_failed(monkeypatch):
    res = resolve("Does Margaret Chen have water backup coverage?")
    conv = client.post("/api/conversations", json={"policy_id": res["policy"]["policy_id"]}).json()["conversation_id"]
    monkeypatch.setattr(ai_client, "base_url", "http://127.0.0.1:9")  # nothing listens here

    r = client.post(f"/api/conversations/{conv}/questions", json={"question": "Is water backup covered?"})
    assert r.status_code == 503
    assert "AI service is unavailable" in r.json()["detail"]

    history = client.get(f"/api/conversations/{conv}/questions").json()
    assert history[-1]["status"] == "failed"  # never left stuck in "processing"


def test_ledger_migration_is_idempotent():
    assert ensure_ledger_columns(engine) == []


# ---- Customer / portfolio questions (answered from policy records) ---------------------------

def ask(conversation_id: str, question: str) -> dict:
    r = client.post(f"/api/conversations/{conversation_id}/questions", json={"question": question})
    assert r.status_code == 201, r.text
    return r.json()


def test_resolution_reports_portfolio_intent():
    assert resolve("How many policies does Margaret Chen have?")["intent"] == "portfolio"
    assert resolve("What policies do we have?")["intent"] == "portfolio"
    assert resolve("Does Margaret Chen have water backup coverage?")["intent"] == "policy"
    assert resolve("Which policies cover water backup?")["intent"] == "policy"  # about wording, not a list


def test_customer_policy_count_without_context():
    conv = client.post("/api/conversations", json={}).json()["conversation_id"]
    d = ask(conv, "How many policies does Margaret Chen have?")
    assert d["answer_type"] == "portfolio" and d["status"] == "answered"
    assert d["model_used"] == "none" and d["guardrail_status"] == "not_applicable"
    numbers = {p["policy_number"] for p in d["portfolio"]["policies"]}
    assert numbers == {"HO-2847-1193", "PA-6120-7742"}  # current policies; spouse's not included
    assert d["answer"].startswith("Margaret Chen has 2 current policies")
    assert next(p for p in d["portfolio"]["policies"] if p["policy_number"] == "HO-2847-1193")["earlier_terms"] == 1


def test_portfolio_question_keeps_active_context():
    res = resolve("Does Margaret Chen have water backup coverage?")
    conv = client.post("/api/conversations", json={"policy_id": res["policy"]["policy_id"]}).json()["conversation_id"]
    d = ask(conv, "how many policies do Margaret Chen have ?")
    assert d["answer_type"] == "portfolio"
    assert client.get(f"/api/conversations/{conv}").json()["policy_context"]["policy_number"] == "HO-2847-1193"


def test_whole_book_and_filters():
    conv = client.post("/api/conversations", json={}).json()["conversation_id"]
    book = ask(conv, "What policies do we have?")
    assert book["portfolio"]["scope"] == "book"
    assert len(book["portfolio"]["policies"]) == 9  # 10 policy rows, one is an earlier term
    auto = ask(conv, "Which customers have auto policies?")
    assert {p["line_of_business"] for p in auto["portfolio"]["policies"]} == {"personal_auto"}
    texas = ask(conv, "How many policies are in Texas?")
    assert {p["state"] for p in texas["portfolio"]["policies"]} == {"TX"}


def test_household_only_when_asked():
    conv = client.post("/api/conversations", json={}).json()["conversation_id"]
    d = ask(conv, "What policies does the Chen household have?")
    assert d["portfolio"]["scope"] == "household"
    assert "PA-6120-7741" in {p["policy_number"] for p in d["portfolio"]["policies"]}


def test_unknown_policyholder_is_not_answered_with_whole_book():
    conv = client.post("/api/conversations", json={}).json()["conversation_id"]
    d = ask(conv, "How many policies does John Smith have?")
    assert d["portfolio"]["scope"] == "not_found" and d["portfolio"]["policies"] == []
    assert d["outcome"] == "insufficient_evidence"
    assert "John Smith" in d["answer"]


def test_portfolio_answer_is_recorded_and_restorable():
    conv = client.post("/api/conversations", json={}).json()["conversation_id"]
    marker = uuid.uuid4().hex[:6]
    d = ask(conv, f"How many policies does Priya Raghavan have? {marker}")
    row = client.get("/api/ledger", params={"search": marker}).json()["items"][0]
    assert row["id"] == d["ledger_id"]
    assert row["answer_type"] == "portfolio" and row["policy_id"] is None
    assert row["insured"] == "Priya Raghavan" and row["outcome"] == "answered"
    restored = client.get(f"/api/conversations/{conv}/messages").json()[0]["answer"]
    assert restored["answer_type"] == "portfolio" and restored["portfolio"]["policies"][0]["policy_number"] == "HO-3310-8821"
    policy_src = client.get(f"/api/sources/policy/{d['evidence'][0]['source_id']}").json()
    assert policy_src["policy_number"] == "HO-3310-8821"
