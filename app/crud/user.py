"""Operaciones de persistencia para usuarios (validación de unicidad y errores HTTP coherentes)."""

import logging
import uuid

from sqlalchemy import select
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
    logger.info("Creando usuario: %s", user_in.username)
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
        db.rollback()
        logger.warning("Conflicto de integridad al crear usuario: %s", user_in.username)
        if _get_user_by_username(db, user_in.username):
            raise DuplicateUsernameError(user_in.username)
        raise DuplicateEmailError(user_in.email)

    logger.info("Usuario creado correctamente: id=%s", db_user.id)
    return db_user


def get_user(db: Session, user_id: uuid.UUID) -> User:
    logger.info("Obteniendo usuario por id: %s", user_id)
    user = db.get(User, user_id)
    if user is None:
        logger.info("Usuario no encontrado: id=%s", user_id)
        raise UserNotFoundError(str(user_id))
    return user


def get_users(db: Session, *, skip: int = 0, limit: int = 100) -> list[User]:
    logger.info("Listando usuarios: skip=%s limit=%s", skip, limit)
    stmt = select(User).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_user(db: Session, user_id: uuid.UUID, user_in: UserUpdate) -> User:
    logger.info("Actualizando usuario: id=%s", user_id)
    db_user = db.get(User, user_id)
    if db_user is None:
        logger.info("Usuario no encontrado para actualizar: id=%s", user_id)
        raise UserNotFoundError(str(user_id))

    update_data = user_in.model_dump(exclude_unset=True)
    if "username" in update_data and update_data["username"] != db_user.username:
        if _get_user_by_username(db, update_data["username"]):
            raise DuplicateUsernameError(update_data["username"])
    if "email" in update_data and update_data["email"] != db_user.email:
        if _get_user_by_email(db, update_data["email"]):
            raise DuplicateEmailError(update_data["email"])

    for field, value in update_data.items():
        setattr(db_user, field, value)

    try:
        db.commit()
        db.refresh(db_user)
    except IntegrityError:
        db.rollback()
        logger.warning("Conflicto de integridad al actualizar usuario: id=%s", user_id)
        if "username" in update_data and _get_user_by_username(db, update_data["username"]):
            raise DuplicateUsernameError(update_data["username"])
        if "email" in update_data and _get_user_by_email(db, update_data["email"]):
            raise DuplicateEmailError(update_data["email"])
        raise

    logger.info("Usuario actualizado: id=%s", db_user.id)
    return db_user


def delete_user(db: Session, user_id: uuid.UUID) -> None:
    logger.info("Eliminando usuario: id=%s", user_id)
    db_user = db.get(User, user_id)
    if db_user is None:
        logger.info("Usuario no encontrado para eliminar: id=%s", user_id)
        raise UserNotFoundError(str(user_id))
    db.delete(db_user)
    db.commit()
    logger.info("Usuario eliminado: id=%s", user_id)
