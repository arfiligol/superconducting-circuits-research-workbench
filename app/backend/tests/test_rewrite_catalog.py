from dataclasses import replace

import pytest
from app_backend.domain.datasets import (
    CharacterizationAnalysisRegistryQuery,
    CharacterizationArtifactPayloadQuery,
    CharacterizationResultBrowseQuery,
    CharacterizationRunHistoryQuery,
    CharacterizationTaggingRequest,
    DatasetProfileUpdate,
    DesignBrowseQuery,
    RawDataIngestionDraft,
    RawDataTraceDraft,
    TraceAxis,
    TraceBrowseQuery,
)
from app_backend.infrastructure.rewrite_app_state_repository import (
    InMemoryRewriteAppStateRepository,
)
from app_backend.infrastructure.rewrite_catalog_repository import (
    COUPLER_DETUNING_DEMO_DEFINITION_ID,
    FLOATING_QUBIT_WITH_XY_LINE_DEFINITION_ID,
    FLUXONIUM_READOUT_CHAIN_DEFINITION_ID,
    InMemoryRewriteCatalogRepository,
)
from app_backend.infrastructure.runtime import (
    reset_runtime_state,
)
from app_backend.main import app
from app_backend.services.dataset_catalog_service import DatasetCatalogService
from app_backend.services.dataset_characterization_service import (
    DatasetCharacterizationService,
)
from app_backend.services.dataset_service import DatasetService
from app_backend.services.dataset_trace_service import DatasetTraceService
from app_backend.services.service_errors import ServiceError
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_catalog_state() -> None:
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


@pytest.fixture
def app_state_repository() -> InMemoryRewriteAppStateRepository:
    repository = InMemoryRewriteAppStateRepository()
    repository.switch_runtime_mode(
        runtime_mode="online",
        server_target_origin="http://127.0.0.1:8000",
    )
    created = repository.create_authenticated_session(
        email="rewrite.local@example.com",
        password="rewrite-local-password",
    )
    assert created is not None
    return repository


@pytest.fixture
def catalog_repository() -> InMemoryRewriteCatalogRepository:
    return InMemoryRewriteCatalogRepository()


@pytest.fixture
def dataset_service(
    app_state_repository: InMemoryRewriteAppStateRepository,
    catalog_repository: InMemoryRewriteCatalogRepository,
) -> DatasetService:
    return DatasetService(
        catalog_service=DatasetCatalogService(
            repository=catalog_repository,
            session_repository=app_state_repository,
        ),
        trace_service=DatasetTraceService(
            repository=catalog_repository,
            session_repository=app_state_repository,
        ),
        characterization_service=DatasetCharacterizationService(
            repository=catalog_repository,
            session_repository=app_state_repository,
        ),
    )


def _create_ingested_trace_design(*, trace_count: int = 1) -> tuple[str, str, list[str]]:
    created = client.post(
        "/datasets",
        json={
            "name": f"Trace CRUD Dataset {trace_count}",
            "family": "fluxonium",
            "device_type": "Fluxonium",
            "source": "measurement",
        },
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["dataset"]["dataset_id"]
    ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "measurement",
            "design_name": "Trace CRUD Target",
            "provenance_label": "measurement-batch",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": f"Y11_{index}",
                    "representation": "complex",
                    "trace_mode_group": "base",
                    "stage_kind": "raw",
                    "provenance_summary": f"Measurement trace {index}",
                    "axes": [{"name": "frequency", "unit": "GHz", "length": 2}],
                    "preview_payload": {
                        "kind": "sampled_series",
                        "points": [[5.0, 0.10 * index], [5.2, 0.15 * index]],
                    },
                }
                for index in range(1, trace_count + 1)
            ],
        },
    )
    assert ingestion.status_code == 200
    payload = ingestion.json()["data"]
    return (
        dataset_id,
        payload["design"]["design_id"],
        [trace["trace_id"] for trace in payload["traces"]],
    )


