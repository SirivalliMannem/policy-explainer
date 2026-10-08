"""SQLAlchemy database connection and session setup for Policy Explainer backend."""

from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Engine connected to PostgreSQL policy_explainer database
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator:
    """FastAPI dependency yielding an independent transactional database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
