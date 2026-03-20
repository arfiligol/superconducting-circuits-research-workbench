import math
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


def _simulation_ptc_payload(
    *,
    enabled: bool = True,
    mode: str = "auto",
    compensate_ports: tuple[str, ...] = ("port_1", "port_2"),
) -> dict[str, object]:
    return {
        "enabled": enabled,
        "mode": mode,
        "compensate_ports": list(compensate_ports),
    }


def _simulation_setup_payload(
    *,
    ptc: dict[str, object] | None = None,
    parameter_sweeps: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "frequency_sweep": {
            "start_ghz": 1.0,
            "stop_ghz": 8.0,
            "point_count": 401,
            "spacing": "linear",
        },
        "parameter_sweeps": parameter_sweeps or [],
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
        "ptc": ptc,
    }


def _submit_local_simulation(
    *,
    ptc_enabled: bool,
    parameter_sweeps: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "dataset_id": "local-dataset-001",
            "definition_id": 3,
            "summary": "Explorer source task.",
            "simulation_setup": _simulation_setup_payload(
                ptc=_simulation_ptc_payload(enabled=ptc_enabled),
                parameter_sweeps=parameter_sweeps,
            ),
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["task"]


def _post_processing_setup_payload(
    *,
    trace_family: str = "z_matrix",
    representation: str = "real",
) -> dict[str, object]:
    return {
        "selections": [
            {
                "trace_family": trace_family,
                "representation": representation,
                "design_id": "design_local_flux_playground",
                "trace_ids": ["trace_local_flux_preview"],
            }
        ],
        "operations": [],
    }


def _submit_local_post_processing(
    *,
    trace_family: str = "z_matrix",
    representation: str = "real",
) -> dict[str, object]:
    upstream_task = _submit_local_simulation(ptc_enabled=True)
    response = client.post(
        "/tasks",
        json={
            "kind": "post_processing",
            "dataset_id": "local-dataset-001",
            "summary": "Explorer downstream task.",
            "upstream_task_id": upstream_task["task_id"],
            "post_processing_setup": _post_processing_setup_payload(
                trace_family=trace_family,
                representation=representation,
            ),
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["task"]


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


def test_completed_simulation_task_returns_explorer_bootstrap_data() -> None:
    task = _submit_local_simulation(ptc_enabled=True)

    response = client.get(f"/tasks/{task['task_id']}/simulation-results/explorer")

    assert response.status_code == 200
    payload = response.json()["data"]
    families = {family["key"]: family for family in payload["bootstrap"]["families"]}
    assert payload["task_id"] == task["task_id"]
    assert payload["task_status"] == "completed"
    assert payload["bootstrap"]["default_selection"] == {
        "family": "s_matrix",
        "source": "raw",
        "metric": "magnitude_db",
        "z0_ohm": 50.0,
        "output_port": 1,
        "input_port": 1,
        "trace_key": (
            "family=s_matrix|source=raw|trace_mode_group=base|output_port=1|"
            "input_port=1|output_mode=mode_0|input_mode=mode_0"
        ),
    }
    assert payload["bootstrap"]["trace_selector"]["output_ports"] == [
        {"port": 1, "label": "Port 1"}
    ]
    assert payload["bootstrap"]["trace_selector"]["input_ports"] == [
        {"port": 1, "label": "Port 1"}
    ]
    assert [source["key"] for source in families["s_matrix"]["available_sources"]] == ["raw"]
    assert [source["key"] for source in families["y_matrix"]["available_sources"]] == [
        "raw",
        "ptc",
    ]
    assert [source["key"] for source in families["z_matrix"]["available_sources"]] == [
        "raw",
        "ptc",
    ]


def test_completed_simulation_task_returns_plottable_trace_payload() -> None:
    task = _submit_local_simulation(ptc_enabled=True)

    response = client.get(
        f"/tasks/{task['task_id']}/simulation-results/explorer"
        "?family=z_matrix&source=ptc&metric=real&z0=75&output_port=1&input_port=1"
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["selection"] == {
        "family": "z_matrix",
        "source": "ptc",
        "metric": "real",
        "z0_ohm": 75.0,
        "output_port": 1,
        "input_port": 1,
        "trace_mode_group": "base",
        "output_port_label": "Port 1",
        "input_port_label": "Port 1",
        "output_mode": "mode_0",
        "input_mode": "mode_0",
        "trace_key": (
            "family=z_matrix|source=ptc|trace_mode_group=base|output_port=1|"
            "input_port=1|output_mode=mode_0|input_mode=mode_0|z0_ohm=75"
        ),
    }
    assert len(payload["plot"]["x_axis"]["values"]) == 401
    assert len(payload["plot"]["series"]) == 1
    assert len(payload["plot"]["series"][0]["values"]) == 401
    assert payload["plot"]["y_axis"]["unit"] == "ohm"
    assert all(math.isfinite(value) for value in payload["plot"]["series"][0]["values"])
    assert len(set(payload["plot"]["series"][0]["values"])) > 1


def test_completed_post_processing_task_returns_explorer_payload() -> None:
    task = _submit_local_post_processing(trace_family="z_matrix", representation="real")

    response = client.get(f"/tasks/{task['task_id']}/simulation-results/explorer")

    assert response.status_code == 200
    payload = response.json()["data"]
    families = {family["key"]: family for family in payload["bootstrap"]["families"]}
    assert payload["task_id"] == task["task_id"]
    assert payload["task_status"] == "completed"
    assert tuple(families) == ("s_matrix", "y_matrix", "z_matrix")
    assert [source["key"] for source in families["s_matrix"]["available_sources"]] == ["raw"]
    assert [source["key"] for source in families["y_matrix"]["available_sources"]] == [
        "raw",
        "ptc",
    ]
    assert [source["key"] for source in families["z_matrix"]["available_sources"]] == [
        "raw",
        "ptc",
    ]
    assert payload["bootstrap"]["default_selection"] == {
        "family": "z_matrix",
        "source": "raw",
        "metric": "real",
        "z0_ohm": 50.0,
        "output_port": 1,
        "input_port": 1,
        "trace_key": (
            "family=z_matrix|source=raw|trace_mode_group=base|output_port=1|"
            "input_port=1|output_mode=mode_0|input_mode=mode_0|z0_ohm=50"
        ),
    }
    assert payload["selection"] == {
        "family": "z_matrix",
        "source": "raw",
        "metric": "real",
        "z0_ohm": 50.0,
        "output_port": 1,
        "input_port": 1,
        "trace_mode_group": "base",
        "output_port_label": "Port 1",
        "input_port_label": "Port 1",
        "output_mode": "mode_0",
        "input_mode": "mode_0",
        "trace_key": (
            "family=z_matrix|source=raw|trace_mode_group=base|output_port=1|"
            "input_port=1|output_mode=mode_0|input_mode=mode_0|z0_ohm=50"
        ),
    }
    assert payload["result_basis"]["trace_payload_available"] is True
    assert payload["result_basis"]["primary_result_handle_id"] == (
        f"task-result:{task['task_id']}:primary"
    )
    assert len(payload["plot"]["series"]) == 1
    assert payload["plot"]["series"][0]["label"].startswith("Raw Z_MATRIX")


def test_pending_or_failed_simulation_task_gets_truthful_explorer_error() -> None:
    _login()
    pending_response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "dataset_id": "fluxonium-2025-031",
            "definition_id": 3,
            "summary": "Pending online simulation.",
            "simulation_setup": _simulation_setup_payload(
                ptc=_simulation_ptc_payload(enabled=False)
            ),
        },
    )
    pending_task = pending_response.json()["data"]["task"]

    pending_explorer = client.get(
        f"/tasks/{pending_task['task_id']}/simulation-results/explorer"
    )
    assert pending_explorer.status_code == 409
    assert pending_explorer.json()["error"]["code"] == "simulation_result_explorer_not_ready"

    client.cookies.clear()
    failed_task = _submit_local_simulation(ptc_enabled=False)
    with _bind_client_app_context(client):
        get_task_service().update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=failed_task["task_id"],
                status="failed",
                progress_percent_complete=100,
                progress_summary="Local execution failed after result materialization.",
                progress_updated_at="2026-03-18T23:00:00+00:00",
                summary="Local execution failed after result materialization.",
            )
        )

    failed_explorer = client.get(
        f"/tasks/{failed_task['task_id']}/simulation-results/explorer"
    )
    assert failed_explorer.status_code == 409
    assert failed_explorer.json()["error"]["code"] == "simulation_result_explorer_unavailable"


