from typing import Annotated

from fastapi import APIRouter, Depends

from src.app.domain.health import HealthStatus
from src.app.infrastructure.runtime import get_health_service
from src.app.services.health_service import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def read_health(
    health_service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthStatus:
    return health_service.get_status()
