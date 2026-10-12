"""Per-employee conversation history, archiving, and history read from stored data only.

These tests write their own conversations and ledger rows and make no AI service calls, so they
run without the AI service. Every AI client entry point is patched to fail if it is reached.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.api.routes import conversations as conversation_routes
from app.db.database import SessionLocal
from app.main import app
from app.models.conversation import Conversation, ConversationQuestion
from app.models.ledger import EvidenceLedger
from app.models.policy import CorePolicy
from app.services.ai_client import ai_client

client = TestClient(app)


def headers(employee_id: str, name: str = "Test Agent", role: str = "csr") -> dict:
    return {"X-Employee-Id": employee_id, "X-Employee-Name": name, "X-Employee-Role": role}


@pytest.fixture
def no_ai(monkeypatch):
    """Fail the test if anything tries to reach the AI service."""
    def forbidden(*_args, **_kwargs):
        raise AssertionError("history must be read from stored data, not the AI service")

    monkeypatch.setattr(ai_client, "explain", forbidden)
    monkeypatch.setattr(ai_client, "interpret", forbidden)
    monkeypatch.setattr(conversation_routes, "interpret_question", forbidden)


@pytest.fixture
def seeded():
    """Two employees, each with a stored conversation (question + ledger answer). Removed afterwards."""
    db = SessionLocal()
    run = uuid.uuid4().hex[:8]
    policy = (
        db.query(CorePolicy).filter(CorePolicy.policy_number == "HO-2847-1193")
        .order_by(CorePolicy.term_number.desc()).first()
    )
    now = datetime.utcnow()
    made = {"conversations": [], "questions": [], "entries": [], "run": run, "policy": policy.policy_number}

    def make(employee_id: str, name: str, role: str, questions: list[str], outcome: str = "answered"):
        conv = Conversation(employee_id=employee_id, policy_id=policy.id, created_at=now, updated_at=now)
        db.add(conv)
        db.flush()
        for i, text in enumerate(questions):
            q = ConversationQuestion(
                conversation_id=conv.id, policy_id=policy.id, question=text,
                status="answered", created_at=now + timedelta(seconds=i),
            )
            db.add(q)
            db.flush()
            entry = EvidenceLedger(
                conversation_id=conv.id, question_id=q.id, policy_id=policy.id, question=text,
                retrieved_evidence=[{"source_type": "clause", "source_id": "c1", "title": "Water back-up",
                                     "content": "We will pay up to $5,000 for water back-up.", "form_number": "HO 04 95",
                                     "page": 1, "heading": "Coverage"}],
                grounding_context="ctx", raw_llm_response="raw", final_answer=f"Stored answer {run} {i}",
                citations=[{"source_id": "c1", "source_type": "clause", "evidence_index": 1,
                            "form_number": "HO 04 95", "page": 1, "heading": "Coverage", "citation_text": "HO 04 95"}],
                confidence="high", guardrail_status="passed", suggested_questions=[],
                employee_id=employee_id, employee_name=name, employee_role=role, outcome=outcome,
                guardrail_checks=[{"name": "evidence_grounded", "status": "passed", "detail": "ok"}],
                model_used="test-model", provider="test", is_fallback=False, latency_ms=1200,
                timings_ms={"retrieval": 40, "grounding": 5, "generation": 1100, "validation": 3},
                retrieval={"clauses_searched": 47, "coverages_searched": 6, "forms_searched": 4},
                created_at=now + timedelta(seconds=i),
            )
            db.add(entry)
            db.flush()
            made["questions"].append(q.id)
            made["entries"].append(entry.id)
        made["conversations"].append(conv.id)
        return conv.id

    made["emp_a"], made["emp_b"] = f"EMP-A-{run}", f"EMP-B-{run}"
    made["conv_a"] = make(made["emp_a"], "Agent Alpha", "csr",
                          [f"Does this homeowners policy cover water backup from a sump pump {run}?",
                           "What is the limit for that coverage?"])
    made["conv_b"] = make(made["emp_b"], "Agent Beta", "adjuster", [f"What is the wind deductible {run}?"],
                          outcome="needs_review")
    db.commit()
    yield made

    # Test fixtures only: remove the rows this test created.
    db.query(EvidenceLedger).filter(EvidenceLedger.id.in_(made["entries"])).delete(synchronize_session=False)
    db.query(ConversationQuestion).filter(ConversationQuestion.id.in_(made["questions"])).delete(synchronize_session=False)
    db.query(Conversation).filter(Conversation.id.in_(made["conversations"])).delete(synchronize_session=False)
    db.commit()
    db.close()


def listed(employee_id: str, **params) -> list[dict]:
    res = client.get("/api/conversations", params=params, headers=headers(employee_id))
    assert res.status_code == 200, res.text
    return res.json()["items"]


def test_lists_only_the_current_employees_conversations(seeded, no_ai):
    a_ids = [c["conversation_id"] for c in listed(seeded["emp_a"])]
    b_ids = [c["conversation_id"] for c in listed(seeded["emp_b"])]
    assert a_ids == [seeded["conv_a"]]
    assert b_ids == [seeded["conv_b"]]
    # Without an identity, neither test employee's conversations are visible.
    anonymous = client.get("/api/conversations").json()["items"]
    assert not {seeded["conv_a"], seeded["conv_b"]} & {c["conversation_id"] for c in anonymous}

    item = listed(seeded["emp_a"])[0]
    assert item["title"].startswith("Does this homeowners policy") and len(item["title"]) <= 41
    assert item["title"].endswith("…")
    assert item["asked_by"] == {"employee_id": seeded["emp_a"], "name": "Agent Alpha", "role": "csr"}
    assert item["policy_number"] == seeded["policy"] and item["question_count"] == 2
    assert item["latest_outcome"] == "answered"
    assert listed(seeded["emp_b"])[0]["latest_outcome"] == "needs_review"


def test_search_matches_the_title(seeded, no_ai):
    assert [c["conversation_id"] for c in listed(seeded["emp_a"], search="SUMP PUMP")] == [seeded["conv_a"]]
    assert listed(seeded["emp_a"], search="wind deductible") == []  # employee B's title


def test_another_employees_conversation_is_not_found(seeded, no_ai):
    conv = seeded["conv_a"]
    other = headers(seeded["emp_b"])
    assert client.get(f"/api/conversations/{conv}", headers=other).status_code == 404
    assert client.get(f"/api/conversations/{conv}/messages", headers=other).status_code == 404
    assert client.get(f"/api/conversations/{conv}/questions", headers=other).status_code == 404
    assert client.post(f"/api/conversations/{conv}/archive", headers=other).status_code == 404
    assert client.delete(f"/api/conversations/{conv}/context", headers=other).status_code == 404
    assert client.post(f"/api/conversations/{conv}/questions", json={"question": "Is it covered?"},
                       headers=other).status_code == 404
    recent = client.get("/api/conversations/recent", headers=other).json()
    assert all(r["conversation_id"] != conv for r in recent)
    # The owner still sees it.
    assert client.get(f"/api/conversations/{conv}", headers=headers(seeded["emp_a"])).status_code == 200


def test_archive_hides_from_lists_and_keeps_the_ledger(seeded, no_ai):
    conv = seeded["conv_a"]
    owner = headers(seeded["emp_a"])
    res = client.post(f"/api/conversations/{conv}/archive", headers=owner)
    assert res.status_code == 200 and res.json()["is_archived"] and res.json()["archived_at"]

    assert listed(seeded["emp_a"]) == []
    assert all(r["conversation_id"] != conv for r in client.get("/api/conversations/recent", headers=owner).json())

    # Nothing deleted: the conversation and every ledger entry remain, and The Record still shows them.
    db = SessionLocal()
    try:
        stored = db.get(Conversation, conv)
        assert stored is not None and stored.is_archived and stored.archived_at is not None
        assert db.query(EvidenceLedger).filter(EvidenceLedger.conversation_id == conv).count() == 2
    finally:
        db.close()
    for entry_id in seeded["entries"][:2]:
        assert client.get(f"/api/ledger/{entry_id}").status_code == 200
    record = client.get("/api/ledger", params={"search": seeded["run"], "limit": 50}).json()
    assert {seeded["entries"][0], seeded["entries"][1]} <= {r["id"] for r in record["items"]}
    # Archiving twice is harmless.
    assert client.post(f"/api/conversations/{conv}/archive", headers=owner).status_code == 200


def test_history_is_read_from_stored_data_without_the_ai_service(seeded, no_ai):
    owner = headers(seeded["emp_a"])
    conv = seeded["conv_a"]
    messages = client.get(f"/api/conversations/{conv}/messages", headers=owner)
    assert messages.status_code == 200
    first = messages.json()[0]
    assert first["asked_by"]["name"] == "Agent Alpha"
    answer = first["answer"]
    assert answer["answer"] == f"Stored answer {seeded['run']} 0"
    assert answer["ledger_id"] == seeded["entries"][0]
    assert answer["timings_ms"]["generation"] == 1100 and answer["citations"][0]["form_number"] == "HO 04 95"
    assert answer["asked_by"] == {"employee_id": seeded["emp_a"], "name": "Agent Alpha", "role": "csr"}
    assert answer["guardrail_status"] == "passed"
    # Everything the "How this was answered" panel shows comes back from storage.
    assert answer["evidence"][0]["form_number"] == "HO 04 95" and "relevance_score" in answer["evidence"][0]
    assert answer["retrieval"]["clauses_searched"] == 47 and answer["retrieval"]["forms_searched"] == 4
    assert answer["grounding_context_chars"] == len("ctx")
    assert answer["model_used"] == "test-model"
    assert answer["guardrail_checks"] == [{"name": "evidence_grounded", "status": "passed", "detail": "ok"}]
    assert client.get(f"/api/conversations/{conv}", headers=owner).status_code == 200
    assert listed(seeded["emp_a"])  # the list endpoint is also storage-only


def test_ledger_records_the_askers_identity(monkeypatch):
    """A question answered from policy records (no AI) stamps name and role on its ledger entry."""
    monkeypatch.setattr(conversation_routes, "interpret_question", lambda *a, **k: None)
    emp = f"EMP-C-{uuid.uuid4().hex[:8]}"
    me = headers(emp, name="Agent Gamma", role="manager")
    conv = client.post("/api/conversations", json={}, headers=me).json()["conversation_id"]
    res = client.post(f"/api/conversations/{conv}/questions",
                      json={"question": "How many policies does Margaret Chen have?"}, headers=me)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["asked_by"] == {"employee_id": emp, "name": "Agent Gamma", "role": "manager"}
    entry = client.get(f"/api/ledger/{body['ledger_id']}").json()
    assert (entry["agent"], entry["agent_name"], entry["agent_role"]) == (emp, "Agent Gamma", "manager")
    # Ledger entries are permanent audit records: this one is archived away, not removed.
    client.post(f"/api/conversations/{conv}/archive", headers=me)
