"""Data Transfer Objects for DerivedParameter Management."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DerivedParameterSummaryDTO(BaseModel):
    """Summary view for listing derived parameters."""

    id: int
    dataset_id: int
    name: str
    value: float
    unit: str | None = None
    device_type: str


class DerivedParameterDetailDTO(BaseModel):
    """Detailed view for a single derived parameter."""

    id: int
    dataset_id: int
    name: str
    value: float
    unit: str | None
    device_type: str
    method: str | None
    extra: dict[str, Any]
    created_at: datetime
