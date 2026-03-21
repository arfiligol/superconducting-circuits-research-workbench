from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from sc_core.execution import (
    TaskExecutionHistoryEvent,
    build_task_control_audit_payload,
    build_task_control_event_log,
    build_task_control_history_event,
    build_task_control_history_metadata,
    build_task_control_history_pair,
    build_task_execution_history_context,
    build_task_lifecycle_history_metadata,
    build_task_submission_history_metadata,
    canonicalize_execution_timestamp,
    canonicalize_task_history_event_metadata,
    canonicalize_utc_datetime,
    normalize_task_history_event_metadata,
    project_task_control_transition,
    project_task_runtime_state_from_history,
    validate_task_history_event_metadata,
)
from sc_core.tasking import (
    REDACTED_RUNTIME_METADATA_VALUE,
    TERMINAL_TASK_STATES,
    allowed_task_runtime_transitions,
    build_lane_processor_summaries,
    build_lane_processor_summaries_from_snapshots,
    build_processor_heartbeat,
    build_processor_heartbeat_from_snapshot,
    build_task_dispatch_record,
    build_task_retry_lineage,
    build_task_state_matrix,
    can_transition_task_state,
    evaluate_task_control_action,
    is_terminal_task_state,
    resolve_worker_task_route,
    summarize_lane_processors,
)


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def _history_event(
    *,
    event_key: str,
    event_type: str,
    occurred_at: datetime,
    message: str,
    metadata: dict[str, object],
    level: str = "info",
) -> TaskExecutionHistoryEvent:
    return TaskExecutionHistoryEvent.from_mapping(
        event_key=event_key,
        event_type=event_type,  # type: ignore[arg-type]
        level=level,  # type: ignore[arg-type]
        occurred_at=occurred_at.isoformat(),
        message=message,
        metadata=metadata,
    )


def test_task_state_matrix_keeps_terminal_states_immutable() -> None:
    matrix = build_task_state_matrix()

    assert matrix["queued"] == ("cancelled", "dispatching")
    assert "termination_requested" in matrix["running"]
    assert allowed_task_runtime_transitions("completed") == ()
    assert is_terminal_task_state("completed") is True
    assert is_terminal_task_state("running") is False
    assert {"completed", "failed", "cancelled", "terminated"} == TERMINAL_TASK_STATES
    assert can_transition_task_state("running", "termination_requested") is True
    assert can_transition_task_state("completed", "failed") is False
    assert can_transition_task_state("terminated", "terminated") is True


def test_control_semantics_keep_cancel_terminate_and_retry_distinct() -> None:
    cancel_running = evaluate_task_control_action("cancel", current_state="running")
    assert cancel_running.accepted is True
    assert cancel_running.requested_state == "cancellation_requested"
    assert cancel_running.creates_new_task_lineage is False

    terminate_cancel_pending = evaluate_task_control_action(
        "terminate",
        current_state="cancellation_requested",
    )
    assert terminate_cancel_pending.accepted is True
    assert terminate_cancel_pending.requested_state == "termination_requested"

    reject_cancel_terminal = evaluate_task_control_action("cancel", current_state="completed")
    assert reject_cancel_terminal.accepted is False
    assert reject_cancel_terminal.rejection_reason == "task_already_terminal"
    assert reject_cancel_terminal.terminal_state_immutable is True

    retry_failed = evaluate_task_control_action("retry", current_state="failed")
    assert retry_failed.accepted is True
    assert retry_failed.creates_new_task_lineage is True
    assert retry_failed.requested_state is None

    lineage = build_task_retry_lineage(
        source_task_id=41,
        source_task_state="failed",
        root_task_id=7,
        prior_retry_attempt=2,
    )
    assert lineage.root_task_id == 7
    assert lineage.parent_task_id == 41
    assert lineage.retry_attempt == 3
    assert lineage.source_terminal_state == "failed"


