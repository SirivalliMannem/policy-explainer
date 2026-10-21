"""Answer several facts in one reply: split the question, answer each part from its source, combine."""

import uuid
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import app.api.routes.conversations as conversation_routes
from app.main import app
from app.schemas.explainer import AIServiceResponse
from app.services.ai_client import ai_client
from app.services.multi_part import split_question

client = TestClient(app)


@pytest.mark.parametrize(
    "question, expected",
    [
        (
            "What is the water backup deductible, which endorsement provides it, and is there an open claim?",
            [("Deductible", "records"), ("Endorsement", "forms"), ("Claims", "records")],
        ),
        (
            "What is the collision deductible, is there an open claim, and who is the adjuster?",
            [("Deductible", "records"), ("Claims", "records"), ("Assigned adjuster", "records")],
        ),
        ("What is the premium? When is the next bill due?", [("Premium", "records"), ("Next bill", "records")]),
        (
            "What is the wind deductible and does it cover hail damage to the roof?",
            [("Deductible", "records"), ("What the policy wording says", "wording")],
        ),
    ],
)
def test_questions_split_into_their_parts(question, expected):
    assert [(p.label, p.source) for p in split_question(question)] == expected


def test_a_part_that_says_it_borrows_the_coverage_named_elsewhere():
    parts = split_question("What is the water backup deductible, which endorsement provides it, and is there an open claim?")
    assert parts[1].text == "which endorsement provides water backup"


@pytest.mark.parametrize(
    "question",
    [
        "What is the limit and deductible for water backup?",  # one fact about one coverage
        "Is water backup covered?",
        "What is the deductible on HO-2847-1193?",
        "Does the policy cover mold, wear and tear, or vermin?",  # one wording question listing perils
    ],
)
def test_single_questions_are_not_split(question):
    assert split_question(question) == []


@pytest.fixture
def session(monkeypatch):
    asked: list[str] = []

    def explain(question, policy_id, **kwargs):
        asked.append(question)
        return AIServiceResponse(
            question=question, answer="Hail is a covered peril under the windstorm or hail wording [E1].",
            confidence="medium", status="answered",
            evidence=[{"source_type": "clause", "source_id": "c-hail", "title": "Windstorm or hail", "content": "...",
                       "relevance_score": 15.0, "form_number": "HO 00 03", "page": 9, "evidence_index": 1}],
            citations=[{"source_id": "c-hail", "source_type": "clause", "evidence_index": 1, "form_number": "HO 00 03"}],
            guardrail_status="passed",
            guardrail_checks=[{"name": "inline_citations", "status": "passed", "detail": "1 inline reference."}],
        )

    monkeypatch.setattr(ai_client, "explain", explain)
    monkeypatch.setattr(ai_client, "interpret", lambda *a, **k: None)
    monkeypatch.setattr(conversation_routes, "interpret_question", lambda *a, **k: None)
    emp = f"EMP-MULTI-{uuid.uuid4().hex[:6]}"
    headers = {"X-Employee-Id": emp, "X-Employee-Name": quote("Multi Tester"), "X-Employee-Role": "csr"}
    made: list[str] = []
    yield headers, made, asked
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


def test_deductible_endorsement_and_claim_in_one_reply_each_with_its_source(session):
    _, _, asked = session
    body = ask(session, "HO-2847-1193", "What is the water backup deductible, which endorsement provides it, and is there an open claim?")
    assert asked == [], "facts and endorsements come from the records, not the language model"
    answer = body["answer"]
    assert "**Deductible:** For policy HO-2847-1193, the deductible for Water Back-Up and Sump Overflow is $500 [E1]." in answer
    assert "**Endorsement:** Water Back-Up and Sump Overflow is provided by endorsement HO 04 95" in answer and "[E2]" in answer
    assert "**Claims:** The available records do not contain any claims on file for policy HO-2847-1193." in answer
    # Each fact has its own source.
    assert [(e["evidence_index"], e["source_type"]) for e in body["evidence"]] == [(1, "coverage"), (2, "form")]
    assert [c["evidence_index"] for c in body["citations"]] == [1, 2]
    assert [p["label"] for p in body["retrieval"]["parts"]] == ["Deductible", "Endorsement", "Claims"]


def test_three_record_facts_from_the_auto_policy(session):
    body = ask(session, "PA-5518-0042", "What is the collision deductible, is there an open claim, and who is the adjuster?")
    assert "$1,000 [E1]" in body["answer"]
    assert "Claim CLM-2026-00417 on policy PA-5518-0042 is currently open" in body["answer"]
    assert "R. Villanueva" in body["answer"]
    assert [e["source_type"] for e in body["evidence"]] == ["coverage", "claim", "claim"]


def test_only_the_wording_part_goes_to_the_language_model(session):
    _, _, asked = session
    body = ask(session, "HO-2847-1193", "What is the wind deductible and does it cover hail damage to the roof?")
    assert asked == ["does it cover hail damage to the roof?"]
    assert "**Deductible:** For policy HO-2847-1193, the deductible for Windstorm or Hail Deductible is 2% of Coverage A [E1]." in body["answer"]
    # The model's [E1] is renumbered after the record fact, so each keeps its own source.
    assert "**What the policy wording says:** Hail is a covered peril under the windstorm or hail wording [E2]." in body["answer"]
    assert [(e["evidence_index"], e["source_type"]) for e in body["evidence"]] == [(1, "coverage"), (2, "clause")]
    assert body["retrieval"]["answer_type"] == "multi_part"
    assert body["evidence"][0]["scope"] == "policy_record"


def test_reopening_shows_the_same_combined_reply(session):
    headers, made, _ = session
    body = ask(session, "HO-2847-1193", "What is the premium? When is the next bill due?")
    stored = client.get(f"/api/conversations/{made[-1]}/messages", headers=headers).json()[-1]["answer"]
    assert stored["answer"] == body["answer"]
    assert stored["retrieval"]["parts"] == body["retrieval"]["parts"]
