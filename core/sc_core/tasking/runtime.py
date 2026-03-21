from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from sc_core.tasking.routing import LaneName

TaskRuntimeState = Literal[
    "queued",
    "dispatching",
    "running",
    "cancellation_requested",
    "cancelling",
    "cancelled",
    "termination_requested",
    "terminated",
    "completed",
    "failed",
]
TerminalTaskState = Literal["completed", "failed", "cancelled", "terminated"]
TaskControlAction = Literal["cancel", "terminate", "retry"]
TaskControlOutcome = Literal["accepted", "rejected"]
TaskControlRejectionReason = Literal[
    "task_not_cancellable",
    "task_not_terminable",
    "task_already_terminal",
    "task_retry_denied",
]
ProcessorState = Literal["healthy", "busy", "degraded", "draining", "offline"]
ProcessorRuntimeMetadataValue = str | int | bool | None | list[str]

TASK_RUNTIME_CONTRACT_VERSION = "sc_task_runtime.v1"
REDACTED_RUNTIME_METADATA_VALUE = "[redacted]"
TERMINAL_TASK_STATES: frozenset[TaskRuntimeState] = frozenset(
    {"completed", "failed", "cancelled", "terminated"}
)
RETRYABLE_TASK_STATES: frozenset[TaskRuntimeState] = frozenset(
    {"completed", "failed", "cancelled", "terminated"}
)
_ALLOWED_TASK_TRANSITIONS: dict[TaskRuntimeState, frozenset[TaskRuntimeState]] = {
    "queued": frozenset({"dispatching", "cancelled"}),
    "dispatching": frozenset({"running", "cancellation_requested", "failed"}),
    "running": frozenset(
        {"completed", "failed", "cancellation_requested", "termination_requested"}
    ),
    "cancellation_requested": frozenset({"cancelling", "termination_requested", "cancelled"}),
    "cancelling": frozenset({"cancelled", "termination_requested"}),
    "termination_requested": frozenset({"terminated"}),
    "cancelled": frozenset(),
    "terminated": frozenset(),
    "completed": frozenset(),
    "failed": frozenset(),
}


@dataclass(frozen=True)
class TaskControlDecision:
    """Canonical evaluation result for one task control request."""

    action: TaskControlAction
    current_state: TaskRuntimeState
    outcome: TaskControlOutcome
    requested_state: TaskRuntimeState | None = None
    rejection_reason: TaskControlRejectionReason | None = None
    creates_new_task_lineage: bool = False
    terminal_state_immutable: bool = False
    idempotent: bool = False

    @property
    def accepted(self) -> bool:
        return self.outcome == "accepted"

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "contract_version": TASK_RUNTIME_CONTRACT_VERSION,
            "action": self.action,
            "current_state": self.current_state,
            "outcome": self.outcome,
            "creates_new_task_lineage": self.creates_new_task_lineage,
            "terminal_state_immutable": self.terminal_state_immutable,
            "idempotent": self.idempotent,
        }
        if self.requested_state is not None:
            payload["requested_state"] = self.requested_state
        if self.rejection_reason is not None:
            payload["rejection_reason"] = self.rejection_reason
        return payload


@dataclass(frozen=True)
class TaskRetryLineage:
    """Canonical lineage record for one retry-created task."""

    source_task_id: int
    root_task_id: int
    parent_task_id: int
    retry_attempt: int
    source_terminal_state: TerminalTaskState

    def to_payload(self) -> dict[str, int | str]:
        return {
            "source_task_id": self.source_task_id,
            "root_task_id": self.root_task_id,
            "parent_task_id": self.parent_task_id,
            "retry_attempt": self.retry_attempt,
            "source_terminal_state": self.source_terminal_state,
        }


@dataclass(frozen=True)
class TaskControlRuntimeProjection:
    """Canonical projection of one persisted control request into runtime state."""

    action: TaskControlAction
    runtime_state: TaskRuntimeState
    requested_state: TaskRuntimeState | None = None
    requested_at: str | None = None
    acknowledged_at: str | None = None
    terminal_at: str | None = None
    creates_new_task_lineage: bool = False

    @property
    def request_acknowledged(self) -> bool:
        return self.acknowledged_at is not None

    @property
    def terminal_transition_complete(self) -> bool:
        return self.terminal_at is not None

    @property
    def terminal_state(self) -> TerminalTaskState | None:
        if self.runtime_state in TERMINAL_TASK_STATES:
            return self.runtime_state
        return None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "contract_version": TASK_RUNTIME_CONTRACT_VERSION,
            "action": self.action,
            "runtime_state": self.runtime_state,
            "request_acknowledged": self.request_acknowledged,
            "terminal_transition_complete": self.terminal_transition_complete,
            "creates_new_task_lineage": self.creates_new_task_lineage,
        }
        if self.requested_state is not None:
            payload["requested_state"] = self.requested_state
        if self.requested_at is not None:
            payload["requested_at"] = self.requested_at
        if self.acknowledged_at is not None:
            payload["acknowledged_at"] = self.acknowledged_at
        if self.terminal_at is not None:
            payload["terminal_at"] = self.terminal_at
        if self.terminal_state is not None:
            payload["terminal_state"] = self.terminal_state
        return payload


