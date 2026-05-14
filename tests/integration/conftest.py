"""Postgres-backed integration tests (optional).

Set ``INTEGRATION_DATABASE_URL`` to a Postgres SQLAlchemy URL, e.g.::

    export INTEGRATION_DATABASE_URL='postgresql+psycopg2://USER:PASSWORD@localhost:5432/myproject_test'

Schemas are recreated (DROP/CREATE mapped tables) only when:

- ``ALLOW_DESTRUCTIVE_INTEGRATION=1``, or
- the URL looks safe (``localhost`` / ``127.0.0.1`` and/or DB name hints like ``*_test``).
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from app.core.database import Base, get_db
from app.main import app
from app.models.user import User  # noqa: F401 — register mapper
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker


def _integration_url() -> str | None:
    url = os.environ.get("INTEGRATION_DATABASE_URL")
    if url and url.startswith("postgresql"):
        return url
    return None


def _url_allows_manage_schema(database_url: str) -> bool:
    if os.environ.get("ALLOW_DESTRUCTIVE_INTEGRATION") == "1":
        return True

    lowered = database_url.lower()
    stripped = lowered.split("?", 1)[0]
    tail_segment = stripped.rsplit("/", 1)[-1] if "/" in stripped else ""

    path_markers_ok = (
        stripped.endswith("_test")
        or "/_test" in stripped
        or "-test" in tail_segment
        or "_test" in tail_segment
        or tail_segment.startswith("test_")
    )

    network_ok = any(
        h in lowered
        for h in (
            "//localhost",
            ":localhost",
            "//127.0.0.1",
            ":127.0.0.1",
        )
    )
    return network_ok or path_markers_ok


@pytest.fixture(scope="session")
def integration_engine() -> Generator:
    url = _integration_url()
    if not url:
        pytest.skip(
            "Set INTEGRATION_DATABASE_URL to a Postgres URL to run @pytest.mark.integration tests",
        )

    if not _url_allows_manage_schema(url):
        pytest.skip(
            "INTEGRATION_DATABASE_URL does not opt into DDL "
            "(set ALLOW_DESTRUCTIVE_INTEGRATION=1 or use a *_test / localhost URI)",
        )

    try:
        engine = create_engine(url, pool_pre_ping=True)
        conn = engine.connect()
        conn.close()
    except OperationalError:
        pytest.skip("Could not reach Postgres for integration tests")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def _purge_users_each_test(integration_engine):
    with integration_engine.begin() as conn:
        conn.execute(delete(User))
    yield


@pytest.fixture
def postgres_client(integration_engine) -> Generator[TestClient, None, None]:
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=integration_engine)

    def override_get_db() -> Generator:
        session = testing_session_local()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
