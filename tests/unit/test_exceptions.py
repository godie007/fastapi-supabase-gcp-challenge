"""HTTP exception helpers — predictable status codes for OpenAPI-aligned errors."""

from __future__ import annotations

import pytest
from app.core.exceptions import DuplicateEmailError, DuplicateUsernameError, UserNotFoundError
from fastapi import status

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("exc_class", "arg", "code"),
    (
        (DuplicateUsernameError, "taken", status.HTTP_409_CONFLICT),
        (DuplicateEmailError, "dup@example.com", status.HTTP_409_CONFLICT),
        (UserNotFoundError, "550e8400-e29b-41d4-a716-446655440000", status.HTTP_404_NOT_FOUND),
    ),
)
def test_domain_exceptions_are_http_compatible(exc_class, arg, code):
    exc = exc_class(arg)
    assert exc.status_code == code
    assert isinstance(exc.detail, str)
    assert arg in exc.detail
