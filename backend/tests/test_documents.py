"""Documents uploaded into the chat: extraction, ownership, answers from the document only, recording."""

import sys
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from document_fixtures import SAMPLE_POLICY_PAGES, docx, pdf  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.document import UploadedDocument, UploadedDocumentPage  # noqa: E402
from app.models.ledger import EvidenceLedger  # noqa: E402
from app.schemas.explainer import AIServiceResponse  # noqa: E402
from app.services.ai_client import ai_client  # noqa: E402
from app.services.document_extraction import MAX_BYTES, ExtractionError, extract  # noqa: E402

client = TestClient(app)


# ── Extraction ──────────────────────────────────────────────────────────────


def test_a_pdf_keeps_its_pages():
    result = extract("renters.pdf", pdf(SAMPLE_POLICY_PAGES))
    assert result.unit == "page" and len(result.pages) == 2
    assert "Deductible: $750" in result.pages[0] and "flood" in result.pages[1]


def test_a_word_file_is_split_into_sections_at_its_headings():
    data = docx([("Declarations", ["Deductible: $500."]), ("Exclusions", ["We do not cover flood."])])
    result = extract("policy.docx", data)
    assert result.unit == "section" and len(result.pages) == 2
    assert result.pages[1].startswith("Exclusions")


def test_a_text_file_is_read():
    result = extract("notes.md", b"# Cover\n\nWater backup up to $5,000.\n\n# Exclusions\n\nNo flood cover.")
    assert result.unit == "section" and len(result.pages) == 2


@pytest.mark.parametrize(
    "name, data, message",
    [
        ("photo.png", b"\x89PNG", "Only PDF, Word"),
        ("empty.pdf", b"", "empty"),
        ("fake.pdf", b"not a pdf at all", "not a PDF"),
        ("scan.pdf", pdf([[]]), "No text could be read"),
        ("huge.txt", b"a" * (MAX_BYTES + 1), "the limit is 10 MB"),
    ],
    ids=["wrong-type", "empty", "not-a-pdf", "scan-without-text", "too-large"],
)
def test_unusable_files_are_refused_with_a_reason(name, data, message):
    with pytest.raises(ExtractionError, match=message):
        extract(name, data)


# ── Upload, ownership and answers ───────────────────────────────────────────


@pytest.fixture
def session(monkeypatch):
    asked: list[tuple] = []

    def explain_document(document_id, question, mode="question"):
        asked.append((document_id, question, mode))
        if "world cup" in question.lower():
            return AIServiceResponse(question=question, answer="The uploaded document does not appear to cover this question.",
                                     confidence="none", status="insufficient_evidence", guardrail_status="no_evidence",
                                     retrieval={"answer_type": "document", "passages_searched": 2})
        return AIServiceResponse(
            question=question, answer="The deductible is $750 per claim [E1].", confidence="medium", status="answered",
            evidence=[{"source_type": "document", "source_id": "page-1", "title": "renters.pdf", "content": "Deductible: $750 per claim.",
                       "form_number": "renters.pdf", "page": 1, "heading": "Page 1", "relevance_score": 9.0, "evidence_index": 1,
                       "scope": "uploaded_document"}],
            citations=[{"source_id": "page-1", "source_type": "document", "evidence_index": 1, "form_number": "renters.pdf", "page": 1}],
            guardrail_status="passed",
            guardrail_checks=[{"name": "inline_citations", "status": "passed", "detail": "1 inline reference."}],
            retrieval={"answer_type": "document", "mode": mode, "document": {"id": document_id, "filename": "renters.pdf", "unit": "page", "page_count": 2}},
        )

    monkeypatch.setattr(ai_client, "explain_document", explain_document)
    headers = {"X-Employee-Id": f"EMP-DOC-{uuid.uuid4().hex[:6]}", "X-Employee-Name": quote("Doc Owner"), "X-Employee-Role": "csr"}
    made: list[str] = []
    yield headers, made, asked
    for conv in made:  # ledger entries are audit records: archive, never delete
        client.post(f"/api/conversations/{conv}/archive", headers=headers)


def new_conversation(session) -> str:
    headers, made, _ = session
    conv = client.post("/api/conversations", json={}, headers=headers).json()["conversation_id"]
    made.append(conv)
    return conv


