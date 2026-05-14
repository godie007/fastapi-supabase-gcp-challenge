"""HTTP routes for users: Pydantic validates; ``app.crud.user`` persists."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, status

from app.api.deps import DbSessionDep
from app.crud import user as user_crud
from app.schemas.errors import ErrorResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(tags=["users"])
log = logging.getLogger(__name__)

# OpenAPI: shared error models for POST bodies (create + register).
_USER_WRITE_RESPONSES: dict[int, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "Conflict: `username` and/or `email` already in use.",
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "description": ("Request body failed Pydantic validation (format, length, email, role)."),
    },
}

_USER_ID_PATH = Path(
    ...,
    description=("Unique user identifier as a **UUID** (RFC 4122). The user must exist in the database."),
    examples=["550e8400-e29b-41d4-a716-446655440000"],
)


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description=(
        "Registers a new user. "
        "Enforces uniqueness of **`username`** and **`email`**. "
        "The server assigns **`id`** and timestamps."
    ),
    response_description="Persisted user with identifier and timestamps.",
    responses=_USER_WRITE_RESPONSES,
)
def create_user(payload: UserCreate, db: DbSessionDep) -> UserResponse:
    return user_crud.create_user(db, payload)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register user",
    description=(
        "**Public sign-up**: same behaviour as **`POST /users/`** — creates a profile with unique "
        "`username` / `email`. Use this alias when documenting onboarding flows."
    ),
    response_description="Newly registered user with server-assigned `id` and timestamps.",
    responses=_USER_WRITE_RESPONSES,
)
def register_user(payload: UserCreate, db: DbSessionDep) -> UserResponse:
    user = user_crud.create_user(db, payload)
    log.info("User registration completed: id=%s username=%s", user.id, user.username)
    return user


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List users",
    description=("Returns a window of users in database insertion order (pagination via **`skip`** / **`limit`**)."),
    response_description="List of users (may be empty).",
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid or out-of-range query parameters.",
        },
    },
)
def list_users(
    db: DbSessionDep,
    skip: Annotated[
        int,
        Query(
            ge=0,
            description="Number of rows to skip from the start of the collection.",
            examples=[0],
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=500,
            description="Maximum page size (hard cap to protect the API).",
            examples=[50],
        ),
    ] = 100,
) -> list[UserResponse]:
    return user_crud.get_users(db, skip=skip, limit=limit)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    description="Returns a single user by **`id`** (UUID).",
    response_description="Full resource representation.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No user exists for the given `user_id`.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter is not a valid UUID.",
        },
    },
)
def read_user(
    user_id: Annotated[uuid.UUID, _USER_ID_PATH],
    db: DbSessionDep,
) -> UserResponse:
    return user_crud.get_user(db, user_id)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user (partial)",
    description=(
        "Applies a **partial** update (`PATCH`): only fields present in the body are changed. "
        "Useful for role, `active`, or name changes without replacing the whole resource."
    ),
    response_description="User after applying changes (refreshed from the database).",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "User not found.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "New `username` or `email` conflicts with another row.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid UUID in path or body incompatible with the schema.",
        },
    },
)
def patch_user(
    user_id: Annotated[uuid.UUID, _USER_ID_PATH],
    payload: UserUpdate,
    db: DbSessionDep,
) -> UserResponse:
    return user_crud.update_user(db, user_id, payload)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete user",
    description=("**Permanently** deletes the user row. Response **`204`** has no body."),
    response_description="No content — operation succeeded.",
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "User deleted successfully.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No user exists for the given `user_id`.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter is not a valid UUID.",
        },
    },
)
def remove_user(
    user_id: Annotated[uuid.UUID, _USER_ID_PATH],
    db: DbSessionDep,
) -> None:
    user_crud.delete_user(db, user_id)
