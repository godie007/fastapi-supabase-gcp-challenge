"""Pydantic models for REST request/response validation and OpenAPI examples."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    """Fields common to create/update shapes (role + active have API-friendly defaults)."""

    username: str = Field(
        ...,
        max_length=100,
        description="Unique username in the system.",
        examples=["jdoe"],
    )
    email: EmailStr = Field(
        ...,
        description="Valid, unique email address.",
        examples=["jdoe@example.com"],
    )
    first_name: str = Field(
        ...,
        max_length=100,
        description="Given name.",
        examples=["Jane"],
    )
    last_name: str = Field(
        ...,
        max_length=100,
        description="Family name.",
        examples=["Doe"],
    )
    role: UserRole = Field(
        default=UserRole.user,
        description="User role (`admin`, `user`, `guest`).",
    )
    active: bool = Field(
        default=True,
        description="Whether the profile is enabled for operational use.",
    )


class UserCreate(UserBase):
    """Complete payload for POST (server supplies ``id`` and timestamps)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "jdoe",
                "email": "jdoe@example.com",
                "first_name": "Jane",
                "last_name": "Doe",
                "role": "user",
                "active": True,
            }
        }
    )


class UserUpdate(BaseModel):
    """PATCH body: every field optional; only provided keys are merged (``exclude_unset`` in CRUD)."""

    username: str | None = Field(
        None,
        max_length=100,
        description="New unique username. Omit if unchanged.",
    )
    email: EmailStr | None = Field(
        None,
        description="New unique email. Omit if unchanged.",
    )
    first_name: str | None = Field(None, max_length=100, description="New given name.")
    last_name: str | None = Field(None, max_length=100, description="New family name.")
    role: UserRole | None = Field(None, description="New role.")
    active: bool | None = Field(None, description="New active flag.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "Janet",
                "role": "admin",
                "active": True,
            }
        }
    )


class UserResponse(BaseModel):
    """Outbound user row (``from_attributes`` maps SQLAlchemy ``User`` instances)."""

    id: uuid.UUID = Field(..., description="Unique identifier (**UUID v4**).")
    username: str = Field(..., description="Username.")
    email: EmailStr = Field(..., description="Email address.")
    first_name: str = Field(..., description="Given name.")
    last_name: str = Field(..., description="Family name.")
    role: UserRole = Field(..., description="Current role.")
    created_at: datetime = Field(
        ...,
        description="Creation timestamp (**timezone-aware**).",
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp (**timezone-aware**).",
    )
    active: bool = Field(..., description="Whether the profile is active.")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "jdoe",
                "email": "jdoe@example.com",
                "first_name": "Jane",
                "last_name": "Doe",
                "role": "user",
                "created_at": "2026-05-13T12:00:00Z",
                "updated_at": "2026-05-13T12:00:00Z",
                "active": True,
            }
        },
    )
