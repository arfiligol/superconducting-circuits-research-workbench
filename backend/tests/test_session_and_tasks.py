from contextlib import contextmanager
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from src.app.domain.tasks import TaskLifecycleUpdate, TaskSubmissionDraft
from src.app.infrastructure.runtime import (
    get_rewrite_app_state_repository,
    get_rewrite_catalog_repository,
    get_task_audit_repository,
    get_task_execution_runtime,
    get_task_service,
    reset_runtime_state,
)
from src.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_app_state() -> None:
    reset_runtime_state()
    client.cookies.clear()


def _login(test_client: TestClient = client) -> dict[str, object]:
    switch_response = test_client.patch(
        "/session/runtime-mode",
        json={
            "runtime_mode": "online",
            "server_origin": "http://127.0.0.1:8000",
            "label": "Default Rewrite Server",
        },
    )
    assert switch_response.status_code == 200
    response = test_client.post(
        "/session/login",
        json={
            "email": "rewrite.local@example.com",
            "password": "rewrite-local-password",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    return payload["data"]


def _simulation_ptc_payload(
    *,
    enabled: bool = True,
    mode: str = "auto",
    compensate_ports: tuple[str, ...] = ("port_1", "port_2"),
) -> dict[str, object]:
    return {
        "enabled": enabled,
        "mode": mode,
        "compensate_ports": list(compensate_ports),
    }


def _simulation_setup_payload(
    *,
    ptc: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "frequency_sweep": {
            "start_ghz": 4.0,
            "stop_ghz": 8.0,
            "point_count": 401,
            "spacing": "linear",
        },
        "parameter_sweeps": [
            {
                "parameter": "junction.inductance_lj",
                "values": [8.4, 8.6, 8.8],
                "unit": "nH",
            }
        ],
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
                "target": "port_A",
                "amplitude": -35.0,
                "frequency_ghz": 6.45,
                "phase_deg": 0.0,
            }
        ],
        "ptc": ptc,
    }


def _post_processing_setup_payload() -> dict[str, object]:
    return {
        "output_view": "fit-report",
        "selections": [
            {
                "trace_family": "s_matrix",
                "representation": "db",
                "design_id": "design-alpha",
                "trace_ids": ["trace-s11-raw"],
            }
        ],
        "operations": [
            {
                "operation": "fit_resonance",
                "enabled": True,
                "config": {
                    "model": "hanger",
                    "window_ghz": [6.2, 6.7],
                },
            }
        ],
    }


@contextmanager
def _bind_client_app_context(test_client: TestClient):
    app_context_id = test_client.cookies.get("sc_app_context")
    assert app_context_id is not None
    repository = get_rewrite_app_state_repository()
    binding = repository.bind_request_app_context_id(app_context_id)
    try:
        yield
    finally:
        repository.reset_request_app_context_id(binding)


def test_get_session_returns_local_space_baseline_without_cookie() -> None:
    response = client.get("/session")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    session = payload["data"]
    assert session["session_id"] == "local-session"
    assert session["runtime_mode"] == "local"
    assert session["auth"] == {
        "state": "local_bypass",
        "mode": "local_bypass",
        "reason": None,
    }
    assert session["connection"]["target"] is None
    assert session["user"] == {
        "id": "local-operator",
        "display_name": "Local Operator",
        "email": None,
        "platform_role": "user",
    }
    assert session["workspace"]["id"] == "local-space"
    assert session["workspace"]["name"] == "Local Space"
    assert session["workspace"]["role"] == "owner"
    assert session["workspace"]["default_task_scope"] == "local"
    assert len(session["workspace"]["memberships"]) == 1
    assert session["active_dataset"]["id"] == "local-dataset-001"
    assert session["active_dataset"]["visibility_scope"] == "local"
    assert session["capabilities"] == {
        "can_switch_runtime_mode": True,
        "can_switch_workspace": False,
        "can_switch_dataset": True,
        "can_import_datasets": True,
        "can_export_datasets": True,
        "can_invite_members": False,
        "can_remove_members": False,
        "can_transfer_workspace_owner": False,
        "can_leave_workspace": False,
        "can_submit_tasks": True,
        "can_cancel_local_tasks": True,
        "can_terminate_local_tasks": True,
        "can_retry_local_tasks": True,
        "can_manage_workspace_tasks": False,
        "can_cancel_own_tasks": False,
        "can_cancel_workspace_tasks": False,
        "can_terminate_workspace_tasks": False,
        "can_retry_own_tasks": False,
        "can_retry_workspace_tasks": False,
        "can_manage_definitions": True,
        "can_publish_definitions": False,
        "can_manage_datasets": True,
        "can_view_audit_logs": False,
    }
    assert payload["meta"]["memberships_count"] == 1


