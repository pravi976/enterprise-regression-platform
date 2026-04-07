"""SQLAlchemy database setup."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from regauto.config import Settings

settings = Settings()
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base SQLAlchemy model."""


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_schema() -> None:
    """Create tables for local development and starter deployments."""
    from regauto import models  # noqa: F401

    Base.metadata.create_all(engine)
