"""Punto de entrada FastAPI: middleware de logging HTTP y registro de rutas."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.router import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Arranque explícito para observabilidad (requisito del challenge: logging básico).
    logger.info("Inicio de la aplicación FastAPI")
    yield


app = FastAPI(title="Users API", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Una línea por petición + duración aproximada; la lógica de negocio permanece en CRUD.
    start = time.perf_counter()
    logger.info("Petición entrante: %s %s", request.method, request.url.path)
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "Petición completada: %s %s -> %s (%.2f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


app.include_router(api_router)