def test_login_returns_canonical_authenticated_workspace_surface() -> None:
    session = _login()

    assert session["runtime_mode"] == "online"
    assert session["connection"]["target"]["origin"] == "http://127.0.0.1:8000"
    assert session["auth"] == {
        "state": "authenticated",
        "mode": "jwt_refresh_cookie",
        "reason": None,
    }
    assert session["user"] == {
        "id": "researcher-01",
        "display_name": "Rewrite Local User",
        "email": "rewrite.local@example.com",
        "platform_role": "user",
    }
    assert session["workspace"]["id"] == "ws-device-lab"
    assert session["workspace"]["role"] == "owner"
    assert session["workspace"]["default_task_scope"] == "workspace"
    assert len(session["workspace"]["memberships"]) == 2
    assert session["workspace"]["memberships"][0]["is_active"] is True
    assert session["active_dataset"]["id"] == "fluxonium-2025-031"
    assert session["capabilities"] == {
        "can_switch_runtime_mode": True,
        "can_switch_workspace": True,
        "can_switch_dataset": True,
        "can_import_datasets": True,
        "can_export_datasets": True,
        "can_invite_members": True,
        "can_remove_members": True,
        "can_transfer_workspace_owner": True,
        "can_leave_workspace": False,
        "can_submit_tasks": True,
        "can_cancel_local_tasks": False,
        "can_terminate_local_tasks": False,
        "can_retry_local_tasks": False,
        "can_manage_workspace_tasks": True,
        "can_cancel_own_tasks": True,
        "can_cancel_workspace_tasks": True,
        "can_terminate_workspace_tasks": True,
        "can_retry_own_tasks": True,
        "can_retry_workspace_tasks": True,
        "can_manage_definitions": True,
        "can_publish_definitions": True,
        "can_manage_datasets": True,
        "can_view_audit_logs": True,
    }

    follow_up = client.get("/session")
    assert follow_up.status_code == 200
    assert follow_up.json()["data"]["auth"]["state"] == "authenticated"


