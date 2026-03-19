from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from src.app.infrastructure.runtime import reset_runtime_state
from src.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_app_state() -> None:
    reset_runtime_state()
    client.cookies.clear()


def _characterization_payload(
    *,
    design_id: str = "design_local_flux_playground",
    analysis_id: str = "admittance_extraction",
    selected_trace_ids: tuple[str, ...] = (
        "trace_local_flux_measurement",
        "trace_local_flux_preview",
    ),
    fit_window: tuple[float, float] = (4.85, 5.25),
    residual_tolerance: float = 0.015,
) -> dict[str, object]:
    return {
        "kind": "characterization",
        "characterization_setup": {
            "design_id": design_id,
            "analysis_id": analysis_id,
            "selected_trace_ids": list(selected_trace_ids),
            "analysis_config": {
                "fit_window": list(fit_window),
                "residual_tolerance": residual_tolerance,
            },
        },
    }


def _login_online() -> None:
    switch_response = client.patch(
        "/session/runtime-mode",
        json={"runtime_mode": "online", "server_origin": "http://127.0.0.1:8000"},
    )
    assert switch_response.status_code == 200
    login_response = client.post(
        "/session/login",
        json={
            "email": "rewrite.local@example.com",
            "password": "rewrite-local-password",
        },
    )
    assert login_response.status_code == 200


def test_local_characterization_registry_exposes_admittance_for_compatible_saved_design() -> None:
    response = client.get(
        "/datasets/local-dataset-001/designs/design_local_flux_playground/"
        "characterization-analysis-registry",
        params=[
            ("selected_trace_ids", "trace_local_flux_measurement"),
            ("selected_trace_ids", "trace_local_flux_preview"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["rows"] == [
        {
            "analysis_id": "admittance_extraction",
            "label": "Admittance Extraction",
            "availability_state": "recommended",
            "required_config_fields": ["fit_window", "residual_tolerance"],
            "trace_compatibility": {
                "matched_trace_count": 2,
                "selected_trace_count": 2,
                "recommended_trace_modes": ["base"],
                "summary": "2 compatible base traces are ready for a stable admittance fit.",
            },
        }
    ]


def test_local_characterization_runtime_summary_is_configured_and_healthy() -> None:
    response = client.get("/tasks/runtime/processors")

    assert response.status_code == 200
    processor = next(
        item
        for item in response.json()["data"]["processors"]
        if item["lane"] == "characterization"
    )
    assert processor == {
        "processor_id": "local-characterization-processor",
        "lane": "characterization",
        "state": "healthy",
        "current_task_id": None,
        "last_heartbeat_at": processor["last_heartbeat_at"],
        "runtime_metadata": {
            "authority": "local_runtime",
            "execution_mode": "in_process",
            "capacity": 1,
        },
    }


@pytest.mark.parametrize(
    ("payload", "status_code", "error_code"),
    [
        (
            _characterization_payload(design_id="missing-design"),
            404,
            "design_not_found",
        ),
        (
            _characterization_payload(analysis_id="unknown-analysis"),
            422,
            "characterization_analysis_invalid",
        ),
        (
            _characterization_payload(selected_trace_ids=("missing-trace",)),
            422,
            "characterization_trace_selection_invalid",
        ),
        (
            _characterization_payload(selected_trace_ids=("trace_local_flux_measurement",)),
            422,
            "characterization_trace_selection_incompatible",
        ),
        (
            _characterization_payload(fit_window=(5.25, 4.85)),
            422,
            "characterization_config_invalid",
        ),
    ],
)
def test_local_characterization_submit_rejects_invalid_payloads(
    payload: dict[str, object],
    status_code: int,
    error_code: str,
) -> None:
    response = client.post("/tasks", json=payload)

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code


def test_online_characterization_submit_rejects_recognized_but_unsupported_analysis() -> None:
    _login_online()

    response = client.post(
        "/tasks",
        json={
            "kind": "characterization",
            "dataset_id": "fluxonium-2025-031",
            "characterization_setup": {
                "design_id": "design_flux_scan_a",
                "analysis_id": "sideband_comparison",
                "selected_trace_ids": ["trace_flux_a_phase"],
                "analysis_config": {"comparison_window": [5.7, 5.9]},
            },
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "characterization_analysis_unsupported"


def test_local_characterization_submit_completes_with_analysis_run_and_result_handles() -> None:
    response = client.post("/tasks", json=_characterization_payload())

    assert response.status_code == 201
    task = response.json()["data"]["task"]
    assert task["status"] == "completed"
    assert task["characterization_setup"] == _characterization_payload()[
        "characterization_setup"
    ]
    assert task["result_refs"]["analysis_run_id"] == task["task_id"]
    assert task["result_refs"]["trace_payload"]["payload_role"] == "analysis_projection"
    assert task["result_refs"]["result_handles"][0]["kind"] == "characterization_report"
    assert task["result_refs"]["result_handles"][0]["status"] == "materialized"


def test_local_characterization_result_surfaces_survive_refresh() -> None:
    submit_response = client.post("/tasks", json=_characterization_payload())
    assert submit_response.status_code == 201

    results_response = client.get(
        "/datasets/local-dataset-001/designs/design_local_flux_playground/characterization-results"
    )
    assert results_response.status_code == 200
    result_row = results_response.json()["data"]["rows"][0]
    assert result_row["analysis_id"] == "admittance_extraction"
    assert result_row["design_id"] == "design_local_flux_playground"

    run_history_response = client.get(
        "/datasets/local-dataset-001/designs/design_local_flux_playground/characterization-run-history"
    )
    assert run_history_response.status_code == 200
    run_row = run_history_response.json()["data"]["rows"][0]
    assert run_row["analysis_id"] == "admittance_extraction"
    assert run_row["result_id"] == result_row["result_id"]

    detail_response = client.get(
        "/datasets/local-dataset-001/designs/design_local_flux_playground/"
        f"characterization-results/{result_row['result_id']}"
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["analysis_id"] == "admittance_extraction"
    assert detail["input_trace_ids"] == [
        "trace_local_flux_measurement",
        "trace_local_flux_preview",
    ]
    assert detail["payload"]["fit_table"][0]["parameter"] == "f01"
    assert detail["artifact_refs"][0]["payload_locator"] == (
        f"artifacts/tasks/{submit_response.json()['data']['task']['task_id']}/admittance-fit-table.json"
    )

    reset_runtime_state()

    refreshed_results = client.get(
        "/datasets/local-dataset-001/designs/design_local_flux_playground/characterization-results"
    )
    refreshed_rows = refreshed_results.json()["data"]["rows"]
    assert any(row["result_id"] == result_row["result_id"] for row in refreshed_rows)

    refreshed_detail = client.get(
        "/datasets/local-dataset-001/designs/design_local_flux_playground/"
        f"characterization-results/{result_row['result_id']}"
    )
    assert refreshed_detail.status_code == 200
    assert refreshed_detail.json()["data"]["result_id"] == result_row["result_id"]
