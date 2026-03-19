import pytest
from fastapi.testclient import TestClient
from src.app.domain.datasets import (
    CharacterizationAnalysisRegistryQuery,
    CharacterizationResultBrowseQuery,
    CharacterizationRunHistoryQuery,
    CharacterizationTaggingRequest,
    DatasetProfileUpdate,
    DesignBrowseQuery,
    TraceBrowseQuery,
)
from src.app.infrastructure.rewrite_app_state_repository import InMemoryRewriteAppStateRepository
from src.app.infrastructure.rewrite_catalog_repository import InMemoryRewriteCatalogRepository
from src.app.infrastructure.runtime import reset_runtime_state
from src.app.main import app
from src.app.services.dataset_service import DatasetService
from src.app.services.service_errors import ServiceError

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
        repository=catalog_repository,
        session_repository=app_state_repository,
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
    assert all(
        row["dataset_id"] != dataset_id for row in deleted.json()["data"]["catalog_rows"]
    )


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
    assert second.json()["error"]["code"] == "dataset_design_conflict"


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
        "metric-fluxonium-f01",
        "metric-fluxonium-anharmonicity",
    ]
    assert [design.design_id for design in designs] == ["design_flux_scan_a"]
    assert designs[0].compare_readiness == "ready"

    assert [row.trace_id for row in trace_rows] == [
        "trace_flux_a_measurement",
        "trace_flux_a_phase",
    ]
    assert not hasattr(trace_rows[0], "preview_payload")
    assert not hasattr(trace_rows[0], "payload_ref")

    assert trace_detail.trace_id == "trace_flux_a_measurement"
    assert trace_detail.preview_payload["kind"] == "sampled_series"
    assert trace_detail.payload_ref is not None
    assert trace_detail.payload_ref.store_key.endswith("batch_4.zarr")
    assert trace_detail.result_handles[0].handle_id == "result:fluxonium-2025-031:fit-summary"


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
    assert result_detail.payload["fit_table"][0]["parameter"] == "f01"
    assert result_detail.artifact_refs[0].artifact_id == "artifact-fit-table-flux-a-01"


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
    assert registry_rows[0].availability_state == "recommended"
    assert registry_rows[0].required_config_fields == (
        "fit_window",
        "residual_tolerance",
    )
    assert registry_rows[0].trace_compatibility.selected_trace_count == 2
    assert registry_rows[0].trace_compatibility.matched_trace_count == 2

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
    assert [row["definition_id"] for row in payload["data"]["rows"]] == [18, 12, 7]
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
    response = client.get("/circuit-definitions/18")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["definition_id"] == 18
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
    definition_id = int(created_payload["definition"]["definition_id"])
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