def test_post_processing_lane_and_processor_summary_are_lane_scoped() -> None:
    route = resolve_worker_task_route(
        task_kind="post_processing",
        request_is_valid=True,
        has_trace_batch_id=True,
    )
    assert route.lane == "simulation"

    now = _utc(2026, 3, 15, 12, 0)
    heartbeats = [
        build_processor_heartbeat(
            processor_id="sim-1",
            lane="simulation",
            state="healthy",
            last_heartbeat_at=now - timedelta(seconds=10),
            runtime_metadata={"version": "1.2.0", "host": {"name": "secret-host"}},
        ),
        build_processor_heartbeat(
            processor_id="sim-2",
            lane="simulation",
            state="busy",
            current_task_id=88,
            last_heartbeat_at=now - timedelta(seconds=15),
            runtime_metadata={"capacity": 2},
        ),
        build_processor_heartbeat(
            processor_id="char-1",
            lane="characterization",
            state="healthy",
            last_heartbeat_at=now - timedelta(seconds=180),
            runtime_metadata={"build": "abc123"},
        ),
        build_processor_heartbeat(
            processor_id="post-1",
            lane="simulation",
            state="degraded",
            last_heartbeat_at=now - timedelta(seconds=5),
            runtime_metadata={"warnings": ["slow-io"], "env": b"token"},
        ),
    ]

    simulation_summary = summarize_lane_processors(
        heartbeats,
        lane="simulation",
        recorded_at=now,
        offline_after_seconds=90,
    )
    assert simulation_summary.healthy_processors == 1
    assert simulation_summary.busy_processors == 1
    assert simulation_summary.degraded_processors == 1
    assert simulation_summary.offline_processors == 0

    characterization_summary = summarize_lane_processors(
        heartbeats,
        lane="characterization",
        recorded_at=now,
        offline_after_seconds=90,
    )
    assert characterization_summary.offline_processors == 1
    assert characterization_summary.healthy_processors == 0

    summaries = build_lane_processor_summaries(
        heartbeats,
        recorded_at=now,
        offline_after_seconds=90,
    )
    assert [summary.lane for summary in summaries] == ["characterization", "simulation"]

    post_payload = heartbeats[-1].to_payload(recorded_at=now, offline_after_seconds=90)
    assert post_payload["runtime_metadata"] == {
        "warnings": ["slow-io"],
        "env": REDACTED_RUNTIME_METADATA_VALUE,
    }


def test_task_control_audit_and_history_payloads_are_redaction_safe() -> None:
    recorded_at = _utc(2026, 3, 15, 12, 30)
    decision = evaluate_task_control_action("retry", current_state="terminated")
    lineage = build_task_retry_lineage(
        source_task_id=91,
        source_task_state="terminated",
        prior_retry_attempt=0,
    )

    audit_payload = build_task_control_audit_payload(
        decision=decision,
        recorded_at=recorded_at,
        lineage=lineage,
        runtime_metadata={
            "processor_version": "2026.03",
            "host": {"name": "hidden"},
            "labels": ["safe", "ops"],
        },
    )
    assert audit_payload["outcome"] == "accepted"
    assert audit_payload["runtime_metadata"] == {
        "processor_version": "2026.03",
        "host": REDACTED_RUNTIME_METADATA_VALUE,
        "labels": ["safe", "ops"],
    }
    assert audit_payload["retry_lineage"] == {
        "source_task_id": 91,
        "root_task_id": 91,
        "parent_task_id": 91,
        "retry_attempt": 1,
        "source_terminal_state": "terminated",
    }

    event_log = build_task_control_event_log(
        task_id=91,
        decision=decision,
        recorded_at=recorded_at,
        lineage=lineage,
        runtime_metadata={"host": {"name": "hidden"}},
    )
    assert event_log.action_kind == "task.retried"
    assert event_log.resource_kind == "task"
    assert event_log.payload["runtime_metadata"] == {
        "host": REDACTED_RUNTIME_METADATA_VALUE,
    }

    history_event = build_task_control_history_event(
        decision=decision,
        occurred_at=recorded_at,
        lineage=lineage,
    )
    assert history_event.event_type == "task_retried"
    assert history_event.level == "info"
    assert history_event.metadata["creates_new_task_lineage"] is True
    assert history_event.metadata["retry_source_task_id"] == 91
    assert history_event.metadata["retry_attempt"] == 1

    history_pair = build_task_control_history_pair(
        task_id=91,
        decision=decision,
        occurred_at=recorded_at,
        lineage=lineage,
        runtime_metadata={"host": {"name": "hidden"}},
    )
    assert history_pair.history_event.event_type == "task_retried"
    assert history_pair.event_log.action_kind == "task.retried"
    assert history_pair.event_log.payload["runtime_metadata"] == {
        "host": REDACTED_RUNTIME_METADATA_VALUE,
    }


