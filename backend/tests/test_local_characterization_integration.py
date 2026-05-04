from __future__ import annotations

import sqlite3
import time
from dataclasses import replace

import numpy as np
import pytest
from core.shared.persistence import (
    LocalZarrTraceStore,
    get_trace_store_path,
)
from core.shared.persistence import (
    database as core_database,
)
from fastapi.testclient import TestClient
from sc_core.execution import TaskResultHandle
from sqlalchemy import select
from src.app.domain.datasets import TraceAxis, TraceDetail, TraceMetadataSummary
from src.app.domain.tasks import (
    CharacterizationSetup,
    TaskDetail,
    TaskProgress,
    TaskResultRefs,
)
from src.app.infrastructure.persisted_characterization_runtime import (
    CharacterizationExecutionRequest,
    CharacterizationExecutionTrace,
    _materialize_trace_grid,
)
from src.app.infrastructure.persistence.database import create_metadata_session_factory
from src.app.infrastructure.persistence.models import RewriteTraceCapabilityRecord
from src.app.infrastructure.runtime import (
    get_catalog_repository,
    get_persisted_characterization_repository,
    reset_runtime_state,
)
from src.app.main import app
from src.app.settings import get_settings
from tests.worker_runtime_harness import (
    drain_lane_queue,
    queue_job_count,
    registered_worker,
)

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


def _submit_characterization_task() -> dict[str, object]:
    response = client.post("/tasks", json=_characterization_payload())
    assert response.status_code == 201
    return response.json()["data"]["task"]


def _create_sweepable_definition(name: str) -> str:
    response = client.post(
        "/circuit-definitions",
        json={
            "name": name,
            "source_text": """{
  "name": "SweepableReadoutChain",
  "parameters": [
    {"name": "Lj", "default": 1000.0, "unit": "pH"}
  ],
  "components": [
    {"name": "R1", "default": 50.0, "unit": "Ohm"},
    {"name": "C1", "default": 100.0, "unit": "fF"},
    {"name": "Lj1", "value_ref": "Lj", "unit": "pH"}
  ],
  "topology": [
    ("P1", "1", "0", 1),
    ("R1", "1", "0", "R1"),
    ("C1", "1", "2", "C1"),
    ("Lj1", "2", "0", "Lj1")
  ]
}""",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["definition"]["definition_id"]


def _submit_local_simulation(
    *,
    definition_id: str,
    parameter_sweeps: list[dict[str, object]],
) -> dict[str, object]:
    response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "dataset_id": "local-dataset-001",
            "definition_id": definition_id,
            "summary": "Sweep-aware characterization source task.",
            "simulation_setup": {
                "frequency_sweep": {
                    "start_ghz": 1.0,
                    "stop_ghz": 8.0,
                    "point_count": 401,
                    "spacing": "linear",
                },
                "parameter_sweeps": parameter_sweeps,
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
                "ptc": {
                    "enabled": False,
                    "mode": "auto",
                    "compensate_ports": ["port_1", "port_2"],
                },
            },
        },
    )
    assert response.status_code == 201
    task = response.json()["data"]["task"]
    detail = task
    for _ in range(3):
        drain_lane_queue("simulation")
        for _ in range(5):
            detail = client.get(f"/tasks/{task['task_id']}").json()["data"]
            if (
                detail["status"] == "completed"
                and detail["result_handoff"]["availability"] == "ready"
            ):
                return detail
            time.sleep(0.05)
    return detail


