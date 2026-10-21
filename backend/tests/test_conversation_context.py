"""Multi-turn conversations: the conversation's customer carries follow-ups that name nobody.

"What are Elena's policies?" then "What are the exclusions?" needs no name; "the second one" picks a
listed policy; another customer asks to switch; an unknown name is never answered from the current
customer; a customer with no policies is said to have none.
"""

import uuid
from urllib.parse import quote

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

import app.api.routes.conversations as conversation_routes
from app.db.database import SessionLocal
from app.main import app
from app.models.conversation import ContextSwitchAudit
from app.models.policy import CoreAccount, CorePolicy
from app.services.ai_client import ai_client

client = TestClient(app)
EMP = "EMP-CONTEXT-01"
H = {"X-Employee-Id": EMP, "X-Employee-Name": quote("Context Tester"), "X-Employee-Role": "csr"}


@pytest.fixture(autouse=True)
def rules_only(monkeypatch):
    # Resolution must not depend on the language model.
    monkeypatch.setattr(ai_client, "interpret", lambda *a, **k: None)
    monkeypatch.setattr(conversation_routes, "interpret_question", lambda *a, **k: None)


@pytest.fixture(scope="module")
def ids():
    db = SessionLocal()
    try:
        def account(name):
            return db.query(CoreAccount).filter(CoreAccount.name == name).one().id

        def current(number):
            return (
                db.query(CorePolicy).filter(CorePolicy.policy_number == number, CorePolicy.status == "in_force").one().id
            )

        return {
            "elena": account("Elena Moreau"), "david": account("David Chen"),
            "elena_home": current("HO-9021-4477"), "elena_auto": current("PA-8830-2215"), "david_auto": current("PA-6120-7741"),
        }
    finally:
        db.close()


def new_conversation(policy_id=None):
    res = client.post("/api/conversations", json={"policy_id": policy_id} if policy_id else {}, headers=H)
    assert res.status_code == 201, res.text
    return res.json()["conversation_id"]


def ask(conv, question):
    res = client.post("/api/policy-resolution/from-question", json={"question": question, "conversation_id": conv}, headers=H)
    assert res.status_code == 200, res.text
    return res.json()


def numbers(r):
    return [c["policy_number"] for c in r["candidates"]]


def choose_customer(conv, customer_id, confirm=False):
    return client.post(f"/api/conversations/{conv}/context",
                       json={"customer_id": customer_id, "confirm_different_customer": confirm}, headers=H)


def test_follow_ups_after_listing_a_customers_policies_need_no_name(ids):
    conv = new_conversation()
    listed = ask(conv, "What are Elena's policies?")
    assert listed["intent"] == "portfolio" and listed["customer"]["customer_id"] == ids["elena"]
    assert choose_customer(conv, ids["elena"]).json()["customer_context"]["policy_count"] == 2

    exclusions = ask(conv, "What are the exclusions?")
    assert exclusions["from_context"] and exclusions["answer_all"]
    assert numbers(exclusions) == ["HO-9021-4477", "PA-8830-2215"]
    assert exclusions["customer_verification"]["status"] == "verified"
    assert exclusions["customer_verification"]["matched_on"] == "conversation"

    deductible = ask(conv, "What about the deductible?")
    assert deductible["from_context"] and numbers(deductible) == ["HO-9021-4477", "PA-8830-2215"]

    second = ask(conv, "What about the second one?")
    assert second["status"] == "resolved" and second["policy"]["policy_number"] == "PA-8830-2215"
    auto = ask(conv, "What are the limits on her auto policy?")
    assert auto["status"] == "resolved" and auto["policy"]["policy_number"] == "PA-8830-2215"


def test_she_and_another_policy_refer_to_the_conversations_customer(ids):
    conv = new_conversation(ids["elena_home"])
    another = ask(conv, "Does she have another policy?")
    assert another["intent"] == "portfolio" and another["from_context"]
    assert another["customer"]["customer_id"] == ids["elena"]
    # Answered from Elena's records, listing her policies, never the whole book.
    answer = client.post(f"/api/conversations/{conv}/questions", json={"question": "Does she have another policy?"}, headers=H).json()
    assert answer["answer_type"] == "portfolio"
    assert "Elena Moreau" in answer["answer"] and "PA-8830-2215" in answer["answer"]
    assert "David Chen" not in answer["answer"]

    other = ask(conv, "What about her other policy?")
    assert other["status"] == "resolved" and other["policy"]["policy_number"] == "PA-8830-2215"
    # A follow-up on the selected policy stays with it.
    same = ask(conv, "Tell me more.")
    assert same["status"] == "no_reference" and same["customer"]["customer_id"] == ids["elena"]


def test_a_name_alone_looks_the_customer_up(ids):
    conv = new_conversation()
    elena = ask(conv, "Elena")
    assert elena["intent"] == "portfolio" and elena["customer_lookup"]
    assert numbers(elena) == ["HO-9021-4477", "PA-8830-2215"]
    answer = client.post(f"/api/conversations/{conv}/questions", json={"question": "Elena"}, headers=H).json()
    assert answer["answer_type"] == "portfolio" and "HO-9021-4477" in answer["answer"] and "PA-8830-2215" in answer["answer"]


