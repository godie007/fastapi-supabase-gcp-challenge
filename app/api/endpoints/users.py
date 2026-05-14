"""HTTP routes for users: Pydantic validates; ``app.crud.user`` persists."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, Request, Response, status

from app.api.deps import DbSessionDep
from app.core.config import get_settings
from app.core.limiter import limiter
from app.crud import user as user_crud
from app.schemas.errors import ErrorResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(tags=["users"])
log = logging.getLogger(__name__)
_settings = get_settings()
_WRITE_RATE = _settings.rate_limit_write if _settings.rate_limit_enabled else "100000/second"

# OpenAPI — rate quota responses (slowapi).
_RATE_TOO_MANY: dict[int, dict[str, Any]] = {
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "description": "`429` — exceeded in-process quota (slowapi); try again later.",
    },
}

# OpenAPI: validation/conflict errors on POST bodies (create + register).
_USER_WRITE_RESPONSES: dict[int, dict[str, Any]] = {
    **_RATE_TOO_MANY,
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "Conflict: `username` and/or `email` already in use.",
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "description": ("Request body failed Pydantic validation (format, length, email, role)."),
    },
}

# 201 Created includes Location header (RFC 7231).
_USER_POST_RESPONSES: dict[int, dict[str, Any]] = {
    **_USER_WRITE_RESPONSES,
    status.HTTP_201_CREATED: {
        "description": "User created.",
        "headers": {
            "Location": {
                "description": "Canonical URL for `GET /users/{id}` of the new resource (RFC 7231).",
                "schema": {"type": "string"},
            },
        },
    },
}


def _attach_user_location(request: Request, response: Response, user_id: uuid.UUID) -> None:
    """Set ``Location`` for ``201 Created`` pointing at the persisted user resource."""
    response.headers["Location"] = str(request.url_for("users-read", user_id=str(user_id)))


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
    responses=_USER_POST_RESPONSES,
)
@limiter.limit(_WRITE_RATE)
def create_user(
    request: Request,
    response: Response,
    db: DbSessionDep,
    payload: UserCreate,
) -> UserResponse:
    user = user_crud.create_user(db, payload)
    _attach_user_location(request, response, user.id)
    return user


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
    responses=_USER_POST_RESPONSES,
)
@limiter.limit(_WRITE_RATE)
def register_user(
    request: Request,
    response: Response,
    db: DbSessionDep,
    payload: UserCreate,
) -> UserResponse:
    user = user_crud.create_user(db, payload)
    log.info("User registration completed: id=%s username=%s", user.id, user.username)
    _attach_user_location(request, response, user.id)
    return user


@router.get(
    "",
    response_model=list[UserResponse],
    summary="List users",
    description=(
        "Same as **`GET /users/`** — offered **without** a trailing slash so clients are not forced "
        "through a redirect that might mishandle query strings (`skip`, `limit`)."
    ),
    response_description="Slice of the collection (may be empty).",
    responses={
        **_RATE_TOO_MANY,
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid or out-of-range query parameters.",
        },
    },
    include_in_schema=False,
)
@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List users",
    description=(
        "Returns a **page** of the **`users`** collection. "
        "Resources are ordered deterministically by **`created_at`**, then **`id`** (stable `skip` / `limit`)."
    ),
    response_description="Slice of the collection (may be empty).",
    responses={
        **_RATE_TOO_MANY,
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid or out-of-range query parameters.",
        },
    },
)
def list_users(
    _request: Request,
    db: DbSessionDep,
    skip: Annotated[
        int,
        Query(
            ge=0,
            description="Offset into the ordered collection (RFC 5988-style paging).",
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
    name="users-read",
    summary="Get user by ID",
    description="Returns an **item** resource: a single user identified by **`id`** (UUID).",
    response_description="Full resource representation.",
    responses={
        **_RATE_TOO_MANY,
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
    _request: Request,
    user_id: Annotated[uuid.UUID, _USER_ID_PATH],
    db: DbSessionDep,
) -> UserResponse:
    return user_crud.get_user(db, user_id)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user (partial)",
    description=(
        "**Partial state change** on an existing item (`PATCH`), not a full replacement (`PUT`). "
        "Only fields present in the body are applied."
    ),
    response_description="User after applying changes (refreshed from the database).",
    responses={
        **_RATE_TOO_MANY,
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
    _request: Request,
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
    description=(
        "**Removes** the user item from the collection. **`DELETE`** is idempotent at the HTTP layer "
        "only in the sense that the resource disappears; a second call yields **`404`**."
    ),
    response_description="No content — operation succeeded.",
    responses={
        **_RATE_TOO_MANY,
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
    _request: Request,
    user_id: Annotated[uuid.UUID, _USER_ID_PATH],
    db: DbSessionDep,
) -> None:
    user_crud.delete_user(db, user_id)
