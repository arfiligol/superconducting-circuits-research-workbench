from dataclasses import replace
from datetime import datetime

import pytest
from sc_core.execution import TaskExecutionResult, TaskResultHandle
from sqlalchemy import update
from src.app.domain.tasks import (
    CharacterizationSetup,
    TaskEventHistoryQuery,
    TaskLifecycleUpdate,
    TaskListQuery,
    TaskResultRefs,
    TaskSubmissionDraft,
)
from src.app.infrastructure.persistence import (
    RewriteTaskDispatchRecord,
    RewriteTaskEventRecord,
    create_metadata_session_factory,
)
from src.app.infrastructure.runtime import (
    get_rewrite_app_state_repository,
    get_rewrite_task_repository,
    get_storage_metadata_repository,
    get_task_audit_repository,
    get_task_execution_runtime,
    get_task_service,
    get_task_snapshot_repository,
    reset_runtime_state,
)
from src.app.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)
from src.app.services.service_errors import ServiceError
from src.app.settings import get_settings


def _enter_online_owner_session() -> None:
    repository = get_rewrite_app_state_repository()
    repository.switch_runtime_mode(
        runtime_mode="online",
        server_target_origin="http://127.0.0.1:8000",
    )
    session = repository.create_authenticated_session(
        email="rewrite.local@example.com",
        password="rewrite-local-password",
    )
    assert session is not None


def _reset_runtime_state_online() -> None:
    reset_runtime_state()
    _enter_online_owner_session()


@pytest.fixture(autouse=True)
def enter_online_runtime() -> None:
    _reset_runtime_state_online()


def _characterization_setup() -> CharacterizationSetup:
    return CharacterizationSetup.from_mapping(
        {
            "design_id": "design_flux_scan_a",
            "analysis_id": "admittance_extraction",
            "selected_trace_ids": [
                "trace_flux_a_measurement",
                "trace_flux_a_layout",
            ],
            "analysis_config": {
                "fit_window": [5.7, 5.9],
                "residual_tolerance": 0.01,
            },
        }
    )


def test_runtime_task_submission_persists_pending_result_metadata() -> None:
    service = get_task_service()

    task = service.submit_task(
        TaskSubmissionDraft(
            kind="characterization",
            dataset_id=None,
            definition_id=None,
            summary=None,
            characterization_setup=_characterization_setup(),
        )
    )
    storage_repository = get_storage_metadata_repository()

    assert storage_repository.get_storage_record("result_handle:pending:306") == (
        task.result_refs.metadata_records[0]
    )
    assert storage_repository.get_result_handle("task-result:306:primary") == (
        task.result_refs.result_handles[0]
    )
    assert task.dispatch is not None
    assert task.dispatch.status == "accepted"
    assert task.dispatch.dispatch_key == "dispatch:306:characterization_run_task"
    assert [event.event_type for event in task.events] == ["task_submitted"]
    assert task.events[0].metadata["dispatch_key"] == "dispatch:306:characterization_run_task"


def test_task_service_submit_preserves_explicit_dataset_dispatch_source_across_reset() -> None:
    task = get_task_service().submit_task(
        TaskSubmissionDraft(
            kind="characterization",
            dataset_id="fluxonium-2025-031",
            definition_id=None,
            summary=None,
            characterization_setup=_characterization_setup(),
        )
    )

    assert task.dispatch is not None
    assert task.dispatch.submission_source == "explicit_dataset"

    _reset_runtime_state_online()

    reloaded_task = get_task_service().get_task(task.task_id)

    assert reloaded_task.dispatch is not None
    assert reloaded_task.dispatch.submission_source == "explicit_dataset"


def test_runtime_bootstrap_persists_seeded_trace_payload_and_materialized_handles() -> None:
    service = get_task_service()
    storage_repository = get_storage_metadata_repository()

    task = service.get_task(303)

    assert task.result_refs.trace_payload is not None
    assert storage_repository.get_storage_record("trace_batch:88") == (
        task.result_refs.metadata_records[0]
    )
    assert storage_repository.get_trace_payload(task.result_refs.trace_payload.store_key) == (
        task.result_refs.trace_payload
    )
    assert storage_repository.get_result_handle("result:fluxonium-2025-031:fit-summary") == (
        task.result_refs.result_handles[0]
    )