def _build_direct_characterization_task(
    *,
    dataset_id: str,
    design_id: str,
    selected_trace_ids: tuple[str, ...],
    fit_window: tuple[float, float],
    residual_tolerance: float,
) -> TaskDetail:
    return TaskDetail(
        task_id=99101,
        kind="characterization",
        lane="characterization",
        execution_mode="run",
        status="running",
        submitted_at="2026-03-30T00:00:00Z",
        owner_user_id="local-user",
        owner_display_name="Local User",
        workspace_id="workspace-local",
        workspace_slug="local",
        visibility_scope="local",
        dataset_id=dataset_id,
        definition_id=None,
        summary="Direct persisted admittance runtime contract test.",
        queue_backend="rq_redis",
        worker_task_name="characterization_run_task",
        request_ready=True,
        submitted_from_active_dataset=True,
        progress=TaskProgress(
            phase="running",
            percent_complete=50,
            summary="Executing persisted admittance extraction.",
            updated_at="2026-03-30T00:00:00Z",
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


def _metadata_session_factory():
    return create_metadata_session_factory(get_settings().database_path)


def _create_legacy_result_bundle_table() -> None:
    core_database.get_engine.cache_clear()
    with sqlite3.connect(get_settings().database_path) as connection:
        connection.execute("DROP TABLE IF EXISTS result_bundle_data_links")
        connection.execute("DROP TABLE IF EXISTS result_bundle_records")
        connection.execute(
            """
            CREATE TABLE result_bundle_records (
                id INTEGER PRIMARY KEY,
                dataset_id INTEGER NOT NULL,
                bundle_type VARCHAR NOT NULL,
                source_meta JSON DEFAULT '{}',
                config_snapshot JSON DEFAULT '{}',
                result_payload JSON DEFAULT '{}',
                created_at DATETIME
            )
            """
        )
        connection.commit()
    core_database.get_engine.cache_clear()


def _result_bundle_columns() -> set[str]:
    with sqlite3.connect(get_settings().database_path) as connection:
        return {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(result_bundle_records)")
        }


def _clear_trace_capabilities(
    dataset_id: str,
    design_id: str,
    trace_ids: tuple[str, ...],
) -> None:
    with _metadata_session_factory()() as session:
        session.query(RewriteTraceCapabilityRecord).filter(
            RewriteTraceCapabilityRecord.dataset_id == dataset_id,
            RewriteTraceCapabilityRecord.design_id == design_id,
            RewriteTraceCapabilityRecord.trace_id.in_(trace_ids),
        ).delete(synchronize_session=False)
        session.commit()


def _overwrite_trace_capabilities_with_analysis_subset(
    dataset_id: str,
    design_id: str,
    trace_id: str,
    analysis_ids: tuple[str, ...],
) -> None:
    with _metadata_session_factory()() as session:
        existing_rows = session.scalars(
            select(RewriteTraceCapabilityRecord)
            .where(
                RewriteTraceCapabilityRecord.dataset_id == dataset_id,
                RewriteTraceCapabilityRecord.design_id == design_id,
                RewriteTraceCapabilityRecord.trace_id == trace_id,
            )
            .order_by(
                RewriteTraceCapabilityRecord.analysis_id.asc(),
                RewriteTraceCapabilityRecord.input_role.asc(),
            )
        ).all()
        replacement_rows = [
            {
                "capability_id": row.capability_id,
                "analysis_id": row.analysis_id,
                "analysis_label": row.analysis_label,
                "input_role": row.input_role,
                "input_role_label": row.input_role_label,
                "status": row.status,
                "summary": row.summary,
                "reasons_json": [
                    {
                        "code": str(reason.get("code", "")),
                        "message": str(reason.get("message", "")),
                        "evidence": (
                            dict(reason["evidence"])
                            if isinstance(reason.get("evidence"), dict)
                            else {}
                        ),
                    }
                    for reason in row.reasons_json
                    if isinstance(reason, dict)
                ],
            }
            for row in existing_rows
            if row.analysis_id in analysis_ids
        ]
    with _metadata_session_factory()() as session:
        session.query(RewriteTraceCapabilityRecord).filter(
            RewriteTraceCapabilityRecord.dataset_id == dataset_id,
            RewriteTraceCapabilityRecord.design_id == design_id,
            RewriteTraceCapabilityRecord.trace_id == trace_id,
        ).delete(synchronize_session=False)
        for row in replacement_rows:
            session.add(
                RewriteTraceCapabilityRecord(
                    dataset_id=dataset_id,
                    design_id=design_id,
                    trace_id=trace_id,
                    capability_id=row["capability_id"],
                    analysis_id=row["analysis_id"],
                    analysis_label=row["analysis_label"],
                    input_role=row["input_role"],
                    input_role_label=row["input_role_label"],
                    status=row["status"],
                    summary=row["summary"],
                    reasons_json=row["reasons_json"],
                )
            )
        session.commit()


def _load_trace_capability_analysis_ids(
    dataset_id: str,
    design_id: str,
    trace_id: str,
) -> tuple[str, ...]:
    with _metadata_session_factory()() as session:
        rows = session.scalars(
            select(RewriteTraceCapabilityRecord)
            .where(
                RewriteTraceCapabilityRecord.dataset_id == dataset_id,
                RewriteTraceCapabilityRecord.design_id == design_id,
                RewriteTraceCapabilityRecord.trace_id == trace_id,
            )
            .order_by(
                RewriteTraceCapabilityRecord.analysis_id.asc(),
                RewriteTraceCapabilityRecord.input_role.asc(),
            )
        ).all()
    return tuple(row.analysis_id for row in rows)


def _create_ineligible_local_characterization_trace() -> tuple[str, str, str]:
    created = client.post(
        "/datasets",
        json={
            "name": "Local Incompatible Characterization Dataset",
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
            "design_name": "Local Incompatible Characterization Design",
            "provenance_label": "incompatible-measurement-batch",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "Y11_sideband",
                    "representation": "imaginary",
                    "trace_mode_group": "sideband",
                    "stage_kind": "raw",
                    "provenance_summary": "Sideband-only measurement trace",
                    "axes": [{"name": "frequency", "unit": "GHz", "length": 2}],
                    "preview_payload": {
                        "kind": "sampled_series",
                        "points": [[5.0, 0.11], [5.2, 0.15]],
                    },
                }
            ],
        },
    )
    assert ingestion.status_code == 200
    payload = ingestion.json()["data"]
    return dataset_id, payload["design"]["design_id"], payload["traces"][0]["trace_id"]


def _create_unsupported_local_characterization_trace() -> tuple[str, str, str]:
    created = client.post(
        "/datasets",
        json={
            "name": "Local Unsupported Characterization Dataset",
            "family": "resonator",
            "device_type": "Resonator",
            "source": "measurement",
        },
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["dataset"]["dataset_id"]
    ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "measurement",
            "design_name": "Local Unsupported Characterization Design",
            "provenance_label": "unsupported-measurement-batch",
            "traces": [
                {
                    "family": "s_matrix",
                    "parameter": "S21_temperature",
                    "representation": "magnitude",
                    "trace_mode_group": "base",
                    "stage_kind": "raw",
                    "provenance_summary": "Temperature sweep resonator trace",
                    "axes": [{"name": "temperature", "unit": "K", "length": 3}],
                    "preview_payload": {
                        "kind": "sampled_series",
                        "points": [[0.01, 0.91], [0.03, 0.84], [0.05, 0.79]],
                    },
                }
            ],
        },
    )
    assert ingestion.status_code == 200
    payload = ingestion.json()["data"]
    return dataset_id, payload["design"]["design_id"], payload["traces"][0]["trace_id"]


