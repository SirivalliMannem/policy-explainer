"""Custom exceptions for LLM provider configuration and execution."""
from __future__ import annotations


class LLMConfigurationError(ValueError):
    """Raised when an LLM provider configuration is invalid or missing required credentials."""
    pass


class LLMProviderError(Exception):
    """Raised when an external LLM provider fails during invocation."""
    pass