def test_task_service_uses_persisted_task_repository_not_app_state_seeds() -> None:
    app_state_repository = get_rewrite_app_state_repository()
    persisted_task = get_task_service().get_task(303)
    persisted_history = get_rewrite_task_repository().get_task_history_view(303)

    assert app_state_repository.list_tasks() == []
    assert app_state_repository.get_task(303) is None
    assert persisted_task.result_refs.trace_batch_id == 88
    assert persisted_task.result_refs.result_handles[0].handle_id == (
        "result:fluxonium-2025-031:fit-summary"
    )
    assert persisted_task.dispatch is not None
    assert persisted_task.dispatch.status == "completed"
    assert persisted_history is not None
    assert persisted_history.event_count == 2
    assert persisted_history.latest_event is not None
    assert persisted_history.latest_event.event_type == "task_completed"


def test_runtime_reset_prefers_persisted_result_handle_over_seed_defaults() -> None:
    initial_task = get_task_service().get_task(303)
    storage_repository = get_storage_metadata_repository()
    updated_result_handle = build_result_handle_ref(
        handle_id=initial_task.result_refs.result_handles[0].handle_id,
        kind=initial_task.result_refs.result_handles[0].kind,
        status=initial_task.result_refs.result_handles[0].status,
        label="Persisted fit summary override",
        metadata_record=replace(
            initial_task.result_refs.result_handles[0].metadata_record,
            version=9,
        ),
        payload_backend=initial_task.result_refs.result_handles[0].payload_backend,
        payload_format=initial_task.result_refs.result_handles[0].payload_format,
        payload_role=initial_task.result_refs.result_handles[0].payload_role,
        payload_locator="artifacts/persisted-fit-summary.json",
        provenance_task_id=initial_task.result_refs.result_handles[0].provenance_task_id,
        provenance=initial_task.result_refs.result_handles[0].provenance,
    )
    storage_repository.save_result_handle(updated_result_handle)

    _reset_runtime_state_online()

    reloaded_task = get_task_service().get_task(303)

    assert reloaded_task.result_refs.result_handles[0].label == "Persisted fit summary override"
    assert reloaded_task.result_refs.result_handles[0].payload_locator == (
        "artifacts/persisted-fit-summary.json"
    )
    assert reloaded_task.result_refs.metadata_records[1].version == 9


def test_runtime_reset_prefers_persisted_task_snapshot_over_seed_defaults() -> None:
    task_snapshot_repository = get_task_snapshot_repository()
    initial_task = get_task_service().get_task(302)
    updated_task = replace(
        initial_task,
        status="failed",
        summary="Persisted task snapshot override",
        progress=replace(
            initial_task.progress,
            phase="failed",
            percent_complete=100,
            summary="Persisted failure summary.",
            updated_at="2026-03-12 11:05:00",
        ),
    )
    task_snapshot_repository.save_task_snapshot(updated_task)

    _reset_runtime_state_online()

    reloaded_task = get_task_service().get_task(302)

    assert reloaded_task.status == "failed"
    assert reloaded_task.summary == "Persisted task snapshot override"
    assert reloaded_task.progress.phase == "failed"
    assert reloaded_task.progress.summary == "Persisted failure summary."


def test_task_service_event_history_query_supports_order_limit_and_filter() -> None:
    events = get_task_service().list_task_events(
        303,
        TaskEventHistoryQuery(
            order="desc",
            limit=1,
            event_type="task_completed",
        ),
    )

    assert [event.event_type for event in events] == ["task_completed"]
    assert events[0].metadata["dispatch_status"] == "completed"


def test_task_service_history_view_coheres_detail_dispatch_and_events() -> None:
    history = get_task_service().get_task_history(
        303,
        TaskEventHistoryQuery(order="desc", limit=2),
    )

    assert history.task.task_id == 303
    assert history.task.dispatch is not None
    assert history.task.dispatch.status == "completed"
    assert history.event_count == 2
    assert history.latest_event is not None
    assert history.latest_event.event_type == "task_completed"
    assert [event.event_type for event in history.task.events] == [
        "task_completed",
        "task_submitted",
    ]
    assert history.task.events[0].metadata["dispatch_key"] == history.task.dispatch.dispatch_key


