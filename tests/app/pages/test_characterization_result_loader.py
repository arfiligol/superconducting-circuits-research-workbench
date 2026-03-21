"""Tests for WS8 persisted characterization recovery helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from legacy.legacy_nicegui_archived.api.schemas import (
    DesignTasksResponse,
    LatestCharacterizationResponse,
    TaskResponse,
)
from legacy.legacy_nicegui_archived.pages.characterization.result_loader import (
    build_recovery_state,
    latest_characterization_task,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _task_response(
    *,
    task_id: int,
    status: str,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    heartbeat_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> TaskResponse:
    timestamp = created_at or _utcnow()
    return TaskResponse(
        id=task_id,
        task_kind="characterization",
        status=status,
        design_id=19,
        trace_batch_id=None,
        analysis_run_id=71,
        requested_by="ui",
        actor_id=3,
        dedupe_key="dedupe",
        request_payload={"parameters": {"analysis_id": "admittance_extraction"}},
        progress_payload={},
        result_summary_payload={},
        error_payload={},
        created_at=timestamp,
        started_at=started_at,
        heartbeat_at=heartbeat_at,
        completed_at=completed_at,
    )


def _latest_result(
    analysis_run_id: int,
    *,
    task_id: int | None = None,
) -> LatestCharacterizationResponse:
    now = _utcnow()
    return LatestCharacterizationResponse(
        analysis_run_id=analysis_run_id,
        design_id=19,
        analysis_id="admittance_extraction",
        analysis_label="Admittance Extraction",
        run_id="char-test",
        status="completed",
        input_trace_ids=[1, 2],
        input_batch_ids=[17],
        input_scope="all_dataset_records",
        trace_mode_group="base",
        config_payload={"fit_window": 5},
        summary_payload={"selected_trace_count": 2},
        created_at=now - timedelta(minutes=2),
        completed_at=now - timedelta(minutes=1),
        task_id=task_id,
    )


def test_latest_characterization_task_prefers_newest_characterization_task() -> None:
    created_at = _utcnow()
    tasks = DesignTasksResponse(
        tasks=[
            TaskResponse(
                id=30,
                task_kind="simulation",
                status="queued",
                design_id=19,
                trace_batch_id=44,
                analysis_run_id=None,
                requested_by="ui",
                actor_id=3,
                dedupe_key="sim",
                request_payload={},
                progress_payload={},
                result_summary_payload={},
                error_payload={},
                created_at=created_at,
                started_at=None,
                heartbeat_at=None,
                completed_at=None,
            ),
            _task_response(task_id=22, status="running", created_at=created_at),
            _task_response(
                task_id=21,
                status="completed",
                created_at=created_at - timedelta(minutes=1),
            ),
        ]
    )

    task = latest_characterization_task(tasks)

    assert task is not None
    assert task.id == 22
    assert task.status == "running"


def test_build_recovery_state_uses_persisted_characterization_task_and_warns() -> None:
    now = _utcnow()
    tasks = DesignTasksResponse(
        tasks=[
            _task_response(
                task_id=31,
                status="running",
                created_at=now - timedelta(minutes=5),
                started_at=now - timedelta(seconds=90),
                heartbeat_at=now - timedelta(seconds=5),
            )
        ]
    )

    recovery = build_recovery_state(
        tasks_response=tasks,
        latest_result=_latest_result(analysis_run_id=71, task_id=31),
        now=now,
    )

    assert recovery.task is not None
    assert recovery.task.id == 31
    assert recovery.latest_result is not None
    assert recovery.latest_result.analysis_run_id == 71
    assert recovery.should_poll is True
    assert recovery.long_running_warning is True


def test_build_recovery_state_recovers_latest_result_without_transient_task_state() -> None:
    recovery = build_recovery_state(
        tasks_response=DesignTasksResponse(tasks=[]),
        latest_result=_latest_result(analysis_run_id=88, task_id=42),
        now=_utcnow(),
    )

    assert recovery.task is None
    assert recovery.latest_result is not None
    assert recovery.latest_result.analysis_run_id == 88
    assert recovery.should_poll is False
    assert recovery.long_running_warning is False