@dataclass(frozen=True)
class ProcessorHeartbeat:
    """Canonical lane-scoped processor heartbeat contract."""

    processor_id: str
    lane: LaneName
    state: ProcessorState
    current_task_id: int | None
    last_heartbeat_at: datetime
    runtime_metadata: dict[str, ProcessorRuntimeMetadataValue] = field(default_factory=dict)

    def effective_state(
        self,
        *,
        recorded_at: datetime,
        offline_after_seconds: int,
    ) -> ProcessorState:
        if (recorded_at - self.last_heartbeat_at).total_seconds() > offline_after_seconds:
            return "offline"
        return self.state

    def to_payload(
        self,
        *,
        recorded_at: datetime | None = None,
        offline_after_seconds: int | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "contract_version": TASK_RUNTIME_CONTRACT_VERSION,
            "processor_id": self.processor_id,
            "lane": self.lane,
            "state": (
                self.effective_state(
                    recorded_at=recorded_at,
                    offline_after_seconds=offline_after_seconds,
                )
                if recorded_at is not None and offline_after_seconds is not None
                else self.state
            ),
            "last_heartbeat_at": self.last_heartbeat_at.isoformat(),
            "runtime_metadata": dict(self.runtime_metadata),
        }
        if self.current_task_id is not None:
            payload["current_task_id"] = self.current_task_id
        return payload


@dataclass(frozen=True)
class LaneProcessorSummary:
    """Canonical processor summary derived per workflow lane."""

    lane: LaneName
    healthy_processors: int = 0
    busy_processors: int = 0
    degraded_processors: int = 0
    draining_processors: int = 0
    offline_processors: int = 0

    def to_payload(self) -> dict[str, object]:
        return {
            "contract_version": TASK_RUNTIME_CONTRACT_VERSION,
            "lane": self.lane,
            "healthy_processors": self.healthy_processors,
            "busy_processors": self.busy_processors,
            "degraded_processors": self.degraded_processors,
            "draining_processors": self.draining_processors,
            "offline_processors": self.offline_processors,
        }


def build_task_state_matrix() -> dict[TaskRuntimeState, tuple[TaskRuntimeState, ...]]:
    """Return the canonical task runtime state matrix."""
    return {
        state: tuple(sorted(next_states))
        for state, next_states in _ALLOWED_TASK_TRANSITIONS.items()
    }


def allowed_task_runtime_transitions(state: TaskRuntimeState) -> tuple[TaskRuntimeState, ...]:
    """Return the canonical next states allowed from one current state."""
    return tuple(sorted(_ALLOWED_TASK_TRANSITIONS[state]))


def is_terminal_task_state(state: TaskRuntimeState) -> bool:
    """Return whether one task state is terminal and therefore immutable."""
    return state in TERMINAL_TASK_STATES


def can_transition_task_state(
    current_state: TaskRuntimeState,
    next_state: TaskRuntimeState,
) -> bool:
    """Return whether one task runtime transition is allowed."""
    if current_state == next_state and is_terminal_task_state(current_state):
        return True
    return next_state in _ALLOWED_TASK_TRANSITIONS[current_state]


def evaluate_task_control_action(
    action: TaskControlAction,
    *,
    current_state: TaskRuntimeState,
) -> TaskControlDecision:
    """Evaluate the canonical control semantics for one persisted task."""
    if action == "cancel":
        return _evaluate_cancel(current_state)
    if action == "terminate":
        return _evaluate_terminate(current_state)
    if action == "retry":
        return _evaluate_retry(current_state)
    raise ValueError(f"Unsupported task control action '{action}'.")


