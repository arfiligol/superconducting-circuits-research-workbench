"""Data Transfer Objects for DataRecord Management."""

from datetime import datetime

from pydantic import BaseModel


class DataRecordSummaryDTO(BaseModel):
    """Summary view for listing data records."""

    id: int
    dataset_id: int
    data_type: str
    parameter: str
    representation: str
    created_at: datetime | None = None


class DataRecordDetailDTO(BaseModel):
    """Detailed view for a single data record."""

    id: int
    dataset_id: int
    data_type: str
    parameter: str
    representation: str
    axes: list
    values: list
    created_at: datetime | None = None