def upload(session, conv: str, name="renters.pdf", data=None) -> dict:
    headers, _, _ = session
    res = client.post(f"/api/conversations/{conv}/documents",
                      files={"file": (name, data if data is not None else pdf(SAMPLE_POLICY_PAGES), "application/pdf")}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_upload_stores_the_text_per_page_and_not_the_file(session):
    conv = new_conversation(session)
    doc = upload(session, conv)
    assert (doc["page_count"], doc["unit"], doc["is_active"]) == (2, "page", True)
    db = SessionLocal()
    try:
        row = db.get(UploadedDocument, doc["document_id"])
        assert len(row.sha256) == 64 and not hasattr(row, "data")
        pages = db.query(UploadedDocumentPage).filter(UploadedDocumentPage.document_id == row.id).order_by(UploadedDocumentPage.page_number).all()
        assert [p.page_number for p in pages] == [1, 2] and "flood" in pages[1].text
    finally:
        db.close()


def test_a_bad_file_is_refused_with_its_reason(session):
    headers, _, _ = session
    conv = new_conversation(session)
    res = client.post(f"/api/conversations/{conv}/documents", files={"file": ("photo.png", b"\x89PNG", "image/png")}, headers=headers)
    assert res.status_code == 422 and "Only PDF, Word" in res.json()["detail"]


def test_questions_are_answered_from_the_document_and_recorded(session):
    headers, _, asked = session
    conv = new_conversation(session)
    doc = upload(session, conv)
    explained = client.post(f"/api/conversations/{conv}/documents/{doc['document_id']}/explain", headers=headers)
    assert explained.status_code == 201 and asked[-1][2] == "summary"
    res = client.post(f"/api/conversations/{conv}/questions", json={"question": "What is the deductible?", "document_id": doc["document_id"]}, headers=headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert asked[-1] == (doc["document_id"], "What is the deductible?", "question")
    assert body["answer_type"] == "document" and body["policy_context"] is None
    assert body["citations"][0]["page"] == 1
    db = SessionLocal()
    try:
        entry = db.get(EvidenceLedger, body["ledger_id"])
        assert entry.retrieval["answer_type"] == "document" and entry.policy_id is None
    finally:
        db.close()
    # Reopening the conversation shows the document answers.
    messages = client.get(f"/api/conversations/{conv}/messages", headers=headers).json()
    assert [m["answer"]["answer_type"] for m in messages] == ["document", "document"]


def test_a_document_answer_that_finds_nothing_is_not_a_policy_gap(session):
    headers, _, _ = session
    conv = new_conversation(session)
    doc = upload(session, conv)
    marker = uuid.uuid4().hex[:6]
    res = client.post(f"/api/conversations/{conv}/questions",
                      json={"question": f"Who won the world cup {marker}?", "document_id": doc["document_id"]}, headers=headers)
    assert res.json()["status"] == "insufficient_evidence"
    items = client.get("/api/dashboard/attention", params={"range": "today"}).json()["items"]
    assert not any(marker in i["question"] for i in items)


def test_one_document_is_attached_at_a_time_and_detaching_keeps_it(session):
    headers, _, _ = session
    conv = new_conversation(session)
    first = upload(session, conv)
    second = upload(session, conv, name="policy.docx", data=docx([("Cover", ["Deductible $500."])]))
    docs = client.get(f"/api/conversations/{conv}/documents", headers=headers).json()
    assert [(d["document_id"], d["is_active"]) for d in docs] == [(second["document_id"], True), (first["document_id"], False)]
    client.post(f"/api/conversations/{conv}/documents/{second['document_id']}/detach", headers=headers)
    res = client.post(f"/api/conversations/{conv}/questions", json={"question": "Deductible?", "document_id": second["document_id"]}, headers=headers)
    assert res.status_code == 409  # detached: no longer answered from


def test_only_the_uploader_can_use_or_read_the_document(session):
    headers, _, _ = session
    conv = new_conversation(session)
    doc = upload(session, conv)
    other = {"X-Employee-Id": "EMP-SOMEONE-ELSE", "X-Employee-Role": "csr"}
    assert client.post(f"/api/conversations/{conv}/documents", files={"file": ("x.pdf", pdf(SAMPLE_POLICY_PAGES), "application/pdf")},
                       headers=other).status_code == 404
    assert client.get(f"/api/conversations/{conv}/documents", headers=other).status_code == 404
    db = SessionLocal()
    try:
        page_id = db.query(UploadedDocumentPage).filter(UploadedDocumentPage.document_id == doc["document_id"]).first().id
    finally:
        db.close()
    assert client.get(f"/api/document-pages/{page_id}", headers=other).status_code == 404
    assert client.get(f"/api/document-pages/{page_id}", headers=headers).json()["text"].startswith("Lakeside Mutual")
    # A document cannot be used from another conversation, even by its owner.
    elsewhere = new_conversation(session)
    res = client.post(f"/api/conversations/{elsewhere}/questions", json={"question": "Deductible?", "document_id": doc["document_id"]}, headers=headers)
    assert res.status_code == 404


def test_blocked_roles_cannot_upload(session):
    conv = new_conversation(session)
    blocked = {"X-Employee-Id": "EMP-BLOCKED", "X-Employee-Role": "suspended"}
    res = client.post(f"/api/conversations/{conv}/documents", files={"file": ("x.pdf", pdf(SAMPLE_POLICY_PAGES), "application/pdf")}, headers=blocked)
    assert res.status_code in (403, 404)