def build_task_retry_lineage(
    *,
    source_task_id: int,
    source_task_state: TaskRuntimeState,
    root_task_id: int | None = None,
    prior_retry_attempt: int = 0,
) -> TaskRetryLineage:
    """Build the canonical retry lineage for one new task created from a terminal task."""
    decision = evaluate_task_control_action("retry", current_state=source_task_state)
    if not decision.accepted:
        raise ValueError(f"Task state '{source_task_state}' is not eligible for retry.")
    return TaskRetryLineage(
        source_task_id=source_task_id,
        root_task_id=source_task_id if root_task_id is None else root_task_id,
        parent_task_id=source_task_id,
        retry_attempt=prior_retry_attempt + 1,
        source_terminal_state=source_task_state,
    )


def build_processor_heartbeat(
    *,
    processor_id: str,
    lane: LaneName,
    state: ProcessorState,
    last_heartbeat_at: datetime,
    current_task_id: int | None = None,
    runtime_metadata: Mapping[str, object] | None = None,
) -> ProcessorHeartbeat:
    """Build a canonical processor heartbeat with redaction-safe runtime metadata."""
    return ProcessorHeartbeat(
        processor_id=processor_id.strip(),
        lane=lane,
        state=state,
        current_task_id=current_task_id,
        last_heartbeat_at=last_heartbeat_at,
        runtime_metadata=sanitize_processor_runtime_metadata(runtime_metadata),
    )


def build_processor_heartbeat_from_snapshot(
    snapshot: Mapping[str, object],
) -> ProcessorHeartbeat:
    """Project one persisted processor snapshot into the canonical heartbeat contract."""
    processor_id = snapshot.get("processor_id")
    if not isinstance(processor_id, str) or not processor_id.strip():
        raise ValueError("Processor snapshot is missing processor_id.")
    return build_processor_heartbeat(
        processor_id=processor_id,
        lane=_coerce_lane_name(snapshot.get("lane")),
        state=_coerce_processor_state(snapshot.get("state")),
        current_task_id=_coerce_optional_int(snapshot.get("current_task_id")),
        last_heartbeat_at=_coerce_datetime(snapshot.get("last_heartbeat_at")),
        runtime_metadata=_coerce_runtime_metadata_mapping(snapshot.get("runtime_metadata")),
    )


def summarize_lane_processors(
    heartbeats: Sequence[ProcessorHeartbeat],
    *,
    lane: LaneName,
    recorded_at: datetime,
    offline_after_seconds: int = 90,
) -> LaneProcessorSummary:
    """Summarize processor health counts for one specific lane only."""
    counts = {
        "healthy": 0,
        "busy": 0,
        "degraded": 0,
        "draining": 0,
        "offline": 0,
    }
    for heartbeat in heartbeats:
        if heartbeat.lane != lane:
            continue
        counts[
            heartbeat.effective_state(
                recorded_at=recorded_at,
                offline_after_seconds=offline_after_seconds,
            )
        ] += 1
    return LaneProcessorSummary(
        lane=lane,
        healthy_processors=counts["healthy"],
        busy_processors=counts["busy"],
        degraded_processors=counts["degraded"],
        draining_processors=counts["draining"],
        offline_processors=counts["offline"],
    )


def build_lane_processor_summaries(
    heartbeats: Sequence[ProcessorHeartbeat],
    *,
    recorded_at: datetime,
    offline_after_seconds: int = 90,
) -> tuple[LaneProcessorSummary, ...]:
    """Build lane-scoped processor summaries without collapsing lanes into global totals."""
    lanes = tuple(sorted({heartbeat.lane for heartbeat in heartbeats}))
    return tuple(
        summarize_lane_processors(
            heartbeats,
            lane=lane,
            recorded_at=recorded_at,
            offline_after_seconds=offline_after_seconds,
        )
        for lane in lanes
    )


def summarize_lane_processor_snapshots(
    snapshots: Sequence[Mapping[str, object]],
    *,
    lane: LaneName,
    recorded_at: datetime,
    offline_after_seconds: int = 90,
) -> LaneProcessorSummary:
    """Project one lane summary directly from raw processor snapshot payloads."""
    return summarize_lane_processors(
        tuple(build_processor_heartbeat_from_snapshot(snapshot) for snapshot in snapshots),
        lane=lane,
        recorded_at=recorded_at,
        offline_after_seconds=offline_after_seconds,
    )


def build_lane_processor_summaries_from_snapshots(
    snapshots: Sequence[Mapping[str, object]],
    *,
    recorded_at: datetime,
    offline_after_seconds: int = 90,
) -> tuple[LaneProcessorSummary, ...]:
    """Project lane-scoped processor summaries from raw snapshot payloads."""
    return build_lane_processor_summaries(
        tuple(build_processor_heartbeat_from_snapshot(snapshot) for snapshot in snapshots),
        recorded_at=recorded_at,
        offline_after_seconds=offline_after_seconds,
    )