def _capabilities_by_analysis(
    capabilities: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    return {capability["analysis_id"]: capability for capability in capabilities}


def _strip_completed_bundle_metadata(task, bundle_key: str):
    return replace(
        task,
        events=tuple(
            replace(
                event,
                metadata={key: value for key, value in event.metadata.items() if key != bundle_key},
            )
            if event.event_type == "task_completed" and bundle_key in event.metadata
            else event
            for event in task.events
        ),
    )


def test_dataset_service_lists_visible_catalog_rows_for_active_workspace(
    dataset_service: DatasetService,
) -> None:
    rows = dataset_service.list_dataset_catalog()

    assert [row.dataset_id for row in rows] == [
        "fluxonium-2025-031",
        "resonator-chip-002",
    ]
    assert rows[0].allowed_actions.select is True
    assert rows[0].allowed_actions.update_profile is True
    assert rows[0].allowed_actions.publish is True
    assert rows[0].allowed_actions.archive is True


def test_dataset_service_rebinds_catalog_visibility_after_workspace_switch(
    dataset_service: DatasetService,
    app_state_repository: InMemoryRewriteAppStateRepository,
) -> None:
    app_state_repository.set_active_workspace_id("ws-modeling")

    rows = dataset_service.list_dataset_catalog()

    assert [row.dataset_id for row in rows] == ["transmon-coupler-014"]
    assert rows[0].allowed_actions.publish is False
    assert rows[0].allowed_actions.archive is False


def test_dataset_service_reads_and_updates_dashboard_profile_surface(
    dataset_service: DatasetService,
) -> None:
    profile = dataset_service.get_dataset_profile("fluxonium-2025-031")

    assert profile.dataset_id == "fluxonium-2025-031"
    assert profile.device_type == "Fluxonium"
    assert profile.capabilities == ("characterization", "simulation_review")

    result = dataset_service.update_dataset_profile(
        "fluxonium-2025-031",
        DatasetProfileUpdate(
            device_type="Fluxonium-X",
            capabilities=("characterization", "comparison"),
            source="manual",
        ),
    )

    assert result.updated_fields == ("device_type", "capabilities", "source")
    assert result.dataset.device_type == "Fluxonium-X"
    assert result.dataset.capabilities == ("characterization", "comparison")
    assert result.dataset.source == "manual"
    assert result.dataset.allowed_actions.update_profile is True


def test_dataset_routes_create_archive_and_delete_lifecycle_contract() -> None:
    created = client.post(
        "/datasets",
        json={
            "name": "Fluxonium Intake 2026",
            "family": "fluxonium",
            "device_type": "Fluxonium",
            "source": "measurement",
        },
    )

    assert created.status_code == 201
    payload = created.json()["data"]
    dataset = payload["dataset"]
    dataset_id = dataset["dataset_id"]
    assert payload["operation"] == "created"
    assert dataset["lifecycle_state"] == "active"
    assert dataset["visibility_scope"] == "private"
    assert dataset["allowed_actions"]["delete"] is True
    assert any(row["dataset_id"] == dataset_id for row in payload["catalog_rows"])

    archived = client.post(f"/datasets/{dataset_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["data"]["dataset"]["lifecycle_state"] == "archived"

    deleted = client.delete(f"/datasets/{dataset_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["dataset"]["lifecycle_state"] == "deleted"
    assert all(row["dataset_id"] != dataset_id for row in deleted.json()["data"]["catalog_rows"])


def test_dataset_ingestion_materializes_design_and_trace_browse_surfaces() -> None:
    created = client.post(
        "/datasets",
        json={
            "name": "Fluxonium Ingestion Demo",
            "family": "fluxonium",
            "device_type": "Fluxonium",
            "source": "measurement",
        },
    ).json()["data"]["dataset"]
    dataset_id = created["dataset_id"]

    measurement_ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "measurement",
            "design_name": "Flux Scan B",
            "provenance_label": "Lab capture #12",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "s11",
                    "representation": "complex",
                    "trace_mode_group": "base",
                    "stage_kind": "raw",
                    "provenance_summary": "Measurement batch #12",
                    "axes": [{"name": "frequency", "unit": "GHz", "length": 401}],
                    "preview_payload": {"kind": "sampled_series", "points": 401},
                }
            ],
        },
    )
    assert measurement_ingestion.status_code == 200
    design_id = measurement_ingestion.json()["data"]["design"]["design_id"]

    layout_ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "layout_simulation",
            "design_name": "Flux Scan B",
            "design_id": design_id,
            "provenance_label": "EM sweep #5",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "s11_layout",
                    "representation": "complex",
                    "trace_mode_group": "base",
                    "stage_kind": "raw",
                    "provenance_summary": "Layout simulation batch #5",
                    "axes": [{"name": "frequency", "unit": "GHz", "length": 401}],
                    "preview_payload": {"kind": "sampled_series", "points": 401},
                }
            ],
        },
    )
    assert layout_ingestion.status_code == 200
    assert layout_ingestion.json()["data"]["design"]["compare_readiness"] == "ready"

    catalog_rows = client.get("/datasets").json()["data"]["rows"]
    assert any(row["dataset_id"] == dataset_id for row in catalog_rows)

    designs = client.get(f"/datasets/{dataset_id}/designs").json()["data"]["rows"]
    assert designs == [
        {
            "design_id": design_id,
            "dataset_id": dataset_id,
            "name": "Flux Scan B",
            "source_coverage": {
                "measurement": 1,
                "layout_simulation": 1,
                "circuit_simulation": 0,
            },
            "compare_readiness": "ready",
            "trace_count": 2,
            "updated_at": "2026-03-17T10:20:00Z",
            "lifecycle_state": "active",
            "redirect_design_id": None,
            "allowed_actions": {
                "rename": True,
                "merge": True,
                "archive": True,
                "delete": True,
                "use_as_target": True,
            },
            "mutation_policy_summary": "Active design scope; usable as a target.",
        }
    ]

    traces = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces").json()["data"]["rows"]
    assert [trace["source_kind"] for trace in traces] == [
        "layout_simulation",
        "measurement",
    ]

    trace_detail = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/traces/{traces[0]['trace_id']}"
    ).json()["data"]
    assert trace_detail["payload_ref"]["store_key"].startswith(
        f"trace_store/datasets/{dataset_id}/designs/{design_id}/"
    )
    assert trace_detail["preview_payload"]["kind"] == "sampled_series"


def test_durable_ingestion_materializes_nd_grid_to_trace_store() -> None:
    import numpy as np
    from app_backend.infrastructure.local_store import LocalZarrTraceStore

    created = client.post(
        "/datasets",
        json={
            "name": "HFSS ND Grid Ingestion",
            "family": "floatingqubit",
            "device_type": "Floating Qubit",
            "source": "layout_simulation",
        },
    ).json()["data"]["dataset"]
    dataset_id = created["dataset_id"]

    ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "layout_simulation",
            "design_name": "FloatingQubitWithXY",
            "provenance_label": "HFSS Y11 sweep",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "Y11",
                    "representation": "imaginary",
                    "trace_mode_group": "base",
                    "stage_kind": "raw",
                    "provenance_summary": "HFSS frequency by L_jun grid",
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
    payload = ingestion.json()["data"]
    design_id = payload["design"]["design_id"]
    trace_id = payload["traces"][0]["trace_id"]
    trace_row = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces").json()["data"][
        "rows"
    ][0]
    assert trace_row["ndim"] == 2
    assert trace_row["shape"] == [3, 2]
    assert trace_row["axes_summary"]["axis_names"] == ["frequency", "L_jun"]
    assert trace_row["available_sweep_axes"] == ["L_jun"]

    detail = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces/{trace_id}").json()[
        "data"
    ]
    assert detail["preview_payload"]["kind"] == "nd_grid"
    assert detail["preview_payload"]["axes"] == [
        {"name": "frequency", "unit": "GHz", "length": 3},
        {"name": "L_jun", "unit": "nH", "length": 2},
    ]
    assert detail["preview_payload"]["shape"] == [3, 2]
    assert detail["preview_payload"]["values_ref"] == "trace_store"
    assert detail["preview_payload"]["points"] == [
        [4.8, -2.0],
        [4.9, 0.2],
        [5.0, 1.2],
    ]
    assert detail["preview_payload"]["preview_sample"] == {
        "source": "trace_store",
        "sample_limit": 800,
        "sample_count": 3,
        "total_point_count": 3,
        "fixed_axes": [
            {"name": "L_jun", "unit": "nH", "index": 0, "value": 8.0},
        ],
    }
    assert detail["payload_ref"]["shape"] == [3, 2]

    trace_store = LocalZarrTraceStore()
    store_ref = {
        key: value for key, value in detail["payload_ref"].items() if key != "payload_role"
    }
    values = trace_store.read_trace_slice(store_ref, selection=())
    np.testing.assert_allclose(values.real, np.zeros((3, 2)))
    np.testing.assert_allclose(
        values.imag,
        np.array([[-2.0, -1.0], [0.2, 0.5], [1.2, 1.6]]),
    )
    np.testing.assert_allclose(
        trace_store.read_axis_slice(store_ref, axis_name="frequency"),
        np.array([4.8, 4.9, 5.0]),
    )
    np.testing.assert_allclose(
        trace_store.read_axis_slice(store_ref, axis_name="L_jun"),
        np.array([8.0, 9.0]),
    )