def test_task_service_lifecycle_update_persists_running_state_across_reset() -> None:
    submitted_task = get_task_service().submit_task(
        TaskSubmissionDraft(
            kind="characterization",
            dataset_id=None,
            definition_id=None,
            summary=None,
            characterization_setup=_characterization_setup(),
        )
    )

    updated_task = get_task_service().update_task_lifecycle(
        TaskLifecycleUpdate(
            task_id=submitted_task.task_id,
            status="running",
            progress_percent_complete=35,
            progress_summary="Characterization worker picked up the task.",
            progress_updated_at="2026-03-12 11:15:00",
            summary="Characterization task is running against persisted state.",
        )
    )

    assert updated_task.status == "running"
    assert updated_task.dispatch is not None
    assert updated_task.dispatch.status == "running"
    assert updated_task.progress.percent_complete == 35
    assert updated_task.summary == "Characterization task is running against persisted state."
    assert [event.event_type for event in updated_task.events] == [
        "task_submitted",
        "task_running",
    ]

    _reset_runtime_state_online()

    reloaded_task = get_task_service().get_task(submitted_task.task_id)

    assert reloaded_task.status == "running"
    assert reloaded_task.dispatch is not None
    assert reloaded_task.dispatch.status == "running"
    assert reloaded_task.dispatch.last_updated_at == "2026-03-12 11:15:00"
    assert reloaded_task.progress.percent_complete == 35
    assert reloaded_task.progress.summary == "Characterization worker picked up the task."
    assert [event.event_type for event in reloaded_task.events] == [
        "task_submitted",
        "task_running",
    ]
    assert reloaded_task.events[1].metadata["progress_percent_complete"] == 35

    history = get_task_service().get_task_history(
        submitted_task.task_id,
        TaskEventHistoryQuery(order="desc", limit=2),
    )
    assert history.event_count == 2
    assert history.latest_event is not None
    assert history.latest_event.event_type == "task_running"
    assert history.task.dispatch is not None
    assert history.latest_event.metadata["dispatch_key"] == history.task.dispatch.dispatch_key

    repository_history = get_rewrite_task_repository().get_task_history_view(
        submitted_task.task_id
    )
    assert repository_history is not None
    assert repository_history.latest_event is not None
    assert repository_history.latest_event.event_type == "task_running"


