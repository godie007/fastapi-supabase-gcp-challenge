"""Shared response models for error payloads in OpenAPI."""

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Typical HTTP error body (`detail` is safe for API consumers)."""

    detail: str = Field(
        ...,
        description="Human-readable message or identifier describing the failure.",
        examples=["User not found: 550e8400-e29b-41d4-a716-446655440000"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"detail": "User not found: 550e8400-e29b-41d4-a716-446655440000"},
                {"detail": "Username already exists: jdoe"},
                {"detail": "Email already exists: jdoe@example.com"},
            ]
        }
    )