def test_durable_hfss_nd_imports_do_not_overwrite_same_design_parameter_collision() -> None:
    created = client.post(
        "/datasets",
        json={
            "name": "HFSS Multi File Identity",
            "family": "floatingqubit",
            "device_type": "Floating Qubit",
            "source": "layout_simulation",
        },
    ).json()["data"]["dataset"]
    dataset_id = created["dataset_id"]

    first = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json=_hfss_nd_ingestion_payload(
            design_name="FloatingQubitWithXY",
            provenance_label="HFSS XY.csv",
            provenance_summary="HFSS XY branch",
            values=[[-2.0, -1.0], [0.2, 0.5], [1.2, 1.6]],
        ),
    )
    assert first.status_code == 200
    design_id = first.json()["data"]["design"]["design_id"]

    second = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json=_hfss_nd_ingestion_payload(
            design_name="FloatingQubitWithXY",
            design_id=design_id,
            provenance_label="HFSS Readout.csv",
            provenance_summary="HFSS readout branch",
            values=[[-3.0, -2.0], [0.4, 0.7], [1.4, 1.8]],
        ),
    )

    assert second.status_code == 200
    trace_ids = {
        first.json()["data"]["traces"][0]["trace_id"],
        second.json()["data"]["traces"][0]["trace_id"],
    }
    assert len(trace_ids) == 2
    assert any("hfss-xy-csv" in trace_id for trace_id in trace_ids)
    assert any("hfss-readout-csv" in trace_id for trace_id in trace_ids)

    rows = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces").json()["data"]["rows"]
    assert len(rows) == 2
    assert {row["trace_id"] for row in rows} == trace_ids
    assert {row["parameter"] for row in rows} == {"Y11"}
    assert all(row["shape"] == [3, 2] for row in rows)
    assert all(row["available_sweep_axes"] == ["L_jun"] for row in rows)
    provenance_by_trace = {row["trace_id"]: row["provenance_summary"] for row in rows}
    assert any("HFSS XY.csv" in summary for summary in provenance_by_trace.values())
    assert any("HFSS Readout.csv" in summary for summary in provenance_by_trace.values())


def _hfss_nd_ingestion_payload(
    *,
    design_name: str,
    provenance_label: str,
    provenance_summary: str,
    values: list[list[float]],
    design_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "kind": "layout_simulation",
        "design_name": design_name,
        "provenance_label": provenance_label,
        "traces": [
            {
                "family": "y_matrix",
                "parameter": "Y11",
                "representation": "imaginary",
                "trace_mode_group": "base",
                "stage_kind": "raw",
                "provenance_summary": provenance_summary,
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
                    "values": values,
                },
            }
        ],
    }
    if design_id is not None:
        payload["design_id"] = design_id
    return payload


def test_rewrite_ingestion_derives_nd_grid_structure_summary(
    catalog_repository: InMemoryRewriteCatalogRepository,
) -> None:
    result = catalog_repository.ingest_raw_data(
        "local-dataset-001",
        RawDataIngestionDraft(
            kind="layout_simulation",
            design_name="HFSS Rewrite ND Grid",
            design_id=None,
            provenance_label="HFSS sweep",
            traces=(
                RawDataTraceDraft(
                    trace_id=None,
                    family="y_matrix",
                    parameter="Y11",
                    representation="imaginary",
                    trace_mode_group="base",
                    stage_kind="raw",
                    provenance_summary="HFSS rewrite grid",
                    axes=(
                        TraceAxis(name="frequency", unit="GHz", length=3),
                        TraceAxis(name="L_jun", unit="nH", length=2),
                    ),
                    preview_payload={
                        "kind": "nd_grid",
                        "axes": [
                            {"name": "frequency", "unit": "GHz", "values": [4.8, 4.9, 5.0]},
                            {"name": "L_jun", "unit": "nH", "values": [8.0, 9.0]},
                        ],
                        "values": [[-2.0, -1.0], [0.2, 0.5], [1.2, 1.6]],
                    },
                ),
            ),
        ),
    )

    assert result is not None
    trace = result.traces[0]
    assert trace.ndim == 2
    assert trace.shape == (3, 2)
    assert trace.axes_summary.axis_names == ("frequency", "L_jun")
    assert trace.available_sweep_axes == ("L_jun",)
    edit_detail = catalog_repository.get_trace_edit_detail(
        "local-dataset-001",
        result.design.design_id,
        trace.trace_id,
    )
    assert edit_detail is not None
    assert edit_detail.editable_numeric_payload["values_ref"] == "trace_store"


def test_dataset_design_creation_materializes_empty_browse_row() -> None:
    created = client.post(
        "/datasets",
        json={
            "name": "Fluxonium Explicit Design Demo",
            "family": "fluxonium",
            "device_type": "Fluxonium",
            "source": "measurement",
        },
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["dataset"]["dataset_id"]

    design_create = client.post(
        f"/datasets/{dataset_id}/designs",
        json={"name": "Simulation Save Target"},
    )

    assert design_create.status_code == 201
    payload = design_create.json()["data"]
    assert payload["operation"] == "created"
    assert payload["design"] == {
        "design_id": "design_simulation-save-target",
        "dataset_id": dataset_id,
        "name": "Simulation Save Target",
        "source_coverage": {
            "measurement": 0,
            "layout_simulation": 0,
            "circuit_simulation": 0,
        },
        "compare_readiness": "blocked",
        "trace_count": 0,
        "updated_at": payload["design"]["updated_at"],
        "lifecycle_state": "active",
        "redirect_design_id": None,
        "allowed_actions": {
            "rename": True,
            "merge": True,
            "archive": True,
            "delete": True,
            "use_as_target": True,
        },
        "mutation_policy_summary": "Active design scope; usable as a target.",
    }
    assert payload["design_rows"] == [payload["design"]]

    browse = client.get(f"/datasets/{dataset_id}/designs")
    assert browse.status_code == 200
    assert browse.json()["data"]["rows"] == [payload["design"]]


def test_dataset_design_creation_rejects_duplicate_name_conflicts() -> None:
    created = client.post(
        "/datasets",
        json={
            "name": "Fluxonium Design Conflict Demo",
            "family": "fluxonium",
            "device_type": "Fluxonium",
            "source": "measurement",
        },
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["dataset"]["dataset_id"]

    first = client.post(
        f"/datasets/{dataset_id}/designs",
        json={"name": "Conflict Target"},
    )
    assert first.status_code == 201

    second = client.post(
        f"/datasets/{dataset_id}/designs",
        json={"name": "Conflict Target"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "design_scope_name_conflict"


def test_design_scope_rename_preserves_design_id() -> None:
    created = client.post(
        "/datasets",
        json={
            "name": "Design Rename Demo",
            "family": "fluxonium",
            "device_type": "Fluxonium",
            "source": "measurement",
        },
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["dataset"]["dataset_id"]
    design = client.post(
        f"/datasets/{dataset_id}/designs",
        json={"name": "Original Scope"},
    ).json()["data"]["design"]

    renamed = client.patch(
        f"/datasets/{dataset_id}/designs/{design['design_id']}",
        json={"name": "Renamed Scope"},
    )

    assert renamed.status_code == 200
    renamed_design = renamed.json()["data"]["design"]
    assert renamed_design["design_id"] == design["design_id"]
    assert renamed_design["name"] == "Renamed Scope"
    assert renamed_design["lifecycle_state"] == "active"


def test_archived_design_scope_is_hidden_from_default_browse_and_blocked_as_target() -> None:
    dataset_id, design_id, _ = _create_ingested_trace_design()

    archived = client.post(f"/datasets/{dataset_id}/designs/{design_id}/archive")

    assert archived.status_code == 200
    assert archived.json()["data"]["design"]["lifecycle_state"] == "archived"
    assert archived.json()["data"]["design"]["allowed_actions"]["use_as_target"] is False
    assert client.get(f"/datasets/{dataset_id}/designs").json()["data"]["rows"] == []
    rows_with_archived = client.get(
        f"/datasets/{dataset_id}/designs",
        params={"include_archived": True},
    ).json()["data"]["rows"]
    assert [row["design_id"] for row in rows_with_archived] == [design_id]

    ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "measurement",
            "design_name": "Trace CRUD Target",
            "design_id": design_id,
            "provenance_label": "blocked-target",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "Y11_blocked",
                    "representation": "complex",
                    "trace_mode_group": "base",
                    "stage_kind": "raw",
                    "provenance_summary": "Blocked target trace",
                    "axes": [{"name": "frequency", "unit": "GHz", "length": 2}],
                    "preview_payload": {
                        "kind": "sampled_series",
                        "points": [[5.0, 0.1], [5.2, 0.2]],
                    },
                }
            ],
        },
    )
    assert ingestion.status_code == 409
    assert ingestion.json()["error"]["code"] == "target_design_scope_invalid"


def test_create_new_ingestion_does_not_hidden_match_existing_design_name() -> None:
    dataset_id, _, _ = _create_ingested_trace_design()

    duplicate_name_ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "measurement",
            "design_name": "Trace CRUD Target",
            "provenance_label": "duplicate-free-text",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "Y11_duplicate",
                    "representation": "complex",
                    "trace_mode_group": "base",
                    "stage_kind": "raw",
                    "provenance_summary": "Duplicate free-text target trace",
                    "axes": [{"name": "frequency", "unit": "GHz", "length": 2}],
                    "preview_payload": {
                        "kind": "sampled_series",
                        "points": [[5.0, 0.1], [5.2, 0.2]],
                    },
                }
            ],
        },
    )

    assert duplicate_name_ingestion.status_code == 409
    assert duplicate_name_ingestion.json()["error"]["code"] == "design_scope_name_conflict"


