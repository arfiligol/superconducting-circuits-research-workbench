"""Tests for WS6 persisted simulation recovery helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from legacy.legacy_nicegui_archived.api.schemas import DesignTasksResponse, LatestTraceBatchResponse, TaskResponse
from legacy.legacy_nicegui_archived.pages.simulation.result_loader import (
    build_recovery_state,
    build_task_recovery_state,
    latest_post_processing_task,
    latest_simulation_task,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _task_response(
    *,
    task_id: int,
    task_kind: str,
    status: str,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    heartbeat_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> TaskResponse:
    timestamp = created_at or _utcnow()
    return TaskResponse(
        id=task_id,
        task_kind=task_kind,
        status=status,
        design_id=12,
        trace_batch_id=44 if status != "failed" else None,
        analysis_run_id=None,
        requested_by="ui",
        actor_id=3,
        dedupe_key="dedupe",
        request_payload={},
        progress_payload={},
        result_summary_payload={},
        error_payload={},
        created_at=timestamp,
        started_at=started_at,
        heartbeat_at=heartbeat_at,
        completed_at=completed_at,
    )


def _latest_result(batch_id: int) -> LatestTraceBatchResponse:
    return LatestTraceBatchResponse(
        batch_id=batch_id,
        design_id=12,
        source_kind="circuit_simulation",
        stage_kind="raw",
        status="completed",
        parent_batch_id=None,
        setup_kind="circuit_simulation.raw",
        setup_version="1.0",
        provenance_payload={"origin": "test"},
        summary_payload={"frequency_points": 3},
        task_id=21,
    )


def test_latest_simulation_task_prefers_newest_simulation_task() -> None:
    created_at = _utcnow()
    tasks = DesignTasksResponse(
        tasks=[
            _task_response(
                task_id=9,
                task_kind="characterization",
                status="queued",
                created_at=created_at,
            ),
            _task_response(
                task_id=8,
                task_kind="simulation",
                status="running",
                created_at=created_at,
            ),
            _task_response(
                task_id=7,
                task_kind="simulation",
                status="completed",
                created_at=created_at - timedelta(minutes=1),
            ),
        ]
    )

    task = latest_simulation_task(tasks)

    assert task is not None
    assert task.id == 8
    assert task.status == "running"


def test_build_recovery_state_uses_persisted_task_and_warns_for_long_running_work() -> None:
    now = _utcnow()
    tasks = DesignTasksResponse(
        tasks=[
            _task_response(
                task_id=21,
                task_kind="simulation",
                status="running",
                created_at=now - timedelta(minutes=5),
                started_at=now - timedelta(seconds=90),
                heartbeat_at=now - timedelta(seconds=10),
            )
        ]
    )

    recovery = build_recovery_state(
        tasks_response=tasks,
        latest_result=_latest_result(44),
        now=now,
    )

    assert recovery.task is not None
    assert recovery.task.id == 21
    assert recovery.latest_result is not None
    assert recovery.latest_result.batch_id == 44
    assert recovery.should_poll is True
    assert recovery.long_running_warning is True


def test_build_recovery_state_recovers_latest_result_without_transient_task_state() -> None:
    recovery = build_recovery_state(
        tasks_response=DesignTasksResponse(tasks=[]),
        latest_result=_latest_result(55),
        now=_utcnow(),
    )

    assert recovery.task is None
    assert recovery.latest_result is not None
    assert recovery.latest_result.batch_id == 55
    assert recovery.should_poll is False
    assert recovery.long_running_warning is False


def test_latest_post_processing_task_prefers_newest_post_processing_task() -> None:
    created_at = _utcnow()
    tasks = DesignTasksResponse(
        tasks=[
            _task_response(
                task_id=11,
                task_kind="simulation",
                status="completed",
                created_at=created_at,
            ),
            _task_response(
                task_id=12,
                task_kind="post_processing",
                status="running",
                created_at=created_at,
            ),
            _task_response(
                task_id=10,
                task_kind="post_processing",
                status="completed",
                created_at=created_at - timedelta(minutes=1),
            ),
        ]
    )

    task = latest_post_processing_task(tasks)

    assert task is not None
    assert task.id == 12
    assert task.status == "running"


def test_build_task_recovery_state_tracks_post_processing_polling_and_warning() -> None:
    now = _utcnow()
    tasks = DesignTasksResponse(
        tasks=[
            _task_response(
                task_id=31,
                task_kind="post_processing",
                status="running",
                created_at=now - timedelta(minutes=5),
                started_at=now - timedelta(seconds=90),
                heartbeat_at=now - timedelta(seconds=8),
            )
        ]
    )

    recovery = build_task_recovery_state(
        tasks_response=tasks,
        task_kind="post_processing",
        now=now,
    )

    assert recovery.task is not None
    assert recovery.task.id == 31
    assert recovery.should_poll is True
    assert recovery.long_running_warning is True
