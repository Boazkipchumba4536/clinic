from fastapi import APIRouter

from app.api.routes.appointments import router as appointments_router
from app.api.routes.doctors import router as doctors_router
from app.api.routes.health import router as health_router
from app.api.routes.patients import router as patients_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(appointments_router)
api_router.include_router(doctors_router)
api_router.include_router(patients_router)