def test_merge_reparents_trace_metadata_and_redirects_source_scope() -> None:
    created = client.post(
        "/datasets",
        json={
            "name": "Design Merge Demo",
            "family": "fluxonium",
            "device_type": "Fluxonium",
            "source": "measurement",
        },
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["dataset"]["dataset_id"]
    target = client.post(
        f"/datasets/{dataset_id}/designs",
        json={"name": "Target Scope"},
    ).json()["data"]["design"]
    source = client.post(
        f"/datasets/{dataset_id}/designs",
        json={"name": "Source Scope"},
    ).json()["data"]["design"]

    for design, parameter in ((target, "Y11_target"), (source, "Y11_source")):
        ingestion = client.post(
            f"/datasets/{dataset_id}/ingestions",
            json={
                "kind": "measurement",
                "design_name": design["name"],
                "design_id": design["design_id"],
                "provenance_label": parameter,
                "traces": [
                    {
                        "family": "y_matrix",
                        "parameter": parameter,
                        "representation": "complex",
                        "trace_mode_group": "base",
                        "stage_kind": "raw",
                        "provenance_summary": parameter,
                        "axes": [{"name": "frequency", "unit": "GHz", "length": 2}],
                        "preview_payload": {
                            "kind": "sampled_series",
                            "points": [[5.0, 0.1], [5.2, 0.2]],
                        },
                    }
                ],
            },
        )
        assert ingestion.status_code == 200

    merged = client.post(
        f"/datasets/{dataset_id}/designs/{source['design_id']}/merge",
        json={"target_design_id": target["design_id"]},
    )

    assert merged.status_code == 200
    payload = merged.json()["data"]
    assert payload["source_design"]["lifecycle_state"] == "archived"
    assert payload["source_design"]["redirect_design_id"] == target["design_id"]
    assert payload["target_design"]["trace_count"] == 2
    assert payload["reparented_counts"]["raw_traces"] == 1
    assert payload["reparented_counts"]["trace_capabilities"] > 0
    assert payload["reparented_counts"]["published_simulation_traces"] == 0
    target_traces = client.get(
        f"/datasets/{dataset_id}/designs/{target['design_id']}/traces"
    ).json()["data"]["rows"]
    assert {row["parameter"] for row in target_traces} == {"Y11_target", "Y11_source"}

    stale_source = client.get(f"/datasets/{dataset_id}/designs/{source['design_id']}/traces")
    assert stale_source.status_code == 409
    assert stale_source.json()["error"]["code"] == "design_scope_redirected"
    assert stale_source.json()["error"]["details"]["redirect_design_id"] == target["design_id"]


def test_design_scope_lifecycle_integrates_ingestion_merge_and_characterization_scope() -> None:
    created = client.post(
        "/datasets",
        json={
            "name": "Integrated DesignScope Lifecycle",
            "family": "floatingqubit",
            "device_type": "Floating Qubit",
            "source": "layout_simulation",
        },
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["dataset"]["dataset_id"]
    target = client.post(
        f"/datasets/{dataset_id}/designs",
        json={"name": "Target Lifecycle Scope"},
    ).json()["data"]["design"]
    source = client.post(
        f"/datasets/{dataset_id}/designs",
        json={"name": "Source Lifecycle Scope"},
    ).json()["data"]["design"]

    target_ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "measurement",
            "design_name": target["name"],
            "design_id": target["design_id"],
            "provenance_label": "target-measurement",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "Y11_target",
                    "representation": "complex",
                    "trace_mode_group": "base",
                    "stage_kind": "raw",
                    "provenance_summary": "Target measurement branch",
                    "axes": [{"name": "frequency", "unit": "GHz", "length": 2}],
                    "preview_payload": {
                        "kind": "sampled_series",
                        "points": [[5.0, 0.1], [5.2, 0.2]],
                    },
                }
            ],
        },
    )
    assert target_ingestion.status_code == 200
    assert target_ingestion.json()["data"]["design"]["design_id"] == target["design_id"]

    source_ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "layout_simulation",
            "design_name": source["name"],
            "design_id": source["design_id"],
            "provenance_label": "source-hfss-sweep",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "Y11",
                    "representation": "imaginary",
                    "trace_mode_group": "base",
                    "stage_kind": "raw",
                    "provenance_summary": "Source HFSS L_jun sweep",
                    "axes": [
                        {"name": "frequency", "unit": "GHz", "length": 5},
                        {"name": "L_jun", "unit": "nH", "length": 2},
                    ],
                    "preview_payload": {
                        "kind": "nd_grid",
                        "axes": [
                            {
                                "name": "frequency",
                                "unit": "GHz",
                                "values": [4.8, 4.9, 5.0, 5.1, 5.2],
                            },
                            {"name": "L_jun", "unit": "nH", "values": [8.0, 9.0]},
                        ],
                        "values": [
                            [-1.0, -0.5],
                            [0.2, 0.6],
                            [1.2, 1.6],
                            [0.2, 0.4],
                            [-0.5, -0.2],
                        ],
                    },
                }
            ],
        },
    )
    assert source_ingestion.status_code == 200
    source_trace_id = source_ingestion.json()["data"]["traces"][0]["trace_id"]
    assert source_ingestion.json()["data"]["design"]["design_id"] == source["design_id"]

    active_designs = client.get(f"/datasets/{dataset_id}/designs")
    assert active_designs.status_code == 200
    assert {row["design_id"] for row in active_designs.json()["data"]["rows"]} == {
        source["design_id"],
        target["design_id"],
    }

    source_registry = client.get(
        f"/datasets/{dataset_id}/designs/{source['design_id']}/characterization-analysis-registry",
        params={"selected_trace_ids": source_trace_id},
    )
    assert source_registry.status_code == 200
    source_registry_rows = {
        row["analysis_id"]: row for row in source_registry.json()["data"]["rows"]
    }
    assert source_registry_rows["admittance_extraction"]["availability_state"] == "recommended"
    assert source_registry_rows["admittance_extraction"]["trace_compatibility"]["summary"] == (
        "1 selected trace is eligible for admittance resonance extraction."
    )

    merged = client.post(
        f"/datasets/{dataset_id}/designs/{source['design_id']}/merge",
        json={"target_design_id": target["design_id"]},
    )
    assert merged.status_code == 200
    merge_payload = merged.json()["data"]
    assert merge_payload["source_design"]["lifecycle_state"] == "archived"
    assert merge_payload["source_design"]["redirect_design_id"] == target["design_id"]
    assert merge_payload["target_design"]["trace_count"] == 2
    assert merge_payload["reparented_counts"]["raw_traces"] == 1
    assert merge_payload["reparented_counts"]["trace_capabilities"] > 0
    assert merge_payload["reparented_counts"]["characterization_registry_rows"] == 0

    active_after_merge = client.get(f"/datasets/{dataset_id}/designs")
    assert active_after_merge.status_code == 200
    assert [row["design_id"] for row in active_after_merge.json()["data"]["rows"]] == [
        target["design_id"]
    ]
    all_designs = client.get(
        f"/datasets/{dataset_id}/designs",
        params={"include_archived": True},
    )
    assert all_designs.status_code == 200
    designs_by_id = {row["design_id"]: row for row in all_designs.json()["data"]["rows"]}
    assert designs_by_id[source["design_id"]]["redirect_design_id"] == target["design_id"]

    target_traces = client.get(f"/datasets/{dataset_id}/designs/{target['design_id']}/traces")
    assert target_traces.status_code == 200
    assert {row["trace_id"] for row in target_traces.json()["data"]["rows"]} == {
        target_ingestion.json()["data"]["traces"][0]["trace_id"],
        source_trace_id,
    }
    reparented_detail = client.get(
        f"/datasets/{dataset_id}/designs/{target['design_id']}/traces/{source_trace_id}"
    )
    assert reparented_detail.status_code == 200
    assert reparented_detail.json()["data"]["design_id"] == target["design_id"]
    assert reparented_detail.json()["data"]["available_sweep_axes"] == ["L_jun"]

    stale_trace_access = client.get(f"/datasets/{dataset_id}/designs/{source['design_id']}/traces")
    assert stale_trace_access.status_code == 409
    assert stale_trace_access.json()["error"]["code"] == "design_scope_redirected"
    assert (
        stale_trace_access.json()["error"]["details"]["redirect_design_id"] == target["design_id"]
    )
    stale_ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "layout_simulation",
            "design_name": source["name"],
            "design_id": source["design_id"],
            "provenance_label": "stale-source-target",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "Y11_stale",
                    "representation": "imaginary",
                    "trace_mode_group": "base",
                    "stage_kind": "raw",
                    "provenance_summary": "Rejected stale target trace",
                    "axes": [{"name": "frequency", "unit": "GHz", "length": 2}],
                    "preview_payload": {
                        "kind": "sampled_series",
                        "points": [[5.0, 0.1], [5.2, 0.2]],
                    },
                }
            ],
        },
    )
    assert stale_ingestion.status_code == 409
    assert stale_ingestion.json()["error"]["code"] == "design_scope_redirected"
    assert stale_ingestion.json()["error"]["details"]["redirect_design_id"] == target["design_id"]

    stale_registry = client.get(
        f"/datasets/{dataset_id}/designs/{source['design_id']}/characterization-analysis-registry",
        params={"selected_trace_ids": source_trace_id},
    )
    assert stale_registry.status_code == 409
    assert stale_registry.json()["error"]["code"] == "design_scope_redirected"
    stale_result = client.get(
        f"/datasets/{dataset_id}/designs/{source['design_id']}/"
        "characterization-results/char-fit-flux-a-01"
    )
    assert stale_result.status_code == 409
    assert stale_result.json()["error"]["code"] == "design_scope_redirected"

    target_registry = client.get(
        f"/datasets/{dataset_id}/designs/{target['design_id']}/characterization-analysis-registry",
        params={"selected_trace_ids": source_trace_id},
    )
    assert target_registry.status_code == 200
    target_registry_rows = {
        row["analysis_id"]: row for row in target_registry.json()["data"]["rows"]
    }
    assert target_registry_rows["admittance_extraction"]["availability_state"] == "recommended"

    wrong_scope_detail = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_b/"
        "characterization-results/char-fit-flux-a-01"
    )
    assert wrong_scope_detail.status_code == 404
    assert wrong_scope_detail.json()["error"]["code"] == "run_not_found"