def test_task_event_metadata_builders_are_canonical_and_complete() -> None:
    context = _task_history_context(task_status="cancelled")

    submission_metadata = build_task_submission_history_metadata(context)
    assert (
        validate_task_history_event_metadata("task_submitted", submission_metadata)
        == submission_metadata
    )

    lifecycle_metadata = build_task_lifecycle_history_metadata(context)
    assert lifecycle_metadata["control_action"] == "cancel"
    assert lifecycle_metadata["control_phase"] == "terminal"
    assert lifecycle_metadata["terminal_state"] == "cancelled"
    assert (
        validate_task_history_event_metadata("task_cancel_requested", lifecycle_metadata)
        == lifecycle_metadata
    )

    retry_lineage = build_task_retry_lineage(
        source_task_id=91,
        source_task_state="terminated",
        prior_retry_attempt=0,
    )
    retry_metadata = build_task_control_history_metadata(
        decision=evaluate_task_control_action("retry", current_state="terminated"),
        lineage=retry_lineage,
    )
    assert retry_metadata["control_action"] == "retry"
    assert retry_metadata["retry_root_task_id"] == 91
    assert validate_task_history_event_metadata("task_retried", retry_metadata) == retry_metadata


def test_incomplete_task_event_metadata_has_stable_normalization_or_failure() -> None:
    normalized_submission = normalize_task_history_event_metadata(
        "task_submitted",
        {
            "dispatch_status": "queued",
            "dispatch_key": "dispatch:1:simulation_run_task",
            "submission_source": "api",
            "worker_task_name": "simulation_run_task",
        },
    )
    assert normalized_submission.metadata["task_status"] == "queued"
    assert normalized_submission.missing_fields == ()
    assert "task_status" in normalized_submission.normalized_fields

    normalized_cancel = normalize_task_history_event_metadata(
        "task_cancel_requested",
        {
            "task_status": "cancelling",
        },
    )
    assert normalized_cancel.metadata["control_action"] == "cancel"
    assert normalized_cancel.metadata["requested_state"] == "cancellation_requested"
    assert normalized_cancel.metadata["control_phase"] == "acknowledged"
    assert normalized_cancel.is_complete is True

    incomplete_retry = normalize_task_history_event_metadata(
        "task_retried",
        {
            "control_action": "retry",
        },
    )
    assert incomplete_retry.is_complete is False
    assert incomplete_retry.missing_fields == (
        "retry_attempt",
        "retry_parent_task_id",
        "retry_root_task_id",
        "retry_source_task_id",
        "retry_source_terminal_state",
    )

    try:
        validate_task_history_event_metadata("task_retried", {"control_action": "retry"})
    except ValueError as exc:
        assert "retry_source_task_id" in str(exc)
    else:
        raise AssertionError("Expected retry metadata validation to fail.")


def test_task_event_metadata_canonicalizer_supports_projection_and_strict_validation() -> None:
    normalized_cancel = canonicalize_task_history_event_metadata(
        "task_cancel_requested",
        {"task_status": "cancelling", "outcome": "accepted"},
    )
    assert normalized_cancel == {
        "task_status": "cancelling",
        "outcome": "accepted",
        "control_action": "cancel",
        "requested_state": "cancellation_requested",
        "control_phase": "acknowledged",
    }

    try:
        canonicalize_task_history_event_metadata(
            "task_retried",
            {"control_action": "retry"},
            require_complete=True,
        )
    except ValueError as exc:
        assert "retry_root_task_id" in str(exc)
    else:
        raise AssertionError(
            "Expected strict canonicalization to reject incomplete retry metadata."
        )

    projected = project_task_runtime_state_from_history(
        (
            _history_event(
                event_key="task_completed:1",
                event_type="task_completed",
                occurred_at=_utc(2026, 3, 15, 12, 0),
                message="done",
                metadata={
                    "dispatch_status": "queued",
                    "dispatch_key": "dispatch:1",
                    "progress_percent_complete": 100,
                    "worker_task_name": "simulation_run_task",
                },
            ),
            _history_event(
                event_key="task_running:2",
                event_type="task_running",
                occurred_at=_utc(2026, 3, 15, 12, 1),
                message="late running",
                metadata={
                    "dispatch_status": "queued",
                    "dispatch_key": "dispatch:1",
                    "progress_percent_complete": 50,
                    "worker_task_name": "simulation_run_task",
                },
            ),
        )
    )
    assert projected == "completed"


