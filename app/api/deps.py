"""Composable FastAPI dependencies (type aliases kept here to avoid coupling routers to ``get_db``)."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

DbSessionDep = Annotated[Session, Depends(get_db)]
