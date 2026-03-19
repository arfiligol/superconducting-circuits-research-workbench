import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from src.app.domain.audit import AuditRecord
from src.app.infrastructure.audit_store import create_audit_engine
from src.app.infrastructure.persistence.database import create_metadata_engine
from src.app.infrastructure.runtime import get_task_audit_repository, reset_runtime_state
from src.app.main import app
from src.app.settings import get_settings

client = TestClient(app)

_AUDIT_DEFINITION_SOURCE = """{
    "name": "AuditDefinition",
    "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
        {"name": "C1", "default": 100.0, "unit": "fF"}
    ],
    "topology": [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("C1", "1", "0", "C1")
    ]
}"""


@pytest.fixture(autouse=True)
def clear_session_cookies() -> None:
    reset_runtime_state()
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
def enter_online_owner_session() -> None:
    _login()


def _characterization_task_payload() -> dict[str, object]:
    return {
        "kind": "characterization",
        "characterization_setup": {
            "design_id": "design_flux_scan_a",
            "analysis_id": "admittance_extraction",
            "selected_trace_ids": [
                "trace_flux_a_measurement",
                "trace_flux_a_layout",
            ],
            "analysis_config": {
                "fit_window": [5.7, 5.9],
                "residual_tolerance": 0.01,
            },
        },
    }


