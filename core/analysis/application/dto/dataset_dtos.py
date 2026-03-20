"""Data Transfer Objects for Dataset Management."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DatasetSummaryDTO(BaseModel):
    """Summary view for listing datasets."""

    id: int
    name: str
    created_at: datetime
    tags: list[str] = Field(default_factory=list)
    origin: str | None = None


class DatasetDetailDTO(BaseModel):
    """Detailed view for a single dataset."""

    id: int
    name: str
    created_at: datetime
    origin: str | None
    source_files: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    data_records_count: int = 0
