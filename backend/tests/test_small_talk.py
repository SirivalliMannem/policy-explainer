"""Conversational replies: greetings and thanks are answered without the AI service or the ledger."""

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import small_talk
from app.services.ai_client import ai_client

client = TestClient(app)
ME = {"X-Employee-Id": "EMP-TALK-01", "X-Employee-Name": quote("Dana Reyes"), "X-Employee-Role": "csr"}


@pytest.mark.parametrize(
    "text, kind",
    [
        ("Hi", "greeting"),
        ("hello there!", "greeting"),
        ("Good morning", "greeting"),
        ("hey, how are you?", "how_are_you"),
        ("What can you do?", "help"),
        ("hi, who are you", "help"),
        ("thanks a lot!", "thanks"),
        ("Thank you so much", "thanks"),
        ("ok", "acknowledge"),
        ("bye for now", "goodbye"),
    ],
)
def test_small_talk_is_recognised(text, kind):
    assert small_talk.classify(text) == kind


@pytest.mark.parametrize(
    "text",
    [
        "hi, what is the deductible on HO-2847-1193?",
        "hello does Margaret Chen have water backup coverage",
        "help me understand the wind deductible",
        "what is the deductible",
        "history of claims",  # starts with "hi" but is not a greeting
        "Okay so what forms are attached",
    ],
)
def test_policy_questions_are_not_small_talk(text):
    assert small_talk.classify(text) is None


@pytest.fixture
def no_ai(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("the AI service must not be called for small talk")

    monkeypatch.setattr(ai_client, "interpret", fail)
    monkeypatch.setattr(ai_client, "explain", fail)


def resolve(question: str):
    res = client.post("/api/policy-resolution/from-question", json={"question": question}, headers=ME)
    assert res.status_code == 200, res.text
    return res.json()


def test_greeting_gets_a_reply_without_the_ai_service(no_ai):
    body = resolve("Hi!")
    assert body["intent"] == "conversation"
    assert body["reply"].startswith("Hi, Dana!")
    # Example questions use real policies on file.
    assert body["suggestions"] and all(any(ch.isdigit() for ch in s) or "policies does" in s for s in body["suggestions"])


def test_help_and_thanks_replies(no_ai):
    assert "Here's what I can do" in resolve("what can you do?")["reply"]
    assert resolve("thanks")["reply"].startswith("You're welcome, Dana!")


def test_off_topic_message_is_answered_politely(monkeypatch):
    def interpret(question, previous=None):
        return {
            "original": question, "corrected": question, "normalized": question, "method": "llm",
            "intent": "other", "policyholders": [], "policy_numbers": [], "search_terms": [], "corrections": [],
            "latency_ms": 1,
        }

    monkeypatch.setattr(ai_client, "interpret", interpret)
    body = resolve("What's the weather in Paris?")
    assert body["intent"] == "off_topic"
    assert body["reply"].startswith("I can only help with insurance policies")


def test_a_policy_question_still_resolves(monkeypatch):
    monkeypatch.setattr(ai_client, "interpret", lambda *a, **k: None)
    body = resolve("Hi, what is the deductible on HO-2847-1193?")
    assert body["intent"] == "policy" and body["status"] == "resolved"
    assert body["policy"]["policy_number"] == "HO-2847-1193"
    assert body["reply"] is None