def test_audit_list_returns_workspace_scoped_rows_and_meta() -> None:
    client.post("/tasks", json=_characterization_task_payload())
    client.post("/tasks/301/cancel")

    response = client.get("/audit-logs?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    action_kinds = [row["action_kind"] for row in payload["data"]["rows"]]
    assert action_kinds[:2] == [
        "task.cancel_requested",
        "task.submitted",
    ]
    assert "auth.login_succeeded" in action_kinds
    assert payload["data"]["rows"][0]["workspace_id"] == "ws-device-lab"
    assert payload["data"]["rows"][0]["actor_summary"] == {
        "user_id": "researcher-01",
        "display_name": "Rewrite Local User",
    }
    assert payload["meta"]["limit"] == 10
    assert payload["meta"]["filter_echo"]["workspace_id"] == "ws-device-lab"


def test_audit_list_supports_filters_and_cursor_navigation() -> None:
    client.post("/tasks", json=_characterization_task_payload())
    client.post("/tasks/301/cancel")
    client.post("/tasks/301/terminate")

    first_page = client.get("/audit-logs?limit=1")
    assert first_page.status_code == 200
    first_row = first_page.json()["data"]["rows"][0]

    filtered = client.get("/audit-logs?action_kind=task.cancel_requested&resource_kind=task")
    assert filtered.status_code == 200
    assert [row["action_kind"] for row in filtered.json()["data"]["rows"]] == [
        "task.cancel_requested"
    ]

    second_page = client.get(f"/audit-logs?limit=2&after={first_row['audit_id']}")
    assert second_page.status_code == 200
    assert [row["action_kind"] for row in second_page.json()["data"]["rows"]] == [
        "task.cancel_requested",
        "task.submitted",
    ]


def test_audit_detail_returns_redacted_payload() -> None:
    repository = get_task_audit_repository()
    repository.append(
        AuditRecord(
            audit_id="audit:manual:redaction",
            occurred_at="2026-03-16T09:00:00Z",
            actor_user_id="researcher-01",
            actor_display_name="Rewrite Local User",
            session_id="rewrite-local-session",
            correlation_id="corr:redaction",
            workspace_id="ws-device-lab",
            action_kind="task.submitted",
            resource_kind="task",
            resource_id="999",
            outcome="accepted",
            payload={
                "safe_field": "visible",
                "api_token": "secret-value",
                "nested": {"password": "secret", "safe_nested": "kept"},
            },
            debug_ref="debug:redaction",
        )
    )

    response = client.get("/audit-logs/audit:manual:redaction")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["correlation_id"] == "corr:redaction"
    assert payload["data"]["debug_ref"] == "debug:redaction"
    assert payload["data"]["payload"] == {
        "safe_field": "visible",
        "api_token": "[redacted]",
        "nested": {"password": "[redacted]", "safe_nested": "kept"},
    }


def test_audit_export_summary_returns_read_surface() -> None:
    client.post("/tasks", json=_characterization_task_payload())

    response = client.get("/audit-logs/export-summary?action_kind=task.submitted")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["status"] == "completed"
    assert payload["data"]["workspace_id"] == "ws-device-lab"
    assert payload["data"]["filter_echo"] == {
        "workspace_id": "ws-device-lab",
        "actor_user_id": None,
        "action_kind": "task.submitted",
        "resource_kind": None,
        "outcome": None,
    }
    assert payload["data"]["artifact_ref"]["backend"] == "audit_export_preview"


def test_audit_query_denies_member_without_governance_permission() -> None:
    _login()
    switch_response = client.patch(
        "/session/active-workspace", json={"workspace_id": "ws-modeling"}
    )
    assert switch_response.status_code == 200

    response = client.get("/audit-logs")

    assert response.status_code == 403
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "audit_access_denied"

    export_response = client.get("/audit-logs/export-summary")
    assert export_response.status_code == 403
    assert export_response.json()["error"]["code"] == "audit_export_denied"


def test_audit_query_denies_cross_workspace_access_for_non_admin() -> None:
    client.post("/tasks", json=_characterization_task_payload())

    response = client.get("/audit-logs?workspace_id=ws-modeling")

    assert response.status_code == 403
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "audit_access_denied"


def test_audit_detail_returns_not_found_for_missing_record() -> None:
    response = client.get("/audit-logs/audit:missing")

    assert response.status_code == 404
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "audit_record_not_found"


def test_audit_query_rejects_invalid_cursor_combination() -> None:
    response = client.get("/audit-logs?after=audit-1&before=audit-2")

    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "audit_query_invalid"


def test_audit_store_uses_separate_sqlite_database() -> None:
    client.post("/tasks", json=_characterization_task_payload())

    metadata_tables = inspect(
        create_metadata_engine(get_settings().database_path)
    ).get_table_names()
    audit_tables = inspect(
        create_audit_engine(get_settings().audit_database_path)
    ).get_table_names()

    assert "audit_log_records" not in metadata_tables
    assert "audit_log_records" in audit_tables


def test_resource_lifecycle_audit_rows_are_queryable() -> None:
    dataset_detail = client.get("/datasets/fluxonium-2025-031/profile")
    assert dataset_detail.status_code == 200
    dataset_response = client.patch(
        "/datasets/fluxonium-2025-031/profile",
        json={
            "device_type": dataset_detail.json()["data"]["device_type"],
            "source": "Audit profile update proof.",
            "capabilities": dataset_detail.json()["data"]["capabilities"],
        },
    )
    assert dataset_response.status_code == 200

    create_definition = client.post(
        "/circuit-definitions",
        json={
            "name": "Audit Definition",
            "source_text": _AUDIT_DEFINITION_SOURCE,
        },
    )
    assert create_definition.status_code == 201
    definition_id = create_definition.json()["data"]["definition"]["definition_id"]
    publish_definition = client.post(f"/circuit-definitions/{definition_id}/publish")
    assert publish_definition.status_code == 200

    dataset_audit = client.get(
        "/audit-logs?action_kind=dataset.profile_updated&resource_kind=dataset"
    )
    assert dataset_audit.status_code == 200
    assert dataset_audit.json()["data"]["rows"][0]["resource_id"] == "fluxonium-2025-031"

    definition_audit = client.get(
        "/audit-logs?action_kind=definition.published&resource_kind=definition"
    )
    assert definition_audit.status_code == 200
    assert definition_audit.json()["data"]["rows"][0]["resource_id"] == str(definition_id)