def _create_legacy_floating_qubit_characterization_trace() -> tuple[str, str, str]:
    created = client.post(
        "/datasets",
        json={
            "name": "Legacy Floating Qubit Characterization Dataset",
            "family": "FloatingQubit",
            "device_type": "FloatingQubit",
            "source": "simulation",
        },
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["dataset"]["dataset_id"]
    ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "layout_simulation",
            "design_name": "FloatingQubitWithXY Legacy",
            "provenance_label": "legacy-floating-qubit-simulation",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "Ydm_real",
                    "representation": "real",
                    "trace_mode_group": "base",
                    "stage_kind": "postprocess",
                    "provenance_summary": "Floating-qubit differential admittance trace",
                    "axes": [{"name": "frequency", "unit": "GHz", "length": 3}],
                    "preview_payload": {
                        "kind": "sampled_series",
                        "points": [[5.0, 0.11], [5.2, 0.15], [5.4, 0.18]],
                    },
                }
            ],
        },
    )
    assert ingestion.status_code == 200
    payload = ingestion.json()["data"]
    return dataset_id, payload["design"]["design_id"], payload["traces"][0]["trace_id"]


def _create_transmon_metadata_floating_qubit_trace() -> tuple[str, str, str]:
    created = client.post(
        "/datasets",
        json={
            "name": "FloatingQubit 100",
            "family": "Transmon",
            "device_type": "FloatingQubit",
            "source": "simulation",
        },
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["dataset"]["dataset_id"]
    design_create = client.post(
        f"/datasets/{dataset_id}/designs",
        json={"name": "FloatingQubitWithXY"},
    )
    assert design_create.status_code == 201
    design_id = design_create.json()["data"]["design"]["design_id"]
    ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "layout_simulation",
            "design_id": design_id,
            "design_name": "FloatingQubitWithXY",
            "provenance_label": "floating-qubit-transmon-metadata",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "Ydm_real",
                    "representation": "real",
                    "trace_mode_group": "base",
                    "stage_kind": "postprocess",
                    "provenance_summary": "Floating-qubit Y-matrix post-processed trace",
                    "axes": [{"name": "frequency", "unit": "GHz", "length": 3}],
                    "preview_payload": {
                        "kind": "sampled_series",
                        "points": [[5.0, 0.11], [5.2, 0.15], [5.4, 0.18]],
                    },
                }
            ],
        },
    )
    assert ingestion.status_code == 200
    payload = ingestion.json()["data"]
    return dataset_id, payload["design"]["design_id"], payload["traces"][0]["trace_id"]


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
    assert rows_by_id["admittance_member_fit"]["prerequisite_state"] == (
        "requires_upstream_result"
    )
    assert rows_by_id["admittance_member_fit"]["upstream_result_requirement"] == {
        "required_upstream_analysis_ids": ["admittance_extraction"],
        "satisfied_result_refs": [],
        "summary": (
            "Requires a completed admittance resonance extraction result "
            "before this pipeline step can run."
        ),
    }
    assert payload["data"]["data_collection_review"]["selected_trace_ids"] == [
        "trace_local_flux_measurement",
        "trace_local_flux_preview",
    ]
    assert payload["data"]["data_collection_review"]["readiness_state"] == "ready"
    assert {
        row["analysis_id"]
        for row in payload["data"]["data_collection_review"]["runnable_analyses"]
    } == {"admittance_extraction"}
    assert "admittance_member_fit" in {
        row["analysis_id"]
        for row in payload["data"]["data_collection_review"]["blocked_analyses"]
    }


def test_local_registry_and_submit_use_trace_capability_first_gating_for_transmon_metadata_case(
) -> None:
    dataset_id, design_id, trace_id = _create_transmon_metadata_floating_qubit_trace()
    _overwrite_trace_capabilities_with_analysis_subset(
        dataset_id,
        design_id,
        trace_id,
        ("coupler_shift_fit",),
    )

    assert set(_load_trace_capability_analysis_ids(dataset_id, design_id, trace_id)) == {
        "coupler_shift_fit"
    }

    trace_response = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces")
    registry_response = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/characterization-analysis-registry",
        params=[("selected_trace_ids", trace_id)],
    )
    submit_response = client.post(
        "/tasks",
        json={
            "kind": "characterization",
            "dataset_id": dataset_id,
            "characterization_setup": {
                "design_id": design_id,
                "analysis_id": "admittance_extraction",
                "selected_trace_ids": [trace_id],
                "analysis_config": {
                    "fit_window": [4.85, 5.25],
                    "residual_tolerance": 0.015,
                },
            },
        },
    )

    assert trace_response.status_code == 200
    trace_row = next(
        row for row in trace_response.json()["data"]["rows"] if row["trace_id"] == trace_id
    )
    admittance_capability = next(
        capability
        for capability in trace_row["analysis_capabilities"]
        if capability["analysis_id"] == "admittance_extraction"
    )
    assert admittance_capability["status"] == "eligible"
    assert admittance_capability["reasons"] == [
        {
            "code": "dataset_family_unpreferred",
            "message": (
                "Trace structure is compatible, but dataset family metadata is outside "
                "the preferred families for this analysis."
            ),
            "evidence": {
                "actual_dataset_family": "Transmon",
                "preferred_dataset_families": ["fluxonium", "floatingqubit"],
            },
        }
    ]

    assert registry_response.status_code == 200
    assert registry_response.json()["data"]["rows"][0] == {
        "analysis_id": "admittance_extraction",
        "label": "Admittance Resonance Extraction",
        "availability_state": "recommended",
        "required_config_fields": ["fit_window", "residual_tolerance"],
        "trace_compatibility": {
            "matched_trace_count": 1,
            "selected_trace_count": 1,
            "recommended_trace_modes": ["base"],
            "summary": "1 selected trace is eligible for admittance resonance extraction.",
        },
        "prerequisite_state": "ready",
        "upstream_result_requirement": None,
        "downstream_unlock_analysis_ids": ["admittance_member_fit"],
    }
    assert "admittance_extraction" in _load_trace_capability_analysis_ids(
        dataset_id,
        design_id,
        trace_id,
    )

    assert submit_response.status_code == 201
    assert submit_response.json()["data"]["operation"] == "submitted"


