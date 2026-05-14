"""Application factory: OpenAPI metadata, request logging, and mounted routers."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.router import api_router
from app.openapi_metadata import API_DESCRIPTION, API_TITLE, OPENAPI_TAGS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hook (extend here for DB probes or warm-up tasks)."""
    logger.info("FastAPI application startup")
    yield


app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
    contact={
        "name": "Backend team — Users API",
        "url": "https://github.com/",
    },
    license_info={
        "name": "Internal / challenge — see repository license",
        "identifier": "MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "syntaxHighlight.theme": "agate",
        "tryItOutEnabled": True,
    },
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Structured access log: method, path, status, wall time (no request body)."""
    start = time.perf_counter()
    logger.info("Incoming request: %s %s", request.method, request.url.path)
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "Request completed: %s %s -> %s (%.2f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


app.include_router(api_router)
