"""Use the policy term in force on the date of loss, and say which term was used.

HO-2847-1193 (Margaret Chen) has two terms with different values:
  term 1  2025-03-01 to 2026-03-01  water back-up deductible $1,000, wind/hail 1% of Coverage A
  term 2  2026-03-01 to 2027-03-01  water back-up deductible $500,   wind/hail 2% of Coverage A
"""

import uuid
from datetime import date
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import app.api.routes.conversations as conversation_routes
from app.db.database import SessionLocal
from app.main import app
from app.schemas.explainer import AIServiceResponse
from app.services.ai_client import ai_client
from app.services.loss_date import extract_loss_date, term_in_force

client = TestClient(app)
TODAY = date(2026, 10, 14)


@pytest.mark.parametrize(
    "question, expected, assumed",
    [
        ("The basement flooded on 2025-11-03", date(2025, 11, 3), False),
        ("loss on 11/3/2025", date(2025, 11, 3), False),
        ("accident 11-03-25", date(2025, 11, 3), False),
        ("Hail damaged the roof on December 5, 2025", date(2025, 12, 5), False),
        ("stolen on 5 Dec 2025", date(2025, 12, 5), False),
        ("the fire happened on the 3rd of November 2025", date(2025, 11, 3), False),
        ("a pipe burst on Nov. 3rd, 2025", date(2025, 11, 3), False),
        ("water damage on March 3", date(2026, 3, 3), True),  # most recent March 3 before today
        ("the car was hit yesterday", date(2026, 10, 13), False),
    ],
)
def test_dates_are_read_as_typed(question, expected, assumed):
    loss = extract_loss_date(question, today=TODAY)
    assert loss is not None and loss.value == expected and loss.year_assumed is assumed


@pytest.mark.parametrize(
    "question",
    [
        "When is the next bill due on HO-2847-1193?",  # a billing date, not a loss
        "What is the premium due on 2026-10-20?",
        "What is the deductible on HO-2847-1193?",  # no date at all
        "Who is the adjuster on CLM-2026-00417?",  # a claim number is not a date
        "Caller at 512-555-0142",  # nor is a phone number
    ],
)
def test_no_loss_date(question):
    assert extract_loss_date(question, today=TODAY) is None


def test_term_boundaries():
    db = SessionLocal()
    try:
        assert term_in_force("HO-2847-1193", date(2025, 3, 1), db).term_number == 1  # first day of term 1
        assert term_in_force("HO-2847-1193", date(2026, 2, 28), db).term_number == 1
        assert term_in_force("HO-2847-1193", date(2026, 3, 1), db).term_number == 2  # renewal day belongs to term 2
        assert term_in_force("HO-2847-1193", date(2024, 1, 1), db) is None
    finally:
        db.close()


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(ai_client, "interpret", lambda *a, **k: None)
    monkeypatch.setattr(conversation_routes, "interpret_question", lambda *a, **k: None)
    monkeypatch.setattr(
        ai_client, "explain",
        lambda question, policy_id, **kw: AIServiceResponse(question=question, answer="(wording)", confidence="high", status="answered"),
    )
    emp = f"EMP-TERM-{uuid.uuid4().hex[:6]}"
    headers = {"X-Employee-Id": emp, "X-Employee-Name": quote("Term Tester"), "X-Employee-Role": "csr"}
    made = []
    yield headers, made
    for conv in made:  # ledger entries are audit records: archive, never delete
        client.post(f"/api/conversations/{conv}/archive", headers=headers)


def ask(setup, question: str) -> tuple[dict, dict]:
    headers, made = setup
    resolution = client.post("/api/policy-resolution/from-question", json={"question": question}, headers=headers).json()
    conv = client.post("/api/conversations", json={}, headers=headers).json()["conversation_id"]
    made.append(conv)
    answer = client.post(
        f"/api/conversations/{conv}/questions",
        json={"question": question, "policy_id": resolution["policy"]["policy_id"]},
        headers=headers,
    )
    assert answer.status_code == 201, answer.text
    return resolution, answer.json()


def test_a_loss_in_the_earlier_term_uses_that_term(setup):
    resolution, answer = ask(setup, "The basement of HO-2847-1193 flooded on 2025-11-03. What is the water backup deductible?")
    assert resolution["policy"]["status"] == "expired"  # term 1, not today's term
    assert resolution["term_selection"]["term_number"] == 1
    assert answer["answer"].startswith(
        "Using term 1 of HO-2847-1193 (March 1, 2025 – March 1, 2026), the term in force on the loss date, November 3, 2025."
    )
    assert "$1,000" in answer["answer"] and "$500" not in answer["answer"]
    assert answer["retrieval"]["term_selection"]["term_number"] == 1


def test_a_loss_in_the_current_term_uses_the_current_term(setup):
    resolution, answer = ask(setup, "What is the water backup deductible on HO-2847-1193 for a loss on 4/10/2026?")
    assert resolution["term_selection"]["term_number"] == 2
    assert "Using term 2 of HO-2847-1193" in answer["answer"] and "$500" in answer["answer"]


def test_a_customer_named_by_name_gets_the_term_for_the_loss_date(setup):
    resolution, answer = ask(setup, "Hail damaged Margaret Chen's roof on December 5, 2025. What is the wind deductible?")
    assert resolution["policy"]["policy_number"] == "HO-2847-1193" and resolution["term_selection"]["term_number"] == 1
    assert "1% of Coverage A" in answer["answer"]


def test_the_answer_step_corrects_the_term_even_if_another_was_selected(setup):
    """The conversation may have today's term selected; a dated question is still answered from the right term."""
    headers, made = setup
    current = client.post("/api/policy-resolution/from-question", json={"question": "HO-2847-1193"}, headers=headers).json()["policy"]
    assert current["status"] == "in_force"
    conv = client.post("/api/conversations", json={"policy_id": current["policy_id"]}, headers=headers).json()["conversation_id"]
    made.append(conv)
    answer = client.post(f"/api/conversations/{conv}/questions",
                         json={"question": "A storm caused damage on 2025-12-05. What is the wind deductible?"}, headers=headers).json()
    assert answer["retrieval"]["term_selection"]["term_number"] == 1
    assert "1% of Coverage A" in answer["answer"]


def test_no_term_in_force_is_reported_not_guessed(setup):
    headers, _ = setup
    resolution = client.post("/api/policy-resolution/from-question",
                             json={"question": "A pipe burst at HO-2847-1193 on 1 January 2024. What is the deductible?"},
                             headers=headers).json()
    term = resolution["term_selection"]
    assert term["status"] == "no_term"
    assert term["message"].startswith("No term of HO-2847-1193 was in force on the loss date, January 1, 2024.")
    assert "term 1: March 1, 2025 – March 1, 2026" in term["message"]


def test_questions_without_a_date_are_unchanged(setup):
    headers, _ = setup
    resolution = client.post("/api/policy-resolution/from-question",
                             json={"question": "What is the water backup deductible on HO-2847-1193?"}, headers=headers).json()
    assert resolution["term_selection"] is None and resolution["policy"]["status"] == "in_force"
