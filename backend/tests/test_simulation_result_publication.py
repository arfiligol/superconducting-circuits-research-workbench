from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from src.app.domain.tasks import TaskLifecycleUpdate
from src.app.infrastructure.runtime import (
    get_rewrite_app_state_repository,
    get_task_service,
    reset_runtime_state,
)
from src.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_app_state() -> None:
    reset_runtime_state()
    client.cookies.clear()


def _login() -> None:
    switched = client.patch(
        "/session/runtime-mode",
        json={
            "runtime_mode": "online",
            "server_origin": "http://127.0.0.1:8000",
            "label": "Default Rewrite Server",
        },
    )
    assert switched.status_code == 200
    response = client.post(
        "/session/login",
        json={
            "email": "rewrite.local@example.com",
            "password": "rewrite-local-password",
        },
    )
    assert response.status_code == 200


def _simulation_setup_payload(*, ptc_enabled: bool) -> dict[str, object]:
    return {
        "frequency_sweep": {
            "start_ghz": 1.0,
            "stop_ghz": 8.0,
            "point_count": 401,
            "spacing": "linear",
        },
        "parameter_sweeps": [],
        "solver": {
            "solver_family": "harmonic_balance",
            "max_iterations": 20,
            "convergence_tolerance": 1e-6,
            "harmonic_balance": {
                "enabled": True,
                "harmonic_count": 5,
                "oversample_factor": 2,
            },
        },
        "sources": [
            {
                "source_id": "port_1_drive",
                "kind": "port_drive",
                "target": "port_1",
                "amplitude": -30.0,
                "frequency_ghz": 5.0,
                "phase_deg": 0.0,
            }
        ],
        "ptc": {
            "enabled": ptc_enabled,
            "mode": "auto",
            "compensate_ports": ["port_1", "port_2"],
        },
    }


def _submit_local_simulation(*, ptc_enabled: bool = True) -> dict[str, object]:
    response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "dataset_id": "local-dataset-001",
            "definition_id": 3,
            "summary": "Result publication source task.",
            "simulation_setup": _simulation_setup_payload(ptc_enabled=ptc_enabled),
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["task"]


def _published_trace_ids(task_id: int, *, include_ptc: bool) -> list[str]:
    trace_ids = [
        f"trace_simulation_task_{task_id}_s_matrix_raw",
        f"trace_simulation_task_{task_id}_y_matrix_raw",
        f"trace_simulation_task_{task_id}_z_matrix_raw",
    ]
    if include_ptc:
        trace_ids.extend(
            [
                f"trace_simulation_task_{task_id}_y_matrix_ptc",
                f"trace_simulation_task_{task_id}_z_matrix_ptc",
            ]
        )
    return trace_ids


@contextmanager
def _bind_client_app_context(test_client: TestClient):
    app_context_id = test_client.cookies.get("sc_app_context")
    assert app_context_id is not None
    repository = get_rewrite_app_state_repository()
    binding = repository.bind_request_app_context_id(app_context_id)
    try:
        yield
    finally:
        repository.reset_request_app_context_id(binding)


def test_completed_simulation_task_can_be_published_and_is_queryable() -> None:
    task = _submit_local_simulation(ptc_enabled=True)

    before_publish = client.get(f"/tasks/{task['task_id']}")
    assert before_publish.status_code == 200
    assert before_publish.json()["data"]["publication_summary"] == {
        "state": "not_published",
        "publish_allowed": True,
        "publication_key": None,
        "target_dataset_id": None,
        "target_design_id": None,
        "target_design_name": None,
        "published_trace_ids": [],
        "published_at": None,
        "source_task_id": task["task_id"],
        "source_result_handle_ids": [
            f"task-result:{task['task_id']}:primary",
        ],
    }

    publish_response = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={
            "dataset_id": "local-dataset-001",
            "design_name": "Fluxonium Simulation Save",
        },
    )

    assert publish_response.status_code == 200
    payload = publish_response.json()["data"]
    assert payload["operation"] == "published"
    assert payload["publication_summary"]["state"] == "published"
    assert payload["publication_summary"]["target_dataset_id"] == "local-dataset-001"
    assert payload["publication_summary"]["target_design_id"] == "design_fluxonium-simulation-save"
    assert payload["publication_summary"]["target_design_name"] == "Fluxonium Simulation Save"
    assert payload["task"]["publication_summary"]["state"] == "published"
    assert payload["design"]["design_id"] == "design_fluxonium-simulation-save"
    assert len(payload["traces"]) == 5

    reloaded = client.get(f"/tasks/{task['task_id']}").json()["data"]
    assert reloaded["publication_summary"]["state"] == "published"
    assert reloaded["publication_summary"]["published_trace_ids"] == _published_trace_ids(
        task["task_id"],
        include_ptc=True,
    )

    reset_runtime_state()
    client.cookies.clear()
    persisted = client.get(f"/tasks/{task['task_id']}").json()["data"]
    assert persisted["publication_summary"]["state"] == "published"
    assert (
        persisted["publication_summary"]["target_design_id"]
        == "design_fluxonium-simulation-save"
    )
    durable_designs = client.get("/datasets/local-dataset-001/designs")
    assert durable_designs.status_code == 200
    assert any(
        row["design_id"] == "design_fluxonium-simulation-save"
        for row in durable_designs.json()["data"]["rows"]
    )
    durable_traces = client.get(
        "/datasets/local-dataset-001/designs/design_fluxonium-simulation-save/traces"
    )
    assert durable_traces.status_code == 200
    assert sorted(
        row["trace_id"] for row in durable_traces.json()["data"]["rows"]
    ) == sorted(
        _published_trace_ids(
            task["task_id"],
            include_ptc=True,
        )
    )


