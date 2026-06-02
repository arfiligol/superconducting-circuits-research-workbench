from fastapi import APIRouter

from src.app.api.routers.audit_logs import router as audit_logs_router
from src.app.api.routers.circuit_definitions import router as circuit_definitions_router
from src.app.api.routers.datasets import router as datasets_router
from src.app.api.routers.health import router as health_router
from src.app.api.routers.runner import router as runner_router
from src.app.api.routers.session import router as session_router
from src.app.api.routers.tasks import router as tasks_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(session_router)
api_router.include_router(tasks_router)
api_router.include_router(runner_router)
api_router.include_router(audit_logs_router)
api_router.include_router(datasets_router)
api_router.include_router(circuit_definitions_router)