def test_execution_timestamp_helpers_normalize_naive_and_offset_inputs_to_utc() -> None:
    assert canonicalize_utc_datetime(datetime(2026, 3, 16, 12, 0)) == datetime(
        2026,
        3,
        16,
        12,
        0,
        tzinfo=UTC,
    )
    assert canonicalize_execution_timestamp("2026-03-16T12:00:00Z") == "2026-03-16T12:00:00+00:00"
    assert canonicalize_execution_timestamp(
        datetime(2026, 3, 16, 12, 0, tzinfo=timezone(timedelta(hours=8)))
    ) == "2026-03-16T04:00:00+00:00"

    context = build_task_execution_history_context(
        task_status="running",
        submitted_at="2026-03-16T12:00:00+08:00",
        progress_updated_at="2026-03-16T12:05:00",
        progress_percent_complete=50,
        dispatch=build_task_dispatch_record(
            task_id=1,
            worker_task_name="simulation_run_task",
            task_status="queued",
            submitted_from_active_dataset=False,
            dataset_id="dataset-1",
            accepted_at="2026-03-16T12:00:00Z",
            last_updated_at="2026-03-16T12:05:00+08:00",
            submission_source="api",
        ),
        worker_task_name="simulation_run_task",
        dataset_id="dataset-1",
        definition_id=7,
    )
    assert context.submitted_at == "2026-03-16T04:00:00+00:00"
    assert context.progress_updated_at == "2026-03-16T12:05:00+00:00"


def test_task_history_projection_recovers_control_runtime_states() -> None:
    cancel_history = (
        _history_event(
            event_key="task_submitted:1",
            event_type="task_submitted",
            occurred_at=_utc(2026, 3, 16, 9, 0),
            message="Task submission accepted by local runtime.",
            metadata={"task_status": "queued"},
        ),
        build_task_control_history_event(
            decision=evaluate_task_control_action("cancel", current_state="running"),
            occurred_at=_utc(2026, 3, 16, 9, 5),
        ),
        _history_event(
            event_key="task_cancel_requested:2",
            event_type="task_cancel_requested",
            occurred_at=_utc(2026, 3, 16, 9, 6),
            message="Task entered the cancel-control path.",
            metadata={"task_status": "cancelling"},
            level="warning",
        ),
        _history_event(
            event_key="task_cancel_requested:3",
            event_type="task_cancel_requested",
            occurred_at=_utc(2026, 3, 16, 9, 7),
            message="Task entered the cancel-control path.",
            metadata={"task_status": "cancelled"},
            level="warning",
        ),
    )

    assert project_task_runtime_state_from_history(cancel_history) == "cancelled"
    cancel_projection = project_task_control_transition(cancel_history)
    assert cancel_projection is not None
    assert cancel_projection.action == "cancel"
    assert cancel_projection.runtime_state == "cancelled"
    assert cancel_projection.requested_state == "cancellation_requested"
    assert cancel_projection.request_acknowledged is True
    assert cancel_projection.terminal_transition_complete is True

    terminate_history = (
        build_task_control_history_event(
            decision=evaluate_task_control_action(
                "terminate",
                current_state="cancellation_requested",
            ),
            occurred_at=_utc(2026, 3, 16, 10, 0),
        ),
        _history_event(
            event_key="task_terminate_requested:2",
            event_type="task_terminate_requested",
            occurred_at=_utc(2026, 3, 16, 10, 1),
            message="Task entered the terminate-control path.",
            metadata={"task_status": "terminated"},
            level="warning",
        ),
    )
    terminate_projection = project_task_control_transition(
        terminate_history,
        runtime_state="terminated",
    )
    assert terminate_projection is not None
    assert terminate_projection.action == "terminate"
    assert terminate_projection.runtime_state == "terminated"
    assert terminate_projection.request_acknowledged is True
    assert terminate_projection.terminal_transition_complete is True


