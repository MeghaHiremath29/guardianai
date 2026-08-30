"""
GuardianAI backend entrypoint.

Run with:
    uvicorn app.main:app --reload
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth.router import router as auth_router
from app.api.users.router import router as users_router
from app.api.people.router import router as people_router
from app.api.devices.router import router as devices_router
from app.api.sensors.router import router as sensors_router
from app.api.emergencies.router import router as emergencies_router
from app.api.notifications.router import router as notifications_router
from app.api.videos.router import router as videos_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.scheduler import start_scheduler, stop_scheduler
from app.db.base_registry import Base
from app.db.session import engine

configure_logging(debug=settings.DEBUG)
logger = logging.getLogger("guardianai.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 1: create tables directly for fast local iteration.
    # From the first Alembic migration onward, prefer `alembic upgrade head`
    # over this, and remove create_all to avoid schema drift.
    Base.metadata.create_all(bind=engine)
    logger.info("guardianai.startup environment=%s", settings.ENVIRONMENT)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="GuardianAI API",
    description="Intelligent Multi-Emergency Detection & Response System — backend API.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "http.request method=%s path=%s status=%s duration_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Return clean, non-leaky validation errors instead of a raw stack trace.
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Invalid request data", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception path=%s error=%s", request.url.path, str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


@app.get("/health", tags=["system"])
def health_check() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(people_router)
app.include_router(devices_router)
app.include_router(sensors_router)
app.include_router(emergencies_router)
app.include_router(notifications_router)
app.include_router(videos_router)
