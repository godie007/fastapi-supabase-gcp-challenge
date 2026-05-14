import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    username: str = Field(..., max_length=100)
    email: EmailStr
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    role: UserRole = UserRole.user
    active: bool = True


class UserCreate(UserBase):
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
    username: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    role: UserRole | None = None
    active: bool | None = None

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
    id: uuid.UUID
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    created_at: datetime
    updated_at: datetime
    active: bool

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