def test_terminal_history_projection_stays_immutable_when_retry_or_cancel_follow() -> None:
    history = (
        _history_event(
            event_key="task_completed:1",
            event_type="task_completed",
            occurred_at=_utc(2026, 3, 16, 11, 0),
            message="Task completed and persisted result metadata.",
            metadata={"task_status": "completed"},
        ),
        build_task_control_history_event(
            decision=evaluate_task_control_action("retry", current_state="completed"),
            occurred_at=_utc(2026, 3, 16, 11, 5),
        ),
        build_task_control_history_event(
            decision=evaluate_task_control_action("cancel", current_state="running"),
            occurred_at=_utc(2026, 3, 16, 11, 10),
        ),
    )

    assert project_task_runtime_state_from_history(history) == "completed"
    retry_projection = project_task_control_transition(history, runtime_state="completed")
    assert retry_projection is not None
    assert retry_projection.action == "retry"
    assert retry_projection.creates_new_task_lineage is True
    assert retry_projection.runtime_state == "completed"
    assert retry_projection.terminal_transition_complete is True


def test_processor_snapshot_projection_preserves_lane_scope() -> None:
    now = _utc(2026, 3, 16, 12, 0)
    snapshots = [
        {
            "processor_id": "sim-1",
            "lane": "simulation",
            "state": "busy",
            "current_task_id": "12",
            "last_heartbeat_at": (now - timedelta(seconds=15)).isoformat(),
            "runtime_metadata": {"host": {"name": "hidden"}},
        },
        {
            "processor_id": "post-1",
            "lane": "simulation",
            "state": "healthy",
            "last_heartbeat_at": now,
            "runtime_metadata": {"version": "1.0.0"},
        },
    ]

    heartbeat = build_processor_heartbeat_from_snapshot(snapshots[0])
    assert heartbeat.current_task_id == 12
    assert heartbeat.last_heartbeat_at.tzinfo == UTC
    assert heartbeat.runtime_metadata == {"host": REDACTED_RUNTIME_METADATA_VALUE}

    naive_heartbeat = build_processor_heartbeat_from_snapshot(
        {
            "processor_id": "sim-2",
            "lane": "simulation",
            "state": "healthy",
            "last_heartbeat_at": "2026-03-16T12:00:00",
            "runtime_metadata": {},
        }
    )
    assert naive_heartbeat.last_heartbeat_at.tzinfo == UTC

    summaries = build_lane_processor_summaries_from_snapshots(
        snapshots,
        recorded_at=now,
        offline_after_seconds=90,
    )
    assert [summary.lane for summary in summaries] == ["simulation"]
    assert summaries[0].busy_processors == 1
    assert summaries[0].healthy_processors == 1


def _task_history_context(*, task_status: str) -> object:
    return build_task_execution_history_context(
        task_status=task_status,  # type: ignore[arg-type]
        submitted_at=_utc(2026, 3, 16, 8, 0).isoformat(),
        progress_updated_at=_utc(2026, 3, 16, 8, 5).isoformat(),
        progress_percent_complete=100,
        dispatch=build_task_dispatch_record(
            task_id=1,
            worker_task_name="simulation_run_task",
            task_status="queued",
            submitted_from_active_dataset=False,
            dataset_id="dataset-1",
            accepted_at=_utc(2026, 3, 16, 8, 0).isoformat(),
            last_updated_at=_utc(2026, 3, 16, 8, 5).isoformat(),
            submission_source="api",
        ),
        worker_task_name="simulation_run_task",
        dataset_id="dataset-1",
        definition_id=7,
        result_handle_ids=("result:1",),
    )
