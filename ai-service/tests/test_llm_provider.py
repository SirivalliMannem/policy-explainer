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

from app.core.config import settings
from app.services.llm import (
    GroqProvider,
    GeminiProvider,
    LLMConfigurationError,
    LLMProviderError,
    LLMService,
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
