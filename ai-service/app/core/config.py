"""AI Service configuration loaded from environment and root .env."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Path to the root repository folder where .env resides
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DOTENV_PATH = ROOT_DIR / ".env"

if DOTENV_PATH.exists():
    load_dotenv(dotenv_path=DOTENV_PATH)
else:
    load_dotenv()


class Settings:
    PROJECT_NAME: str = "Policy Explainer AI Service"
    SERVICE_NAME: str = "policy-explainer-ai-service"
    VERSION: str = "0.1.0"
    PORT: int = 8001

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5436/policy_explainer",
    )

    # LLM Provider Configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")

    # Groq Configuration (Current Provider)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

    # Gemini Configuration (Second Provider - for later use)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_BASE_URL: str = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")

    # Question understanding before retrieval: "auto" (language model with rules fallback),
    # "rules" (deterministic only, no extra model call) or "off".
    QUERY_INTERPRETER: str = os.getenv("QUERY_INTERPRETER", "auto")

    # Legacy compatibility aliases
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")


settings = Settings()
