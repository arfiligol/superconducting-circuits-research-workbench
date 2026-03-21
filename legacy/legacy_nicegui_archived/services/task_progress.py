"""Reusable progress/heartbeat payload contracts for persisted task execution."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    """Return one naive UTC timestamp without using deprecated utcnow()."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class TaskProgressUpdate:
    """Structured progress update that maps cleanly to `TaskRecord.progress_payload`."""

    phase: str
    summary: str
    stage_label: str | None = None
    current_step: int | None = None
    total_steps: int | None = None
    warning: str | None = None
    stale_after_seconds: int | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_payload(
        self,
        *,
        recorded_at: datetime | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Serialize one update into the persisted task progress shape."""
        payload: dict[str, Any] = {
            "phase": str(self.phase).strip(),
            "summary": str(self.summary).strip(),
            "recorded_at": (recorded_at or _utcnow()).isoformat(),
        }
        if self.stage_label:
            payload["stage_label"] = str(self.stage_label)
        if self.current_step is not None:
            payload["current_step"] = int(self.current_step)
        if self.total_steps is not None:
            payload["total_steps"] = int(self.total_steps)
        if self.warning:
            payload["warning"] = str(self.warning)
        if self.stale_after_seconds is not None:
            payload["stale_after_seconds"] = int(self.stale_after_seconds)
        if self.details:
            payload["details"] = dict(self.details)
        if extra:
            payload.update(dict(extra))
        return payload


ProgressCallback = Callable[[TaskProgressUpdate], None]


def emit_progress(
    callback: ProgressCallback | None,
    update: TaskProgressUpdate,
) -> TaskProgressUpdate:
    """Dispatch one update to an optional progress callback and return it."""
    if callback is not None:
        callback(update)
    return update


def progress_update(
    *,
    phase: str,
    summary: str,
    stage_label: str | None = None,
    current_step: int | None = None,
    total_steps: int | None = None,
    warning: str | None = None,
    stale_after_seconds: int | None = None,
    details: Mapping[str, Any] | None = None,
) -> TaskProgressUpdate:
    """Build one structured progress update."""
    return TaskProgressUpdate(
        phase=phase,
        summary=summary,
        stage_label=stage_label,
        current_step=current_step,
        total_steps=total_steps,
        warning=warning,
        stale_after_seconds=stale_after_seconds,
        details=dict(details or {}),
    )
