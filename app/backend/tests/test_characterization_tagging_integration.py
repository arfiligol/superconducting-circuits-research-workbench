from __future__ import annotations

from datetime import datetime

import pytest
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


def test_get_characterization_result_exposes_identify_surface_fields() -> None:
    response = client.get(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/"
        "characterization-results/char-fit-flux-a-01"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["identify_surface"] == {
        "source_parameters": [
            {
                "artifact_id": "char-fit-flux-a-01:identify-summary",
                "source_parameter": "lowest_observed_frequency_ghz",
                "label": "Lowest observed frequency",
                "artifact_title": "Admittance identify summary",
                "current_designated_metric": "lowest_observed_frequency_ghz",
            },
            {
                "artifact_id": "char-fit-flux-a-01:identify-summary",
                "source_parameter": "highest_observed_frequency_ghz",
                "label": "Highest observed frequency",
                "artifact_title": "Admittance identify summary",
                "current_designated_metric": None,
            },
            {
                "artifact_id": "char-fit-flux-a-01:identify-summary",
                "source_parameter": "residual_rms_max",
                "label": "Max residual RMS",
                "artifact_title": "Admittance identify summary",
                "current_designated_metric": "residual_rms_max",
            },
        ],
        "designated_metrics": [
            {
                "metric_key": "lowest_observed_frequency_ghz",
                "label": "Lowest Observed Frequency",
            },
            {
                "metric_key": "highest_observed_frequency_ghz",
                "label": "Highest Observed Frequency",
            },
            {"metric_key": "residual_rms_max", "label": "Max Residual RMS"},
        ],
        "applied_tags": [
            {
                "artifact_id": "char-fit-flux-a-01:identify-summary",
                "source_parameter": "lowest_observed_frequency_ghz",
                "designated_metric": "lowest_observed_frequency_ghz",
                "designated_metric_label": "Lowest Observed Frequency",
                "tagged_at": "2026-03-14T11:05:00Z",
            },
            {
                "artifact_id": "char-fit-flux-a-01:identify-summary",
                "source_parameter": "residual_rms_max",
                "designated_metric": "residual_rms_max",
                "designated_metric_label": "Max Residual RMS",
                "tagged_at": "2026-03-14T11:08:00Z",
            },
        ],
    }


def test_post_characterization_taggings_applies_idempotently_and_updates_metrics_summary() -> None:
    tagging_payload = {
        "artifact_id": "artifact-resonator-temp-table",
        "source_parameter": "Qi_high_temp",
        "designated_metric": "qi_high_temp",
    }

    response = client.post(
        "/datasets/resonator-chip-002/designs/design_resonator_temp/"
        "characterization-results/char-resonator-temp-qi/taggings",
        json=tagging_payload,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    tagged_at = payload["data"]["tagged_metric"]["tagged_at"]
    datetime.fromisoformat(tagged_at.replace("Z", "+00:00"))
    assert payload["data"] == {
        "tagging_status": "applied",
        "dataset_id": "resonator-chip-002",
        "design_id": "design_resonator_temp",
        "result_id": "char-resonator-temp-qi",
        "artifact_id": "artifact-resonator-temp-table",
        "source_parameter": "Qi_high_temp",
        "designated_metric": "qi_high_temp",
        "tagged_metric": {
            "metric_id": "metric-resonator-chip-002-qi-high-temp",
            "label": "High Temperature Qi",
            "source_parameter": "Qi_high_temp",
            "designated_metric": "qi_high_temp",
            "tagged_at": tagged_at,
        },
    }

    detail_response = client.get(
        "/datasets/resonator-chip-002/designs/design_resonator_temp/"
        "characterization-results/char-resonator-temp-qi"
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["data"]["identify_surface"]["applied_tags"] == [
        {
            "artifact_id": "artifact-resonator-temp-table",
            "source_parameter": "Qi_high_temp",
            "designated_metric": "qi_high_temp",
            "designated_metric_label": "High Temperature Qi",
            "tagged_at": tagged_at,
        }
    ]
    assert detail_payload["data"]["identify_surface"]["source_parameters"] == [
        {
            "artifact_id": "artifact-resonator-temp-table",
            "source_parameter": "Qi_low_temp",
            "label": "Qi low temp",
            "artifact_title": "Quality factor table",
            "current_designated_metric": None,
        },
        {
            "artifact_id": "artifact-resonator-temp-table",
            "source_parameter": "Qi_high_temp",
            "label": "Qi high temp",
            "artifact_title": "Quality factor table",
            "current_designated_metric": "qi_high_temp",
        },
    ]

    metrics_response = client.get("/datasets/resonator-chip-002/metrics-summary")
    assert metrics_response.status_code == 200
    metrics_payload = metrics_response.json()
    assert metrics_payload["ok"] is True
    assert metrics_payload["data"]["rows"] == [
        {
            "metric_id": "metric-resonator-chip-002-qi-high-temp",
            "label": "High Temperature Qi",
            "source_parameter": "Qi_high_temp",
            "designated_metric": "qi_high_temp",
            "tagged_at": tagged_at,
        }
    ]

    repeat_response = client.post(
        "/datasets/resonator-chip-002/designs/design_resonator_temp/"
        "characterization-results/char-resonator-temp-qi/taggings",
        json=tagging_payload,
    )
    assert repeat_response.status_code == 200
    repeat_payload = repeat_response.json()
    assert repeat_payload["ok"] is True
    assert repeat_payload["data"]["tagging_status"] == "already_applied"
    assert repeat_payload["data"]["tagged_metric"]["metric_id"] == (
        "metric-resonator-chip-002-qi-high-temp"
    )
    assert repeat_payload["data"]["tagged_metric"]["tagged_at"] == tagged_at


def test_post_characterization_taggings_rejects_validation_errors() -> None:
    response = client.post(
        "/datasets/resonator-chip-002/designs/design_resonator_temp/"
        "characterization-results/char-resonator-temp-qi/taggings",
        json={
            "artifact_id": "",
            "source_parameter": "Qi_high_temp",
            "designated_metric": "qi_high_temp",
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "request_validation_failed"
    assert payload["error"]["category"] == "validation_error"
    assert payload["error"]["retryable"] is False


def test_post_characterization_taggings_rejects_conflicts() -> None:
    response = client.post(
        "/datasets/fluxonium-2025-031/designs/design_flux_scan_a/"
        "characterization-results/char-fit-flux-a-01/taggings",
        json={
            "artifact_id": "char-fit-flux-a-01:identify-summary",
            "source_parameter": "highest_observed_frequency_ghz",
            "designated_metric": "lowest_observed_frequency_ghz",
        },
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "tagging_conflict"
    assert payload["error"]["category"] == "conflict"
    assert payload["error"]["retryable"] is False