def test_dataset_service_exposes_tagged_metrics_and_summary_first_browse_contract(
    dataset_service: DatasetService,
) -> None:
    metrics = dataset_service.list_tagged_core_metrics("fluxonium-2025-031")
    designs = dataset_service.list_designs(
        "fluxonium-2025-031",
        DesignBrowseQuery(search="Flux Scan A"),
    )
    trace_rows = dataset_service.list_trace_metadata(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        TraceBrowseQuery(family="y_matrix", source_kind="measurement"),
    )
    trace_detail = dataset_service.get_trace_detail(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        "trace_flux_a_measurement",
    )

    assert [metric.metric_id for metric in metrics] == [
        "metric-fluxonium-lowest-observed-frequency-ghz",
        "metric-fluxonium-residual-rms-max",
    ]
    assert [design.design_id for design in designs] == ["design_flux_scan_a"]
    assert designs[0].compare_readiness == "ready"

    assert [row.trace_id for row in trace_rows] == [
        "trace_flux_a_measurement",
        "trace_flux_a_phase",
    ]
    assert not hasattr(trace_rows[0], "preview_payload")
    assert not hasattr(trace_rows[0], "payload_ref")
    assert trace_rows[0].ndim == 1
    assert trace_rows[0].shape == (trace_detail.axes[0].length,)
    assert trace_rows[0].axes_summary.axis_names == ("frequency",)
    assert trace_rows[0].axis_signature == trace_rows[1].axis_signature
    assert trace_rows[0].collection_projection is not None
    collection_key = trace_rows[0].collection_projection.collection_key
    layout_collection_key = dataset_service.get_trace_detail(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        "trace_flux_a_layout",
    ).collection_projection.collection_key
    phase_collection_key = dataset_service.get_trace_detail(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        "trace_flux_a_phase",
    ).collection_projection.collection_key
    assert collection_key == layout_collection_key
    assert phase_collection_key != collection_key
    assert trace_rows[0].allowed_actions.edit is False
    assert trace_rows[0].allowed_actions.delete is False
    assert "source workflow" in trace_rows[0].mutation_policy_summary
    filtered_rows = dataset_service.list_trace_metadata(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        TraceBrowseQuery(axis_name="frequency", collection_key=collection_key),
    )
    assert [row.trace_id for row in filtered_rows] == [
        "trace_flux_a_measurement",
        "trace_flux_a_layout",
    ]

    assert trace_detail.trace_id == "trace_flux_a_measurement"
    assert trace_detail.ndim == 1
    assert trace_detail.axes_summary.axis_names == ("frequency",)
    assert trace_detail.collection_projection is not None
    assert trace_detail.collection_projection.collection_key == collection_key
    assert trace_detail.preview_payload["kind"] == "series"
    assert len(trace_detail.preview_payload["points"]) == trace_detail.axes[0].length
    assert trace_detail.payload_ref is not None
    assert trace_detail.payload_ref.store_key.endswith("batch_4.zarr")
    assert trace_detail.result_handles[0].handle_id == "result:fluxonium-2025-031:fit-summary"


