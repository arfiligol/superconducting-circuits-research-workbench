from __future__ import annotations

import csv
import os
from pathlib import Path

import numpy as np
import pytest
from core.shared.persistence import LocalZarrTraceStore
from fastapi.testclient import TestClient
from sc_core.execution import TaskResultHandle
from src.app.domain.tasks import (
    CharacterizationSetup,
    TaskDetail,
    TaskProgress,
    TaskResultRefs,
)
from src.app.infrastructure.persisted_characterization_runtime import (
    CharacterizationExecutionRequest,
    CharacterizationExecutionTrace,
)
from src.app.infrastructure.runtime import (
    get_catalog_repository,
    get_persisted_characterization_repository,
    reset_runtime_state,
)
from src.app.main import app

client = TestClient(app)

RUN_HFSS_REAL_DATA_E2E = os.environ.get("RUN_HFSS_REAL_DATA_E2E") == "1"
DEFAULT_PF6FQ_RAW_DATA_ROOT = Path(
    "/Users/arfiligol/Github/superconducting-circuits-tutorial/data/raw/layout_simulation/PF6FQ"
)
PF6FQ_RAW_DATA_ROOT = Path(
    os.environ.get("PF6FQ_RAW_DATA_ROOT", str(DEFAULT_PF6FQ_RAW_DATA_ROOT))
)
XY_IM_Y11_FILE = PF6FQ_RAW_DATA_ROOT / "Q0" / "PF6FQ_Q0_XY_Im_Y11.csv"
READOUT_IM_Y11_FILE = PF6FQ_RAW_DATA_ROOT / "Q0" / "PF6FQ_Q0_Readout_Im_Y11.csv"
XY_RE_YIN_FILE = PF6FQ_RAW_DATA_ROOT / "Q0" / "PF6FQ_Q0_XY_Re_Yin.csv"
EXPECTED_PF6FQ_FILES = (XY_IM_Y11_FILE, READOUT_IM_Y11_FILE, XY_RE_YIN_FILE)

pytestmark = pytest.mark.skipif(
    not RUN_HFSS_REAL_DATA_E2E,
    reason="Set RUN_HFSS_REAL_DATA_E2E=1 to run PF6FQ real-data E2E tests.",
)


@pytest.fixture(autouse=True)
def reset_app_state() -> None:
    reset_runtime_state()
    client.cookies.clear()
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


def _require_real_files() -> None:
    missing = [str(path) for path in EXPECTED_PF6FQ_FILES if not path.is_file()]
    if missing:
        expected = "\n".join(str(path) for path in EXPECTED_PF6FQ_FILES)
        pytest.skip(
            "PF6FQ real-data opt-in is enabled, but required files are missing. "
            f"PF6FQ_RAW_DATA_ROOT={PF6FQ_RAW_DATA_ROOT}. Expected files:\n{expected}. "
            f"Missing files: {missing}"
        )


def _read_hfss_imaginary_y11_grid(path: Path) -> dict[str, object]:
    frequency_values: set[float] = set()
    sweep_values: set[float] = set()
    value_by_coordinate: dict[tuple[float, float], float] = {}

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        headers = next(reader)
        assert headers == [
            "L_jun [nH]",
            "Freq [GHz]",
            "im(Yt(Rectangle5_T1,Rectangle5_T1)) []",
        ]
        for row in reader:
            sweep = float(row[0])
            frequency = float(row[1])
            value = float(row[2])
            frequency_values.add(frequency)
            sweep_values.add(sweep)
            value_by_coordinate[(frequency, sweep)] = value

    frequencies = sorted(frequency_values)
    l_jun_values = sorted(sweep_values)
    values = [
        [value_by_coordinate[(frequency, sweep)] for sweep in l_jun_values]
        for frequency in frequencies
    ]
    assert len(values) == 25000
    assert len(values[0]) == 10

    return {
        "family": "y_matrix",
        "parameter": "Y11",
        "representation": "imaginary",
        "trace_mode_group": "base",
        "stage_kind": "raw",
        "provenance_summary": f"Layout simulation import · {path.name} · Y11 imaginary",
        "axes": [
            {"name": "frequency", "unit": "GHz", "length": len(frequencies)},
            {"name": "L_jun", "unit": "nH", "length": len(l_jun_values)},
        ],
        "preview_payload": {
            "kind": "nd_grid",
            "axes": [
                {"name": "frequency", "unit": "GHz", "values": frequencies},
                {"name": "L_jun", "unit": "nH", "values": l_jun_values},
            ],
            "values": values,
        },
    }


