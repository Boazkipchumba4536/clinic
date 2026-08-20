import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

import app.models  # noqa: F401  # register metadata
from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError, SlotUnavailable
from app.schemas import ErrorBody, ErrorResponse

settings = get_settings()


def error_payload(code: str, message: str, details: dict | None = None) -> dict:
    body = ErrorBody(code=code, message=message, details=details or {})
    return ErrorResponse(error=body).model_dump()


def create_app() -> FastAPI:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    application = FastAPI(
        title="Clinic Booking API",
        version="1.0.0",
        description=(
            "REST API for a small clinic appointment system. "
            "Working hours are interpreted in Africa/Nairobi; instants are stored in UTC. "
            "Authentication is intentionally out of scope for this assessment."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=settings.cors_origin_list != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)

    @application.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.details),
        )

    @application.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "VALIDATION_ERROR",
                "Request validation failed.",
                {"errors": exc.errors()},
            ),
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code, message),
        )

    @application.exception_handler(IntegrityError)
    async def integrity_handler(_request: Request, exc: IntegrityError) -> JSONResponse:
        orig = str(getattr(exc, "orig", exc))
        if "uq_appointments_doctor_slot_booked" in orig:
            conflict = SlotUnavailable()
            return JSONResponse(
                status_code=conflict.status_code,
                content=error_payload(conflict.code, conflict.message),
            )
        return JSONResponse(
            status_code=409,
            content=error_payload("INTEGRITY_ERROR", "The request conflicts with existing data."),
        )

    @application.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "name": "Clinic Booking API",
            "docs": "/docs",
            "health": "/health",
        }

    return application


app = create_app()
