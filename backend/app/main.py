"""Main FastAPI application for Policy Explainer backend."""

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes.conversations import router as conversations_router
from app.api.routes.customers import router as customers_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.policies import router as policies_router
from app.api.routes.policy_resolution import router as policy_resolution_router
from app.core.config import settings
from app.db.database import Base, engine, get_db

# Ensure new conversation application tables and evidence ledger exist
from app.models import Conversation, ConversationQuestion, EvidenceLedger  # noqa: F401
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

# Enable CORS for browser access from frontend (localhost:5173, localhost:5174, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(customers_router)
app.include_router(policy_resolution_router)
app.include_router(policies_router)
app.include_router(conversations_router)
app.include_router(dashboard_router)


@app.get("/health")
def health_check():
    """Service health check endpoint."""
    return {
        "status": "ok",
        "service": "policy-explainer-backend",
    }


@app.get("/health/db")
def health_db_check(db: Session = Depends(get_db)):
    """Database connectivity health check executing a lightweight probe."""
    try:
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            return {
                "status": "ok",
                "database": "connected",
            }
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unexpected response from database probe",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {exc}",
        )
