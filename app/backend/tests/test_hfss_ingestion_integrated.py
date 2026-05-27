import numpy as np
import pytest
from core.shared.persistence import LocalZarrTraceStore
from fastapi.testclient import TestClient
from src.app.infrastructure.runtime import reset_runtime_state
from src.app.main import app

client = TestClient(app)


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


def _capabilities_by_analysis(
    capabilities: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    return {
        str(capability["analysis_id"]): capability
        for capability in capabilities
    }


def test_hfss_nd_grid_ingestion_persists_trace_store_and_is_characterization_eligible() -> None:
    created = client.post(
        "/datasets",
        json={
            "name": "HFSS Integrated Verification",
            "family": "floatingqubit",
            "device_type": "Floating Qubit",
            "source": "layout_simulation",
        },
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["dataset"]["dataset_id"]

    ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "layout_simulation",
            "design_name": "PF6FQ Integrated HFSS",
            "provenance_label": "HFSS Y11 frequency by L_jun smoke",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "Y11",
                    "representation": "imaginary",
                    "trace_mode_group": "base",
                    "stage_kind": "raw",
                    "provenance_summary": "HFSS im(Yt) frequency by L_jun grid",
                    "axes": [
                        {"name": "frequency", "unit": "GHz", "length": 3},
                        {"name": "L_jun", "unit": "nH", "length": 2},
                    ],
                    "preview_payload": {
                        "kind": "nd_grid",
                        "axes": [
                            {"name": "frequency", "unit": "GHz", "values": [4.8, 4.9, 5.0]},
                            {"name": "L_jun", "unit": "nH", "values": [8.0, 9.0]},
                        ],
                        "values": [
                            [-2.0, -1.0],
                            [0.2, 0.5],
                            [1.2, 1.6],
                        ],
                    },
                }
            ],
        },
    )
    assert ingestion.status_code == 200
    ingestion_payload = ingestion.json()["data"]
    design_id = ingestion_payload["design"]["design_id"]
    trace_id = ingestion_payload["traces"][0]["trace_id"]

    trace_rows = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces")
    assert trace_rows.status_code == 200
    trace_row = trace_rows.json()["data"]["rows"][0]
    assert trace_row["source_kind"] == "layout_simulation"
    assert trace_row["family"] == "y_matrix"
    assert trace_row["parameter"] == "Y11"
    assert trace_row["representation"] == "imaginary"
    assert trace_row["ndim"] == 2
    assert trace_row["shape"] == [3, 2]
    assert trace_row["axes_summary"] == {
        "rank": 2,
        "axis_names": ["frequency", "L_jun"],
        "axis_units": ["GHz", "nH"],
        "axis_lengths": [3, 2],
    }
    assert trace_row["available_sweep_axes"] == ["L_jun"]
    row_capabilities = _capabilities_by_analysis(trace_row["analysis_capabilities"])
    assert row_capabilities["admittance_extraction"]["status"] == "eligible"

    trace_detail = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/traces/{trace_id}"
    )
    assert trace_detail.status_code == 200
    detail = trace_detail.json()["data"]
    assert detail["axes"] == [
        {"name": "frequency", "unit": "GHz", "length": 3},
        {"name": "L_jun", "unit": "nH", "length": 2},
    ]
    preview = detail["preview_payload"]
    assert preview["kind"] == "nd_grid"
    assert preview["axes"] == [
        {"name": "frequency", "unit": "GHz", "length": 3},
        {"name": "L_jun", "unit": "nH", "length": 2},
    ]
    assert preview["shape"] == [3, 2]
    assert preview["values_ref"] == "trace_store"
    assert preview["preview_sample"]["fixed_axes"] == [
        {"name": "L_jun", "unit": "nH", "index": 0, "value": 8.0}
    ]

    store_ref = {
        key: value
        for key, value in detail["payload_ref"].items()
        if key != "payload_role"
    }
    values = LocalZarrTraceStore().read_trace_slice(store_ref, selection=())
    np.testing.assert_allclose(values.real, np.zeros((3, 2)))
    np.testing.assert_allclose(
        values.imag,
        np.array([[-2.0, -1.0], [0.2, 0.5], [1.2, 1.6]]),
    )
    np.testing.assert_allclose(
        LocalZarrTraceStore().read_axis_slice(store_ref, axis_name="frequency"),
        np.array([4.8, 4.9, 5.0]),
    )
    np.testing.assert_allclose(
        LocalZarrTraceStore().read_axis_slice(store_ref, axis_name="L_jun"),
        np.array([8.0, 9.0]),
    )

    registry = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/characterization-analysis-registry",
        params=[("selected_trace_ids", trace_id)],
    )
    assert registry.status_code == 200
    rows_by_id = {
        row["analysis_id"]: row
        for row in registry.json()["data"]["rows"]
    }
    assert rows_by_id["admittance_extraction"]["availability_state"] == "recommended"
    assert rows_by_id["admittance_extraction"]["trace_compatibility"] == {
        "matched_trace_count": 1,
        "selected_trace_count": 1,
        "recommended_trace_modes": ["base"],
        "summary": "1 selected trace is eligible for admittance resonance extraction.",
    }