def test_local_seed_single_trace_preview_uses_full_series_for_one_dimensional_preview(
    catalog_repository: InMemoryRewriteCatalogRepository,
) -> None:
    trace_detail = catalog_repository.get_trace_detail(
        "local-dataset-001",
        "design_local_flux_playground",
        "trace_local_flux_preview",
    )

    assert trace_detail is not None
    assert trace_detail.preview_payload["kind"] == "series"
    assert len(trace_detail.preview_payload["points"]) == trace_detail.axes[0].length


def test_ingested_trace_can_be_updated_without_changing_identity() -> None:
    dataset_id, design_id, trace_ids = _create_ingested_trace_design()
    trace_id = trace_ids[0]

    response = client.patch(
        f"/datasets/{dataset_id}/designs/{design_id}/traces/{trace_id}",
        json={
            "parameter": "Y11_edited",
            "representation": "real",
            "provenance_summary": "Edited measurement trace",
            "numeric_payload": {
                "kind": "series_table",
                "columns": [
                    {"key": "frequency", "label": "Frequency", "unit": "GHz", "role": "axis"},
                    {"key": "value", "label": "Value", "unit": None, "role": "value"},
                ],
                "rows": [
                    {"frequency": 5.0, "value": 0.21},
                    {"frequency": 5.1, "value": 0.25},
                    {"frequency": 5.2, "value": 0.27},
                ],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["operation"] == "updated"
    assert payload["trace"]["trace_id"] == trace_id
    assert payload["trace"]["parameter"] == "Y11_edited"
    assert payload["trace"]["representation"] == "real"
    assert payload["trace"]["provenance_summary"] == "Edited measurement trace"
    assert payload["trace"]["allowed_actions"] == {"edit": True, "delete": True}
    assert payload["trace"]["mutation_policy_summary"] == "Manually ingested raw trace."
    updated_capabilities = _capabilities_by_analysis(payload["trace"]["analysis_capabilities"])
    assert updated_capabilities["admittance_extraction"]["status"] == "eligible"
    assert (
        updated_capabilities["admittance_extraction"]["summary"]
        == "Eligible as admittance resonance source."
    )
    assert updated_capabilities["junction_parameter_identification"]["status"] == ("ineligible")
    assert (
        updated_capabilities["junction_parameter_identification"]["summary"]
        == "Requires complex representation."
    )

    preview = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces/{trace_id}")
    assert preview.status_code == 200
    preview_payload = preview.json()["data"]
    assert preview_payload["axes"] == [{"name": "frequency", "unit": "GHz", "length": 3}]
    assert preview_payload["preview_payload"]["points"] == [
        [5.0, 0.21],
        [5.1, 0.25],
        [5.2, 0.27],
    ]

    rows = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces").json()["data"]["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["trace_id"] == trace_id
    assert row["dataset_id"] == dataset_id
    assert row["design_id"] == design_id
    assert row["family"] == "y_matrix"
    assert row["parameter"] == "Y11_edited"
    assert row["representation"] == "real"
    assert row["trace_mode_group"] == "base"
    assert row["source_kind"] == "measurement"
    assert row["stage_kind"] == "raw"
    assert row["provenance_summary"] == "Edited measurement trace"
    assert row["allowed_actions"] == {"edit": True, "delete": True}
    assert row["mutation_policy_summary"] == "Manually ingested raw trace."
    row_capabilities = _capabilities_by_analysis(row["analysis_capabilities"])
    assert row_capabilities["admittance_extraction"]["status"] == "eligible"
    assert row_capabilities["sideband_comparison"]["status"] == "ineligible"
    assert row_capabilities["screening_summary"]["status"] == "ineligible"


def test_trace_list_rows_materialize_backend_mutation_gating() -> None:
    dataset_id, design_id, _ = _create_ingested_trace_design()

    response = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces")

    assert response.status_code == 200
    row = response.json()["data"]["rows"][0]
    assert row["allowed_actions"] == {"edit": True, "delete": True}
    assert row["mutation_policy_summary"] == "Manually ingested raw trace."


def test_trace_edit_path_returns_dedicated_edit_payload() -> None:
    dataset_id, design_id, trace_ids = _create_ingested_trace_design()
    trace_id = trace_ids[0]

    response = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces/{trace_id}/edit")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["trace_id"] == trace_id
    assert payload["dataset_id"] == dataset_id
    assert payload["design_id"] == design_id
    assert payload["editable_metadata"] == {
        "parameter": "Y11_1",
        "representation": "complex",
        "provenance_summary": "Measurement trace 1",
    }
    assert payload["immutable_summary"] == {
        "family": "y_matrix",
        "trace_mode_group": "base",
        "source_kind": "measurement",
        "stage_kind": "raw",
    }
    assert payload["editable_numeric_payload"]["kind"] == "series_table"
    assert payload["allowed_actions"] == {"edit": True, "delete": True}
    assert payload["mutation_policy_summary"] == "Manually ingested raw trace."
    capability_map = _capabilities_by_analysis(payload["analysis_capabilities"])
    assert capability_map["admittance_extraction"]["status"] == "eligible"
    assert capability_map["sideband_comparison"]["status"] == "ineligible"


def test_trace_update_rejects_preview_payload_as_edit_authority() -> None:
    dataset_id, design_id, trace_ids = _create_ingested_trace_design()
    trace_id = trace_ids[0]

    response = client.patch(
        f"/datasets/{dataset_id}/designs/{design_id}/traces/{trace_id}",
        json={"preview_payload": {"kind": "sampled_series", "points": [[1.0, 0.1]]}},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "request_validation_failed"


def test_seeded_trace_update_and_delete_are_rejected_when_trace_is_read_only() -> None:
    update = client.patch(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/traces/trace_flux_a_measurement",
        json={"parameter": "forbidden-edit"},
    )
    assert update.status_code == 409
    assert update.json()["error"]["code"] == "trace_update_denied"

    delete = client.delete(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/traces/trace_flux_a_measurement"
    )
    assert delete.status_code == 409
    assert delete.json()["error"]["code"] == "trace_delete_denied"


def test_ingested_trace_can_be_deleted_from_a_design() -> None:
    dataset_id, design_id, trace_ids = _create_ingested_trace_design()
    trace_id = trace_ids[0]

    response = client.delete(f"/datasets/{dataset_id}/designs/{design_id}/traces/{trace_id}")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload == {
        "operation": "deleted",
        "deleted_trace_id": trace_id,
        "deleted_count": 1,
        "design": {
            "design_id": design_id,
            "dataset_id": dataset_id,
            "name": "Trace CRUD Target",
            "source_coverage": {
                "measurement": 0,
                "layout_simulation": 0,
                "circuit_simulation": 0,
            },
            "compare_readiness": "blocked",
            "trace_count": 0,
            "updated_at": payload["design"]["updated_at"],
            "lifecycle_state": "active",
            "redirect_design_id": None,
            "allowed_actions": {
                "rename": True,
                "merge": True,
                "archive": True,
                "delete": True,
                "use_as_target": True,
            },
            "mutation_policy_summary": "Active design scope; usable as a target.",
        },
    }
    rows = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces").json()["data"]["rows"]
    assert rows == []
    detail = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces/{trace_id}")
    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "trace_not_found"


def test_ingested_traces_support_batch_delete() -> None:
    dataset_id, design_id, trace_ids = _create_ingested_trace_design(trace_count=2)

    response = client.post(
        f"/datasets/{dataset_id}/designs/{design_id}/traces/batch-delete",
        json={"trace_ids": trace_ids},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["operation"] == "deleted"
    assert payload["deleted_trace_ids"] == trace_ids
    assert payload["deleted_count"] == 2
    assert payload["design"]["design_id"] == design_id
    assert payload["design"]["trace_count"] == 0
    rows = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces").json()["data"]["rows"]
    assert rows == []


def test_dataset_service_exposes_characterization_result_summary_and_detail_surfaces(
    dataset_service: DatasetService,
) -> None:
    result_rows = dataset_service.list_characterization_results(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        CharacterizationResultBrowseQuery(status="completed"),
    )
    result_detail = dataset_service.get_characterization_result(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        "char-fit-flux-a-01",
    )
    artifact_payload = dataset_service.get_characterization_artifact_payload(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        "char-fit-flux-a-01",
        "char-fit-flux-a-01:mode-frequency-grid",
        CharacterizationArtifactPayloadQuery(preset_id="mode_by_input_table"),
    )

    assert [row.result_id for row in result_rows] == ["char-fit-flux-a-01"]
    assert result_rows[0].dataset_id == "fluxonium-2025-031"
    assert result_rows[0].design_id == "design_flux_scan_a"
    assert result_rows[0].status == "completed"
    assert result_rows[0].provenance_summary == "Measurement batch #4 + layout batch #2"

    assert result_detail.result_id == "char-fit-flux-a-01"
    assert result_detail.analysis_id == "admittance_extraction"
    assert result_detail.input_trace_ids == (
        "trace_flux_a_measurement",
        "trace_flux_a_layout",
    )
    assert result_detail.payload["contract_version"] == "admittance_member_phase1_v1"
    assert result_detail.artifact_refs[0].artifact_id == "char-fit-flux-a-01:mode-frequency-grid"
    assert artifact_payload.payload["compare_groups"][0]["cells"][0] == [5.612, 5.587, None]


def test_dataset_service_exposes_characterization_analysis_registry_and_run_history_surfaces(
    dataset_service: DatasetService,
) -> None:
    registry_rows = dataset_service.list_characterization_analysis_registry(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        CharacterizationAnalysisRegistryQuery(
            selected_trace_ids=(
                "trace_flux_a_measurement",
                "trace_flux_a_layout",
            ),
        ),
    )
    run_rows = dataset_service.list_characterization_run_history(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        CharacterizationRunHistoryQuery(
            analysis_id="admittance_extraction",
        ),
    )

    assert [row.analysis_id for row in registry_rows] == [
        "admittance_extraction",
        "sideband_comparison",
        "junction_parameter_identification",
    ]
    assert registry_rows[0].availability_state == "unavailable"
    assert registry_rows[0].required_config_fields == (
        "fit_window",
        "residual_tolerance",
    )
    assert registry_rows[0].trace_compatibility.selected_trace_count == 2
    assert registry_rows[0].trace_compatibility.matched_trace_count == 0
    assert registry_rows[0].trace_compatibility.summary == (
        "Selected trace compatibility could not be re-evaluated because this design "
        "does not yet carry durable trace capability markings."
    )
    assert registry_rows[1].availability_state == "unavailable"
    assert registry_rows[1].trace_compatibility.summary == (
        "Selected trace compatibility could not be re-evaluated because this design "
        "does not yet carry durable trace capability markings."
    )

    assert [row.run_id for row in run_rows] == ["run-flux-a-003"]
    assert run_rows[0].dataset_id == "fluxonium-2025-031"
    assert run_rows[0].design_id == "design_flux_scan_a"
    assert run_rows[0].analysis_id == "admittance_extraction"
    assert run_rows[0].result_id == "char-fit-flux-a-01"


def test_dataset_service_applies_identify_tagging_and_updates_dashboard_metrics_summary(
    dataset_service: DatasetService,
) -> None:
    detail_before = dataset_service.get_characterization_result(
        "resonator-chip-002",
        "design_resonator_temp",
        "char-resonator-temp-qi",
    )

    assert detail_before.identify_surface.applied_tags == ()
    assert detail_before.identify_surface.source_parameters[0].current_designated_metric is None

    result = dataset_service.apply_characterization_tagging(
        "resonator-chip-002",
        "design_resonator_temp",
        "char-resonator-temp-qi",
        CharacterizationTaggingRequest(
            artifact_id="artifact-resonator-temp-table",
            source_parameter="Qi_low_temp",
            designated_metric="qi_low_temp",
        ),
    )

    detail_after = dataset_service.get_characterization_result(
        "resonator-chip-002",
        "design_resonator_temp",
        "char-resonator-temp-qi",
    )
    metrics = dataset_service.list_tagged_core_metrics("resonator-chip-002")

    assert result.tagging_status == "applied"
    assert result.tagged_metric.metric_id == "metric-resonator-chip-002-qi-low-temp"
    assert detail_after.identify_surface.applied_tags[0].designated_metric == "qi_low_temp"
    assert (
        detail_after.identify_surface.source_parameters[0].current_designated_metric
        == "qi_low_temp"
    )
    assert [metric.metric_id for metric in metrics] == [
        "metric-resonator-chip-002-qi-low-temp",
    ]
    assert metrics[0].label == "Low Temperature Qi"


def test_dataset_service_rejects_invisible_dataset_outside_active_workspace(
    dataset_service: DatasetService,
) -> None:
    with pytest.raises(ServiceError) as exc_info:
        dataset_service.get_dataset_profile("transmon-coupler-014")

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "dataset_not_visible_in_workspace"
    assert exc_info.value.category == "permission_denied"


def test_list_circuit_definitions_returns_seeded_summaries() -> None:
    response = client.get("/circuit-definitions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert [row["definition_id"] for row in payload["data"]["rows"]] == [
        FLOATING_QUBIT_WITH_XY_LINE_DEFINITION_ID,
        FLUXONIUM_READOUT_CHAIN_DEFINITION_ID,
        COUPLER_DETUNING_DEMO_DEFINITION_ID,
    ]
    assert payload["data"]["rows"][0]["name"] == "FloatingQubitWithXYLine"
    assert payload["data"]["rows"][0]["visibility_scope"] == "private"
    assert payload["data"]["rows"][0]["allowed_actions"] == {
        "update": True,
        "delete": True,
        "publish": True,
        "clone": True,
    }
    assert payload["meta"]["limit"] == 20
    assert payload["meta"]["has_more"] is False


def test_list_circuit_definitions_supports_search_and_sort() -> None:
    response = client.get(
        "/circuit-definitions?search_query=Fluxonium&sort_by=name&sort_order=asc&limit=1"
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["data"]["rows"]] == ["FluxoniumReadoutChain"]
    assert payload["data"]["total_count"] == 1
    assert payload["meta"]["filter_echo"]["search_query"] == "Fluxonium"


def test_get_circuit_definition_returns_detail_payload() -> None:
    response = client.get(f"/circuit-definitions/{FLOATING_QUBIT_WITH_XY_LINE_DEFINITION_ID}")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["definition_id"] == FLOATING_QUBIT_WITH_XY_LINE_DEFINITION_ID
    assert payload["workspace_id"] == "ws-device-lab"
    assert payload["visibility_scope"] == "private"
    assert payload["allowed_actions"] == {
        "update": True,
        "delete": True,
        "publish": True,
        "clone": True,
    }
    assert payload["preview_artifacts"] == [
        "expanded-netlist.json",
        "validation-summary.json",
        "schemdraw-preview.svg",
    ]
    assert payload["validation_summary"] == {
        "status": "valid",
        "notice_count": 3,
        "warning_count": 0,
        "blocking_notice_count": 0,
    }
    assert payload["validation_notices"][0]["code"] == "definition_parsed"
    assert "expanded" in payload["normalized_output"]


def test_create_update_publish_clone_and_delete_circuit_definition_flow() -> None:
    created = client.post(
        "/circuit-definitions",
        json={
            "name": "ReadoutPreview",
            "source_text": _valid_circuit_source("ReadoutPreview"),
        },
    )

    assert created.status_code == 201
    created_payload = created.json()["data"]
    definition_id = created_payload["definition"]["definition_id"]
    assert created_payload["operation"] == "created"
    assert created_payload["definition"]["name"] == "ReadoutPreview"
    assert created_payload["definition"]["visibility_scope"] == "private"
    assert created_payload["definition"]["concurrency_token"] == f"etag_{definition_id}_1"

    updated = client.put(
        f"/circuit-definitions/{definition_id}",
        json={
            "name": "ReadoutPreviewV2",
            "source_text": _valid_circuit_source("ReadoutPreviewV2"),
            "concurrency_token": created_payload["definition"]["concurrency_token"],
        },
    )
    assert updated.status_code == 200
    updated_payload = updated.json()["data"]
    assert updated_payload["operation"] == "updated"
    assert updated_payload["definition"]["name"] == "ReadoutPreviewV2"
    assert updated_payload["definition"]["concurrency_token"] == f"etag_{definition_id}_2"

    published = client.post(f"/circuit-definitions/{definition_id}/publish")
    assert published.status_code == 200
    assert published.json()["data"]["definition"]["visibility_scope"] == "workspace"

    cloned = client.post(
        f"/circuit-definitions/{definition_id}/clone",
        json={"name": "ReadoutPreview Private Copy"},
    )
    assert cloned.status_code == 201
    cloned_payload = cloned.json()["data"]["definition"]
    assert cloned_payload["name"] == "ReadoutPreview Private Copy"
    assert cloned_payload["visibility_scope"] == "private"
    assert cloned_payload["lineage_parent_id"] == definition_id

    deleted = client.delete(f"/circuit-definitions/{definition_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {
        "operation": "deleted",
        "definition_id": definition_id,
    }

    missing = client.get(f"/circuit-definitions/{definition_id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "definition_not_found"


def test_create_circuit_definition_rejects_blank_name() -> None:
    response = client.post(
        "/circuit-definitions",
        json={
            "name": "   ",
            "source_text": _valid_circuit_source("readout_preview"),
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "request_validation_failed"


def test_schemdraw_route_is_removed_from_backend_active_surface() -> None:
    route_paths = {route.path for route in app.router.routes}

    assert "/schemdraw/render" not in route_paths
    assert "/api/backend/schemdraw/render" not in route_paths


def _valid_circuit_source(name: str) -> str:
    return f"""{{
    "name": "{name}",
    "components": [
        {{"name": "R1", "default": 50.0, "unit": "Ohm"}},
        {{"name": "C1", "default": 100.0, "unit": "fF"}},
        {{"name": "Lj1", "default": 1000.0, "unit": "pH"}},
        {{"name": "C2", "default": 1000.0, "unit": "fF"}}
    ],
    "topology": [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("C1", "1", "2", "C1"),
        ("Lj1", "2", "0", "Lj1"),
        ("C2", "2", "0", "C2")
    ]
}}"""
