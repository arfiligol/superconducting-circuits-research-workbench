import pytest
from datetime import UTC, datetime, timedelta

from sc_core.execution import (
    canonicalize_execution_timestamp,
    canonicalize_task_history_event_metadata,
)
from sc_core.tasking import (
    REDACTED_RUNTIME_METADATA_VALUE,
    LaneName,
    TaskSubmissionKind,
    WorkerTaskName,
    build_lane_processor_summaries,
    build_processor_heartbeat,
    build_task_retry_lineage,
    evaluate_task_control_action,
    extract_parameters_payload,
    resolve_worker_task_route,
)


def test_extract_parameters_payload_returns_mapping_copy() -> None:
    payload = {
        "parameters": {
            "dataset_id": "fluxonium-2025-031",
            "retry": 2,
        },
        "ignored": "value",
    }

    extracted = extract_parameters_payload(payload)

    assert extracted == {
        "dataset_id": "fluxonium-2025-031",
        "retry": 2,
    }
    assert extracted is not payload["parameters"]


@pytest.mark.parametrize(
    ("task_kind", "request_is_valid", "has_trace_batch_id", "expected_lane", "expected_name"),
    [
        ("simulation", True, True, "simulation", "simulation_run_task"),
        ("simulation", True, False, "simulation", "simulation_smoke_task"),
        ("post_processing", True, True, "post_processing", "post_processing_run_task"),
        ("post_processing", False, True, "post_processing", "post_processing_smoke_task"),
        ("characterization", True, False, "characterization", "characterization_run_task"),
        ("characterization", False, False, "characterization", "characterization_smoke_task"),
    ],
)
def test_resolve_worker_task_route_matches_worker_lane_contract(
    task_kind: TaskSubmissionKind,
    request_is_valid: bool,
    has_trace_batch_id: bool,
    expected_lane: LaneName,
    expected_name: WorkerTaskName,
) -> None:
    route = resolve_worker_task_route(
        task_kind=task_kind,
        request_is_valid=request_is_valid,
        has_trace_batch_id=has_trace_batch_id,
    )

    assert route.lane == expected_lane
    assert route.worker_task_name == expected_name
    assert route.execution_mode == ("run" if expected_name.endswith("_run_task") else "smoke")


def test_resolve_worker_task_route_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unsupported task kind"):
        resolve_worker_task_route(
            task_kind="unsupported",  # type: ignore[arg-type] - intentional invalid contract probe
            request_is_valid=True,
            has_trace_batch_id=True,
        )


def test_task_control_and_retry_contracts_are_importable_from_backend() -> None:
    cancel_decision = evaluate_task_control_action("cancel", current_state="running")
    retry_lineage = build_task_retry_lineage(
        source_task_id=5,
        source_task_state="failed",
        prior_retry_attempt=1,
    )

    assert cancel_decision.requested_state == "cancellation_requested"
    assert cancel_decision.accepted is True
    assert retry_lineage.root_task_id == 5
    assert retry_lineage.retry_attempt == 2


def test_lane_scoped_processor_summary_contract_is_redaction_safe() -> None:
    now = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
    heartbeats = [
        build_processor_heartbeat(
            processor_id="sim-1",
            lane="simulation",
            state="busy",
            current_task_id=12,
            last_heartbeat_at=now - timedelta(seconds=5),
            runtime_metadata={"version": "1.0.0"},
        ),
        build_processor_heartbeat(
            processor_id="sim-2",
            lane="simulation",
            state="healthy",
            last_heartbeat_at=now - timedelta(seconds=120),
            runtime_metadata={"host": {"name": "private"}},
        ),
    ]

    summaries = build_lane_processor_summaries(
        heartbeats,
        recorded_at=now,
        offline_after_seconds=90,
    )

    assert len(summaries) == 1
    assert summaries[0].lane == "simulation"
    assert summaries[0].busy_processors == 1
    assert summaries[0].offline_processors == 1
    assert heartbeats[1].to_payload(recorded_at=now, offline_after_seconds=90)[
        "runtime_metadata"
    ] == {"host": REDACTED_RUNTIME_METADATA_VALUE}


def test_execution_canonical_helpers_are_importable_for_adopters() -> None:
    assert canonicalize_execution_timestamp("2026-03-16T12:00:00Z") == "2026-03-16T12:00:00+00:00"
    assert canonicalize_task_history_event_metadata(
        "task_cancel_requested",
        {"task_status": "cancelling"},
    ) == {
        "task_status": "cancelling",
        "control_action": "cancel",
        "requested_state": "cancellation_requested",
        "control_phase": "acknowledged",
    }
