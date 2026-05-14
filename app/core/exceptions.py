"""Domain-level HTTP exceptions (maps business rules -> status codes FastAPI emits)."""

from fastapi import HTTPException, status


class DuplicateUsernameError(HTTPException):
    def __init__(self, username: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username already exists: {username}",
        )


class DuplicateEmailError(HTTPException):
    def __init__(self, email: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email already exists: {email}",
        )


class UserNotFoundError(HTTPException):
    def __init__(self, user_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {user_id}",
        )
