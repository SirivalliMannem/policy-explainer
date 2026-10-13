"""Comprehensive unit and integration tests for LLM provider configuration and switching."""
from __future__ import annotations

import os
import sys
import pytest
from unittest.mock import MagicMock, patch
import httpx

# Ensure ai-service directory is in python path
ai_service_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ai_service_dir not in sys.path:
    sys.path.insert(0, ai_service_dir)

import json
from app.core.config import settings
from app.db.database import SessionLocal
from app.models.policy import CorePolicy
from app.services.explainer_pipeline import ExplainerPipeline
from app.services.llm import (
    GroqProvider,
    GeminiProvider,
    LLMConfigurationError,
    LLMProviderError,
    LLMService,
)
from app.services.llm.base import (
    parse_structured_response,
    validate_ai_suggestions,
)
from app.services.retrieval.evidence_retriever import EvidenceItem


@pytest.fixture
def sample_evidence():
    """Sample EvidenceItem list for testing."""
    return [
        EvidenceItem(
            source_type="clause",
            source_id="clause-1",
            title="Water Back-up and Sump Discharge or Overflow",
            form_number="HO 04 95",
            edition="01 14",
            page=1,
            section="Section I - Property Coverages",
            heading="Water Back-up",
            content="We cover direct physical loss caused by water which backs up through sewers or drains.",
            plain_language="Water backup covers loss from sewer/drain overflow up to policy limits.",
            relevance_score=0.95,
        )
    ]


# ==============================================================================
# TEST 1: LLM_PROVIDER=groq -> Groq provider selected
# ==============================================================================
def test_1_provider_selection_groq(monkeypatch):
    """TEST 1: LLM_PROVIDER=groq selects GroqProvider."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    provider = LLMService.get_provider()
    assert isinstance(provider, GroqProvider)
    assert provider.name == "groq"
    assert provider.model == "openai/gpt-oss-120b"


# ==============================================================================
# TEST 2: LLM_PROVIDER=gemini -> Gemini provider selected
# ==============================================================================
def test_2_provider_selection_gemini(monkeypatch):
    """TEST 2: LLM_PROVIDER=gemini selects GeminiProvider."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    provider = LLMService.get_provider()
    assert isinstance(provider, GeminiProvider)
    assert provider.name == "gemini"
    assert provider.model == "gemini-2.5-flash"


# ==============================================================================
# TEST 3: Groq selected + missing GROQ_API_KEY -> clear configuration error
# ==============================================================================
def test_3_groq_missing_api_key_raises_configuration_error(monkeypatch):
    """TEST 3: Groq selected but missing GROQ_API_KEY raises LLMConfigurationError."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")

    provider = LLMService.get_provider()
    assert provider.is_configured is False

    with pytest.raises(LLMConfigurationError) as exc_info:
        LLMService.validate_configuration()

    err_msg = str(exc_info.value)
    assert "Groq" in err_msg
    assert "GROQ_API_KEY" in err_msg
    assert "missing or empty" in err_msg


# ==============================================================================
# TEST 4: Gemini selected + missing GEMINI_API_KEY -> clear configuration error
# ==============================================================================
def test_4_gemini_missing_api_key_raises_configuration_error(monkeypatch):
    """TEST 4: Gemini selected but missing GEMINI_API_KEY raises LLMConfigurationError."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    provider = LLMService.get_provider()
    assert provider.is_configured is False

    with pytest.raises(LLMConfigurationError) as exc_info:
        LLMService.validate_configuration()

    err_msg = str(exc_info.value)
    assert "Gemini" in err_msg
    assert "GEMINI_API_KEY" in err_msg
    assert "missing or empty" in err_msg


# ==============================================================================
# TEST 5: Groq selected + Gemini key empty -> application still works
# ==============================================================================
def test_5_groq_selected_gemini_key_empty(monkeypatch, sample_evidence):
    """TEST 5: Groq selected with empty Gemini key validates cleanly and functions."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock_valid_groq_key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    # Configuration validation passes without requiring GEMINI_API_KEY
    LLMService.validate_configuration()

    provider = LLMService.get_provider()
    assert isinstance(provider, GroqProvider)
    assert provider.is_configured is True

    # Generation fallback or execution works cleanly
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Water backup is covered under HO 04 95."}}]
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = LLMService.generate_answer(
            question="Is water backup covered?",
            grounding_context="Context wording",
            evidence=sample_evidence,
        )
        assert res.answer == "Water backup is covered under HO 04 95."
        assert res.model_used == "openai/gpt-oss-120b"
        assert res.is_fallback is False


# ==============================================================================
# TEST 6: Gemini selected + Groq key empty -> does NOT require Groq
# ==============================================================================
def test_6_gemini_selected_groq_key_empty(monkeypatch, sample_evidence):
    """TEST 6: Gemini selected with empty Groq key validates cleanly and does not require Groq."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "AIza_mock_valid_gemini_key")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")

    # Configuration validation passes without requiring GROQ_API_KEY
    LLMService.validate_configuration()

    provider = LLMService.get_provider()
    assert isinstance(provider, GeminiProvider)
    assert provider.is_configured is True

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Gemini confirms water backup coverage."}]}}]
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = LLMService.generate_answer(
            question="Is water backup covered?",
            grounding_context="Context wording",
            evidence=sample_evidence,
        )
        assert res.answer == "Gemini confirms water backup coverage."
        assert res.model_used == "gemini-2.5-flash"
        assert res.is_fallback is False


