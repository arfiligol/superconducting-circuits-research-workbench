"""Typed query objects for persistence repository pagination/filter APIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TraceModeFilter = Literal["all", "base", "sideband"]


@dataclass(slots=True, frozen=True)
class TraceIndexPageQuery:
    """Query payload for lightweight trace-index pagination/filtering."""

    search: str = ""
    sort_by: str = "id"
    descending: bool = False
    data_type: str = ""
    data_types: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ()
    representation: str = ""
    mode_filter: TraceModeFilter = "all"
    ids: tuple[int, ...] | None = None
    limit: int = 20
    offset: int = 0
