"""'Explain in plain words' on a cited clause: an AI explanation, labelled, never invented when unavailable."""

import pytest
from fastapi.testclient import TestClient

import app.api.routes.sources as source_routes
from app.db.database import SessionLocal
from app.main import app
from app.models.policy import Clause
from app.services.ai_client import ai_client

client = TestClient(app)


@pytest.fixture
def clause_id():
    db = SessionLocal()
    try:
        return db.query(Clause).filter(Clause.heading == "Accidental Discharge Or Overflow Of Water Or Steam").first().id
    finally:
        db.close()


@pytest.fixture
def calls(monkeypatch):
    seen: list[dict] = []
    reply = {"status": "explained", "explanation": "This clause covers water that suddenly escapes from plumbing.",
             "model_used": "openai/gpt-oss-120b", "provider": "groq"}

    def plain_language(heading, form_number, text):
        seen.append({"heading": heading, "form_number": form_number, "text": text})
        return dict(reply)

    monkeypatch.setattr(ai_client, "plain_language", plain_language)
    monkeypatch.setattr(source_routes, "_EXPLAINED", {})
    yield seen, reply


def test_the_clause_text_is_explained_and_labelled_apart_from_approved_wording(clause_id, calls):
    seen, _ = calls
    res = client.post(f"/api/sources/clause/{clause_id}/plain-language")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "explained"
    assert body["explanation"].startswith("This clause covers water")
    assert body["approved_plain_language"]  # the carrier's own explanation is returned separately
    # The model is given that clause's own wording and nothing else.
    assert seen[0]["form_number"] == "HO 00 03" and seen[0]["heading"] == "Accidental Discharge Or Overflow Of Water Or Steam"


def test_a_clause_is_explained_once(clause_id, calls):
    seen, _ = calls
    client.post(f"/api/sources/clause/{clause_id}/plain-language")
    client.post(f"/api/sources/clause/{clause_id}/plain-language")
    assert len(seen) == 1


def test_when_the_model_is_unavailable_nothing_is_invented_and_a_retry_is_possible(clause_id, calls):
    seen, reply = calls
    reply.clear()
    reply.update(status="unavailable", reason="The language model is not available right now (it may be busy). Try again in a moment.")
    first = client.post(f"/api/sources/clause/{clause_id}/plain-language").json()
    assert first["status"] == "unavailable" and first["explanation"] == ""
    client.post(f"/api/sources/clause/{clause_id}/plain-language")
    assert len(seen) == 2  # not cached


def test_unknown_clause_and_blocked_roles(clause_id, calls):
    assert client.post("/api/sources/clause/no-such-clause/plain-language").status_code == 404
    blocked = {"X-Employee-Id": "EMP-BLOCKED", "X-Employee-Role": "suspended"}
    assert client.post(f"/api/sources/clause/{clause_id}/plain-language", headers=blocked).status_code == 403