def test_ptc_source_only_appears_when_capability_exists() -> None:
    task = _submit_local_simulation(ptc_enabled=False)

    response = client.get(f"/tasks/{task['task_id']}/simulation-results/explorer")

    assert response.status_code == 200
    payload = response.json()["data"]
    families = {family["key"]: family for family in payload["bootstrap"]["families"]}
    assert [source["key"] for source in families["y_matrix"]["available_sources"]] == ["raw"]
    assert [source["key"] for source in families["z_matrix"]["available_sources"]] == ["raw"]

    rejected = client.get(
        f"/tasks/{task['task_id']}/simulation-results/explorer"
        "?family=z_matrix&source=ptc&metric=real"
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "request_validation_failed"


def test_ptc_source_is_gated_to_y_and_z_families_only() -> None:
    task = _submit_local_simulation(ptc_enabled=True)

    response = client.get(f"/tasks/{task['task_id']}/simulation-results/explorer")

    assert response.status_code == 200
    payload = response.json()["data"]
    families = {family["key"]: family for family in payload["bootstrap"]["families"]}
    assert [source["key"] for source in families["s_matrix"]["available_sources"]] == ["raw"]
    assert [source["key"] for source in families["y_matrix"]["available_sources"]] == [
        "raw",
        "ptc",
    ]
    assert [source["key"] for source in families["z_matrix"]["available_sources"]] == [
        "raw",
        "ptc",
    ]


def test_metric_changes_do_not_change_trace_key_but_canonical_selection_changes_do() -> None:
    task = _submit_local_simulation(ptc_enabled=True)

    magnitude = client.get(
        f"/tasks/{task['task_id']}/simulation-results/explorer"
        "?family=y_matrix&source=raw&metric=magnitude&output_port=1&input_port=1"
    )
    assert magnitude.status_code == 200
    real = client.get(
        f"/tasks/{task['task_id']}/simulation-results/explorer"
        "?family=y_matrix&source=raw&metric=real&output_port=1&input_port=1"
    )
    assert real.status_code == 200
    ptc = client.get(
        f"/tasks/{task['task_id']}/simulation-results/explorer"
        "?family=y_matrix&source=ptc&metric=real&output_port=1&input_port=1"
    )
    assert ptc.status_code == 200

    magnitude_key = magnitude.json()["data"]["selection"]["trace_key"]
    real_key = real.json()["data"]["selection"]["trace_key"]
    ptc_key = ptc.json()["data"]["selection"]["trace_key"]

    assert magnitude_key == real_key
    assert ptc_key != real_key


def test_parameter_sweep_bootstrap_and_selection_change_the_plotted_point() -> None:
    task = _submit_local_simulation(
        ptc_enabled=True,
        parameter_sweeps=[
            {
                "parameter": "L_jun",
                "values": [22.0, 24.0, 26.0],
                "unit": "nH",
            },
            {
                "parameter": "C_q",
                "values": [0.055, 0.05814],
                "unit": "pF",
            },
        ],
    )

    response = client.get(f"/tasks/{task['task_id']}/simulation-results/explorer")
    assert response.status_code == 200
    payload = response.json()["data"]

    assert payload["bootstrap"]["parameter_sweep"] == {
        "active": True,
        "point_count": 6,
        "axes": [
            {
                "parameter": "L_jun",
                "label": "L_jun",
                "unit": "nH",
                "values": [22.0, 24.0, 26.0],
                "selected_value_index": 0,
            },
            {
                "parameter": "C_q",
                "label": "C_q",
                "unit": "pF",
                "values": [0.055, 0.05814],
                "selected_value_index": 0,
            },
        ],
    }
    assert payload["selection"]["sweep_index"] == 0
    assert payload["plot"]["metadata"]["sweep_index"] == 0
    default_trace_key = payload["selection"]["trace_key"]

    shifted = client.get(
        f"/tasks/{task['task_id']}/simulation-results/explorer"
        "?family=s_matrix&source=raw&metric=magnitude_db&output_port=1&input_port=1&sweep_index=5"
    )
    assert shifted.status_code == 200
    shifted_payload = shifted.json()["data"]

    assert shifted_payload["selection"]["sweep_index"] == 5
    assert shifted_payload["plot"]["metadata"]["sweep_index"] == 5
    assert shifted_payload["selection"]["trace_key"] != default_trace_key
    assert shifted_payload["plot"]["series"][0]["values"] != payload["plot"]["series"][0]["values"]


def test_retry_task_recovers_missing_persisted_setup_for_explorer() -> None:
    source_task = _submit_local_simulation(ptc_enabled=True)
    retried = client.post(f"/tasks/{source_task['task_id']}/retry").json()["data"]["task"]

    with _bind_client_app_context(client):
        task_service = get_task_service()
        retried_detail = task_service.get_task(retried["task_id"])
        task_service._repository.merge_task_event_metadata(
            retried_detail.task_id,
            retried_detail.events[0].event_key,
            {"simulation_setup": None},
        )

    recovered_detail = client.get(f"/tasks/{retried['task_id']}").json()["data"]
    assert recovered_detail["simulation_setup"] == source_task["simulation_setup"]

    explorer = client.get(f"/tasks/{retried['task_id']}/simulation-results/explorer")
    assert explorer.status_code == 200


def test_explorer_rejects_ports_not_declared_by_definition() -> None:
    task = _submit_local_simulation(ptc_enabled=True)

    response = client.get(
        f"/tasks/{task['task_id']}/simulation-results/explorer"
        "?family=s_matrix&metric=magnitude_db&output_port=2&input_port=1"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "request_validation_failed"