def test_login_rejects_invalid_credentials() -> None:
    switch_response = client.patch(
        "/session/runtime-mode",
        json={"runtime_mode": "online", "server_origin": "http://127.0.0.1:8000"},
    )
    assert switch_response.status_code == 200
    response = client.post(
        "/session/login",
        json={
            "email": "rewrite.local@example.com",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "auth_invalid_credentials"
    session = client.get("/session").json()["data"]
    assert session["runtime_mode"] == "online"
    assert session["auth"]["state"] == "anonymous"


def test_logout_clears_session_continuity() -> None:
    _login()

    response = client.post("/session/logout")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["runtime_mode"] == "online"
    assert payload["data"]["auth"] == {
        "state": "anonymous",
        "mode": "jwt_refresh_cookie",
        "reason": None,
    }
    assert payload["data"]["user"] is None
    assert client.get("/session").json()["data"]["auth"]["state"] == "anonymous"


def test_patch_session_active_workspace_rebinds_dataset_and_capabilities() -> None:
    _login()
    response = client.patch("/session/active-workspace", json={"workspace_id": "ws-modeling"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["workspace"]["id"] == "ws-modeling"
    assert payload["data"]["active_dataset_resolution"] == "rebound"
    assert payload["data"]["active_dataset"]["id"] == "transmon-coupler-014"
    assert payload["data"]["detached_task_ids"] == [301, 302, 303]
    assert payload["data"]["capabilities"]["can_invite_members"] is False
    assert payload["data"]["workspace"]["memberships"][1]["is_active"] is True


def test_patch_session_active_dataset_rejects_dataset_outside_workspace() -> None:
    _login()
    response = client.patch("/session/active-dataset", json={"dataset_id": "transmon-coupler-014"})

    assert response.status_code == 403
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "dataset_not_visible_in_workspace"
    assert response.json()["error"]["category"] == "permission_denied"


def test_patch_session_active_dataset_can_clear_context() -> None:
    _login()
    response = client.patch("/session/active-dataset", json={"dataset_id": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["active_dataset"] is None
    assert payload["data"]["capabilities"]["can_switch_dataset"] is True


def test_session_mutations_require_authenticated_session() -> None:
    switch_response = client.patch(
        "/session/runtime-mode",
        json={"runtime_mode": "online", "server_origin": "http://127.0.0.1:8000"},
    )
    assert switch_response.status_code == 200
    response = client.patch("/session/active-dataset", json={"dataset_id": None})

    assert response.status_code == 401
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "auth_required"
    assert response.json()["error"]["category"] == "auth_required"


def test_get_session_returns_degraded_when_continuity_cannot_be_restored() -> None:
    _login()
    reset_runtime_state()

    response = client.get("/session")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["runtime_mode"] == "local"
    assert payload["data"]["auth"] == {
        "state": "local_bypass",
        "mode": "local_bypass",
        "reason": None,
    }
    assert payload["data"]["workspace"]["id"] == "local-space"
    assert payload["data"]["capabilities"]["can_submit_tasks"] is True


def test_session_mutations_reject_degraded_continuity() -> None:
    _login()
    reset_runtime_state()

    response = client.patch("/session/active-dataset", json={"dataset_id": None})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["runtime_mode"] == "local"
    assert payload["active_dataset"] is None


def test_get_session_requires_context_rebind_when_active_dataset_is_archived() -> None:
    _login()
    catalog_repository = get_rewrite_catalog_repository()
    catalog_repository.set_dataset_lifecycle_state("fluxonium-2025-031", "archived")

    response = client.get("/session")

    assert response.status_code == 409
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "context_rebind_required"
    assert response.json()["error"]["category"] == "conflict"


def test_switch_workspace_can_clear_active_dataset_when_target_has_no_visible_dataset() -> None:
    _login()
    catalog_repository = get_rewrite_catalog_repository()
    catalog_repository.set_dataset_lifecycle_state("transmon-coupler-014", "archived")

    response = client.patch("/session/active-workspace", json={"workspace_id": "ws-modeling"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["active_dataset_resolution"] == "cleared"
    assert payload["data"]["active_dataset"] is None
    assert payload["data"]["workspace"]["id"] == "ws-modeling"


def test_switch_workspace_rejects_missing_membership() -> None:
    _login()
    response = client.patch("/session/active-workspace", json={"workspace_id": "ws-missing"})

    assert response.status_code == 403
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "workspace_membership_required"


def test_session_rebind_after_member_removal_does_not_keep_old_workspace_dataset() -> None:
    _login()
    repository = get_rewrite_app_state_repository()

    assert repository.remove_workspace_member("ws-device-lab", "researcher-01") is True

    response = client.get("/session")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["workspace"]["id"] == "ws-modeling"
    assert payload["active_dataset"]["id"] == "transmon-coupler-014"
    assert payload["active_dataset"]["workspace_id"] == "ws-modeling"


def test_runtime_mode_switch_rejects_unreachable_online_target() -> None:
    response = client.patch(
        "/session/runtime-mode",
        json={"runtime_mode": "online", "server_origin": "http://offline.invalid:8000"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "target_unreachable"
    follow_up = client.get("/session").json()["data"]
    assert follow_up["runtime_mode"] == "local"
    assert follow_up["auth"]["state"] == "local_bypass"


def test_runtime_mode_switch_resets_remote_auth_and_rebuilds_online_context() -> None:
    _login()

    switched_local = client.patch("/session/runtime-mode", json={"runtime_mode": "local"})
    assert switched_local.status_code == 200
    local_payload = switched_local.json()["data"]
    assert local_payload["runtime_mode"] == "local"
    assert local_payload["auth_transition"] == "entered_local_bypass"

    switched_online = client.patch(
        "/session/runtime-mode",
        json={"runtime_mode": "online", "server_origin": "http://127.0.0.1:8000"},
    )
    assert switched_online.status_code == 200
    online_payload = switched_online.json()["data"]
    assert online_payload["runtime_mode"] == "online"
    assert online_payload["auth"]["state"] == "anonymous"
    assert online_payload["auth_transition"] == "online_auth_required"
    assert online_payload["session_reset"] is True
    assert online_payload["detached_task_ids"] == [300]

    follow_up = client.get("/session").json()["data"]
    assert follow_up["runtime_mode"] == "online"
    assert follow_up["auth"]["state"] == "anonymous"


def test_runtime_mode_switch_is_isolated_per_client_context() -> None:
    with TestClient(app) as client_a, TestClient(app) as client_b:
        _login(client_a)
        _login(client_b)

        switch_local = client_a.patch("/session/runtime-mode", json={"runtime_mode": "local"})

        assert switch_local.status_code == 200
        session_a = client_a.get("/session").json()["data"]
        session_b = client_b.get("/session").json()["data"]
        assert session_a["runtime_mode"] == "local"
        assert session_a["workspace"]["name"] == "Local Space"
        assert session_b["runtime_mode"] == "online"
        assert session_b["auth"]["state"] == "authenticated"
        assert session_b["workspace"]["id"] == "ws-device-lab"


def test_runtime_mode_switch_only_resets_caller_authenticated_session() -> None:
    with TestClient(app) as client_a, TestClient(app) as client_b:
        _login(client_a)
        _login(client_b)

        switched_local = client_a.patch("/session/runtime-mode", json={"runtime_mode": "local"})
        assert switched_local.status_code == 200
        switched_online = client_a.patch(
            "/session/runtime-mode",
            json={"runtime_mode": "online", "server_origin": "http://127.0.0.1:8000"},
        )

        assert switched_online.status_code == 200
        session_a = client_a.get("/session").json()["data"]
        assert session_a["runtime_mode"] == "online"
        assert session_a["auth"]["state"] == "anonymous"

        dataset_switch = client_b.patch("/session/active-dataset", json={"dataset_id": None})
        assert dataset_switch.status_code == 200
        assert dataset_switch.json()["data"]["auth"]["state"] == "authenticated"
        assert client_b.get("/session").json()["data"]["auth"]["state"] == "authenticated"


def test_queue_visibility_remains_mode_aware_per_client_context() -> None:
    with TestClient(app) as local_client, TestClient(app) as online_client:
        _login(online_client)

        local_rows = local_client.get("/tasks").json()["data"]["rows"]
        online_rows = online_client.get("/tasks").json()["data"]["rows"]

        assert [row["task_id"] for row in local_rows] == [300]
        assert all(row["visibility_scope"] == "local" for row in local_rows)
        assert [row["task_id"] for row in online_rows] == [301, 302, 303]
        assert all(row["visibility_scope"] != "local" for row in online_rows)


def test_local_catalog_and_definitions_use_local_visibility_scope() -> None:
    datasets = client.get("/datasets").json()["data"]["rows"]
    definitions = client.get("/circuit-definitions").json()["data"]["rows"]

    assert datasets[0]["dataset_id"] == "local-dataset-001"
    assert datasets[0]["visibility_scope"] == "local"
    assert datasets[0]["allowed_actions"]["publish"] is False
    assert definitions[0]["definition_id"] == 3
    assert definitions[0]["visibility_scope"] == "local"
    assert definitions[0]["allowed_actions"]["publish"] is False


def test_publish_definition_is_unavailable_in_local_mode() -> None:
    response = client.post("/circuit-definitions/3/publish")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "definition_publish_online_only"


def test_leave_workspace_rebinds_active_dataset_to_remaining_workspace_context() -> None:
    _login()
    invitation_response = client.post(
        "/session/workspace-invitations",
        json={
            "workspace_id": "ws-device-lab",
            "email": "collaborator.local@example.com",
            "role": "member",
        },
    )
    invite_token = invitation_response.json()["data"]["invitation"]["invite_token"]
    client.post("/session/logout")
    switch_response = client.patch(
        "/session/runtime-mode",
        json={"runtime_mode": "online", "server_origin": "http://127.0.0.1:8000"},
    )
    assert switch_response.status_code == 200
    client.post(
        "/session/login",
        json={
            "email": "collaborator.local@example.com",
            "password": "collaborator-local-password",
        },
    )
    accept_response = client.post(
        "/session/workspace-invitations/accept",
        json={"invite_token": invite_token},
    )
    assert accept_response.status_code == 200
    switch_response = client.patch(
        "/session/active-workspace", json={"workspace_id": "ws-device-lab"}
    )
    assert switch_response.status_code == 200

    leave_response = client.post(
        "/session/workspace-memberships/leave",
        json={"workspace_id": "ws-device-lab"},
    )

    assert leave_response.status_code == 200
    session_response = client.get("/session")
    payload = session_response.json()["data"]
    assert payload["workspace"]["id"] == "ws-modeling"
    assert payload["active_dataset"]["id"] == "transmon-coupler-014"
    assert payload["active_dataset"]["workspace_id"] == "ws-modeling"


def test_permission_failure_returns_debug_ref_header_and_payload() -> None:
    _login()

    response = client.patch("/session/active-dataset", json={"dataset_id": "transmon-coupler-014"})

    assert response.status_code == 403
    assert response.headers["X-Debug-Ref"] == response.json()["error"]["debug_ref"]
    assert response.json()["error"]["debug_ref"].startswith("debug:req:")


def test_list_tasks_returns_backend_owned_queue_read_model() -> None:
    response = client.get("/tasks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert [row["task_id"] for row in payload["data"]["rows"]] == [300]
    assert payload["data"]["rows"][0] == {
        "task_id": 300,
        "summary": "Local Space preview simulation is running.",
        "status": "running",
        "lane": "simulation",
        "task_kind": "simulation",
        "owner_display_name": "Local Operator",
        "visibility_scope": "local",
        "updated_at": "2026-03-17 08:50:00",
        "result_availability": "pending",
        "allowed_actions": {
            "attach": True,
            "cancel": True,
            "terminate": True,
            "retry": False,
            "rejection_reason": None,
        },
        "control_state": "none",
    }
    assert payload["data"]["worker_summary"] == [
        {
            "lane": "simulation",
            "healthy_processors": 1,
            "busy_processors": 1,
            "degraded_processors": 0,
            "draining_processors": 0,
            "offline_processors": 0,
        },
        {
            "lane": "characterization",
            "healthy_processors": 1,
            "busy_processors": 0,
            "degraded_processors": 0,
            "draining_processors": 0,
            "offline_processors": 0,
        },
    ]
    assert payload["meta"]["filter_echo"] == {
        "status": None,
        "lane": None,
        "scope": "workspace",
        "dataset_id": None,
        "q": None,
    }


def test_list_tasks_supports_filters_and_hides_non_visible_rows() -> None:
    _login()
    response = client.get(
        "/tasks?status=completed&lane=simulation&scope=owned&dataset_id=fluxonium-2025-031&limit=1"
    )

    assert response.status_code == 200
    payload = response.json()
    assert [row["task_id"] for row in payload["data"]["rows"]] == [303]
    assert payload["data"]["rows"][0]["visibility_scope"] == "owned"

    default_response = client.get("/tasks")
    assert [row["task_id"] for row in default_response.json()["data"]["rows"]] == [301, 302, 303]


def test_get_task_returns_attach_ready_detail_with_result_handoff() -> None:
    _login()
    response = client.get("/tasks/303")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    detail = payload["data"]
    assert detail["task_id"] == 303
    assert detail["task_kind"] == "post_processing"
    assert detail["worker_task_name"] == "post_processing_run_task"
    assert detail["visibility_scope"] == "owned"
    assert detail["control_state"] == "none"
    assert detail["dispatch"] == {
        "dispatch_key": "dispatch:303:post_processing_run_task",
        "status": "completed",
        "submission_source": "active_dataset",
        "accepted_at": "2026-03-11 19:05:00",
        "last_updated_at": "2026-03-11 19:18:00",
    }
    assert detail["allowed_actions"] == {
        "attach": True,
        "cancel": False,
        "terminate": False,
        "retry": True,
        "rejection_reason": "task_already_terminal",
    }
    assert detail["result_handoff"] == {
        "availability": "ready",
        "primary_result_handle_id": "result:fluxonium-2025-031:fit-summary",
        "result_handle_count": 2,
        "trace_payload_available": True,
    }
    assert [event["event_type"] for event in detail["events"]] == [
        "task_submitted",
        "task_completed",
    ]


def test_get_task_returns_not_found_for_hidden_task() -> None:
    _login()
    response = client.get("/tasks/304")

    assert response.status_code == 404
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "task_not_found"


def test_get_task_events_returns_persisted_event_history_readmodel() -> None:
    _login()
    response = client.get("/tasks/303/events?order=desc&limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["task_id"] == 303
    assert [event["event_type"] for event in payload["data"]["events"]] == [
        "task_completed",
        "task_submitted",
    ]
    assert payload["meta"]["event_count"] == 2
    assert payload["meta"]["filter_echo"] == {"order": "desc", "event_type": None}


def test_submit_task_returns_persisted_attach_ready_detail_and_audit_record() -> None:
    response = client.post("/tasks", json={"kind": "characterization"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    task = payload["data"]["task"]
    assert payload["data"]["operation"] == "submitted"
    assert task["task_id"] == 306
    assert task["dataset_id"] == "local-dataset-001"
    assert task["visibility_scope"] == "local"
    assert task["dispatch"]["status"] == "accepted"
    assert task["result_handoff"] == {
        "availability": "pending",
        "primary_result_handle_id": "task-result:306:primary",
        "result_handle_count": 1,
        "trace_payload_available": False,
    }
    assert task["events"][0]["metadata"]["audit_action"] == "task.submitted"

    records = get_task_audit_repository().list_records_for_resource(
        resource_kind="task",
        resource_id="306",
    )
    assert len(records) == 1
    assert records[0].action_kind == "task.submitted"
    assert records[0].outcome == "accepted"


def test_submit_simulation_task_persists_structured_setup_for_rehydration() -> None:
    simulation_setup = _simulation_setup_payload(ptc=_simulation_ptc_payload())
    response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "definition_id": 3,
            "summary": "Fluxonium sweep with HB setup.",
            "simulation_setup": simulation_setup,
        },
    )

    assert response.status_code == 201
    task = response.json()["data"]["task"]
    assert task["simulation_setup"] == simulation_setup
    assert task["simulation_setup"]["ptc"] == _simulation_ptc_payload()
    assert task["downstream_source_capabilities"] == {
        "raw": {"available": True},
        "ptc": {
            "available": True,
            "enabled": True,
            "mode": "auto",
            "compensate_ports": ["port_1", "port_2"],
        },
    }
    assert task["post_processing_setup"] is None
    assert task["upstream_task_id"] is None
    assert task["downstream_task_ids"] == []
    assert task["events"][0]["metadata"]["simulation_setup"] == simulation_setup

    reset_runtime_state()

    reloaded = client.get(f"/tasks/{task['task_id']}").json()["data"]
    assert reloaded["simulation_setup"] == simulation_setup
    assert reloaded["simulation_setup"]["ptc"] == _simulation_ptc_payload()
    assert reloaded["downstream_source_capabilities"]["ptc"]["available"] is True
    assert reloaded["summary"] == "Fluxonium sweep with HB setup."


def test_post_processing_task_persists_upstream_lineage_and_downstream_reference() -> None:
    simulation_setup = _simulation_setup_payload(ptc=_simulation_ptc_payload())
    simulation_response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "definition_id": 3,
            "summary": "Upstream simulation for fit bundle.",
            "simulation_setup": simulation_setup,
        },
    )
    upstream_task_id = simulation_response.json()["data"]["task"]["task_id"]

    post_processing_response = client.post(
        "/tasks",
        json={
            "kind": "post_processing",
            "dataset_id": "local-dataset-001",
            "summary": "Fit the latest fluxonium run.",
            "upstream_task_id": upstream_task_id,
            "post_processing_setup": _post_processing_setup_payload(),
        },
    )

    assert post_processing_response.status_code == 201
    task = post_processing_response.json()["data"]["task"]
    assert task["upstream_task_id"] == upstream_task_id
    assert task["post_processing_setup"] == _post_processing_setup_payload()
    assert task["events"][0]["metadata"]["upstream_task_id"] == upstream_task_id

    upstream = client.get(f"/tasks/{upstream_task_id}").json()["data"]
    assert upstream["downstream_task_ids"] == [task["task_id"]]

    reset_runtime_state()

    reloaded = client.get(f"/tasks/{task['task_id']}").json()["data"]
    assert reloaded["upstream_task_id"] == upstream_task_id
    assert reloaded["post_processing_setup"] == _post_processing_setup_payload()


def test_submit_simulation_task_rejects_invalid_ptc_payload() -> None:
    simulation_setup = _simulation_setup_payload(
        ptc={
            "enabled": True,
            "mode": "auto",
            "compensate_ports": "port_1",
        }
    )

    response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "definition_id": 3,
            "summary": "Reject malformed ptc payload.",
            "simulation_setup": simulation_setup,
        },
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "request_validation_failed"
    assert (
        response.json()["error"]["message"]
        == "simulation_setup.ptc.compensate_ports must be an array."
    )


def test_simulation_task_detail_exposes_disabled_ptc_capability_state() -> None:
    response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "definition_id": 3,
            "summary": "Simulation with disabled ptc.",
            "simulation_setup": _simulation_setup_payload(
                ptc=_simulation_ptc_payload(enabled=False, mode="manual")
            ),
        },
    )

    assert response.status_code == 201
    task = response.json()["data"]["task"]
    assert task["simulation_setup"]["ptc"] == {
        "enabled": False,
        "mode": "manual",
        "compensate_ports": ["port_1", "port_2"],
    }
    assert task["downstream_source_capabilities"] == {
        "raw": {"available": True},
        "ptc": {
            "available": False,
            "enabled": False,
            "mode": "manual",
            "compensate_ports": ["port_1", "port_2"],
        },
    }


def test_submitted_task_survives_runtime_reset_in_routes() -> None:
    created = client.post("/tasks", json={"kind": "characterization"}).json()["data"]["task"]

    reset_runtime_state()

    queue_response = client.get("/tasks")
    assert [row["task_id"] for row in queue_response.json()["data"]["rows"]][:2] == [300, 306]

    detail_response = client.get("/tasks/306")
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["dispatch"] == created["dispatch"]

    events_response = client.get("/tasks/306/events?order=asc&limit=10")
    assert [event["event_type"] for event in events_response.json()["data"]["events"]] == [
        "task_submitted"
    ]


def test_cancel_task_persists_control_state_and_emits_audit() -> None:
    _login()
    response = client.post("/tasks/301/cancel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    task = payload["data"]["task"]
    assert payload["data"]["operation"] == "cancel_requested"
    assert task["status"] == "cancellation_requested"
    assert task["control_state"] == "cancellation_requested"
    assert task["allowed_actions"] == {
        "attach": True,
        "cancel": False,
        "terminate": True,
        "retry": False,
        "rejection_reason": "cancellation_requested",
    }
    assert task["events"][-1]["event_type"] == "task_cancel_requested"
    assert task["events"][-1]["metadata"]["audit_action"] == "task.cancel_requested"

    records = get_task_audit_repository().list_records_for_resource(
        resource_kind="task",
        resource_id="301",
    )
    assert [record.action_kind for record in records] == ["task.cancel_requested"]

    reset_runtime_state()
    _login()

    reloaded = client.get("/tasks/301").json()["data"]
    assert reloaded["status"] == "cancellation_requested"
    assert reloaded["control_state"] == "cancellation_requested"
    assert reloaded["events"][-1]["event_type"] == "task_cancel_requested"


def test_terminate_task_persists_control_state_and_blocks_repeat_cancel() -> None:
    _login()
    response = client.post("/tasks/301/terminate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["task"]["status"] == "termination_requested"
    assert payload["data"]["task"]["control_state"] == "termination_requested"
    assert payload["data"]["task"]["events"][-1]["event_type"] == "task_terminate_requested"

    cancelled_response = client.post("/tasks/301/cancel")
    assert cancelled_response.status_code == 409
    assert cancelled_response.json()["error"]["code"] == "task_not_cancellable"


def test_retry_creates_new_task_with_lineage_and_audit() -> None:
    _login()
    response = client.post("/tasks/303/retry")

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    task = payload["data"]["task"]
    assert payload["data"]["operation"] == "retried"
    assert task["task_id"] == 306
    assert task["retry_of_task_id"] == 303
    assert task["summary"] == "Retry of task 303: Fluxonium fit bundle was post-processed."
    assert [event["event_type"] for event in task["events"]] == [
        "task_submitted",
        "task_retried",
    ]

    source_task = client.get("/tasks/303").json()["data"]
    assert source_task["events"][-1]["event_type"] == "task_retried"
    assert source_task["events"][-1]["metadata"]["replacement_task_id"] == 306

    records = get_task_audit_repository().list_records_for_resource(
        resource_kind="task",
        resource_id="306",
    )
    assert [record.action_kind for record in records] == ["task.retried"]


def test_retry_denies_non_terminal_task() -> None:
    _login()
    response = client.post("/tasks/301/retry")

    assert response.status_code == 409
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "task_retry_denied"


def test_runtime_updates_flow_through_detail_events_and_result_handoff() -> None:
    submitted_task = get_task_service().submit_task(
        TaskSubmissionDraft(
            kind="characterization",
            dataset_id=None,
            definition_id=None,
            summary="Execution runtime route proof.",
        )
    )

    get_task_execution_runtime().start_task(
        submitted_task.task_id,
        recorded_at=datetime(2026, 3, 12, 13, 0, 0),
        worker_pid=4747,
        stale_after_seconds=240,
    )

    response = client.get(f"/tasks/{submitted_task.task_id}")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "running"
    assert payload["dispatch"]["status"] == "running"
    assert payload["result_handoff"]["availability"] == "pending"
    assert payload["events"][-1]["event_type"] == "task_running"
    assert payload["events"][-1]["metadata"]["audit_action"] == "worker.task_started"
    assert payload["events"][-1]["metadata"]["worker_pid"] == 4747
    assert payload["events"][-1]["metadata"]["stale_after_seconds"] == 240


def test_failed_task_reports_result_handoff_none_after_lifecycle_update() -> None:
    _login()
    with _bind_client_app_context(client):
        get_task_service().update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=302,
                status="failed",
                progress_percent_complete=100,
                progress_summary="Persisted failure summary.",
                progress_updated_at="2026-03-12 11:05:00",
                summary="Persisted task snapshot override",
            )
        )

    payload = client.get("/tasks/302").json()["data"]
    assert payload["status"] == "failed"
    assert payload["result_handoff"] == {
        "availability": "none",
        "primary_result_handle_id": None,
        "result_handle_count": 0,
        "trace_payload_available": False,
    }
    assert payload["allowed_actions"]["retry"] is True


def test_submit_simulation_task_requires_definition_id() -> None:
    response = client.post("/tasks", json={"kind": "simulation"})

    assert response.status_code == 422
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "simulation_definition_required"


def test_submit_post_processing_task_requires_dataset_context() -> None:
    _login()
    cleared = client.patch("/session/active-dataset", json={"dataset_id": None})
    assert cleared.status_code == 200

    response = client.post("/tasks", json={"kind": "post_processing"})

    assert response.status_code == 422
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "dataset_context_required"
