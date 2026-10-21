"""AI Service configuration loaded from environment and root .env."""

import os
from pathlib import Path
from dotenv import load_dotenv

from fi360_shared.agents import POLICY_EXPLAINER

def _repo_root() -> Path:
    """Directory that holds .env when running from the repo.

    Inside the image the app lives at /app, so there is no repo root. Compose
    injects the environment, and load_dotenv() below is a no-op.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".env").is_file() or (parent / "docker-compose.yml").is_file():
            return parent
    return here.parents[2]


ROOT_DIR = _repo_root()
DOTENV_PATH = ROOT_DIR / ".env"

if DOTENV_PATH.exists():
    load_dotenv(dotenv_path=DOTENV_PATH)
else:
    load_dotenv()


class Settings:
    PROJECT_NAME: str = "Policy Explainer"
    SERVICE_NAME: str = "policy-explainer"
    AGENT_CODE: str = POLICY_EXPLAINER
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

    # Meaning-based clause search alongside word match: a small local embedding model (no API key).
    # "on" (default) or "off". The model is downloaded once into SEMANTIC_CACHE_DIR
    # (default agents/policy-explainer/.model_cache); without it, search uses word match only.
    SEMANTIC_SEARCH: str = os.getenv("SEMANTIC_SEARCH", "on")
    SEMANTIC_MODEL: str = os.getenv("SEMANTIC_MODEL", "BAAI/bge-small-en-v1.5")
    SEMANTIC_CACHE_DIR: str = os.getenv("SEMANTIC_CACHE_DIR", "")

    # Legacy compatibility aliases
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")


settings = Settings()
