"""Find the policy from a claim number, account number, email, phone, VIN, plate, address or vehicle."""

from urllib.parse import quote

import pytest
from app.db.database import SessionLocal
from app.services.policy_resolver import resolve_policy_from_question


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def resolved(question: str, db) -> tuple[str, str, list[str]]:
    r = resolve_policy_from_question(question, db)
    numbers = [r.policy.policy_number] if r.policy else sorted(c.policy_number for c in r.candidates)
    return r.status, r.matched_on, numbers


@pytest.mark.parametrize(
    "question, matched_on, numbers",
    [
        ("What is the status of claim CLM-2026-00417?", "claim_number", ["PA-5518-0042"]),
        ("claim clm 2026 417 - who is the adjuster?", "claim_number", ["PA-5518-0042"]),
        ("Caller at (716) 555-0193 wants to know their coverage", "phone", ["HO-3310-8821"]),
        ("caller 512-555-0266 about the car", "phone", ["PA-5518-0042"]),
        ("VIN JTMRWRFV8ND512884 - is collision covered?", "vin", ["PA-5518-0042"]),
        ("Plate TX KLM4418, what is the deductible?", "plate", ["PA-5518-0042"]),
        ("plate KLM4418", "plate", ["PA-5518-0042"]),
        ("What is the deductible at 1408 Wilshire Bend?", "address", ["HO-2847-1193"]),
        ("Does 4 Alderbrook Court have water backup?", "address", ["HO-9021-4477"]),
        ("Is the RAV4 covered for rental?", "vehicle", ["PA-5518-0042"]),
        ("Does the Lexus RX 350 have comprehensive?", "vehicle", ["PA-6120-7742"]),
        ("What does the 2018 Honda Civic cover?", "vehicle", ["PA-5518-0042"]),
        ("Does Elena Moreau's Volvo have roadside?", "vehicle", ["PA-8830-2215"]),
    ],
)
def test_identifier_opens_the_right_policy(question, matched_on, numbers, db):
    assert resolved(question, db) == ("resolved", matched_on, numbers)


def test_customer_identifiers_find_all_their_policies(db):
    # An email or account number names a customer; a customer with home and auto gets both.
    assert resolved("margaret.chen@example.com asked about her deductible", db) == (
        "ambiguous", "email", ["HO-2847-1193", "PA-6120-7742"],
    )
    assert resolved("Customer is ACCT-100455, when is the bill due?", db) == (
        "ambiguous", "account_number", ["HO-9021-4477", "PA-8830-2215"],
    )


def test_shared_address_with_a_car_hint_asks(db):
    # Margaret and David Chen both garage a car at 1408 Wilshire Bend.
    status, matched_on, numbers = resolved("Does the car at 1408 Wilshire Bend have collision?", db)
    assert (status, matched_on, numbers) == ("ambiguous", "address", ["PA-6120-7741", "PA-6120-7742"])


def test_a_named_customer_is_never_given_someone_elses_vehicle(db):
    # Elena Moreau has no Toyota; Daniel Ortiz does. The name decides, not Daniel's car.
    status, matched_on, numbers = resolved("Is Elena's Toyota covered?", db)
    assert "PA-5518-0042" not in numbers
    assert numbers == ["HO-9021-4477", "PA-8830-2215"]


@pytest.mark.parametrize(
    "question",
    ["What about 2 policies with a $500 deductible?", "Is water backup covered for 30 days?", "What is the deductible?"],
)
def test_amounts_and_counts_are_not_identifiers(question, db):
    assert resolved(question, db)[0] == "no_reference"


def test_unknown_identifier_is_reported_not_guessed(db):
    status, matched_on, numbers = resolved("Unknown claim CLM-2026-99999", db)
    assert (status, matched_on, numbers) == ("not_found", "claim_number", [])
    assert resolved("Customer phone (999) 555-0000", db)[:2] == ("not_found", "phone")


def test_from_question_endpoint_reports_the_identifier(monkeypatch):
    # Imported here so the resolver tests above run without starting the whole app.
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.ai_client import ai_client

    client = TestClient(app)
    monkeypatch.setattr(ai_client, "interpret", lambda *a, **k: None)
    headers = {"X-Employee-Id": "EMP-ID-01", "X-Employee-Name": quote("Test Agent"), "X-Employee-Role": "csr"}
    body = client.post(
        "/api/policy-resolution/from-question",
        json={"question": "Who is the adjuster on CLM-2026-00417?"},
        headers=headers,
    ).json()
    assert body["status"] == "resolved" and body["matched_on"] == "claim_number"
    assert body["policy"]["policy_number"] == "PA-5518-0042"
    # A customer identifier with several policies is answered for each (feature 1).
    body = client.post(
        "/api/policy-resolution/from-question",
        json={"question": "elena.moreau@example.com - any deductibles?"},
        headers=headers,
    ).json()
    assert body["status"] == "ambiguous" and body["answer_all"] is True


def test_exact_identifiers_survive_the_interpreter_rewriting_them(monkeypatch):
    """The language model may rewrite an email or claim number; the lookup uses what was typed."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.ai_client import ai_client

    rewrites = {
        "margaret.chen@example.com asked about her deductible": "Margaret Chen asked about her deductible.",
        "Who is the adjuster on CLM-2026-00417?": "Who is the adjuster on claim CLM 2026?",
    }

    def interpret(question, previous=None):
        text = rewrites.get(question, question)
        return {"original": question, "corrected": text, "normalized": text, "method": "llm", "intent": "policy",
                "policyholders": [], "policy_numbers": [], "search_terms": [], "corrections": [], "latency_ms": 1}

    monkeypatch.setattr(ai_client, "interpret", interpret)
    client = TestClient(app)
    headers = {"X-Employee-Id": "EMP-ID-02", "X-Employee-Name": quote("Test Agent"), "X-Employee-Role": "csr"}

    body = client.post("/api/policy-resolution/from-question",
                       json={"question": "margaret.chen@example.com asked about her deductible"}, headers=headers).json()
    assert body["matched_on"] == "email" and body["answer_all"] is True
    assert sorted(c["policy_number"] for c in body["candidates"]) == ["HO-2847-1193", "PA-6120-7742"]

    body = client.post("/api/policy-resolution/from-question",
                       json={"question": "Who is the adjuster on CLM-2026-00417?"}, headers=headers).json()
    assert body["matched_on"] == "claim_number" and body["policy"]["policy_number"] == "PA-5518-0042"
