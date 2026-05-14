"""User persistence: validates uniqueness before commit and maps DB races to HTTP conflicts.

Callers (FastAPI routes) never touch ``Session`` rollback rules—every public function here
leaves the session in a clean state (either committed or rolled back on ``IntegrityError``).
"""

import logging
import uuid

from sqlalchemy import asc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateEmailError, DuplicateUsernameError, UserNotFoundError
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


def _get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalars(select(User).where(User.username == username)).first()


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email)).first()


def create_user(db: Session, user_in: UserCreate) -> User:
    logger.info("Creating user: %s", user_in.username)
    if _get_user_by_username(db, user_in.username):
        raise DuplicateUsernameError(user_in.username)
    if _get_user_by_email(db, user_in.email):
        raise DuplicateEmailError(user_in.email)

    db_user = User(
        username=user_in.username,
        email=user_in.email,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        role=user_in.role,
        active=user_in.active,
    )
    db.add(db_user)
    try:
        db.commit()
        db.refresh(db_user)
    except IntegrityError:
        # Rare race: unique index hit between our SELECT check and INSERT — surface as 409.
        db.rollback()
        logger.warning("Integrity conflict while creating user: %s", user_in.username)
        if _get_user_by_username(db, user_in.username):
            raise DuplicateUsernameError(user_in.username) from None
        raise DuplicateEmailError(user_in.email) from None

    logger.info("User created successfully: id=%s", db_user.id)
    return db_user


def get_user(db: Session, user_id: uuid.UUID) -> User:
    logger.info("Fetching user by id: %s", user_id)
    user = db.get(User, user_id)
    if user is None:
        logger.info("User not found: id=%s", user_id)
        raise UserNotFoundError(str(user_id))
    return user


def get_users(db: Session, *, skip: int = 0, limit: int = 100) -> list[User]:
    logger.info("Listing users: skip=%s limit=%s", skip, limit)
    # Deterministic order: stable offset/limit semantics across pages (REST collection paging).
    stmt = (
        select(User)
        .order_by(asc(User.created_at), asc(User.id))
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def update_user(db: Session, user_id: uuid.UUID, user_in: UserUpdate) -> User:
    logger.info("Updating user: id=%s", user_id)
    db_user = db.get(User, user_id)
    if db_user is None:
        logger.info("User not found for update: id=%s", user_id)
        raise UserNotFoundError(str(user_id))

    update_data = user_in.model_dump(exclude_unset=True)
    if (
        "username" in update_data
        and update_data["username"] != db_user.username
        and _get_user_by_username(db, update_data["username"])
    ):
        raise DuplicateUsernameError(update_data["username"])
    if (
        "email" in update_data
        and update_data["email"] != db_user.email
        and _get_user_by_email(db, update_data["email"])
    ):
        raise DuplicateEmailError(update_data["email"])

    for field, value in update_data.items():
        setattr(db_user, field, value)

    try:
        db.commit()
        db.refresh(db_user)
    except IntegrityError as exc:
        # Same pattern as create: prefer explicit username/email errors over raw 500.
        db.rollback()
        logger.warning("Integrity conflict while updating user: id=%s", user_id)
        if "username" in update_data and _get_user_by_username(db, update_data["username"]):
            raise DuplicateUsernameError(update_data["username"]) from None
        if "email" in update_data and _get_user_by_email(db, update_data["email"]):
            raise DuplicateEmailError(update_data["email"]) from None
        raise exc

    logger.info("User updated: id=%s", db_user.id)
    return db_user


def delete_user(db: Session, user_id: uuid.UUID) -> None:
    logger.info("Deleting user: id=%s", user_id)
    db_user = db.get(User, user_id)
    if db_user is None:
        logger.info("User not found for delete: id=%s", user_id)
        raise UserNotFoundError(str(user_id))
    db.delete(db_user)
    db.commit()
    logger.info("User deleted: id=%s", user_id)