def test_execution_runtime_persists_start_heartbeat_and_completion_across_reset() -> None:
    submitted_task = get_task_service().submit_task(
        TaskSubmissionDraft(
            kind="characterization",
            dataset_id=None,
            definition_id=None,
            summary="Execution runtime characterization proof.",
            characterization_setup=_characterization_setup(),
        )
    )
    runtime = get_task_execution_runtime()

    started_task = runtime.start_task(
        submitted_task.task_id,
        recorded_at=datetime(2026, 3, 12, 12, 0, 0),
        worker_pid=4242,
        stale_after_seconds=180,
    )
    heartbeat_task = runtime.heartbeat_task(
        submitted_task.task_id,
        recorded_at=datetime(2026, 3, 12, 12, 5, 0),
        summary="Characterization worker is sweeping the next resonance window.",
        percent_complete=60,
        stage_label="characterization_run_task",
        current_step=3,
        total_steps=5,
    )
    trace_batch_record = build_metadata_record_ref(
        "trace_batch",
        f"trace_batch:{submitted_task.task_id}",
        version=1,
    )
    result_handle_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:{submitted_task.task_id}",
        version=2,
    )
    result_refs = TaskResultRefs(
        result_handle=TaskResultHandle(trace_batch_id=submitted_task.task_id),
        metadata_records=(trace_batch_record, result_handle_record),
        trace_payload=build_trace_payload_ref(
            payload_role="task_output",
            store_key=f"tasks/{submitted_task.task_id}/trace-batch.zarr",
            store_uri=f"trace_store/tasks/{submitted_task.task_id}/trace-batch.zarr",
            group_path=f"tasks/{submitted_task.task_id}/trace_batch",
            array_path="signals/iq_real",
            dtype="float64",
            shape=(64, 1024),
            chunk_shape=(16, 1024),
        ),
        result_handles=(
            build_result_handle_ref(
                handle_id=f"task-result:{submitted_task.task_id}:primary",
                kind="characterization_report",
                status="materialized",
                label="Materialized characterization report",
                metadata_record=result_handle_record,
                payload_backend="json_artifact",
                payload_format="json",
                payload_role="report_artifact",
                payload_locator=(
                    f"artifacts/tasks/{submitted_task.task_id}/characterization-report.json"
                ),
                provenance_task_id=submitted_task.task_id,
                provenance=build_result_provenance_ref(
                    source_dataset_id=submitted_task.dataset_id,
                    source_task_id=submitted_task.task_id,
                    trace_batch_record=trace_batch_record,
                ),
            ),
        ),
    )
    completed_task = runtime.complete_task(
        submitted_task.task_id,
        recorded_at=datetime(2026, 3, 12, 12, 12, 0),
        result=TaskExecutionResult(
            result_summary_payload={"artifact_label": "characterization-report"},
            trace_batch_id=submitted_task.task_id,
        ),
        result_refs=result_refs,
    )

    assert started_task.status == "running"
    assert started_task.events[-1].metadata["audit_action"] == "worker.task_started"
    assert started_task.events[-1].metadata["worker_pid"] == 4242
    assert heartbeat_task.progress.percent_complete == 60
    assert heartbeat_task.events[-1].metadata["current_step"] == 3
    assert heartbeat_task.events[-1].metadata["total_steps"] == 5
    assert completed_task.status == "completed"
    assert completed_task.dispatch is not None
    assert completed_task.dispatch.status == "completed"
    assert completed_task.events[-1].event_type == "task_completed"
    assert completed_task.events[-1].metadata["audit_action"] == "worker.task_completed"
    assert completed_task.events[-1].metadata["trace_batch_id"] == submitted_task.task_id
    assert [event.event_type for event in completed_task.events] == [
        "task_submitted",
        "task_running",
        "task_running",
        "task_completed",
    ]

    _reset_runtime_state_online()

    reloaded_task = get_task_service().get_task(submitted_task.task_id)

    assert reloaded_task.status == "completed"
    assert reloaded_task.dispatch is not None
    assert reloaded_task.dispatch.status == "completed"
    assert reloaded_task.progress.summary == "Characterization task completed."
    assert reloaded_task.result_refs.trace_batch_id == submitted_task.task_id
    assert reloaded_task.result_refs.result_handles[0].status == "materialized"
    assert [event.event_type for event in reloaded_task.events] == [
        "task_submitted",
        "task_running",
        "task_running",
        "task_completed",
    ]
    assert reloaded_task.events[1].metadata["stale_after_seconds"] == 180
    assert reloaded_task.events[1].metadata["worker_pid"] == 4242
    assert reloaded_task.events[2].metadata["current_step"] == 3
    assert reloaded_task.events[3].metadata["audit_action"] == "worker.task_completed"
    assert reloaded_task.events[3].metadata["trace_batch_id"] == submitted_task.task_id


def test_execution_runtime_reconcile_marks_running_task_failed_with_safe_metadata() -> None:
    submitted_task = get_task_service().submit_task(
        TaskSubmissionDraft(
            kind="characterization",
            dataset_id=None,
            definition_id=None,
            summary=None,
            characterization_setup=_characterization_setup(),
        )
    )
    runtime = get_task_execution_runtime()
    runtime.start_task(
        submitted_task.task_id,
        recorded_at=datetime(2026, 3, 12, 12, 20, 0),
        worker_pid=5252,
    )

    reconciled_task = runtime.reconcile_stale_task(
        submitted_task.task_id,
        recorded_at=datetime(2026, 3, 12, 12, 30, 0),
        stale_before=datetime(2026, 3, 12, 12, 25, 0),
    )

    assert reconciled_task.status == "failed"
    assert reconciled_task.dispatch is not None
    assert reconciled_task.dispatch.status == "failed"
    assert reconciled_task.events[-1].event_type == "task_failed"
    assert reconciled_task.events[-1].metadata["audit_action"] == "reconcile.task_failed"
    assert reconciled_task.events[-1].metadata["error_code"] == "stale_task_timeout"
    assert "message" not in reconciled_task.events[-1].metadata

    _reset_runtime_state_online()

    reloaded_history = get_task_service().get_task_history(
        submitted_task.task_id,
        TaskEventHistoryQuery(order="desc", limit=4),
    )

    assert reloaded_history.task.status == "failed"
    assert reloaded_history.latest_event is not None
    assert reloaded_history.latest_event.event_type == "task_failed"
    assert reloaded_history.latest_event.metadata["audit_action"] == "reconcile.task_failed"
    assert reloaded_history.latest_event.metadata["stale_before"] == "2026-03-12T12:25:00"