def test_local_trace_registry_read_repair_backfills_legacy_floating_qubit_capabilities() -> None:
    dataset_id, design_id, trace_id = _create_legacy_floating_qubit_characterization_trace()
    _clear_trace_capabilities(dataset_id, design_id, (trace_id,))

    trace_response = client.get(f"/datasets/{dataset_id}/designs/{design_id}/traces")
    registry_response = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/characterization-analysis-registry",
        params=[("selected_trace_ids", trace_id)],
    )

    assert trace_response.status_code == 200
    trace_row = next(
        row for row in trace_response.json()["data"]["rows"] if row["trace_id"] == trace_id
    )
    assert trace_row["analysis_capabilities"] != []
    assert any(
        capability["analysis_id"] == "admittance_extraction"
        for capability in trace_row["analysis_capabilities"]
    )

    assert registry_response.status_code == 200
    rows_by_id = {
        row["analysis_id"]: row for row in registry_response.json()["data"]["rows"]
    }
    assert rows_by_id["admittance_extraction"] == {
        "analysis_id": "admittance_extraction",
        "label": "Admittance Resonance Extraction",
        "availability_state": "recommended",
        "required_config_fields": ["fit_window", "residual_tolerance"],
        "trace_compatibility": {
            "matched_trace_count": 1,
            "selected_trace_count": 1,
            "recommended_trace_modes": ["base"],
            "summary": "1 selected trace is eligible for admittance resonance extraction.",
        },
        "prerequisite_state": "ready",
        "upstream_result_requirement": None,
        "downstream_unlock_analysis_ids": ["admittance_member_fit"],
    }
    assert rows_by_id["admittance_member_fit"]["prerequisite_state"] == (
        "requires_upstream_result"
    )
    assert _load_trace_capability_analysis_ids(dataset_id, design_id, trace_id) == (
        "admittance_extraction",
    )