def test_pending_failed_and_wrong_kind_publish_requests_are_rejected_truthfully() -> None:
    pending_response = client.post(
        "/tasks/300/simulation-results/publish",
        json={"dataset_id": "local-dataset-001", "design_name": "Pending Publish"},
    )
    assert pending_response.status_code == 409
    assert pending_response.json()["error"]["code"] == "simulation_result_publish_not_ready"

    failed_task = _submit_local_simulation(ptc_enabled=False)
    with _bind_client_app_context(client):
        get_task_service().update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=failed_task["task_id"],
                status="failed",
                progress_percent_complete=100,
                progress_summary="Execution failed after result materialization.",
                progress_updated_at="2026-03-19T12:10:00+00:00",
                summary="Execution failed after result materialization.",
            )
        )

    failed_response = client.post(
        f"/tasks/{failed_task['task_id']}/simulation-results/publish",
        json={"dataset_id": "local-dataset-001", "design_name": "Failed Publish"},
    )
    assert failed_response.status_code == 409
    assert failed_response.json()["error"]["code"] == "simulation_result_publish_not_ready"

    _login()
    wrong_kind_response = client.post(
        "/tasks/303/simulation-results/publish",
        json={"dataset_id": "fluxonium-2025-031", "design_name": "Wrong Kind"},
    )
    assert wrong_kind_response.status_code == 409
    assert (
        wrong_kind_response.json()["error"]["code"]
        == "simulation_result_publish_task_invalid"
    )


def test_repeated_publish_is_idempotent_and_does_not_duplicate_dataset_records() -> None:
    task = _submit_local_simulation(ptc_enabled=False)
    first = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={"dataset_id": "local-dataset-001", "design_name": "Stable Publish Target"},
    )
    assert first.status_code == 200
    assert first.json()["data"]["operation"] == "published"

    second = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={"dataset_id": "local-dataset-001", "design_name": "Stable Publish Target"},
    )
    assert second.status_code == 200
    assert second.json()["data"]["operation"] == "already_published"
    assert second.json()["data"]["design"]["name"] == "Stable Publish Target"

    traces = client.get(
        "/datasets/local-dataset-001/designs/design_stable-publish-target/traces"
    )
    assert traces.status_code == 200
    rows = traces.json()["data"]["rows"]
    assert len(rows) == 3
    assert [row["trace_id"] for row in rows] == _published_trace_ids(
        task["task_id"],
        include_ptc=False,
    )

    reset_runtime_state()
    client.cookies.clear()

    third = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={"dataset_id": "local-dataset-001", "design_name": "Stable Publish Target"},
    )
    assert third.status_code == 200
    assert third.json()["data"]["operation"] == "already_published"

    post_reset_rows = client.get(
        "/datasets/local-dataset-001/designs/design_stable-publish-target/traces"
    ).json()["data"]["rows"]
    assert len(post_reset_rows) == 3
    assert [row["trace_id"] for row in post_reset_rows] == _published_trace_ids(
        task["task_id"],
        include_ptc=False,
    )


def test_published_trace_records_keep_source_task_provenance_and_are_browse_visible() -> None:
    task = _submit_local_simulation(ptc_enabled=True)
    publish = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={
            "dataset_id": "local-dataset-001",
            "design_name": "Published Explorer Design",
        },
    )
    assert publish.status_code == 200

    designs = client.get("/datasets/local-dataset-001/designs")
    assert designs.status_code == 200
    design_rows = designs.json()["data"]["rows"]
    published_design = next(
        row for row in design_rows if row["design_id"] == "design_published-explorer-design"
    )
    assert published_design["source_coverage"]["circuit_simulation"] == 5

    trace_rows = client.get(
        "/datasets/local-dataset-001/designs/design_published-explorer-design/traces"
    )
    assert trace_rows.status_code == 200
    rows = trace_rows.json()["data"]["rows"]
    assert {row["source_kind"] for row in rows} == {"circuit_simulation"}

    trace_detail = client.get(
        "/datasets/local-dataset-001/designs/design_published-explorer-design/"
        f"traces/trace_simulation_task_{task['task_id']}_y_matrix_ptc"
    )
    assert trace_detail.status_code == 200
    detail = trace_detail.json()["data"]
    assert detail["result_handles"][0]["provenance_task_id"] == task["task_id"]
    assert detail["result_handles"][0]["provenance"]["source_task_id"] == task["task_id"]
    assert detail["result_handles"][0]["provenance"]["source_dataset_id"] == "local-dataset-001"
    assert detail["payload_ref"]["store_key"].startswith(
        "datasets/local-dataset-001/designs/design_published-explorer-design/"
    )


def test_publish_rejects_unsupported_alternate_target_dataset_semantics() -> None:
    task = _submit_local_simulation(ptc_enabled=False)

    publish = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={
            "dataset_id": "fluxonium-2025-031",
            "design_name": "Wrong Dataset Target",
        },
    )

    assert publish.status_code == 409
    assert (
        publish.json()["error"]["code"]
        == "simulation_result_publish_target_unsupported"
    )
