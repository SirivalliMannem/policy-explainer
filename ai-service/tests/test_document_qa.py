"""Answers from an uploaded document: grounded in its passages, cited by page, nothing invented."""

import os
import sys
import uuid
from datetime import datetime

import pytest
import sqlalchemy as sa

ai_service_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ai_service_dir not in sys.path:
    sys.path.insert(0, ai_service_dir)

from app.db.database import SessionLocal
from app.services import document_qa
from app.services.llm.exceptions import LLMProviderError

PAGES = [
    "Lakeside Mutual Renters Policy - Declarations\nPolicyholder: Jordan Avery.\nPersonal property limit: $30,000. Deductible: $750 per claim.",
    "Exclusions\nWe do not pay for damage caused by flood or surface water.\nBicycles are covered up to $1,500 when stolen from a locked storage room.",
]


class FakeProvider:
    name, model, is_configured = "groq", "openai/gpt-oss-120b", True

    def __init__(self, reply="", error=None):
        self.reply, self.error, self.prompts = reply, error, []

    def complete(self, system, user, **kwargs):
        self.prompts.append((system, user))
        if self.error:
            raise self.error
        return self.reply


@pytest.fixture(scope="module")
def document_id():
    """An uploaded document as the backend stores it (a conversation, the document, its pages)."""
    db = SessionLocal()
    conv, doc = str(uuid.uuid4()), str(uuid.uuid4())
    now = datetime.utcnow()
    db.execute(sa.text("insert into conversation (id, employee_id, status, created_at, updated_at, is_archived) "
                       "values (:id, 'EMP-DOCQA', 'archived', :now, :now, true)"), {"id": conv, "now": now})
    db.execute(sa.text("insert into uploaded_document (id, conversation_id, employee_id, filename, content_type, size_bytes, sha256, "
                       "page_count, char_count, unit, is_active, created_at) values (:id, :conv, 'EMP-DOCQA', 'renters.pdf', "
                       "'application/pdf', 1000, :sha, 2, 300, 'page', true, :now)"),
               {"id": doc, "conv": conv, "sha": "0" * 64, "now": now})
    for n, text in enumerate(PAGES, start=1):
        db.execute(sa.text("insert into uploaded_document_page (id, document_id, page_number, text) values (:id, :doc, :n, :t)"),
                   {"id": str(uuid.uuid4()), "doc": doc, "n": n, "t": text})
    db.commit()
    db.close()
    return doc


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def run(monkeypatch, db, document_id, question, reply="", mode="question", error=None):
    provider = FakeProvider(reply, error)
    monkeypatch.setattr(document_qa.LLMService, "get_provider", classmethod(lambda cls, name=None: provider))
    return document_qa.answer_from_document(document_id, question, mode, db), provider


def test_a_question_is_answered_from_the_matching_page(monkeypatch, db, document_id):
    result, provider = run(monkeypatch, db, document_id, "Is flood damage covered?", reply="Flood damage is not covered [E1].")
    assert result["status"] == "answered" and result["answer"] == "Flood damage is not covered [E1]."
    assert result["evidence"][0]["page"] == 2 and result["evidence"][0]["heading"] == "Page 2"
    assert result["citations"][0]["page"] == 2
    # The model saw only passages of the document.
    assert "We do not pay for damage caused by flood" in provider.prompts[0][1]
    assert all(c["status"] == "passed" for c in result["guardrail_checks"])


def test_the_explanation_reads_across_the_whole_document(monkeypatch, db, document_id):
    result, provider = run(monkeypatch, db, document_id, "Explain", mode="summary",
                           reply="A renters policy for Jordan Avery [E1].\nKey points:\n- Flood is excluded [E2].")
    assert [e["page"] for e in result["evidence"]] == [1, 2]
    assert result["retrieval"]["mode"] == "summary" and result["confidence"] == "high"
    assert "simple, plain language" in provider.prompts[0][0]


def test_an_unrelated_question_is_declined(monkeypatch, db, document_id):
    result, provider = run(monkeypatch, db, document_id, "Who won the 2022 World Cup?", reply=document_qa.NOT_IN_DOCUMENT)
    assert result["status"] == "insufficient_evidence" and result["evidence"] == []
    # The model still saw the document's overview, so it could judge that the question is unrelated.
    assert "Lakeside Mutual" in provider.prompts[0][1]


def test_a_broad_question_gets_the_documents_overview_and_marked_general_knowledge(monkeypatch, db, document_id):
    reply = ("The uploaded document is a renters policy for Jordan Avery [E1]. "
             "In general, a homeowners policy also insures the dwelling, which a renters policy does not.")
    result, provider = run(monkeypatch, db, document_id, "Can this relate to a homeowners policy?", reply=reply)
    assert result["status"] == "answered" and result["retrieval"]["general_knowledge"] is True
    assert {e["page"] for e in result["evidence"]} == {1, 2}  # the overview of the whole document
    assert "In general," in provider.prompts[0][0]  # general knowledge allowed only when marked


def test_an_answer_with_only_marked_general_knowledge_is_reported_not_blocked(monkeypatch, db, document_id):
    result, _ = run(monkeypatch, db, document_id, "Can this relate to a homeowners policy?",
                    reply="In general, homeowners and renters policies both cover personal property.")
    inline = next(c for c in result["guardrail_checks"] if c["name"] == "inline_citations")
    assert inline["status"] == "warning" and result["guardrail_status"] == "passed"


def test_the_policy_on_file_is_given_for_comparison_and_labelled(monkeypatch, db, document_id):
    from app.models.policy import CorePolicy

    policy = db.query(CorePolicy).filter(CorePolicy.policy_number == "HO-9021-4477").order_by(CorePolicy.term_number.desc()).first()
    provider = FakeProvider("The uploaded document excludes flood [E1]; the policy on file also excludes it [E2].")
    monkeypatch.setattr(document_qa.LLMService, "get_provider", classmethod(lambda cls, name=None: provider))
    result = document_qa.answer_from_document(document_id, "Is flood damage excluded?", "question", db, policy.id)
    scopes = [e["scope"] for e in result["evidence"]]
    assert "uploaded_document" in scopes and "policy_on_file" in scopes
    assert result["retrieval"]["policy_passages"] >= 1
    assert "POLICY ON FILE" in provider.prompts[0][1] and "UPLOADED DOCUMENT" in provider.prompts[0][1]


def test_when_the_passages_do_not_answer_it_the_model_says_so_and_nothing_is_shown(monkeypatch, db, document_id):
    result, _ = run(monkeypatch, db, document_id, "What is the flood deductible?", reply=document_qa.NOT_IN_DOCUMENT)
    assert result["status"] == "insufficient_evidence"
    assert "does not say" in result["answer"]


def test_without_the_model_the_matching_passages_are_shown_with_their_pages(monkeypatch, db, document_id):
    result, _ = run(monkeypatch, db, document_id, "Are stolen bicycles covered?", error=LLMProviderError("HTTP 429"))
    assert result["is_fallback"] is True and result["confidence"] == "low"
    assert "Page 2:" in result["answer"] and "Bicycles are covered up to $1,500" in result["answer"]


def test_an_answer_that_cites_nothing_is_flagged(monkeypatch, db, document_id):
    result, _ = run(monkeypatch, db, document_id, "Is flood damage covered?", reply="No, flood is not covered.")
    assert result["guardrail_status"] == "flagged"
    assert any(c["name"] == "inline_citations" and c["status"] == "failed" for c in result["guardrail_checks"])


def test_an_unknown_document_is_not_found(db):
    assert document_qa.answer_from_document(str(uuid.uuid4()), "anything", "question", db) is None