def test_local_registry_read_repair_preserves_selected_scope_truthfulness() -> None:
    trace_ids = (
        "trace_local_flux_measurement",
        "trace_local_flux_preview",
    )
    _clear_trace_capabilities("local-dataset-001", "design_local_flux_playground", trace_ids)

    response = client.get(
        "/datasets/local-dataset-001/designs/design_local_flux_playground/"
        "characterization-analysis-registry",
        params=[("selected_trace_ids", trace_id) for trace_id in trace_ids],
    )

    assert response.status_code == 200
    rows = response.json()["data"]["rows"]
    assert rows[0] == {
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
    assert {
        analysis_id
        for trace_id in trace_ids
        for analysis_id in _load_trace_capability_analysis_ids(
            "local-dataset-001",
            "design_local_flux_playground",
            trace_id,
        )
    } >= {
        "admittance_extraction",
        "junction_parameter_identification",
        "screening_summary",
        "sideband_comparison",
    }


def test_local_characterization_runtime_summary_reports_idle_worker_presence() -> None:
    with registered_worker(
        "characterization",
        name="sc-worker-characterization:4311",
    ):
        response = client.get("/tasks/runtime/processors")

    assert response.status_code == 200
    processor = next(
        item for item in response.json()["data"]["processors"] if item["lane"] == "characterization"
    )
    assert processor["processor_id"] == "sc-worker-characterization:4311"
    assert processor["state"] == "idle"
    assert processor["current_task_id"] is None
    assert processor["runtime_metadata"] == {
        "authority": "rq_redis",
        "execution_mode": "worker_process",
        "lane": "characterization",
        "queue_names": ["characterization"],
        "worker_pid": 4311,
    }


@pytest.mark.parametrize(
    ("payload", "status_code", "error_code"),
    [
        (
            _characterization_payload(design_id="missing-design"),
            404,
            "target_design_scope_invalid",
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


def test_local_characterization_submit_accepts_single_eligible_trace() -> None:
    response = client.post(
        "/tasks",
        json=_characterization_payload(selected_trace_ids=("trace_local_flux_measurement",)),
    )

    assert response.status_code == 201
    task = response.json()["data"]["task"]
    assert task["status"] == "queued"
    assert task["characterization_setup"]["selected_trace_ids"] == ["trace_local_flux_measurement"]


def test_local_characterization_submit_rejects_ineligible_selected_trace() -> None:
    dataset_id, design_id, trace_id = _create_ineligible_local_characterization_trace()
    payload = _characterization_payload(
        design_id=design_id,
        selected_trace_ids=(trace_id,),
    )
    payload["dataset_id"] = dataset_id

    response = client.post("/tasks", json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "characterization_trace_selection_incompatible"
    assert "not eligible for admittance resonance extraction" in error["message"]


def test_local_downstream_characterization_requires_upstream_result_before_runtime_support_check(
) -> None:
    missing_upstream_response = client.post(
        "/tasks",
        json={
            "kind": "characterization",
            "dataset_id": "local-dataset-001",
            "characterization_setup": {
                "design_id": "design_local_flux_playground",
                "analysis_id": "admittance_member_fit",
                "selected_trace_ids": ["trace_local_flux_measurement"],
                "analysis_config": {"branch_selector": "mode:0"},
            },
        },
    )

    assert missing_upstream_response.status_code == 422
    assert missing_upstream_response.json()["error"]["code"] == (
        "characterization_upstream_result_required"
    )

    unsupported_response = client.post(
        "/tasks",
        json={
            "kind": "characterization",
            "dataset_id": "local-dataset-001",
            "characterization_setup": {
                "design_id": "design_local_flux_playground",
                "analysis_id": "admittance_member_fit",
                "selected_trace_ids": ["trace_local_flux_measurement"],
                "analysis_config": {"branch_selector": "mode:0"},
                "input_result_refs": [
                    {
                        "analysis_id": "admittance_extraction",
                        "result_id": "char-fit-flux-a-01",
                        "run_id": "analysis-run-101",
                        "artifact_id": "char-fit-flux-a-01:mode-frequency-grid",
                        "contract_version": "admittance_member_phase1_v1",
                        "title": "Flux Scan A admittance resonance extraction",
                    }
                ],
            },
        },
    )

    assert unsupported_response.status_code == 409
    assert unsupported_response.json()["error"]["code"] == (
        "characterization_analysis_unsupported"
    )


def test_local_registry_marks_compatible_but_unsupported_analysis_as_unavailable() -> None:
    dataset_id, design_id, trace_id = _create_unsupported_local_characterization_trace()
    _clear_trace_capabilities(dataset_id, design_id, (trace_id,))

    registry_response = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/characterization-analysis-registry",
        params=[("selected_trace_ids", trace_id)],
    )

    assert registry_response.status_code == 200
    assert registry_response.json()["data"]["rows"] == [
        {
            "analysis_id": "quality_factor_fit",
            "label": "Quality Factor Fit",
            "availability_state": "unavailable",
            "required_config_fields": ["temperature_window"],
            "trace_compatibility": {
                "matched_trace_count": 1,
                "selected_trace_count": 1,
                "recommended_trace_modes": ["base"],
                "summary": (
                    "1 selected trace is compatible with quality factor fit, "
                    "but the current runtime does not yet support executing this analysis."
                ),
            },
            "prerequisite_state": "ready",
            "upstream_result_requirement": None,
            "downstream_unlock_analysis_ids": [],
        }
    ]
    assert _load_trace_capability_analysis_ids(dataset_id, design_id, trace_id) == (
        "quality_factor_fit",
    )

    submit_response = client.post(
        "/tasks",
        json={
            "kind": "characterization",
            "dataset_id": dataset_id,
            "characterization_setup": {
                "design_id": design_id,
                "analysis_id": "quality_factor_fit",
                "selected_trace_ids": [trace_id],
                "analysis_config": {"temperature_window": [0.01, 0.05]},
            },
        },
    )

    assert submit_response.status_code == 409
    assert submit_response.json()["error"]["code"] == "characterization_analysis_unsupported"


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
    task = _submit_characterization_task()

    assert task["status"] == "queued"
    assert task["dispatch"]["status"] == "accepted"
    assert queue_job_count("characterization") == 1

    drain_lane_queue("characterization")

    detail = client.get(f"/tasks/{task['task_id']}").json()["data"]
    assert detail["status"] == "completed"
    assert detail["characterization_setup"]["design_id"] == "design_local_flux_playground"
    assert detail["characterization_setup"]["analysis_id"] == "admittance_extraction"
    assert detail["characterization_setup"]["selected_trace_ids"] == [
        "trace_local_flux_measurement",
        "trace_local_flux_preview",
    ]
    assert detail["characterization_setup"]["input_collection_payload"] is not None
    assert (
        detail["characterization_setup"]["input_collection_payload"]["shared_axes"][0]["name"]
        == "frequency"
    )
    assert (
        detail["characterization_setup"]["input_collection_payload"]["shared_axes"][0]["values"]
        == []
    )
    assert isinstance(detail["result_refs"]["analysis_run_id"], int)
    assert detail["result_refs"]["analysis_run_id"] > 0
    assert detail["result_refs"]["trace_payload"]["payload_role"] == "analysis_projection"
    assert detail["result_refs"]["result_handles"][0]["handle_id"] == (
        f"analysis-run:{detail['result_refs']['analysis_run_id']}:report"
    )
    assert detail["result_refs"]["result_handles"][0]["kind"] == "characterization_report"
    assert detail["result_refs"]["result_handles"][0]["status"] == "materialized"


def test_local_characterization_submit_upgrades_legacy_result_bundle_schema_before_persisting_runs(
) -> None:
    _create_legacy_result_bundle_table()
    assert "design_id" not in _result_bundle_columns()

    task = _submit_characterization_task()
    drain_lane_queue("characterization")

    detail = client.get(f"/tasks/{task['task_id']}").json()["data"]
    assert detail["status"] == "completed"
    assert isinstance(detail["result_refs"]["analysis_run_id"], int)
    assert detail["result_refs"]["analysis_run_id"] > 0
    assert {
        "design_id",
        "parent_batch_id",
        "role",
        "status",
        "schema_source_hash",
        "simulation_setup_hash",
        "completed_at",
    } <= _result_bundle_columns()


def test_local_characterization_result_surfaces_survive_refresh() -> None:
    submitted = _submit_characterization_task()
    drain_lane_queue("characterization")

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
    task_detail = client.get(f"/tasks/{submitted['task_id']}").json()["data"]
    assert task_detail["result_handoff"]["availability"] == "ready"
    assert detail["payload"]["analysis_run_id"] == task_detail["result_refs"]["analysis_run_id"]
    assert detail["payload"]["contract_version"] == "admittance_member_phase1_v1"
    assert detail["payload"]["input_axis"]["axis_key"] == "selected_scope"
    assert detail["payload"]["member_axis"]["axis_key"] == "member_key"
    assert detail["artifact_refs"][0]["artifact_id"] == (
        f"{result_row['result_id']}:mode-frequency-grid"
    )
    assert detail["artifact_refs"][0]["view_kind"] == "preset_query"
    assert detail["artifact_refs"][0]["query_spec"]["supported_query_fields"] == [
        "view_mode",
        "preset_id",
    ]
    assert detail["artifact_refs"][0]["payload_locator"] == (
        f"characterization/{result_row['result_id']}/mode-frequency-grid.json"
    )
    artifact_response = client.get(
        "/datasets/local-dataset-001/designs/design_local_flux_playground/"
        f"characterization-results/{result_row['result_id']}/artifacts/"
        f"{result_row['result_id']}:mode-frequency-grid",
        params={"preset_id": "mode_by_input_table"},
    )
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()["data"]
    assert artifact_payload["preset_id"] == "mode_by_input_table"
    assert artifact_payload["payload"]["layout"] == {
        "rows_axis": "mode_index",
        "columns_axis": "selected_scope",
        "cell_metric": "frequency_ghz",
        "compare_axis": "member_key",
    }
    assert artifact_payload["payload"]["columns"] == [
        {"axis_value": 0.0, "label": "0", "unit": None}
    ]
    assert len(artifact_payload["payload"]["compare_groups"]) == 2
    assert {
        group["member"]["trace_id"] for group in artifact_payload["payload"]["compare_groups"]
    } == {
        "trace_local_flux_measurement",
        "trace_local_flux_preview",
    }

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


def test_local_characterization_taggings_survive_refresh() -> None:
    submitted = _submit_characterization_task()
    drain_lane_queue("characterization")

    results_response = client.get(
        "/datasets/local-dataset-001/designs/design_local_flux_playground/characterization-results"
    )
    assert results_response.status_code == 200
    result_row = results_response.json()["data"]["rows"][0]

    tagging_response = client.post(
        "/datasets/local-dataset-001/designs/design_local_flux_playground/"
        f"characterization-results/{result_row['result_id']}/taggings",
        json={
            "artifact_id": f"{result_row['result_id']}:identify-summary",
            "source_parameter": "residual_rms_max",
            "designated_metric": "residual_rms_max",
        },
    )
    assert tagging_response.status_code == 200
    tagged_metric = tagging_response.json()["data"]["tagged_metric"]

    detail_response = client.get(
        "/datasets/local-dataset-001/designs/design_local_flux_playground/"
        f"characterization-results/{result_row['result_id']}"
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["identify_surface"]["applied_tags"] == [
        {
            "artifact_id": f"{result_row['result_id']}:identify-summary",
            "source_parameter": "residual_rms_max",
            "designated_metric": "residual_rms_max",
            "designated_metric_label": "Max Residual RMS",
            "tagged_at": tagged_metric["tagged_at"],
        }
    ]

    metrics_response = client.get("/datasets/local-dataset-001/metrics-summary")
    assert metrics_response.status_code == 200
    assert {
        "metric_id": "metric-local-dataset-001-residual-rms-max",
        "label": "Max Residual RMS",
        "source_parameter": "residual_rms_max",
        "designated_metric": "residual_rms_max",
        "tagged_at": tagged_metric["tagged_at"],
    } in metrics_response.json()["data"]["rows"]

    reset_runtime_state()

    refreshed_detail = client.get(
        "/datasets/local-dataset-001/designs/design_local_flux_playground/"
        f"characterization-results/{result_row['result_id']}"
    )
    assert refreshed_detail.status_code == 200
    refreshed_task = client.get(f"/tasks/{submitted['task_id']}").json()["data"]
    assert refreshed_task["result_handoff"]["availability"] == "ready"
    assert refreshed_detail.json()["data"]["identify_surface"]["applied_tags"] == [
        {
            "artifact_id": f"{result_row['result_id']}:identify-summary",
            "source_parameter": "residual_rms_max",
            "designated_metric": "residual_rms_max",
            "designated_metric_label": "Max Residual RMS",
            "tagged_at": tagged_metric["tagged_at"],
        }
    ]


def test_local_persisted_admittance_runtime_exposes_axis_aware_sweep_contract() -> None:
    definition_id = _create_sweepable_definition("LocalAdmittanceSweepCharacterization")
    simulation_task = _submit_local_simulation(
        definition_id=definition_id,
        parameter_sweeps=[
            {
                "parameter": "Lj",
                "values": [850.0, 1000.0, 1150.0],
                "unit": "pH",
            }
        ],
    )
    assert simulation_task["status"] == "completed"

    publish_response = client.post(
        f"/tasks/{simulation_task['task_id']}/simulation-results/publish",
        json={
            "dataset_id": "local-dataset-001",
            "design_name": "Local Admittance Sweep Characterization",
        },
    )
    assert publish_response.status_code == 200
    publish_payload = publish_response.json()["data"]
    design_id = publish_payload["design"]["design_id"]
    trace_id = next(
        trace["trace_id"]
        for trace in publish_payload["traces"]
        if trace["family"] == "y_matrix" and trace["trace_mode_group"] == "base"
    )
    catalog_repository = get_catalog_repository()
    design = catalog_repository.get_design("local-dataset-001", design_id)
    assert design is not None
    trace_summary = next(
        trace
        for trace in catalog_repository.list_trace_metadata("local-dataset-001", design_id)
        if trace.trace_id == trace_id
    )
    trace_detail = catalog_repository.get_trace_detail(
        "local-dataset-001",
        design_id,
        trace_id,
    )
    assert trace_summary.available_sweep_axes == ("Lj",)
    assert trace_detail is not None

    execution_result = get_persisted_characterization_repository().run_admittance_extraction(
        CharacterizationExecutionRequest(
            task=_build_direct_characterization_task(
                dataset_id="local-dataset-001",
                design_id=design_id,
                selected_trace_ids=(trace_id,),
                fit_window=(1.0, 8.0),
                residual_tolerance=0.05,
            ),
            design=design,
            traces=(
                CharacterizationExecutionTrace(
                    summary=trace_summary,
                    detail=trace_detail,
                ),
            ),
        )
    )
    result_id = execution_result.result_summary_payload["characterization_result_id"]

    results_response = client.get(
        f"/datasets/local-dataset-001/designs/{design_id}/characterization-results"
    )
    assert results_response.status_code == 200
    result_rows = results_response.json()["data"]["rows"]
    assert any(row["result_id"] == result_id for row in result_rows)

    detail_response = client.get(
        f"/datasets/local-dataset-001/designs/{design_id}/characterization-results/{result_id}"
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["payload"]["contract_version"] == "admittance_member_phase1_v1"
    assert detail["payload"]["input_axis"]["axis_key"] == "Lj"
    assert detail["payload"]["input_axis"]["length"] == 3
    assert detail["payload"]["member_axis"]["axis_key"] == "member_key"
    assert detail["payload"]["metric"]["metric_key"] == "frequency_ghz"
    assert detail["payload"]["analysis_run_id"] == execution_result.result_refs.analysis_run_id
    assert detail["artifact_refs"][0]["view_kind"] == "preset_query"
    assert detail["artifact_refs"][0]["query_spec"]["supported_view_modes"] == [
        "table",
        "plot",
    ]

    artifact_response = client.get(
        f"/datasets/local-dataset-001/designs/{design_id}/"
        f"characterization-results/{result_id}/artifacts/"
        f"{result_id}:mode-frequency-grid",
        params={"preset_id": "mode_by_input_table"},
    )
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()["data"]
    assert artifact_payload["payload"]["layout"] == {
        "rows_axis": "mode_index",
        "columns_axis": "Lj",
        "cell_metric": "frequency_ghz",
        "compare_axis": "member_key",
    }
    assert [column["axis_value"] for column in artifact_payload["payload"]["columns"]] == [
        850.0,
        1000.0,
        1150.0,
    ]
    assert len(artifact_payload["payload"]["compare_groups"]) == 1
    assert len(artifact_payload["payload"]["cells"]) >= 1
    assert all(len(row) == 3 for row in artifact_payload["payload"]["cells"])

    mode_plot_response = client.get(
        f"/datasets/local-dataset-001/designs/{design_id}/"
        f"characterization-results/{result_id}/artifacts/"
        f"{result_id}:mode-frequency-grid",
        params={"view_mode": "plot"},
    )
    assert mode_plot_response.status_code == 200
    assert mode_plot_response.json()["data"]["preset_id"] == "mode_profile_plot"
    assert mode_plot_response.json()["data"]["payload"]["layout"] == {
        "x_axis": "mode_index",
        "y_metric": "frequency_ghz",
        "series_axis": "Lj",
        "compare_axis": "member_key",
    }

    sweep_plot_response = client.get(
        f"/datasets/local-dataset-001/designs/{design_id}/"
        f"characterization-results/{result_id}/artifacts/"
        f"{result_id}:mode-frequency-grid",
        params={"preset_id": "sweep_profile_plot"},
    )
    assert sweep_plot_response.status_code == 200
    assert sweep_plot_response.json()["data"]["payload"]["layout"] == {
        "x_axis": "Lj",
        "y_metric": "frequency_ghz",
        "series_axis": "mode_index",
        "compare_axis": "member_key",
    }

    reset_runtime_state()
    refreshed_detail = client.get(
        f"/datasets/local-dataset-001/designs/{design_id}/characterization-results/{result_id}"
    )
    assert refreshed_detail.status_code == 200
    assert refreshed_detail.json()["data"]["payload"]["input_axis"]["axis_key"] == "Lj"


def test_persisted_admittance_runtime_rejects_multiple_non_frequency_sweeps() -> None:
    trace = CharacterizationExecutionTrace(
        summary=TraceMetadataSummary(
            trace_id="trace_hfss_multi_sweep",
            dataset_id="dataset_hfss",
            design_id="design_hfss",
            family="y_matrix",
            parameter="Y11",
            representation="imaginary",
            trace_mode_group="base",
            source_kind="layout_simulation",
            stage_kind="raw",
            provenance_summary="HFSS multi-sweep grid",
        ),
        detail=TraceDetail(
            trace_id="trace_hfss_multi_sweep",
            dataset_id="dataset_hfss",
            design_id="design_hfss",
            axes=(
                TraceAxis(name="frequency", unit="GHz", length=3),
                TraceAxis(name="L_jun", unit="nH", length=2),
                TraceAxis(name="C_jun", unit="fF", length=2),
            ),
            preview_payload={"kind": "nd_grid", "values_ref": "trace_store"},
            payload_ref=None,
            result_handles=(),
        ),
    )

    with pytest.raises(ValueError, match="at most one sweep axis"):
        _materialize_trace_grid(
            trace=trace,
            trace_store=object(),
            store_ref={},
            raw_values=np.zeros((3, 2, 2), dtype=np.complex128),
        )


def test_hfss_nd_ingestion_can_run_admittance_extraction() -> None:
    created = client.post(
        "/datasets",
        json={
            "name": "HFSS Characterization Run Through",
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
            "design_name": "FloatingQubitWithXY",
            "provenance_label": "HFSS XY_and_Readout.csv",
            "traces": [
                {
                    "family": "y_matrix",
                    "parameter": "Y11",
                    "representation": "imaginary",
                    "trace_mode_group": "base",
                    "stage_kind": "raw",
                    "provenance_summary": "HFSS XY and readout branch",
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
    assert ingestion.status_code == 200
    design_id = ingestion.json()["data"]["design"]["design_id"]
    trace_id = ingestion.json()["data"]["traces"][0]["trace_id"]

    registry_response = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/characterization-analysis-registry",
        params={"selected_trace_ids": trace_id},
    )
    assert registry_response.status_code == 200
    registry_rows = {
        row["analysis_id"]: row for row in registry_response.json()["data"]["rows"]
    }
    assert registry_rows["admittance_extraction"]["availability_state"] == "recommended"

    catalog_repository = get_catalog_repository()
    design = catalog_repository.get_design(dataset_id, design_id)
    assert design is not None
    trace_summary = next(
        trace
        for trace in catalog_repository.list_trace_metadata(dataset_id, design_id)
        if trace.trace_id == trace_id
    )
    assert trace_summary.shape == (5, 2)
    assert trace_summary.available_sweep_axes == ("L_jun",)
    trace_detail = catalog_repository.get_trace_detail(dataset_id, design_id, trace_id)
    assert trace_detail is not None
    assert trace_detail.preview_payload["values_ref"] == "trace_store"
    assert trace_detail.payload_ref is not None

    # Legacy HFSS imports could persist truthful ND preview metadata while the TraceStore
    # payload was still a 1D frequency slice. Characterization must recover from the
    # embedded ND preview rather than failing before users can re-ingest.
    LocalZarrTraceStore(root_path=get_trace_store_path()).write_trace(
        design_id=1,
        batch_id=1,
        trace_id=1,
        values=1j * np.asarray([-1.0, 0.2, 1.2, 0.2, -0.5], dtype=np.float64),
        axes=(
            {
                "name": "frequency",
                "unit": "GHz",
                "values": np.asarray([4.8, 4.9, 5.0, 5.1, 5.2], dtype=np.float64),
            },
        ),
        store_key=trace_detail.payload_ref.store_key,
        payload_role="raw",
        writer_version="test.legacy_hfss_1d_payload",
    )
    trace_detail = replace(
        trace_detail,
        preview_payload={
            "kind": "nd_grid",
            "axes": [
                {"name": "frequency", "unit": "GHz", "values": [4.8, 4.9, 5.0, 5.1, 5.2]},
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
    )

    execution_result = get_persisted_characterization_repository().run_admittance_extraction(
        CharacterizationExecutionRequest(
            task=_build_direct_characterization_task(
                dataset_id=dataset_id,
                design_id=design_id,
                selected_trace_ids=(trace_id,),
                fit_window=(4.8, 5.2),
                residual_tolerance=10.0,
            ),
            design=design,
            traces=(
                CharacterizationExecutionTrace(
                    summary=trace_summary,
                    detail=trace_detail,
                ),
            ),
        )
    )
    result_id = execution_result.result_summary_payload["characterization_result_id"]
    detail_response = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/characterization-results/{result_id}"
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["payload"]["input_axis"]["axis_key"] == "L_jun"
    assert detail["payload"]["input_axis"]["length"] == 2
    assert detail["payload"]["metric"]["metric_key"] == "frequency_ghz"
    artifact_response = client.get(
        f"/datasets/{dataset_id}/designs/{design_id}/"
        f"characterization-results/{result_id}/artifacts/"
        f"{result_id}:mode-frequency-grid",
        params={"preset_id": "mode_by_input_table"},
    )
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()["data"]["payload"]
    assert [column["axis_value"] for column in artifact_payload["columns"]] == [8.0, 9.0]
    assert artifact_payload["cells"]
