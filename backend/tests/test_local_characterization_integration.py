from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from src.app.infrastructure.persistence.database import create_metadata_session_factory
from src.app.infrastructure.persistence.models import RewriteTraceCapabilityRecord
from src.app.infrastructure.runtime import reset_runtime_state
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


def _metadata_session_factory():
    return create_metadata_session_factory(get_settings().database_path)


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
    ingestion = client.post(
        f"/datasets/{dataset_id}/ingestions",
        json={
            "kind": "layout_simulation",
            "design_id": "design_floatingqubitwithxy",
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
    assert payload["data"]["rows"] == [
        {
            "analysis_id": "admittance_extraction",
            "label": "Admittance Resonance Extraction",
            "availability_state": "recommended",
            "required_config_fields": ["fit_window", "residual_tolerance"],
            "trace_compatibility": {
                "matched_trace_count": 2,
                "selected_trace_count": 2,
                "recommended_trace_modes": ["base"],
                "summary": (
                    "2 selected traces are eligible for admittance resonance extraction."
                ),
            },
        },
        {
            "analysis_id": "sideband_comparison",
            "label": "Sideband Comparison",
            "availability_state": "unavailable",
            "required_config_fields": ["comparison_window"],
            "trace_compatibility": {
                "matched_trace_count": 0,
                "selected_trace_count": 2,
                "recommended_trace_modes": ["sideband"],
                "summary": (
                    "2 selected traces are not eligible for sideband comparison "
                    "because Requires sideband trace mode coverage."
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
                    "2 selected traces are not eligible for junction parameter "
                    "identification because Requires complex representation."
                ),
            },
        },
        {
            "analysis_id": "screening_summary",
            "label": "Screening Summary",
            "availability_state": "unavailable",
            "required_config_fields": ["screening_mode"],
            "trace_compatibility": {
                "matched_trace_count": 0,
                "selected_trace_count": 2,
                "recommended_trace_modes": ["base"],
                "summary": (
                    "2 selected traces are not eligible for screening summary "
                    "because Requires s matrix traces."
                ),
            },
        },
    ]


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
        row
        for row in trace_response.json()["data"]["rows"]
        if row["trace_id"] == trace_id
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
        row
        for row in trace_response.json()["data"]["rows"]
        if row["trace_id"] == trace_id
    )
    assert trace_row["analysis_capabilities"] != []
    assert any(
        capability["analysis_id"] == "admittance_extraction"
        for capability in trace_row["analysis_capabilities"]
    )

    assert registry_response.status_code == 200
    assert registry_response.json()["data"]["rows"] == [
        {
            "analysis_id": "admittance_extraction",
            "label": "Admittance Resonance Extraction",
            "availability_state": "recommended",
            "required_config_fields": ["fit_window", "residual_tolerance"],
            "trace_compatibility": {
                "matched_trace_count": 1,
                "selected_trace_count": 1,
                "recommended_trace_modes": ["base"],
                "summary": (
                    "1 selected trace is eligible for admittance resonance extraction."
                ),
            },
        }
    ]
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
        item
        for item in response.json()["data"]["processors"]
        if item["lane"] == "characterization"
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
    assert task["characterization_setup"]["selected_trace_ids"] == [
        "trace_local_flux_measurement"
    ]


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
    assert detail["characterization_setup"] == _characterization_payload()[
        "characterization_setup"
    ]
    assert isinstance(detail["result_refs"]["analysis_run_id"], int)
    assert detail["result_refs"]["analysis_run_id"] > 0
    assert detail["result_refs"]["trace_payload"]["payload_role"] == "analysis_projection"
    assert detail["result_refs"]["result_handles"][0]["handle_id"] == (
        f"analysis-run:{detail['result_refs']['analysis_run_id']}:report"
    )
    assert detail["result_refs"]["result_handles"][0]["kind"] == "characterization_report"
    assert detail["result_refs"]["result_handles"][0]["status"] == "materialized"


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
    assert detail["payload"]["fit_table"][0]["parameter"] == "f01"
    assert detail["artifact_refs"][0]["payload_locator"] == (
        f"characterization/{result_row['result_id']}/fit-table.json"
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
            "artifact_id": f"{result_row['result_id']}:fit-table",
            "source_parameter": "residual_rms",
            "designated_metric": "residual_rms",
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
            "artifact_id": f"{result_row['result_id']}:fit-table",
            "source_parameter": "residual_rms",
            "designated_metric": "residual_rms",
            "designated_metric_label": "Residual RMS",
            "tagged_at": tagged_metric["tagged_at"],
        }
    ]

    metrics_response = client.get("/datasets/local-dataset-001/metrics-summary")
    assert metrics_response.status_code == 200
    assert {
        "metric_id": "metric-local-dataset-001-residual-rms",
        "label": "Residual RMS",
        "source_parameter": "residual_rms",
        "designated_metric": "residual_rms",
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
            "artifact_id": f"{result_row['result_id']}:fit-table",
            "source_parameter": "residual_rms",
            "designated_metric": "residual_rms",
            "designated_metric_label": "Residual RMS",
            "tagged_at": tagged_metric["tagged_at"],
        }
    ]
