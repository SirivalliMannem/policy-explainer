"""Application configuration loaded from environment and root .env."""

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
    PROJECT_NAME: str = "Policy Explainer"
    SERVICE_NAME: str = "policy-explainer-backend"
    VERSION: str = "0.1.0"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5436/policy_explainer",
    )

    # LLM Provider Configuration (AI Service)
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")

    # AI Microservice Boundary
    AI_SERVICE_URL: str = os.getenv("AI_SERVICE_URL", "http://localhost:8001")


settings = Settings()
