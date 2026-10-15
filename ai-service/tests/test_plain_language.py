"""Plain-language explanation of one clause: grounded in its text, never a coverage decision, never invented."""

import os
import sys

ai_service_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ai_service_dir not in sys.path:
    sys.path.insert(0, ai_service_dir)

from app.services import plain_language
from app.services.llm.exceptions import LLMProviderError

CLAUSE = "We insure for sudden and accidental discharge or overflow of water from within a plumbing system."


class FakeProvider:
    name = "groq"
    model = "openai/gpt-oss-120b"

    def __init__(self, reply="", error=None, configured=True):
        self.reply, self.error, self.is_configured = reply, error, configured
        self.prompts = []

    def complete(self, system, user, **kwargs):
        self.prompts.append((system, user))
        if self.error:
            raise self.error
        return self.reply


def use(monkeypatch, provider):
    monkeypatch.setattr(plain_language.LLMService, "get_provider", classmethod(lambda cls, name=None: provider))
    return provider


def test_the_clause_is_explained_from_its_own_text(monkeypatch):
    provider = use(monkeypatch, FakeProvider("This clause covers water that suddenly escapes from the plumbing."))
    result = plain_language.explain_clause("Accidental Discharge", "HO 00 03", CLAUSE)
    assert result.status == "explained"
    assert result.explanation == "This clause covers water that suddenly escapes from the plumbing."
    assert (result.provider, result.model_used) == ("groq", "openai/gpt-oss-120b")
    system, user = provider.prompts[0]
    assert CLAUSE in user and "Form: HO 00 03" in user
    assert "Do not say whether any particular loss or claim is covered" in system


def test_an_explanation_that_decides_coverage_is_withheld(monkeypatch):
    use(monkeypatch, FakeProvider("Your claim will be paid because the pipe burst suddenly."))
    result = plain_language.explain_clause("Accidental Discharge", "HO 00 03", CLAUSE)
    assert result.status == "unavailable" and result.explanation == ""
    assert "coverage decision" in result.reason


def test_without_a_model_nothing_is_generated(monkeypatch):
    use(monkeypatch, FakeProvider(error=LLMProviderError("HTTP 429")))
    busy = plain_language.explain_clause("Accidental Discharge", "HO 00 03", CLAUSE)
    assert busy.status == "unavailable" and busy.explanation == ""
    use(monkeypatch, FakeProvider(configured=False))
    assert plain_language.explain_clause("Accidental Discharge", "HO 00 03", CLAUSE).status == "unavailable"