def test_service_read_reconciles_stale_dispatch_snapshot_to_task_lifecycle() -> None:
    submitted_task = get_task_service().submit_task(
        TaskSubmissionDraft(
            kind="characterization",
            dataset_id=None,
            definition_id=None,
            summary=None,
            characterization_setup=_characterization_setup(),
        )
    )
    get_task_service().update_task_lifecycle(
        TaskLifecycleUpdate(
            task_id=submitted_task.task_id,
            status="running",
            progress_percent_complete=15,
            progress_summary="Dispatch/lifecycle reconciliation proof.",
            progress_updated_at="2026-03-12 11:17:00",
        )
    )

    session_factory = create_metadata_session_factory(get_settings().database_path)
    with session_factory() as session:
        session.execute(
            update(RewriteTaskDispatchRecord)
            .where(RewriteTaskDispatchRecord.task_id == submitted_task.task_id)
            .values(status="accepted", last_updated_at="2026-03-12 10:30:00")
        )
        session.commit()

    _reset_runtime_state_online()

    reloaded_task = get_task_service().get_task(submitted_task.task_id)

    assert reloaded_task.dispatch is not None
    assert reloaded_task.dispatch.status == "running"
    assert reloaded_task.dispatch.last_updated_at == "2026-03-12 11:17:00"
    assert reloaded_task.progress.summary == "Dispatch/lifecycle reconciliation proof."


def test_task_service_event_history_redacts_sensitive_metadata_fields() -> None:
    seeded_task = get_task_service().get_task(303)
    assert seeded_task.task_id == 303

    session_factory = create_metadata_session_factory(get_settings().database_path)
    with session_factory() as session:
        event_row = (
            session.query(RewriteTaskEventRecord)
            .filter(RewriteTaskEventRecord.task_id == 303)
            .filter(RewriteTaskEventRecord.event_type == "task_completed")
            .one()
        )
        event_row.metadata_json = {
            **event_row.metadata_json,
            "token": "raw-secret-token",
            "store_uri": "trace_store/datasets/private-secret.zarr",
            "dispatch_key": "dispatch:303:post_processing_run_task",
        }
        session.commit()

    _reset_runtime_state_online()

    events = get_task_service().list_task_events(
        303,
        TaskEventHistoryQuery(order="desc", limit=5),
    )

    assert events[0].event_type == "task_completed"
    assert "token" not in events[0].metadata
    assert "store_uri" not in events[0].metadata
    assert events[0].metadata["dispatch_key"] == "dispatch:303:post_processing_run_task"


