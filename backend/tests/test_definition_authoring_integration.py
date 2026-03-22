import pytest
from fastapi.testclient import TestClient
from src.app.infrastructure.runtime import reset_runtime_state
from src.app.main import app
from tests.worker_runtime_harness import drain_lane_queue

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


def _sample_definition_source(circuit_name: str) -> str:
    return (
        "{\n"
        f'  "name": "{circuit_name}",\n'
        '  "components": [\n'
        '    {"name": "R1", "default": 50.0, "unit": "Ohm"},\n'
        '    {"name": "C1", "default": 100.0, "unit": "fF"},\n'
        '    {"name": "Lj1", "default": 1000.0, "unit": "pH"}\n'
        "  ],\n"
        '  "topology": [\n'
        '    ["P1", "1", "0", 1],\n'
        '    ["R1", "1", "0", "R1"],\n'
        '    ["C1", "1", "2", "C1"],\n'
        '    ["Lj1", "2", "0", "Lj1"]\n'
        "  ]\n"
        "}"
    )


def _simulation_setup_payload() -> dict[str, object]:
    return {
        "frequency_sweep": {
            "start_ghz": 4.0,
            "stop_ghz": 8.0,
            "point_count": 401,
            "spacing": "linear",
        },
        "parameter_sweeps": [],
        "solver": {
            "solver_family": "hfss-hb",
            "max_iterations": 40,
            "convergence_tolerance": 1e-6,
            "harmonic_balance": {
                "enabled": True,
                "harmonic_count": 7,
                "oversample_factor": 3,
            },
        },
        "sources": [
            {
                "source_id": "drive-port-a",
                "kind": "port_drive",
                "target": "port_1",
                "amplitude": -35.0,
                "frequency_ghz": 6.45,
                "phase_deg": 0.0,
            }
        ],
    }


def test_definition_authoring_catalog_to_editor_save_update_round_trip() -> None:
    catalog_response = client.get("/circuit-definitions")

    assert catalog_response.status_code == 200
    catalog_payload = catalog_response.json()
    assert catalog_payload["ok"] is True
    catalog_rows = catalog_payload["data"]["rows"]
    assert len(catalog_rows) == 3
    assert set(catalog_rows[0]) == {
        "allowed_actions",
        "created_at",
        "definition_id",
        "name",
        "owner_display_name",
        "visibility_scope",
    }

    detail_response = client.get(f"/circuit-definitions/{catalog_rows[0]['definition_id']}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["ok"] is True
    original_detail = detail_payload["data"]
    assert original_detail["definition_id"] == catalog_rows[0]["definition_id"]
    assert original_detail["allowed_actions"]["update"] is True
    assert len(original_detail["preview_artifacts"]) == 3
    assert set(original_detail["validation_summary"]) == {
        "status",
        "notice_count",
        "warning_count",
        "blocking_notice_count",
    }
    assert original_detail["validation_summary"]["status"] in {"valid", "warning", "invalid"}

    created_response = client.post(
        "/circuit-definitions",
        json={
            "name": "RewriteDefinitionAuthoringSmoke",
            "source_text": _sample_definition_source("rewrite_definition_authoring_smoke"),
        },
    )

    assert created_response.status_code == 201
    created_payload = created_response.json()
    assert created_payload["ok"] is True
    created_detail = created_payload["data"]["definition"]
    created_definition_id = int(created_detail["definition_id"])
    assert created_payload["data"]["operation"] == "created"
    assert created_detail["name"] == "RewriteDefinitionAuthoringSmoke"
    assert created_detail["source_text"] == _sample_definition_source(
        "rewrite_definition_authoring_smoke"
    ).rstrip()
    assert "rewrite_definition_authoring_smoke" in created_detail["normalized_output"]
    assert len(created_detail["preview_artifacts"]) >= 1

    created_detail_response = client.get(f"/circuit-definitions/{created_definition_id}")
    assert created_detail_response.status_code == 200
    created_detail_payload = created_detail_response.json()
    assert created_detail_payload["ok"] is True
    assert created_detail_payload["data"] == created_detail

    updated_response = client.put(
        f"/circuit-definitions/{created_definition_id}",
        json={
            "name": "RewriteDefinitionAuthoringSmokeV2",
            "source_text": _sample_definition_source("rewrite_definition_authoring_smoke_v2"),
        },
    )

    assert updated_response.status_code == 200
    updated_payload = updated_response.json()
    assert updated_payload["ok"] is True
    updated_detail = updated_payload["data"]["definition"]
    assert updated_payload["data"]["operation"] == "updated"
    assert updated_detail["name"] == "RewriteDefinitionAuthoringSmokeV2"
    assert updated_detail["source_text"] == _sample_definition_source(
        "rewrite_definition_authoring_smoke_v2"
    ).rstrip()
    assert "rewrite_definition_authoring_smoke_v2" in updated_detail["normalized_output"]
    assert updated_detail["validation_summary"]["status"] in {"valid", "warning", "invalid"}
    assert updated_detail["preview_artifacts"] == created_detail["preview_artifacts"]

    refreshed_catalog_response = client.get(
        "/circuit-definitions?sort_by=created_at&sort_order=desc"
    )
    assert refreshed_catalog_response.status_code == 200
    refreshed_catalog_payload = refreshed_catalog_response.json()
    assert refreshed_catalog_payload["ok"] is True
    refreshed_catalog_rows = refreshed_catalog_payload["data"]["rows"]
    assert refreshed_catalog_rows[0]["definition_id"] == created_definition_id
    assert refreshed_catalog_rows[0]["name"] == "RewriteDefinitionAuthoringSmokeV2"
    assert "source_text" not in refreshed_catalog_rows[0]
    assert "normalized_output" not in refreshed_catalog_rows[0]


def test_local_definition_persists_across_runtime_reset_and_can_submit_simulation_task() -> None:
    switch_response = client.patch("/session/runtime-mode", json={"runtime_mode": "local"})
    assert switch_response.status_code == 200

    create_response = client.post(
        "/circuit-definitions",
        json={
            "name": "PersistedLocalDefinition",
            "source_text": _sample_definition_source("PersistedLocalDefinition"),
        },
    )

    assert create_response.status_code == 201
    created_detail = create_response.json()["data"]["definition"]
    definition_id = int(created_detail["definition_id"])

    reset_runtime_state()
    client.cookies.clear()

    switched_local = client.patch("/session/runtime-mode", json={"runtime_mode": "local"})
    assert switched_local.status_code == 200

    detail_response = client.get(f"/circuit-definitions/{definition_id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()["data"]
    assert detail_payload["definition_id"] == definition_id
    assert detail_payload["name"] == "PersistedLocalDefinition"

    submit_response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "definition_id": definition_id,
            "simulation_setup": _simulation_setup_payload(),
        },
    )

    assert submit_response.status_code == 201
    task = submit_response.json()["data"]["task"]
    assert task["definition_id"] == definition_id
    assert task["status"] == "queued"
    assert task["dispatch"]["status"] == "accepted"

    drain_lane_queue("simulation")

    completed = client.get(f"/tasks/{task['task_id']}").json()["data"]
    assert completed["definition_id"] == definition_id
    assert completed["status"] == "completed"