def sanitize_processor_runtime_metadata(
    metadata: Mapping[str, object] | None,
) -> dict[str, ProcessorRuntimeMetadataValue]:
    """Coerce runtime metadata into a redaction-safe processor contract payload."""
    if metadata is None:
        return {}
    sanitized: dict[str, ProcessorRuntimeMetadataValue] = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            continue
        sanitized[key] = _sanitize_runtime_metadata_value(value)
    return sanitized


def _evaluate_cancel(current_state: TaskRuntimeState) -> TaskControlDecision:
    if current_state in TERMINAL_TASK_STATES:
        return TaskControlDecision(
            action="cancel",
            current_state=current_state,
            outcome="rejected",
            rejection_reason="task_already_terminal",
            terminal_state_immutable=True,
        )
    if current_state == "queued":
        return TaskControlDecision(
            action="cancel",
            current_state=current_state,
            outcome="accepted",
            requested_state="cancelled",
        )
    if current_state in {"dispatching", "running"}:
        return TaskControlDecision(
            action="cancel",
            current_state=current_state,
            outcome="accepted",
            requested_state="cancellation_requested",
        )
    if current_state in {"cancellation_requested", "cancelling"}:
        return TaskControlDecision(
            action="cancel",
            current_state=current_state,
            outcome="accepted",
            requested_state=current_state,
            idempotent=True,
        )
    return TaskControlDecision(
        action="cancel",
        current_state=current_state,
        outcome="rejected",
        rejection_reason="task_not_cancellable",
    )


def _evaluate_terminate(current_state: TaskRuntimeState) -> TaskControlDecision:
    if current_state in TERMINAL_TASK_STATES:
        return TaskControlDecision(
            action="terminate",
            current_state=current_state,
            outcome="rejected",
            rejection_reason="task_already_terminal",
            terminal_state_immutable=True,
        )
    if current_state in {"running", "cancellation_requested", "cancelling"}:
        return TaskControlDecision(
            action="terminate",
            current_state=current_state,
            outcome="accepted",
            requested_state="termination_requested",
        )
    if current_state == "termination_requested":
        return TaskControlDecision(
            action="terminate",
            current_state=current_state,
            outcome="accepted",
            requested_state="termination_requested",
            idempotent=True,
        )
    return TaskControlDecision(
        action="terminate",
        current_state=current_state,
        outcome="rejected",
        rejection_reason="task_not_terminable",
    )


def _evaluate_retry(current_state: TaskRuntimeState) -> TaskControlDecision:
    if current_state in RETRYABLE_TASK_STATES:
        return TaskControlDecision(
            action="retry",
            current_state=current_state,
            outcome="accepted",
            creates_new_task_lineage=True,
            terminal_state_immutable=True,
        )
    return TaskControlDecision(
        action="retry",
        current_state=current_state,
        outcome="rejected",
        rejection_reason="task_retry_denied",
    )


def _sanitize_runtime_metadata_value(value: object) -> ProcessorRuntimeMetadataValue:
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [
            (
                item
                if isinstance(item, str)
                else REDACTED_RUNTIME_METADATA_VALUE
                if isinstance(item, Mapping | bytes | bytearray)
                else str(item)
            )
            for item in value
        ]
    return REDACTED_RUNTIME_METADATA_VALUE


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        coerced = value
    elif isinstance(value, str):
        text = value.strip()
        normalized_text = text[:-1] + "+00:00" if text.endswith("Z") else text
        coerced = datetime.fromisoformat(normalized_text)
    else:
        raise ValueError("Expected datetime-compatible last_heartbeat_at value.")
    if coerced.tzinfo is None:
        return coerced.replace(tzinfo=UTC)
    return coerced.astimezone(UTC)


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("Expected integer-compatible current_task_id value.")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text:
            return int(text)
    raise ValueError("Expected integer-compatible current_task_id value.")


def _coerce_lane_name(value: object) -> LaneName:
    if value in {"simulation", "characterization"}:
        return value
    raise ValueError("Expected supported lane value.")


def _coerce_processor_state(value: object) -> ProcessorState:
    if value in {"healthy", "busy", "degraded", "draining", "offline"}:
        return value
    raise ValueError("Expected supported processor state value.")


def _coerce_runtime_metadata_mapping(value: object) -> Mapping[str, object] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value
    raise ValueError("Expected mapping runtime_metadata value.")