def test_schemdraw_render_returns_svg_preview_and_diagnostics() -> None:
    response = client.post(
        "/schemdraw/render",
        json={
            "source_text": (
                "import schemdraw\n"
                "import schemdraw.elements as elm\n\n"
                "def build_drawing(relation):\n"
                "    drawing = schemdraw.Drawing(show=False)\n"
                "    tag = relation.get('tag', 'draft')\n"
                "    linked = relation.get('linked_schema') or {}\n"
                "    drawing += elm.Resistor().label(f\"R-{tag}\")\n"
                "    drawing += elm.Capacitor().down().label(linked.get('name', 'unlinked'))\n"
                "    return drawing\n"
            ),
            "relation_config": {
                "tag": "draft",
                "labels": {"P1": "input"},
                "cursor_position": {"x": 12.0, "y": 18.0},
                "probe_points": [{"name": "P1", "x": 14.0, "y": 18.0}],
            },
            "linked_schema": {
                "definition_id": 18,
                "workspace_id": "ws-device-lab",
                "name": "FloatingQubitWithXYLine",
            },
            "document_version": 14,
            "request_id": "req_sdraw_14",
            "render_mode": "debounced",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "rendered"
    assert payload["request_id"] == "req_sdraw_14"
    assert payload["svg"].startswith("<svg")
    assert "Schemdraw Structural Preview" not in payload["svg"]
    assert "R-draft" in payload["svg"]
    assert "FloatingQubitWithXYLine" in payload["svg"]
    assert payload["cursor_position"] == {"x": 12.0, "y": 18.0}
    assert payload["probe_points"] == [{"name": "P1", "x": 14.0, "y": 18.0}]
    assert payload["preview_metadata"]["linked_definition_id"] == 18
    assert payload["preview_metadata"]["width"] > 0
    assert payload["preview_metadata"]["height"] > 0
    assert payload["preview_metadata"]["view_box"]


def test_schemdraw_render_reflects_source_and_relation_changes_in_svg() -> None:
    source_template = (
        "import schemdraw\n"
        "import schemdraw.elements as elm\n\n"
        "def build_drawing(relation):\n"
        "    drawing = schemdraw.Drawing(show=False)\n"
        "    drawing += elm.Resistor().label(relation.get('left_label', 'L'))\n"
        "    drawing += elm.Line().right().length(1)\n"
        "    drawing += elm.Capacitor().label(relation.get('right_label', 'R'))\n"
        "    return drawing\n"
    )

    first = client.post(
        "/schemdraw/render",
        json={
            "source_text": source_template,
            "relation_config": {"left_label": "R-alpha", "right_label": "C-beta"},
            "linked_schema": None,
            "document_version": 31,
            "request_id": "req_sdraw_31",
            "render_mode": "debounced",
        },
    )
    second = client.post(
        "/schemdraw/render",
        json={
            "source_text": source_template.replace(
                "Line().right().length(1)",
                "Line().down().length(1.5)",
            ),
            "relation_config": {"left_label": "R-gamma", "right_label": "C-delta"},
            "linked_schema": None,
            "document_version": 32,
            "request_id": "req_sdraw_32",
            "render_mode": "manual",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_svg = first.json()["data"]["svg"]
    second_svg = second.json()["data"]["svg"]
    assert first_svg is not None
    assert second_svg is not None
    assert "R-alpha" in first_svg
    assert "C-beta" in first_svg
    assert "R-gamma" in second_svg
    assert "C-delta" in second_svg
    assert first_svg != second_svg


def test_schemdraw_render_returns_blocking_diagnostics_for_invalid_source() -> None:
    response = client.post(
        "/schemdraw/render",
        json={
            "source_text": (
                "import schemdraw\n"
                "import schemdraw.elements as elm\n\n"
                "def build_drawing(relation):\n"
                "    d = schemdraw.Drawing(show=False)\n"
                "    d += elm.Note().at((2.0, -1.2)).label(\n"
                "        'Mutual coupling:\n"
                "M = L12·Δz\n"
                "or use K(L1,L2)',\n"
                "        loc='center'\n"
                "    )\n"
                "    return d\n"
            ),
            "relation_config": {"tag": "draft"},
            "linked_schema": None,
            "document_version": 21,
            "request_id": "req_sdraw_21",
            "render_mode": "manual",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "syntax_error"
    assert payload["svg"] is None
    assert payload["diagnostics"][0]["code"] == "schemdraw_syntax_error"
    assert payload["diagnostics"][0]["source"] == "python_syntax"
    assert payload["diagnostics"][0]["message"] != "The Schemdraw source cannot be parsed."
    assert "string literal" in payload["diagnostics"][0]["message"].lower()
    assert payload["diagnostics"][0]["blocking"] is True
    assert payload["diagnostics"][0]["line"] is not None
    assert payload["diagnostics"][0]["column"] is not None


def test_schemdraw_render_returns_runtime_diagnostic_when_entrypoint_fails() -> None:
    response = client.post(
        "/schemdraw/render",
        json={
            "source_text": (
                "import schemdraw\n"
                "import schemdraw.elements as elm\n\n"
                "def build_drawing(relation):\n"
                "    return 1 / 0\n"
            ),
            "relation_config": {"tag": "draft"},
            "linked_schema": None,
            "document_version": 22,
            "request_id": "req_sdraw_22",
            "render_mode": "manual",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "runtime_error"
    assert payload["svg"] is None
    assert payload["diagnostics"][0]["code"] == "schemdraw_runtime_error"
    assert "division by zero" in payload["diagnostics"][0]["message"]
    assert payload["diagnostics"][0]["line"] == 5


def test_schemdraw_render_returns_runtime_diagnostic_for_top_level_source_failure() -> None:
    response = client.post(
        "/schemdraw/render",
        json={
            "source_text": (
                "import schemdraw\n"
                "boom = 1 / 0\n\n"
                "def build_drawing(relation):\n"
                "    return schemdraw.Drawing(show=False)\n"
            ),
            "relation_config": {"tag": "draft"},
            "linked_schema": None,
            "document_version": 23,
            "request_id": "req_sdraw_23",
            "render_mode": "manual",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "runtime_error"
    assert payload["svg"] is None
    assert payload["diagnostics"][0]["code"] == "schemdraw_runtime_error"
    assert "division by zero" in payload["diagnostics"][0]["message"]
    assert payload["diagnostics"][0]["blocking"] is True
    assert payload["diagnostics"][0]["line"] == 2


def test_schemdraw_route_is_exposed_on_backend_canonical_path() -> None:
    route_paths = {route.path for route in app.router.routes}

    assert "/schemdraw/render" in route_paths
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