# ==============================================================================
# ADDITIONAL TESTS: Invalid provider, controlled fallback, no key leakage
# ==============================================================================
def test_unsupported_provider_raises_configuration_error(monkeypatch):
    """Unsupported provider names raise clean configuration error."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    with pytest.raises(LLMConfigurationError) as exc_info:
        LLMService.get_provider()
    assert "Unsupported LLM provider 'anthropic'" in str(exc_info.value)
    assert "groq" in str(exc_info.value)
    assert "gemini" in str(exc_info.value)


def test_groq_network_failure_falls_back_without_leakage(monkeypatch, sample_evidence):
    """Network failure engages deterministic fallback and preserves system response."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock_key")

    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        res = LLMService.generate_answer(
            question="Is water backup covered?",
            grounding_context="Context",
            evidence=sample_evidence,
        )
        assert res.is_fallback is True
        assert res.model_used == "grounded-carrier-engine"
        assert "HO 04 95" in res.answer


def test_groq_provider_direct_call_without_key_raises_error():
    """Invoking generate directly on unconfigured provider raises LLMConfigurationError."""
    provider = GroqProvider(api_key="", model="openai/gpt-oss-120b")
    with pytest.raises(LLMConfigurationError):
        provider.generate("test", "context", [])


def test_gemini_provider_direct_call_without_key_raises_error():
    """Invoking generate directly on unconfigured Gemini provider raises LLMConfigurationError."""
    provider = GeminiProvider(api_key="", model="gemini-2.5-flash")
    with pytest.raises(LLMConfigurationError):
        provider.generate("test", "context", [])


def test_groq_rate_limit_retries_once_when_window_is_short(monkeypatch, sample_evidence):
    """HTTP 429 with a short retry-after is retried once instead of falling back immediately."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock_key")

    limited = MagicMock(status_code=429, headers={"retry-after": "0"})
    ok = MagicMock(status_code=200)
    ok.json.return_value = {"choices": [{"message": {"content": "Covered under HO 04 95 [E1]."}}]}

    with patch("httpx.Client.post", side_effect=[limited, ok]) as post:
        res = LLMService.generate_answer("Is water backup covered?", "Context", sample_evidence)
    assert post.call_count == 2
    assert res.is_fallback is False and res.provider == "groq"


def test_groq_long_rate_limit_falls_back_with_reason(monkeypatch, sample_evidence):
    """A long rate-limit window falls back and records why, rather than stalling the request."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock_key")

    limited = MagicMock(status_code=429, headers={"retry-after": "60"})
    with patch("httpx.Client.post", return_value=limited) as post:
        res = LLMService.generate_answer("Is water backup covered?", "Context", sample_evidence)
    assert post.call_count == 1
    assert res.is_fallback is True
    assert "429" in (res.fallback_reason or "")


# ==============================================================================
# AI-GENERATED SUGGESTED QUESTIONS TESTS
# ==============================================================================

def test_groq_generates_answer_and_suggestions_in_single_call(monkeypatch, sample_evidence):
    """Groq returns answer plus dynamically generated suggestions in a single structured API call."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock_valid_key")

    provider = LLMService.get_provider()
    assert isinstance(provider, GroqProvider)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_payload = {
        "answer": "Water backup is covered up to $5,000 under endorsement HO 04 95 [E1].",
        "suggested_questions": [
            "What is the deductible for water backup?",
            "Does coverage include sump pump overflow?",
            "Are foundation damages excluded under this endorsement?",
        ],
    }
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(mock_payload)}}]
    }

    with patch("httpx.Client.post", return_value=mock_resp) as post:
        res = LLMService.generate_answer(
            question="Is water backup covered?",
            grounding_context="Grounding context with HO 04 95",
            evidence=sample_evidence,
        )
        # Exactly one call to Groq
        assert post.call_count == 1
        assert res.is_fallback is False
        assert res.model_used == provider.model
        assert "Water backup is covered" in res.answer
        assert len(res.suggested_questions) == 3
        assert res.suggested_questions[0] == "What is the deductible for water backup?"
        assert res.suggested_questions[1] == "Does coverage include sump pump overflow?"
        assert res.suggested_questions[2] == "Are foundation damages excluded under this endorsement?"


def test_groq_429_uses_carrier_engine_and_python_suggestions_without_second_groq_call(monkeypatch, sample_evidence):
    """Groq HTTP 429 engages deterministic fallback and Python SuggestionGenerator with NO second Groq call."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock_valid_key")

    limited = MagicMock(status_code=429, headers={"retry-after": "60"})
    with patch("httpx.Client.post", return_value=limited) as post:
        res = LLMService.generate_answer(
            question="Is water backup covered?",
            grounding_context="Context",
            evidence=sample_evidence,
        )
        assert post.call_count == 1
        assert res.is_fallback is True
        assert res.model_used == "grounded-carrier-engine"
        assert res.suggested_questions == []  # LLM did not generate suggestions; pipeline falls back

    # Now verify in full ExplainerPipeline
    db = SessionLocal()
    try:
        policy = db.query(CorePolicy).filter(CorePolicy.policy_number.like("%2847%")).first()
        if policy:
            interp = {
                "original": "Does this policy have water backup coverage?",
                "corrected": "Does this policy have water backup coverage?",
                "normalized": "Does this policy have water backup coverage?",
                "method": "rules",
                "search_terms": ["water backup"],
            }
            with patch("httpx.Client.post", return_value=limited) as post:
                pipeline_resp = ExplainerPipeline.process_question(
                    question="Does this policy have water backup coverage?",
                    policy_id=policy.id,
                    db=db,
                    interpretation=interp,
                )
                # Exactly one call to Groq was attempted for answer generation; NEVER called for suggestions
                assert post.call_count == 1
                assert pipeline_resp.is_fallback is True
                assert pipeline_resp.model_used == "grounded-carrier-engine"
                # Fallback suggestions are generated by SuggestionGenerator
                assert len(pipeline_resp.suggested_questions) > 0
                assert all(isinstance(s, str) for s in pipeline_resp.suggested_questions)
    finally:
        db.close()


