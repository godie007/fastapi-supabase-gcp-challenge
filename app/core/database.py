"""SQLAlchemy engine, session factory, and FastAPI dependency for DB access.

Design notes:
- SQLite (used in tests): ``StaticPool`` + ``check_same_thread=False`` so parallel
  TestClient requests and the same in-memory DB behave predictably.
- PostgreSQL (production): bounded pool with ``pool_recycle`` under Cloud Run /
  Supabase so connections are renewed before idle timeouts.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in this package."""


_engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def _create_engine_instance(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        # Single shared connection for ephemeral file/memory DBs avoids pool churn in CI.
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
            poolclass=StaticPool,
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=4,
        # Renew before typical managed Postgres / proxy idle cutoff (~300 s).
        pool_recycle=280,
        pool_timeout=30,
    )


def configure_engine(database_url: str | None = None) -> None:
    """(Re)bind the global engine — tests call this with alternate URLs; dispose old pool first."""
    global _engine, SessionLocal
    url = database_url or get_settings().database_url
    if _engine is not None:
        _engine.dispose()
    _engine = _create_engine_instance(url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        configure_engine()
    assert _engine is not None
    return _engine


def get_db() -> Generator[Session, None, None]:
    """Yield one request-scoped session; always closed after the response."""
    global SessionLocal
    if SessionLocal is None:
        configure_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
