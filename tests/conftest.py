from collections.abc import Generator

import pytest
from app.core.database import Base, get_db
from app.main import app
from app.models import user as user_model  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def user_payload(index: int = 0, **overrides) -> dict:
    """Build a valid create payload; `index` keeps username/email unique per call."""
    data = {
        "username": f"operator_{index}",
        "email": f"operator_{index}@example.com",
        "first_name": "Test",
        "last_name": f"User{index}",
        "role": "user",
        "active": True,
    }
    data.update(overrides)
    return data


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(db_engine) -> Generator[TestClient, None, None]:
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

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


@pytest.fixture
def sample_user_payload() -> dict:
    return user_payload(0, username="jdoe", email="jdoe@example.com", first_name="Jane", last_name="Doe")
