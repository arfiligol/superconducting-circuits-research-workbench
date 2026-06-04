from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class AxisPayload:
    """Axis definition for dataset payloads."""

    name: str
    unit: str
    values: Sequence[float]


@dataclass(frozen=True)
class DataPayload:
    """Single data record payload."""

    data_type: str
    parameter: str
    representation: str
    axes: list[AxisPayload]
    values: list


@dataclass(frozen=True)
class DatasetPayload:
    """Preprocessed ingest payload destined for design/trace persistence."""

    source_meta: dict
    parameters: dict
    data_records: list[DataPayload]
    raw_files: list[str]
