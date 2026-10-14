"""Simple facts come straight from the records; the language model is used only for what wording means.

Each question is asked the way an employee would phrase it, and the test checks which path answered it:
the records (no model call), the language model, or both (a fact plus an explanation of its wording).
"""

import uuid
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import app.api.routes.conversations as conversation_routes
from app.main import app
from app.schemas.explainer import AIServiceResponse
from app.services.ai_client import ai_client

client = TestClient(app)
HEADERS = {"X-Employee-Id": f"EMP-FACT-{uuid.uuid4().hex[:6]}", "X-Employee-Name": quote("Fact Tester"), "X-Employee-Role": "csr"}
WORDING_ANSWER = "(explanation of the policy wording)"


@pytest.fixture(scope="module")
def setup():
    def policy_id(number: str) -> str:
        res = client.post("/api/policy-resolution/from-question", json={"question": number}, headers=HEADERS)
        return res.json()["policy"]["policy_id"]

    ids = {"HO": policy_id("HO-2847-1193"), "PA": policy_id("PA-5518-0042")}
    conv = client.post("/api/conversations", json={}, headers=HEADERS).json()["conversation_id"]
    yield conv, ids
    # Ledger entries are permanent audit records: archive the test conversation instead of deleting it.
    client.post(f"/api/conversations/{conv}/archive", headers=HEADERS)


@pytest.fixture
def model_calls(monkeypatch):
    calls: list[str] = []

    def explain(question, policy_id, **kwargs):
        calls.append(question)
        return AIServiceResponse(question=question, answer=WORDING_ANSWER, confidence="high", status="answered")

    monkeypatch.setattr(ai_client, "explain", explain)
    monkeypatch.setattr(ai_client, "interpret", lambda *a, **k: None)
    monkeypatch.setattr(conversation_routes, "interpret_question", lambda *a, **k: None)
    return calls


def ask(setup, policy: str, question: str) -> dict:
    conv, ids = setup
    res = client.post(f"/api/conversations/{conv}/questions", json={"question": question, "policy_id": ids[policy]}, headers=HEADERS)
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.parametrize(
    "policy, question, expected",
    [
        # Deductible
        ("PA", "What is the collision deductible?", "$1,000"),
        ("HO", "How much do I pay out of pocket for wind damage?", "2% of Coverage A"),
        # Limit
        ("HO", "What is the dwelling limit?", "$512,000"),
        ("HO", "How much coverage is there for personal property?", "$256,000"),
        ("HO", "What is the max payout for loss of use?", "$102,400"),
        # Premium
        ("PA", "What is the premium?", "$1,744.00"),
        ("HO", "How much does this policy cost per year?", "$2,685.00"),
        # Bill due
        ("PA", "When is the next bill due?", "2026-10-20"),
        ("PA", "Is the account past due?", "nothing is past due"),
        # Claim status
        ("PA", "What is the status of claim CLM-2026-00417?", "open"),
        ("PA", "Is claim CLM-2026-00417 still open?", "open"),
        # Assigned adjuster
        ("PA", "Who is the adjuster on CLM-2026-00417?", "R. Villanueva"),
        ("PA", "Who is handling the claim?", "R. Villanueva"),
        ("PA", "Who is assigned to my claim?", "R. Villanueva"),
    ],
)
def test_simple_facts_come_from_the_records(setup, model_calls, policy, question, expected):
    body = ask(setup, policy, question)
    assert model_calls == [], "a simple fact must not call the language model"
    assert expected in body["answer"]
    assert body["citations"], "a fact read from the records still cites the record"


@pytest.mark.parametrize(
    "policy, question",
    [
        ("HO", "Is water backup covered?"),
        ("HO", "What does the policy exclude for mold?"),
        ("PA", "Does collision cover a rental car?"),
        ("HO", "Why is the wind deductible a percentage?"),
    ],
)
def test_wording_questions_use_clause_search_and_the_model(setup, model_calls, policy, question):
    body = ask(setup, policy, question)
    assert model_calls == [question]
    # The explanation comes from the model; a fact the question names may be stated first from the records.
    assert body["answer"].endswith(WORDING_ANSWER)


def test_a_fact_with_a_wording_question_gets_both(setup, model_calls):
    body = ask(setup, "HO", "What is the wind deductible and how does it apply?")
    assert model_calls, "the wording part is explained by the model"
    assert body["answer"].startswith("For policy HO-2847-1193, the deductible for Windstorm or Hail")
    assert WORDING_ANSWER in body["answer"]