def _read_real_yin_series(path: Path) -> dict[str, object]:
    points: list[list[float]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        headers = next(reader)
        assert headers[0] == "Freq [GHz]"
        for row in reader:
            points.append([float(row[0]), float(row[1])])

    assert len(points) == 8
    return {
        "family": "y_matrix",
        "parameter": "Yin",
        "representation": "real",
        "trace_mode_group": "base",
        "stage_kind": "raw",
        "provenance_summary": f"Layout simulation import · {path.name} · Yin real",
        "axes": [{"name": "frequency", "unit": "GHz", "length": len(points)}],
        "preview_payload": {
            "kind": "sampled_series",
            "points": points,
        },
    }


def _create_dataset() -> str:
    response = client.post(
        "/datasets",
        json={
            "name": "PF6FQ Real HFSS E2E",
            "family": "floatingqubit",
            "device_type": "Floating Qubit",
            "source": "layout_simulation",
        },
    )
    assert response.status_code == 201
    return str(response.json()["data"]["dataset"]["dataset_id"])


def _ingest_trace(
    *,
    dataset_id: str,
    design_name: str,
    design_id: str | None,
    path: Path,
    trace: dict[str, object],
) -> dict[str, object]:
    body: dict[str, object] = {
        "kind": "layout_simulation",
        "design_name": design_name,
        "provenance_label": path.name,
        "traces": [trace],
    }
    if design_id is not None:
        body["design_id"] = design_id
    response = client.post(f"/datasets/{dataset_id}/ingestions", json=body)
    assert response.status_code == 200
    return response.json()["data"]


def _store_ref_from_detail(detail: dict[str, object]) -> dict[str, object]:
    payload_ref = detail["payload_ref"]
    assert isinstance(payload_ref, dict)
    return {
        key: value
        for key, value in payload_ref.items()
        if key != "payload_role"
    }


def _capabilities_by_analysis(
    capabilities: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    return {
        str(capability["analysis_id"]): capability
        for capability in capabilities
    }


def _build_direct_characterization_task(
    *,
    dataset_id: str,
    design_id: str,
    selected_trace_ids: tuple[str, ...],
    fit_window: tuple[float, float],
    residual_tolerance: float,
) -> TaskDetail:
    return TaskDetail(
        task_id=990601,
        kind="characterization",
        lane="characterization",
        execution_mode="run",
        status="running",
        submitted_at="2026-04-30T00:00:00Z",
        owner_user_id="local-user",
        owner_display_name="Local User",
        workspace_id="workspace-local",
        workspace_slug="local",
        visibility_scope="local",
        dataset_id=dataset_id,
        definition_id=None,
        summary="PF6FQ real-data persisted admittance extraction.",
        queue_backend="backend_db",
        worker_task_name="characterization_run_task",
        request_ready=True,
        submitted_from_active_dataset=True,
        progress=TaskProgress(
            phase="running",
            percent_complete=50,
            summary="Executing PF6FQ real-data admittance extraction.",
            updated_at="2026-04-30T00:00:00Z",
        ),
        result_refs=TaskResultRefs(
            result_handle=TaskResultHandle(),
            metadata_records=(),
            trace_payload=None,
            result_handles=(),
        ),
        characterization_setup=CharacterizationSetup(
            design_id=design_id,
            analysis_id="admittance_extraction",
            selected_trace_ids=selected_trace_ids,
            analysis_config={
                "fit_window": list(fit_window),
                "residual_tolerance": residual_tolerance,
            },
        ),
    )


def test_pf6fq_real_hfss_ingestion_browse_and_characterization_e2e() -> None:
    _require_real_files()
    xy_trace = _read_hfss_imaginary_y11_grid(XY_IM_Y11_FILE)
    readout_trace = _read_hfss_imaginary_y11_grid(READOUT_IM_Y11_FILE)
    yin_trace = _read_real_yin_series(XY_RE_YIN_FILE)

    dataset_id = _create_dataset()
    xy_ingestion = _ingest_trace(
        dataset_id=dataset_id,
        design_name="PF6FQ Q0",
        design_id=None,
        path=XY_IM_Y11_FILE,
        trace=xy_trace,
    )
    design_id = str(xy_ingestion["design"]["design_id"])
    xy_trace_id = str(xy_ingestion["traces"][0]["trace_id"])
    readout_ingestion = _ingest_trace(
        dataset_id=dataset_id,
        design_name="PF6FQ Q0",
        design_id=design_id,
        path=READOUT_IM_Y11_FILE,
        trace=readout_trace,
    )
    readout_trace_id = str(readout_ingestion["traces"][0]["trace_id"])
    yin_ingestion = _ingest_trace(
        dataset_id=dataset_id,
        design_name="PF6FQ Q0",
        design_id=design_id,
        path=XY_RE_YIN_FILE,
        trace=yin_trace,
    )
    yin_trace_id = str(yin_ingestion["traces"][0]["trace_id"])

    assert len({xy_trace_id, readout_trace_id, yin_trace_id}) == 3
    designs = client.get(f"/datasets/{dataset_id}/designs")
    assert designs.status_code == 200
    design = next(
        row for row in designs.json()["data"]["rows"] if row["design_id"] == design_id
    )
    assert design["name"] == "PF6FQ Q0"
    assert design["trace_count"] == 3

    trace_rows = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces")
    assert trace_rows.status_code == 200
    rows = trace_rows.json()["data"]["rows"]
    assert {row["trace_id"] for row in rows} == {xy_trace_id, readout_trace_id, yin_trace_id}
    assert all("preview_payload" not in row for row in rows)
    assert all("payload_ref" not in row for row in rows)

    xy_row = next(row for row in rows if row["trace_id"] == xy_trace_id)
    assert xy_row["source_kind"] == "layout_simulation"
    assert xy_row["family"] == "y_matrix"
    assert xy_row["parameter"] == "Y11"
    assert xy_row["representation"] == "imaginary"
    assert xy_row["ndim"] == 2
    assert xy_row["shape"] == [25000, 10]
    assert xy_row["axes_summary"] == {
        "rank": 2,
        "axis_names": ["frequency", "L_jun"],
        "axis_units": ["GHz", "nH"],
        "axis_lengths": [25000, 10],
    }
    assert xy_row["available_sweep_axes"] == ["L_jun"]
    row_capabilities = _capabilities_by_analysis(xy_row["analysis_capabilities"])
    assert row_capabilities["admittance_extraction"]["status"] == "eligible"

    detail_response = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/traces/{xy_trace_id}"
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["preview_payload"] == {
        "kind": "nd_grid",
        "axes": [
            {"name": "frequency", "unit": "GHz", "length": 25000},
            {"name": "L_jun", "unit": "nH", "length": 10},
        ],
        "shape": [25000, 10],
        "values_ref": "trace_store",
    }
    assert "values" not in detail["preview_payload"]

    store = LocalZarrTraceStore()
    stored_values = store.read_trace_slice(_store_ref_from_detail(detail), selection=())
    expected_values = np.asarray(xy_trace["preview_payload"]["values"], dtype=np.float64)
    np.testing.assert_allclose(stored_values.real, np.zeros((25000, 10)))
    np.testing.assert_allclose(stored_values.imag, expected_values)

    registry = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/characterization-analysis-registry",
        params=[("selected_trace_ids", xy_trace_id)],
    )
    assert registry.status_code == 200
    registry_rows = {
        row["analysis_id"]: row
        for row in registry.json()["data"]["rows"]
    }
    assert registry_rows["admittance_extraction"]["availability_state"] == "recommended"
    assert registry_rows["admittance_extraction"]["trace_compatibility"] == {
        "matched_trace_count": 1,
        "selected_trace_count": 1,
        "recommended_trace_modes": ["base"],
        "summary": "1 selected trace is eligible for admittance resonance extraction.",
    }

    catalog_repository = get_catalog_repository()
    persisted_design = catalog_repository.get_design(dataset_id, design_id)
    assert persisted_design is not None
    trace_summary = next(
        trace
        for trace in catalog_repository.list_trace_metadata(dataset_id, design_id)
        if trace.trace_id == xy_trace_id
    )
    trace_detail = catalog_repository.get_trace_detail(dataset_id, design_id, xy_trace_id)
    assert trace_detail is not None
    execution_result = get_persisted_characterization_repository().run_admittance_extraction(
        CharacterizationExecutionRequest(
            task=_build_direct_characterization_task(
                dataset_id=dataset_id,
                design_id=design_id,
                selected_trace_ids=(xy_trace_id,),
                fit_window=(3.8, 6.8),
                residual_tolerance=10.0,
            ),
            design=persisted_design,
            traces=(
                CharacterizationExecutionTrace(
                    summary=trace_summary,
                    detail=trace_detail,
                ),
            ),
        )
    )
    assert execution_result.result_summary_payload["characterization_result_id"]

    results = client.get(f"/datasets/{dataset_id}/designs/{design_id}/characterization-results")
    assert results.status_code == 200
    result_row = next(
        row
        for row in results.json()["data"]["rows"]
        if row["analysis_id"] == "admittance_extraction"
    )
    result_id = str(result_row["result_id"])
    result_detail = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/characterization-results/{result_id}"
    )
    assert result_detail.status_code == 200
    result_payload = result_detail.json()["data"]
    assert result_payload["payload"]["input_axis"]["axis_key"] == "L_jun"
    assert result_payload["payload"]["input_axis"]["length"] == 10
    assert result_payload["payload"]["metric"]["metric_key"] == "frequency_ghz"

    artifact = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/"
        f"characterization-results/{result_id}/artifacts/"
        f"{result_id}:mode-frequency-grid",
        params={"preset_id": "mode_by_input_table"},
    )
    assert artifact.status_code == 200
    artifact_payload = artifact.json()["data"]["payload"]
    assert artifact_payload["layout"] == {
        "rows_axis": "mode_index",
        "columns_axis": "L_jun",
        "cell_metric": "frequency_ghz",
        "compare_axis": "member_key",
    }
    assert [column["axis_value"] for column in artifact_payload["columns"]] == [
        0.0,
        5.0,
        10.0,
        15.0,
        18.0,
        20.0,
        22.0,
        24.0,
        26.0,
        28.0,
    ]
