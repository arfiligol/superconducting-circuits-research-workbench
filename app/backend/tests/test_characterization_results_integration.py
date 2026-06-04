from __future__ import annotations

import pytest
from app_backend.infrastructure.runtime import reset_runtime_state
from app_backend.main import app
from fastapi.testclient import TestClient

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
    assert payload["data"]["input_result_refs"] == []
    assert payload["data"]["downstream_unlock_analysis_ids"] == ["admittance_member_fit"]
    assert payload["data"]["payload"] == {
        "contract_version": "admittance_member_phase1_v1",
        "analysis_run_id": 101,
        "analysis_config": {
            "fit_window": [5.4, 6.0],
            "residual_tolerance": 0.02,
        },
        "input_axis": {
            "axis_key": "flux_bias",
            "label": "Flux bias",
            "unit": "mA",
            "length": 3,
        },
        "derived_axis": {
            "axis_key": "mode_index",
            "label": "Mode index",
            "length": 2,
        },
        "member_axis": {
            "axis_key": "member_key",
            "label": "Collection member",
            "length": 2,
        },
        "metric": {
            "metric_key": "frequency_ghz",
            "label": "Frequency",
            "unit": "GHz",
        },
        "fit_window_ghz": [5.4, 6.0],
        "member_count": 2,
        "masked_input_indices_by_member": [[2], [2]],
        "masked_member_count": 2,
        "mode_capacity": 2,
    }
    assert payload["data"]["diagnostics"] == [
        {
            "severity": "info",
            "code": "fit_residual_rms_evaluated",
            "message": (
                "All persisted input positions stay within the configured residual tolerance."
            ),
            "blocking": False,
        },
        {
            "severity": "warning",
            "code": "masked_input_positions_preserved",
            "message": (
                "1 input positions remained fully masked and were preserved in the "
                "persisted result surface."
            ),
            "blocking": False,
        },
    ]
    artifact_refs = payload["data"]["artifact_refs"]
    assert [artifact["artifact_id"] for artifact in artifact_refs] == [
        "char-fit-flux-a-01:mode-frequency-grid",
        "char-fit-flux-a-01:identify-summary",
        "char-fit-flux-a-01:report",
    ]
    grid_artifact = artifact_refs[0]
    assert grid_artifact["view_kind"] == "preset_query"
    assert grid_artifact["axes"] == [
        {
            "axis_key": "flux_bias",
            "label": "Flux bias",
            "role": "input",
            "unit": "mA",
            "length": 3,
        },
        {
            "axis_key": "member_key",
            "label": "Collection member",
            "role": "member",
            "unit": None,
            "length": 2,
        },
        {
            "axis_key": "mode_index",
            "label": "Mode index",
            "role": "derived",
            "unit": None,
            "length": 2,
        },
    ]
    assert grid_artifact["query_spec"]["supported_query_fields"] == [
        "view_mode",
        "preset_id",
    ]
    assert [preset["compare_axis"] for preset in grid_artifact["presets"]] == [
        "member_key",
        "member_key",
        "member_key",
    ]
    identify_artifact = artifact_refs[1]
    assert identify_artifact["identify_source"] is True
    assert identify_artifact["presets"][0]["preset_id"] == "summary_table"
    report_artifact = artifact_refs[2]
    assert report_artifact["view_kind"] == "json"
    assert report_artifact["query_spec"]["query_style"] == "static"


def test_get_characterization_artifact_payload_returns_phase1_admittance_presets() -> None:
    table_response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/"
        "characterization-results/char-fit-flux-a-01/artifacts/"
        "char-fit-flux-a-01:mode-frequency-grid",
        params={"preset_id": "mode_by_input_table"},
    )

    assert table_response.status_code == 200
    table_payload = table_response.json()
    assert table_payload["data"]["preset_id"] == "mode_by_input_table"
    assert table_payload["data"]["view_kind"] == "table"
    assert table_payload["data"]["payload"]["layout"] == {
        "rows_axis": "mode_index",
        "columns_axis": "flux_bias",
        "cell_metric": "frequency_ghz",
        "compare_axis": "member_key",
    }
    assert table_payload["data"]["payload"]["compare_groups"][0]["compare_key"] == (
        "measurement:trace_flux_a_measurement"
    )
    assert table_payload["data"]["payload"]["compare_groups"][0]["cells"] == [
        [5.612, 5.587, None],
        [5.846, 5.821, None],
    ]
    assert table_payload["data"]["payload"]["compare_groups"][0]["mask"] == [
        [False, False, True],
        [False, False, True],
    ]
    assert table_payload["data"]["payload"]["compare_groups"][1]["compare_key"] == (
        "layout_simulation:trace_flux_a_layout"
    )

    plot_response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/"
        "characterization-results/char-fit-flux-a-01/artifacts/"
        "char-fit-flux-a-01:mode-frequency-grid",
        params={"view_mode": "plot"},
    )

    assert plot_response.status_code == 200
    plot_payload = plot_response.json()
    assert plot_payload["data"]["preset_id"] == "mode_profile_plot"
    assert plot_payload["data"]["view_kind"] == "plot"
    assert plot_payload["data"]["payload"]["layout"] == {
        "x_axis": "mode_index",
        "y_metric": "frequency_ghz",
        "series_axis": "flux_bias",
        "compare_axis": "member_key",
    }
    measurement_series = [
        series
        for series in plot_payload["data"]["payload"]["series"]
        if series["compare_key"] == "measurement:trace_flux_a_measurement"
    ]
    assert measurement_series[0]["x_values"] == [0, 1]
    assert measurement_series[0]["y_values"] == [5.612, 5.846]
    assert measurement_series[0]["mask"] == [False, False]


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
