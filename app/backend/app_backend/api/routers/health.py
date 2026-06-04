from typing import Annotated

from fastapi import APIRouter, Depends

from app_backend.domain.health import HealthStatus
from app_backend.infrastructure.runtime import get_health_service
from app_backend.services.health_service import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def read_health(
    health_service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthStatus:
    return health_service.get_status()
