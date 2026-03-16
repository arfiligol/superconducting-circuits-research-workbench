from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from src.app.infrastructure.runtime import reset_runtime_state
from src.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_session_cookies() -> None:
    client.cookies.clear()


def _login() -> None:
    switch_response = client.patch(
        "/session/runtime-mode",
        json={"runtime_mode": "online", "server_origin": "http://127.0.0.1:8000"},
    )
    assert switch_response.status_code == 200
    response = client.post(
        "/session/login",
        json={
            "email": "rewrite.local@example.com",
            "password": "rewrite-local-password",
        },
    )
    assert response.status_code == 200


@pytest.fixture(autouse=True)
def reset_app_state() -> None:
    reset_runtime_state()
    _login()


def test_list_characterization_results_returns_summary_rows_and_filter_echo() -> None:
    response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-results"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["meta"]["limit"] == 20
    assert payload["meta"]["has_more"] is False
    assert payload["meta"]["filter_echo"] == {
        "dataset_id": "fluxonium-2025-031",
        "design_id": "design_flux_scan_a",
        "search": None,
        "status": None,
        "analysis_id": None,
    }
    assert [row["result_id"] for row in payload["data"]["rows"]] == [
        "char-fit-flux-a-01",
        "char-sideband-flux-a-02",
    ]
    for row in payload["data"]["rows"]:
        assert "payload" not in row
        assert "diagnostics" not in row
        assert "artifact_refs" not in row
        assert row["dataset_id"] == "fluxonium-2025-031"
        assert row["design_id"] == "design_flux_scan_a"

    search_response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-results",
        params={"search": "sideband"},
    )
    assert search_response.status_code == 200
    assert [row["result_id"] for row in search_response.json()["data"]["rows"]] == [
        "char-sideband-flux-a-02"
    ]
    assert search_response.json()["meta"]["filter_echo"]["search"] == "sideband"

    status_response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-results",
        params={"status": "completed"},
    )
    assert status_response.status_code == 200
    assert [row["result_id"] for row in status_response.json()["data"]["rows"]] == [
        "char-fit-flux-a-01"
    ]
    assert status_response.json()["meta"]["filter_echo"]["status"] == "completed"

    analysis_response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-results",
        params={"analysis_id": "admittance_extraction"},
    )
    assert analysis_response.status_code == 200
    assert [row["result_id"] for row in analysis_response.json()["data"]["rows"]] == [
        "char-fit-flux-a-01"
    ]
    assert analysis_response.json()["meta"]["filter_echo"]["analysis_id"] == (
        "admittance_extraction"
    )


def test_get_characterization_result_returns_detail_only_payload() -> None:
    response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/"
        "characterization-results/char-fit-flux-a-01"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["result_id"] == "char-fit-flux-a-01"
    assert payload["data"]["analysis_id"] == "admittance_extraction"
    assert payload["data"]["input_trace_ids"] == [
        "trace_flux_a_measurement",
        "trace_flux_a_layout",
    ]
    assert payload["data"]["payload"]["fit_table"][0] == {
        "parameter": "f01",
        "value": 5.742,
        "unit": "GHz",
    }
    assert payload["data"]["diagnostics"] == [
        {
            "severity": "info",
            "code": "fit_residual_checked",
            "message": "Residual RMS stays within the characterization threshold.",
            "blocking": False,
        }
    ]
    assert payload["data"]["artifact_refs"] == [
        {
            "artifact_id": "artifact-fit-table-flux-a-01",
            "category": "fit_table",
            "view_kind": "table",
            "title": "Fit table",
            "payload_format": "json",
            "payload_locator": "artifacts/characterization/flux-a-fit-table.json",
        },
        {
            "artifact_id": "artifact-fit-plot-flux-a-01",
            "category": "plot",
            "view_kind": "plot",
            "title": "Admittance overlay",
            "payload_format": "svg",
            "payload_locator": "artifacts/characterization/flux-a-fit-plot.svg",
        },
    ]


def test_characterization_result_routes_reject_invisible_dataset() -> None:
    _login()
    switch_response = client.patch(
        "/session/active-workspace",
        json={"workspace_id": "ws-modeling"},
    )
    assert switch_response.status_code == 200

    response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-results"
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "dataset_not_visible_in_workspace"
    assert payload["error"]["category"] == "permission_denied"
    assert payload["error"]["retryable"] is False


def test_characterization_result_detail_rejects_missing_result() -> None:
    response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/"
        "characterization-results/missing-result"
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "run_not_found"
    assert payload["error"]["category"] == "not_found"
    assert payload["error"]["retryable"] is False
