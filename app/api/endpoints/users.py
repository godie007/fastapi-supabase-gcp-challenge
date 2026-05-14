"""Rutas REST del recurso User: delegación fina a la capa CRUD."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import user as user_crud
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(tags=["users"])


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    return user_crud.create_user(db, payload)


@router.get("/", response_model=list[UserResponse])
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)) -> list[UserResponse]:
    return user_crud.get_users(db, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
def read_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> UserResponse:
    return user_crud.get_user(db, user_id)


@router.patch("/{user_id}", response_model=UserResponse)
def patch_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
) -> UserResponse:
    return user_crud.update_user(db, user_id, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def remove_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    user_crud.delete_user(db, user_id)
