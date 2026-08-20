from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import get_settings_dep
from app.core import database as db
from app.core.config import Settings
from app.schemas import HealthOut

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthOut,
    responses={503: {"model": HealthOut}},
    summary="Liveness and database connectivity",
)
async def health(
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> HealthOut | JSONResponse:
    try:
        async with db.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timezone": settings.clinic_timezone,
                "database": "down",
            },
        )
    return HealthOut(status="ok", timezone=settings.clinic_timezone, database="up")