def test_malformed_ai_suggestions_preserves_valid_answer_and_falls_back(monkeypatch, sample_evidence):
    """Malformed suggestion format in Groq JSON response preserves valid answer and falls back to Python generator."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock_valid_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_payload = {
        "answer": "Water backup is covered under HO 04 95 [E1].",
        "suggested_questions": "invalid - should be a list, not a string",
    }
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(mock_payload)}}]
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = LLMService.generate_answer(
            question="Is water backup covered?",
            grounding_context="Context with HO 04 95",
            evidence=sample_evidence,
        )
        # Valid answer is preserved, malformed suggestions are safely dropped to empty list
        assert res.is_fallback is False
        assert res.answer == "Water backup is covered under HO 04 95 [E1]."
        assert res.suggested_questions == []

    # In pipeline, empty suggestions trigger fallback to Python SuggestionGenerator
    db = SessionLocal()
    try:
        policy = db.query(CorePolicy).filter(CorePolicy.policy_number.like("%2847%")).first()
        if policy:
            interp = {
                "original": "Does this policy have water backup coverage?",
                "corrected": "Does this policy have water backup coverage?",
                "normalized": "Does this policy have water backup coverage?",
                "method": "rules",
                "search_terms": ["water backup"],
            }
            with patch("httpx.Client.post", return_value=mock_resp):
                pipeline_resp = ExplainerPipeline.process_question(
                    question="Does this policy have water backup coverage?",
                    policy_id=policy.id,
                    db=db,
                    interpretation=interp,
                )
                assert pipeline_resp.is_fallback is False
                assert pipeline_resp.answer == "Water backup is covered under HO 04 95 [E1]."
                # Python generator safely filled in the suggestions
                assert len(pipeline_resp.suggested_questions) > 0
    finally:
        db.close()


def test_ai_suggestions_validation_filtering(sample_evidence):
    """Suggestions are capped at 3, filtered for duplicates, question near-repeats, and unevidenced forms."""
    question = "Does this policy have water backup coverage?"

    raw_candidates = [
        "Does this policy have water backup coverage?",  # Exact repeat -> rejected
        "What is the water backup limit?",  # Valid 1 -> accepted
        "What is the water backup limit?",  # Duplicate of valid 1 -> rejected
        "What deductible applies to water backup?",  # Valid 2 -> accepted
        "Can I claim under endorsement HO 99 99?",  # Hallucinated form not in evidence -> rejected
        "What is the coverage condition for drains under HO 04 95?",  # Valid 3 (HO 04 95 in evidence) -> accepted
        "What is another extra question?",  # 4th valid -> dropped by MAX_AI_SUGGESTIONS cap
    ]

    validated = validate_ai_suggestions(raw_candidates, question, sample_evidence)
    assert len(validated) == 3
    assert "Does this policy have water backup coverage?" not in validated
    assert "Can I claim under endorsement HO 99 99?" not in validated
    assert validated[0] == "What is the water backup limit?"
    assert validated[1] == "What deductible applies to water backup?"
    assert "HO 04 95" in validated[2]


def test_parse_structured_response_markdown_fence_and_plain_text(sample_evidence):
    """parse_structured_response handles markdown code fences and legacy plain-text responses gracefully."""
    question = "Is water backup covered?"

    # Markdown fenced JSON
    fenced = """```json
{
  "answer": "Yes, water backup is covered [E1].",
  "suggested_questions": ["What is the water backup limit?"]
}
```"""
    answer, suggestions = parse_structured_response(fenced, question, sample_evidence)
    assert answer == "Yes, water backup is covered [E1]."
    assert suggestions == ["What is the water backup limit?"]

    # Plain text without JSON
    plain = "Direct plain text answer without JSON markers."
    answer, suggestions = parse_structured_response(plain, question, sample_evidence)
    assert answer == plain
    assert suggestions == []
