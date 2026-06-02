from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from src.app.domain.datasets import (
    CharacterizationAnalysisRegistryRow,
    CharacterizationAnalysisTraceCompatibility,
)
from src.app.infrastructure.runtime import get_catalog_repository, reset_runtime_state
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
    rows_by_id = {
        row["analysis_id"]: row for row in payload["data"]["rows"]
    }
    assert rows_by_id["admittance_extraction"] == {
        "analysis_id": "admittance_extraction",
        "label": "Admittance Resonance Extraction",
        "availability_state": "recommended",
        "required_config_fields": ["fit_window", "residual_tolerance"],
        "trace_compatibility": {
            "matched_trace_count": 2,
            "selected_trace_count": 2,
            "recommended_trace_modes": ["base"],
            "summary": "2 selected traces are eligible for admittance resonance extraction.",
        },
        "prerequisite_state": "ready",
        "upstream_result_requirement": None,
        "downstream_unlock_analysis_ids": ["admittance_member_fit"],
    }
    assert rows_by_id["admittance_member_fit"]["prerequisite_state"] == "ready"
    assert rows_by_id["admittance_member_fit"]["upstream_result_requirement"] is not None
    assert rows_by_id["admittance_member_fit"]["upstream_result_requirement"][
        "required_upstream_analysis_ids"
    ] == ["admittance_extraction"]
    assert payload["data"]["data_collection_review"]["readiness_state"] == "ready"


def test_characterization_registry_ignores_incomplete_legacy_row_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = get_catalog_repository()
    monkeypatch.setattr(
        repository,
        "list_characterization_analysis_registry",
        lambda dataset_id, design_id: (
            CharacterizationAnalysisRegistryRow(
                analysis_id="sideband_comparison",
                label="Legacy Sideband Only",
                availability_state="available",
                required_config_fields=("comparison_window",),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=99,
                    selected_trace_count=0,
                    recommended_trace_modes=("sideband",),
                    summary="legacy row should not drive active registry inclusion",
                ),
            ),
        ),
    )

    response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/"
        "characterization-analysis-registry",
        params=[
            ("selected_trace_ids", "trace_flux_a_measurement"),
            ("selected_trace_ids", "trace_flux_a_layout"),
        ],
    )

    assert response.status_code == 200
    rows = response.json()["data"]["rows"]
    assert [row["analysis_id"] for row in rows] == [
        "admittance_extraction",
        "admittance_member_fit",
        "sideband_comparison",
        "junction_parameter_identification",
        "screening_summary",
    ]
    assert rows[2]["label"] == "Sideband Comparison"


def test_characterization_registry_fallback_does_not_overclaim_selected_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = get_catalog_repository()
    original_trace_rows = tuple(
        repository.list_trace_metadata("fluxonium-2025-031", "design_flux_scan_a")
    )
    monkeypatch.setattr(
        repository,
        "list_trace_metadata",
        lambda dataset_id, design_id: tuple(
            replace(trace, analysis_capabilities=()) for trace in original_trace_rows
        ),
    )
    monkeypatch.setattr(
        repository,
        "list_characterization_analysis_registry",
        lambda dataset_id, design_id: (
            CharacterizationAnalysisRegistryRow(
                analysis_id="admittance_extraction",
                label="Legacy Admittance Extraction",
                availability_state="recommended",
                required_config_fields=("fit_window", "residual_tolerance"),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=2,
                    selected_trace_count=0,
                    recommended_trace_modes=("base",),
                    summary="legacy selected scope should not stay recommended",
                ),
            ),
        ),
    )

    response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/"
        "characterization-analysis-registry",
        params=[
            ("selected_trace_ids", "trace_flux_a_measurement"),
            ("selected_trace_ids", "trace_flux_a_layout"),
        ],
    )

    assert response.status_code == 200
    assert response.json()["data"]["rows"] == [
        {
            "analysis_id": "admittance_extraction",
            "label": "Admittance Resonance Extraction",
            "availability_state": "unavailable",
            "required_config_fields": ["fit_window", "residual_tolerance"],
            "trace_compatibility": {
                "matched_trace_count": 0,
                "selected_trace_count": 2,
                "recommended_trace_modes": ["base"],
                "summary": (
                    "Selected trace compatibility could not be re-evaluated because "
                    "this design does not yet carry durable trace capability markings."
                ),
            },
            "prerequisite_state": "ready",
            "upstream_result_requirement": None,
            "downstream_unlock_analysis_ids": ["admittance_member_fit"],
        }
    ]


def test_characterization_registry_fallback_marks_unsupported_analysis_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = get_catalog_repository()
    original_trace_rows = tuple(
        repository.list_trace_metadata("fluxonium-2025-031", "design_flux_scan_a")
    )
    monkeypatch.setattr(
        repository,
        "list_trace_metadata",
        lambda dataset_id, design_id: tuple(
            replace(trace, analysis_capabilities=()) for trace in original_trace_rows
        ),
    )
    monkeypatch.setattr(
        repository,
        "list_characterization_analysis_registry",
        lambda dataset_id, design_id: (
            CharacterizationAnalysisRegistryRow(
                analysis_id="sideband_comparison",
                label="Legacy Sideband Comparison",
                availability_state="available",
                required_config_fields=("comparison_window",),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=1,
                    selected_trace_count=0,
                    recommended_trace_modes=("sideband",),
                    summary="legacy sideband row overclaimed local run support",
                ),
            ),
        ),
    )

    response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/"
        "characterization-analysis-registry"
    )

    assert response.status_code == 200
    assert response.json()["data"]["rows"] == [
        {
            "analysis_id": "sideband_comparison",
            "label": "Sideband Comparison",
            "availability_state": "unavailable",
            "required_config_fields": ["comparison_window"],
            "trace_compatibility": {
                "matched_trace_count": 1,
                "selected_trace_count": 0,
                "recommended_trace_modes": ["sideband"],
                "summary": (
                    "Legacy trace coverage suggests sideband comparison may be "
                    "relevant, but the current runtime does not yet support "
                    "executing this analysis."
                ),
            },
            "prerequisite_state": "ready",
            "upstream_result_requirement": None,
            "downstream_unlock_analysis_ids": [],
        }
    ]

    submit_response = client.post(
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

    assert submit_response.status_code == 409
    assert submit_response.json()["error"]["code"] == "characterization_analysis_unsupported"


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
            "input_result_refs": [],
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
            "label": "Flux Scan A admittance resonance extraction",
            "status": "completed",
            "scope": "design_traces",
            "trace_count": 2,
            "sources_summary": "Y base 2",
            "provenance_summary": "Measurement batch #4 + layout batch #2",
            "updated_at": "2026-03-14T11:12:00Z",
            "result_id": "char-fit-flux-a-01",
            "input_result_refs": [],
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
