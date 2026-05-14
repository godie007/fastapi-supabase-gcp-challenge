"""Configuration, DB engine/session, and domain-level HTTP exceptions."""

from app.core.config import Settings, get_settings
from app.core.database import Base, configure_engine, get_db, get_engine
from app.core.exceptions import (
    DuplicateEmailError,
    DuplicateUsernameError,
    UserNotFoundError,
)

__all__ = [
    "Base",
    "DuplicateEmailError",
    "DuplicateUsernameError",
    "Settings",
    "UserNotFoundError",
    "configure_engine",
    "get_db",
    "get_engine",
    "get_settings",
]
