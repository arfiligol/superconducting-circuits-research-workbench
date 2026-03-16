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


def test_characterization_analysis_registry_returns_summary_rows_and_trace_filter_echo() -> None:
    response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/"
        "characterization-analysis-registry",
        params=[
            ("selected_trace_ids", "trace_flux_a_measurement"),
            ("selected_trace_ids", "trace_flux_a_layout"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["meta"]["filter_echo"] == {
        "dataset_id": "fluxonium-2025-031",
        "design_id": "design_flux_scan_a",
        "selected_trace_ids": [
            "trace_flux_a_measurement",
            "trace_flux_a_layout",
        ],
    }
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
                "summary": "Two compatible base traces are ready for a stable admittance fit.",
            },
        },
        {
            "analysis_id": "sideband_comparison",
            "label": "Sideband Comparison",
            "availability_state": "available",
            "required_config_fields": ["comparison_window"],
            "trace_compatibility": {
                "matched_trace_count": 1,
                "selected_trace_count": 2,
                "recommended_trace_modes": ["sideband"],
                "summary": (
                    "One compatible sideband trace is visible, but comparison coverage "
                    "remains thin."
                ),
            },
        },
        {
            "analysis_id": "junction_parameter_identification",
            "label": "Junction Parameter Identification",
            "availability_state": "unavailable",
            "required_config_fields": ["fit_window", "prior_family"],
            "trace_compatibility": {
                "matched_trace_count": 0,
                "selected_trace_count": 2,
                "recommended_trace_modes": ["base", "sideband"],
                "summary": (
                    "No compatible trace bundle currently satisfies the identification "
                    "prerequisites."
                ),
            },
        },
    ]


def test_characterization_run_history_supports_analysis_filter_and_cursor_meta() -> None:
    first_page_response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-run-history",
        params={"limit": 1},
    )

    assert first_page_response.status_code == 200
    first_page_payload = first_page_response.json()
    assert first_page_payload["ok"] is True
    assert first_page_payload["meta"]["limit"] == 1
    assert first_page_payload["meta"]["next_cursor"] == "1"
    assert first_page_payload["meta"]["prev_cursor"] is None
    assert first_page_payload["meta"]["has_more"] is True
    assert first_page_payload["meta"]["filter_echo"] == {
        "dataset_id": "fluxonium-2025-031",
        "design_id": "design_flux_scan_a",
        "analysis_id": None,
    }
    assert first_page_payload["data"]["rows"] == [
        {
            "run_id": "run-flux-a-004",
            "dataset_id": "fluxonium-2025-031",
            "design_id": "design_flux_scan_a",
            "analysis_id": "sideband_comparison",
            "label": "Flux Scan A sideband comparison",
            "status": "failed",
            "scope": "design_traces",
            "trace_count": 1,
            "sources_summary": "Y phase 1",
            "provenance_summary": "Measurement sideband trace · batch #4",
            "updated_at": "2026-03-14T11:20:00Z",
            "result_id": "char-sideband-flux-a-02",
        }
    ]

    second_page_response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-run-history",
        params={"limit": 1, "cursor": "1"},
    )
    assert second_page_response.status_code == 200
    second_page_payload = second_page_response.json()
    assert second_page_payload["ok"] is True
    assert second_page_payload["meta"]["next_cursor"] is None
    assert second_page_payload["meta"]["prev_cursor"] == "0"
    assert second_page_payload["meta"]["has_more"] is False
    assert second_page_payload["data"]["rows"] == [
        {
            "run_id": "run-flux-a-003",
            "dataset_id": "fluxonium-2025-031",
            "design_id": "design_flux_scan_a",
            "analysis_id": "admittance_extraction",
            "label": "Flux Scan A admittance fit",
            "status": "completed",
            "scope": "design_traces",
            "trace_count": 2,
            "sources_summary": "Y base 2",
            "provenance_summary": "Measurement batch #4 + layout batch #2",
            "updated_at": "2026-03-14T11:12:00Z",
            "result_id": "char-fit-flux-a-01",
        }
    ]

    filtered_response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-run-history",
        params={"analysis_id": "admittance_extraction"},
    )
    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert filtered_payload["ok"] is True
    assert filtered_payload["meta"]["filter_echo"] == {
        "dataset_id": "fluxonium-2025-031",
        "design_id": "design_flux_scan_a",
        "analysis_id": "admittance_extraction",
    }
    assert [row["run_id"] for row in filtered_payload["data"]["rows"]] == ["run-flux-a-003"]


def test_characterization_registry_rejects_invisible_dataset() -> None:
    _login()
    switch_response = client.patch(
        "/session/active-workspace",
        json={"workspace_id": "ws-modeling"},
    )
    assert switch_response.status_code == 200

    response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/"
        "characterization-analysis-registry"
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "dataset_not_visible_in_workspace"
    assert payload["error"]["category"] == "permission_denied"
    assert payload["error"]["retryable"] is False


def test_characterization_run_history_rejects_missing_dataset() -> None:
    response = client.get(
        "/datasets/missing-dataset/designs/design_flux_scan_a/characterization-run-history"
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "dataset_not_found"
    assert payload["error"]["category"] == "not_found"
    assert payload["error"]["retryable"] is False
