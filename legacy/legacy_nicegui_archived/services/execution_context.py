"""Shared execution-context contracts for UI, worker, CLI, and API callers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.shared.persistence.models import normalize_user_role


def _utcnow() -> datetime:
    """Return one naive UTC timestamp without using deprecated utcnow()."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class ActorContext:
    """One explicit actor shape that does not depend on HTTP/session objects."""

    actor_id: int | None = None
    requested_by: str = "system"
    role: str | None = None
    auth_source: str = "system"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        requested_by = str(self.requested_by).strip() or "system"
        auth_source = str(self.auth_source).strip() or "system"
        role = self.role
        normalized_role = normalize_user_role(role) if role is not None else None
        object.__setattr__(self, "requested_by", requested_by)
        object.__setattr__(self, "auth_source", auth_source)
        object.__setattr__(self, "role", normalized_role)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_payload(self) -> dict[str, Any]:
        """Return one JSON-safe actor payload for task/audit propagation."""
        payload: dict[str, Any] = {
            "actor_id": self.actor_id,
            "requested_by": self.requested_by,
            "auth_source": self.auth_source,
        }
        if self.role is not None:
            payload["role"] = self.role
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True)
class UseCaseContext:
    """Cross-surface execution metadata carried through application boundaries."""

    actor: ActorContext = field(default_factory=ActorContext)
    source: str = "system"
    task_id: int | None = None
    dedupe_key: str | None = None
    force_rerun: bool = False
    requested_at: datetime = field(default_factory=_utcnow)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        source = str(self.source).strip() or "system"
        dedupe_key = str(self.dedupe_key).strip() or None if self.dedupe_key is not None else None
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "dedupe_key", dedupe_key)
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def requested_by(self) -> str:
        """Expose the persisted task requested-by token."""
        return self.actor.requested_by

    def to_payload(self) -> dict[str, Any]:
        """Return one JSON-safe context payload for task requests/audit."""
        payload: dict[str, Any] = {
            "source": self.source,
            "force_rerun": bool(self.force_rerun),
            "requested_at": self.requested_at.isoformat(),
            "actor": self.actor.to_payload(),
        }
        if self.task_id is not None:
            payload["task_id"] = int(self.task_id)
        if self.dedupe_key is not None:
            payload["dedupe_key"] = self.dedupe_key
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


def build_ui_use_case_context(
    *,
    actor_id: int | None = None,
    role: str | None = None,
    requested_by: str = "ui",
    metadata: Mapping[str, Any] | None = None,
) -> UseCaseContext:
    """Build one UI-originated use-case context without coupling to session objects."""
    return UseCaseContext(
        actor=ActorContext(
            actor_id=actor_id,
            requested_by=requested_by,
            role=role,
            auth_source="ui",
            metadata=dict(metadata or {}),
        ),
        source="ui",
    )
