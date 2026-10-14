"""Company guidance: approved articles searched next to the policy wording, shown apart from the answer."""

import uuid
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import app.api.routes.conversations as conversation_routes
from app.db.database import SessionLocal
from app.main import app
from app.models.policy import CorePolicy
from app.schemas.explainer import AIServiceResponse
from app.services.ai_client import ai_client
from app.services.company_guidance import find_guidance, matched_keywords

client = TestClient(app)


def _policy(db, number):
    return db.query(CorePolicy).filter(CorePolicy.policy_number == number).order_by(CorePolicy.term_number.desc()).first()


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.mark.parametrize(
    "number, question, titles",
    [
        (
            "HO-2847-1193",
            "My basement flooded because the sewer backed up. Is that covered?",
            ["Water backup and sump overflow cover", "Water damage: what is covered and what is not"],
        ),
        ("HO-2847-1193", "Why is my wind deductible a percentage?", ["Wind and hail: why the deductible is a percentage"]),
        ("PA-5518-0042", "I hit a deer, is that collision or comprehensive?", ["Collision and comprehensive: which one applies"]),
        ("PA-5518-0042", "Who is the adjuster?", []),
        ("HO-2847-1193", "What is the deductible on HO-2847-1193?", []),  # one keyword is not enough
    ],
)
def test_articles_match_on_their_keywords(db, number, question, titles):
    assert [a["title"] for a in find_guidance(question, _policy(db, number), db)] == titles


def test_articles_for_another_line_of_business_are_not_offered(db):
    # Collision/comprehensive is an auto article: a homeowners policy never gets it.
    assert find_guidance("Is hitting a deer collision or comprehensive?", _policy(db, "HO-2847-1193"), db) == []


def test_a_state_programme_applies_only_in_its_state(db):
    question = "The house is not habitable after the storm, will you pay for a hotel?"
    assert [a["title"] for a in find_guidance(question, _policy(db, "HO-2847-1193"), db)] == [
        "Emergency accommodation during a named storm event"
    ]  # TX
    assert find_guidance(question, _policy(db, "HO-3310-8821"), db) == []  # NY


def test_a_keyword_inside_a_longer_one_counts_once():
    assert matched_keywords("is it covered?", ["covered", "is it covered"]) == ["is it covered"]


def test_articles_carry_the_approved_text_and_a_g_reference(db):
    article = find_guidance("Why is my wind deductible a percentage?", _policy(db, "HO-2847-1193"), db)[0]
    assert article["ref"] == "G1"
    assert article["body"].startswith("In states exposed to severe convective storms")
    assert article["spoken"].startswith("Wind and hail runs on a percentage")
    assert article["matched_on"] == ["wind", "deductible", "percentage"]


@pytest.fixture
def session(monkeypatch):
    reply = {"answer": "Sewer back-up is covered by endorsement HO 04 95 [E1].", "status": "answered"}

    def explain(question, policy_id, **kwargs):
        return AIServiceResponse(
            question=question, answer=reply["answer"], confidence="medium", status=reply["status"],
            evidence=[] if reply["status"] != "answered" else [
                {"source_type": "clause", "source_id": "c-wb", "title": "Water back-up", "content": "...",
                 "relevance_score": 14.0, "form_number": "HO 04 95", "page": 1, "evidence_index": 1}],
            citations=[] if reply["status"] != "answered" else [
                {"source_id": "c-wb", "source_type": "clause", "evidence_index": 1, "form_number": "HO 04 95"}],
            guardrail_status="passed",
            guardrail_checks=[{"name": "inline_citations", "status": "passed", "detail": "1 inline reference."}],
        )

    monkeypatch.setattr(ai_client, "explain", explain)
    monkeypatch.setattr(ai_client, "interpret", lambda *a, **k: None)
    monkeypatch.setattr(conversation_routes, "interpret_question", lambda *a, **k: None)
    headers = {"X-Employee-Id": f"EMP-GUIDE-{uuid.uuid4().hex[:6]}", "X-Employee-Name": quote("Guide Tester"), "X-Employee-Role": "csr"}
    made: list[str] = []
    yield headers, made, reply
    for conv in made:  # ledger entries are audit records: archive, never delete
        client.post(f"/api/conversations/{conv}/archive", headers=headers)


def ask(session, policy_number: str, question: str) -> dict:
    headers, made, _ = session
    pid = client.post("/api/policy-resolution/from-question", json={"question": policy_number}, headers=headers).json()["policy"]["policy_id"]
    conv = client.post("/api/conversations", json={}, headers=headers).json()["conversation_id"]
    made.append(conv)
    res = client.post(f"/api/conversations/{conv}/questions", json={"question": question, "policy_id": pid}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


SEWER = "My basement flooded because the sewer backed up. Is that covered?"


def test_guidance_is_shown_beside_the_policy_answer_not_inside_it(session):
    body = ask(session, "HO-2847-1193", SEWER)
    guidance = body["retrieval"]["company_guidance"]
    assert guidance["searched"] is True
    assert [a["ref"] for a in guidance["articles"]] == ["G1", "G2"]
    assert body["answer"] == "Sewer back-up is covered by endorsement HO 04 95 [E1]."  # unchanged by guidance
    assert all(e["source_type"] != "knowledge" for e in body["evidence"])
    check = next(c for c in body["guardrail_checks"] if c["name"] == "guidance_not_overriding_form")
    assert check["status"] == "passed"
    assert body["outcome"] == "answered"


def test_an_answer_that_cites_guidance_is_flagged_for_review(session):
    _, _, reply = session
    reply["answer"] = "Sewer back-up is covered [G1]."
    body = ask(session, "HO-2847-1193", SEWER)
    check = next(c for c in body["guardrail_checks"] if c["name"] == "guidance_not_overriding_form")
    assert check["status"] == "failed"
    assert body["guardrail_status"] == "flagged"
    assert body["outcome"] == "needs_review"


def test_a_withheld_answer_gets_no_guidance(session):
    _, _, reply = session
    reply.update(answer="The policy wording does not answer this.", status="insufficient_evidence")
    body = ask(session, "HO-2847-1193", SEWER)
    assert body["retrieval"]["company_guidance"]["articles"] == []
    assert not any(c["name"] == "guidance_not_overriding_form" for c in body["guardrail_checks"])


def test_record_answers_get_guidance_too_and_reopening_keeps_it(session):
    headers, made, _ = session
    body = ask(session, "HO-2847-1193", "What is the wind deductible on HO-2847-1193?")
    assert body["retrieval"]["answer_type"] == "factual_lookup"
    assert [a["title"] for a in body["retrieval"]["company_guidance"]["articles"]] == [
        "Wind and hail: why the deductible is a percentage"
    ]
    stored = client.get(f"/api/conversations/{made[-1]}/messages", headers=headers).json()[-1]["answer"]
    assert stored["retrieval"]["company_guidance"] == body["retrieval"]["company_guidance"]


def test_no_matching_article_means_no_guidance(session):
    body = ask(session, "PA-5518-0042", "Who is the adjuster on PA-5518-0042?")
    assert body["retrieval"]["company_guidance"] == {"searched": True, "articles": []}