def test_task_service_lifecycle_update_persists_completed_result_refs_across_reset() -> None:
    submitted_task = get_task_service().submit_task(
        TaskSubmissionDraft(
            kind="characterization",
            dataset_id=None,
            definition_id=None,
            summary=None,
            characterization_setup=_characterization_setup(),
        )
    )
    trace_batch_record = build_metadata_record_ref(
        "trace_batch",
        f"trace_batch:{submitted_task.task_id}",
        version=1,
    )
    result_handle_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:{submitted_task.task_id}",
        version=2,
    )
    completed_result_refs = TaskResultRefs(
        result_handle=TaskResultHandle(trace_batch_id=submitted_task.task_id),
        metadata_records=(trace_batch_record, result_handle_record),
        trace_payload=build_trace_payload_ref(
            payload_role="task_output",
            store_key=f"tasks/{submitted_task.task_id}/trace-batch.zarr",
            store_uri=f"trace_store/tasks/{submitted_task.task_id}/trace-batch.zarr",
            group_path=f"tasks/{submitted_task.task_id}/trace_batch",
            array_path="signals/iq_real",
            dtype="float64",
            shape=(64, 1024),
            chunk_shape=(16, 1024),
        ),
        result_handles=(
            build_result_handle_ref(
                handle_id=f"task-result:{submitted_task.task_id}:primary",
                kind="characterization_report",
                status="materialized",
                label="Materialized characterization report",
                metadata_record=result_handle_record,
                payload_backend="json_artifact",
                payload_format="json",
                payload_role="report_artifact",
                payload_locator=(
                    f"artifacts/tasks/{submitted_task.task_id}/characterization-report.json"
                ),
                provenance_task_id=submitted_task.task_id,
                provenance=build_result_provenance_ref(
                    source_dataset_id=submitted_task.dataset_id,
                    source_task_id=submitted_task.task_id,
                    trace_batch_record=trace_batch_record,
                ),
            ),
        ),
    )

    completed_task = get_task_service().update_task_lifecycle(
        TaskLifecycleUpdate(
            task_id=submitted_task.task_id,
            status="completed",
            progress_percent_complete=100,
            progress_summary="Characterization task completed and published artifacts.",
            progress_updated_at="2026-03-12 11:22:00",
            summary="Characterization artifacts were materialized.",
            result_refs=completed_result_refs,
        )
    )

    assert completed_task.status == "completed"
    assert completed_task.dispatch is not None
    assert completed_task.dispatch.status == "completed"
    assert completed_task.result_refs.trace_batch_id == submitted_task.task_id
    assert completed_task.result_refs.result_handles[0].status == "materialized"
    assert completed_task.result_refs.trace_payload is not None
    assert [event.event_type for event in completed_task.events] == [
        "task_submitted",
        "task_completed",
    ]
    assert completed_task.events[1].metadata["result_handle_ids"] == [
        f"task-result:{submitted_task.task_id}:primary"
    ]

    _reset_runtime_state_online()

    reloaded_task = get_task_service().get_task(submitted_task.task_id)

    assert reloaded_task.status == "completed"
    assert [event.event_type for event in reloaded_task.events] == [
        "task_submitted",
        "task_completed",
    ]
    assert reloaded_task.events[1].metadata["result_handle_ids"] == [
        f"task-result:{submitted_task.task_id}:primary"
    ]
    assert reloaded_task.dispatch is not None
    assert reloaded_task.dispatch.dispatch_key == (
        f"dispatch:{submitted_task.task_id}:characterization_run_task"
    )
    assert reloaded_task.dispatch.status == "completed"
    assert reloaded_task.dispatch.submission_source == "active_dataset"
    assert reloaded_task.progress.phase == "completed"
    assert reloaded_task.result_refs.trace_batch_id == submitted_task.task_id
    assert reloaded_task.result_refs.result_handles[0].payload_locator == (
        f"artifacts/tasks/{submitted_task.task_id}/characterization-report.json"
    )
    assert reloaded_task.result_refs.trace_payload is not None
    assert reloaded_task.result_refs.trace_payload.store_key == (
        f"tasks/{submitted_task.task_id}/trace-batch.zarr"
    )


def test_task_service_lifecycle_update_rejects_invalid_completed_progress() -> None:
    submitted_task = get_task_service().submit_task(
        TaskSubmissionDraft(
            kind="characterization",
            dataset_id=None,
            definition_id=None,
            summary=None,
            characterization_setup=_characterization_setup(),
        )
    )

    with pytest.raises(ServiceError) as exc_info:
        get_task_service().update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=submitted_task.task_id,
                status="completed",
                progress_percent_complete=80,
                progress_summary="Invalid completion payload.",
                progress_updated_at="2026-03-12 11:25:00",
            )
        )

    assert exc_info.value.code == "task_lifecycle_update_invalid"


def test_runtime_reset_keeps_submitted_task_row_and_storage_refs() -> None:
    submitted_task = get_task_service().submit_task(
        TaskSubmissionDraft(
            kind="characterization",
            dataset_id=None,
            definition_id=None,
            summary=None,
            characterization_setup=_characterization_setup(),
        )
    )

    _reset_runtime_state_online()

    reloaded_task = get_task_service().get_task(submitted_task.task_id)

    assert reloaded_task.task_id == submitted_task.task_id
    assert reloaded_task.status == "queued"
    assert reloaded_task.dispatch is not None
    assert reloaded_task.dispatch.status == "accepted"
    assert reloaded_task.dataset_id == "fluxonium-2025-031"
    assert reloaded_task.result_refs.result_handles == submitted_task.result_refs.result_handles
    assert get_rewrite_task_repository().get_task(submitted_task.task_id) is not None


