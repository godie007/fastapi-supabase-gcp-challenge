"""Pydantic user schemas — sanitization and enums without spinning up the ASGI stack."""

from __future__ import annotations

import pytest
from app.models.user import UserRole
from app.schemas.user import UserCreate, UserUpdate
from pydantic import ValidationError

pytestmark = pytest.mark.unit


def test_create_strips_names_and_lowercases_email():
    obj = UserCreate(
        username="  alice  ",
        email=" Alice@Example.COM ",
        first_name="  Ada ",
        last_name=" Lovelace ",
    )
    assert obj.username == "alice"
    assert obj.email == "alice@example.com"


def test_create_rejects_whitespace_username():
    with pytest.raises(ValidationError):
        UserCreate(username="   ", email="z@example.com", first_name="A", last_name="B")


def test_create_unknown_role_raises():
    with pytest.raises(ValidationError):
        UserCreate(
            username="u",
            email="u@example.com",
            first_name="f",
            last_name="l",
            role="not_a_role",
        )


def test_update_optional_fields_normalized_or_rejected():
    u = UserUpdate(username="  x  ", email="  Y@Z.COM  ")
    assert u.username == "x"
    assert u.email == "y@z.com"

    with pytest.raises(ValidationError):
        UserUpdate(username="   ", email=None)


def test_all_roles_construct():
    """Enum wiring matches OpenAPI literals."""
    for role in UserRole:
        c = UserCreate(
            username=f"role_{role.value}",
            email=f"{role.value}@example.com",
            first_name="R",
            last_name="Z",
            role=role,
        )
        assert c.role == role
