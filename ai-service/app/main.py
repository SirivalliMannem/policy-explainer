"""Main FastAPI application for Policy Explainer AI Service microservice."""

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes.explain import router as explain_router
from app.core.config import settings
from app.db.database import get_db

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

# Register routes
app.include_router(explain_router)


@app.get("/health")
def health_check():
    """Service health check endpoint."""
    return {
        "status": "ok",
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
    }


@app.get("/health/db")
def health_db_check(db: Session = Depends(get_db)):
    """Database connectivity health check."""
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