def test_execution_runtime_consumes_cancellation_request_and_persists_terminal_cancelled_state(
) -> None:
    service = get_task_service()
    runtime = get_task_execution_runtime()

    requested_task = service.cancel_task(301)

    assert requested_task.status == "cancellation_requested"
    assert requested_task.events[-1].event_type == "task_cancel_requested"

    cancelling_task = runtime.consume_control_request(
        301,
        recorded_at=datetime(2026, 3, 17, 9, 20, 0),
        worker_pid=5511,
    )

    assert cancelling_task.status == "cancelling"
    assert cancelling_task.control_state == "cancellation_requested"
    assert cancelling_task.events[-1].event_type == "task_cancel_requested"
    assert cancelling_task.events[-1].metadata["audit_action"] == (
        "worker.task_cancellation_acknowledged"
    )

    queue = service.get_queue_view(TaskListQuery(limit=20))
    assert queue.worker_summary == ()

    cancelled_task = runtime.finalize_cancelled(
        301,
        recorded_at=datetime(2026, 3, 12, 12, 23, 0),
    )

    assert cancelled_task.status == "cancelled"
    assert cancelled_task.control_state == "none"
    assert cancelled_task.events[-1].event_type == "task_cancel_requested"
    assert cancelled_task.events[-1].metadata["audit_action"] == "worker.task_cancelled"

    audit_records = get_task_audit_repository().list_records_for_resource(
        resource_kind="task",
        resource_id="301",
    )
    assert {record.action_kind for record in audit_records} == {
        "worker.task_cancelled",
        "worker.task_cancellation_acknowledged",
        "task.cancel_requested",
    }

    with pytest.raises(ServiceError) as exc_info:
        runtime.finalize_terminated(
            301,
            recorded_at=datetime(2026, 3, 17, 9, 24, 0),
        )
    assert exc_info.value.code == "task_execution_transition_invalid"

    _reset_runtime_state_online()

    reloaded_task = get_task_service().get_task(301)
    assert reloaded_task.status == "cancelled"
    assert reloaded_task.control_state == "none"

    reloaded_queue = get_task_service().get_queue_view(TaskListQuery(limit=20))
    assert reloaded_queue.worker_summary == ()


def test_execution_runtime_consumes_termination_request_and_persists_terminated_state() -> None:
    service = get_task_service()
    runtime = get_task_execution_runtime()

    requested_task = service.terminate_task(301)

    assert requested_task.status == "termination_requested"
    assert requested_task.events[-1].event_type == "task_terminate_requested"

    acknowledged_task = runtime.consume_control_request(
        301,
        recorded_at=datetime(2026, 3, 17, 9, 30, 0),
        worker_pid=6611,
    )

    assert acknowledged_task.status == "termination_requested"
    assert acknowledged_task.control_state == "termination_requested"
    assert acknowledged_task.events[-1].event_type == "task_terminate_requested"
    assert acknowledged_task.events[-1].metadata["audit_action"] == (
        "worker.task_termination_acknowledged"
    )

    queue = service.get_queue_view(TaskListQuery(limit=20))
    assert queue.worker_summary == ()

    terminated_task = runtime.finalize_terminated(
        301,
        recorded_at=datetime(2026, 3, 17, 9, 33, 0),
    )

    assert terminated_task.status == "terminated"
    assert terminated_task.control_state == "none"
    assert terminated_task.events[-1].event_type == "task_terminate_requested"
    assert terminated_task.events[-1].metadata["audit_action"] == "worker.task_terminated"

    audit_records = get_task_audit_repository().list_records_for_resource(
        resource_kind="task",
        resource_id="301",
    )
    assert {record.action_kind for record in audit_records} == {
        "worker.task_terminated",
        "worker.task_termination_acknowledged",
        "task.terminate_requested",
    }

    _reset_runtime_state_online()

    reloaded_task = get_task_service().get_task(301)
    assert reloaded_task.status == "terminated"
    assert reloaded_task.control_state == "none"

    reloaded_queue = get_task_service().get_queue_view(TaskListQuery(limit=20))
    assert reloaded_queue.worker_summary == ()