def test_a_customer_with_no_policies_is_said_to_have_none():
    # A customer added for this test only and removed after it: the seeded customers all have policies.
    db = SessionLocal()
    account_id = str(uuid.uuid4())
    db.execute(sa.text("insert into core_account (id, account_number, name, email, phone, address_line, city, state, "
                       "postal_code, household_role, org_id, synthetic, created_at) values (:id, 'TEST-NOPOL', 'Quentin Okonkwo', "
                       "'', '', '', '', '', '', '', '', true, now())"), {"id": account_id})
    db.commit()
    try:
        conv = new_conversation()
        r = ask(conv, "Quentin Okonkwo")
        assert r["intent"] == "portfolio" and r["customer_lookup"]
        assert r["customer_verification"]["status"] == "verified"
        assert "no policies" in r["customer_verification"]["message"]
        answer = client.post(f"/api/conversations/{conv}/questions", json={"question": "Quentin Okonkwo"}, headers=H).json()
        assert "Quentin Okonkwo has no current policies on file" in answer["answer"]
        # A policy question about them says the same, rather than "customer not found".
        assert ask(conv, "What are Quentin Okonkwo's exclusions?")["customer_verification"]["status"] == "verified"
    finally:
        db.execute(sa.text("delete from core_account where id = :id"), {"id": account_id})
        db.commit()
        db.close()


def test_an_unknown_customer_stops_and_never_uses_the_current_one(ids):
    conv = new_conversation()
    assert choose_customer(conv, ids["elena"]).status_code == 200
    r = ask(conv, "What is Zorblax's deductible?")
    assert r["status"] == "not_found" and r["customer_verification"]["status"] == "not_found"
    assert r["candidates"] == [] and r["policy"] is None and not r["from_context"]
    alone = ask(new_conversation(), "Sirivalli Rao")
    assert alone["customer_verification"]["status"] == "not_found"


def test_another_customer_needs_confirmation_and_is_never_answered_from_the_current_one(ids):
    conv = new_conversation()
    assert choose_customer(conv, ids["elena"]).status_code == 200
    david = ask(conv, "What about David?")
    assert david["customer"]["customer_id"] == ids["david"] and not david["from_context"]
    # The context does not move to David without confirmation, by policy or by customer.
    assert client.post(f"/api/conversations/{conv}/context", json={"policy_id": ids["david_auto"]}, headers=H).status_code == 409
    assert choose_customer(conv, ids["david"]).status_code == 409
    # Nor can a question about David be answered with Elena as the conversation's customer.
    q = client.post(f"/api/conversations/{conv}/questions", json={"question": "What are David's exclusions?"}, headers=H)
    assert q.status_code == 409
    q = client.post(f"/api/conversations/{conv}/questions", json={"question": "Exclusions?", "policy_id": ids["david_auto"]}, headers=H)
    assert q.status_code == 409
    # Confirmed: the conversation is David's, and the switch is in the audit trail.
    switched = choose_customer(conv, ids["david"], confirm=True).json()
    assert switched["customer_context"]["customer_id"] == ids["david"] and switched["policy_context"] is None
    db = SessionLocal()
    try:
        audit = db.query(ContextSwitchAudit).filter(ContextSwitchAudit.conversation_id == conv).all()
    finally:
        db.close()
    assert any(a.switch_type == "different_customer" and a.outcome == "success" and a.new_customer_id == ids["david"]
               and a.previous_customer_id == ids["elena"] for a in audit)
    assert any(a.outcome == "rejected" for a in audit)


def test_a_reference_that_picks_no_policy_is_asked_about_not_reported_as_missing_customer(ids):
    conv = new_conversation(ids["david_auto"])
    r = ask(conv, "What about the third one?")
    assert r["status"] == "not_found" and r["customer_verification"]["status"] == "verified"
    assert "only 1 policy" in r["message"]


def test_without_any_context_a_pronoun_is_asked_about():
    r = ask(new_conversation(), "What are her exclusions?")
    assert r["status"] == "no_reference" and not r["from_context"] and r["customer"] is None


def test_a_reopened_conversation_keeps_its_customer(ids):
    conv = new_conversation()
    assert choose_customer(conv, ids["elena"]).status_code == 200
    reopened = client.get(f"/api/conversations/{conv}", headers=H).json()
    assert reopened["customer_context"]["customer_name"] == "Elena Moreau" and reopened["policy_context"] is None
    assert ask(conv, "What are the exclusions?")["from_context"]
    # Selecting one of her policies keeps her as the customer; clearing the context clears both.
    client.post(f"/api/conversations/{conv}/context", json={"policy_id": ids["elena_auto"]}, headers=H)
    assert client.get(f"/api/conversations/{conv}", headers=H).json()["customer_context"]["customer_id"] == ids["elena"]
    cleared = client.delete(f"/api/conversations/{conv}/context", headers=H).json()
    assert cleared.get("customer_context") is None
    assert not ask(conv, "What are the exclusions?")["from_context"]
