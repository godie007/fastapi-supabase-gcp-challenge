from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
SessionLocal = None


def _create_engine_instance(database_url: str):
    if database_url.startswith("sqlite"):
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
        pool_recycle=280,
        pool_timeout=30,
    )


def configure_engine(database_url: str | None = None) -> None:
    """Bind SQLAlchemy engine and session factory (used by tests)."""
    global _engine, SessionLocal
    url = database_url or get_settings().database_url
    if _engine is not None:
        _engine.dispose()
    _engine = _create_engine_instance(url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def get_engine():
    global _engine
    if _engine is None:
        configure_engine()
    assert _engine is not None
    return _engine


def get_db() -> Generator[Session, None, None]:
    global SessionLocal
    if SessionLocal is None:
        configure_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
