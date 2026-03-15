from fastapi.testclient import TestClient
from src.app.infrastructure.runtime import (
    get_task_audit_repository,
    get_workspace_collaboration_service,
    reset_runtime_state,
)
from src.app.main import app

client = TestClient(app)


def _login(
    *,
    email: str = "rewrite.local@example.com",
    password: str = "rewrite-local-password",
) -> dict[str, object]:
    response = client.post(
        "/session/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["data"]


def _logout() -> None:
    client.post("/session/logout")


def _cookie_value(name: str) -> str | None:
    value: str | None = None
    for cookie in client.cookies.jar:
        if cookie.name != name:
            continue
        value = cookie.value
    return value


def test_refresh_rotates_refresh_token_and_restores_authenticated_session() -> None:
    session = _login()
    old_refresh_token = _cookie_value("sc_session_refresh")
    assert old_refresh_token is not None
    assert session["auth"]["mode"] == "jwt_refresh_cookie"

    response = client.post("/session/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["auth"]["state"] == "authenticated"
    assert client.cookies.get("sc_session_refresh") != old_refresh_token

    client.cookies.set("sc_session_refresh", old_refresh_token)
    stale_refresh = client.post("/session/refresh")
    assert stale_refresh.status_code == 401
    assert stale_refresh.json()["error"]["code"] == "auth_refresh_invalid"


def test_logout_revokes_refresh_family() -> None:
    _login()
    old_refresh_token = _cookie_value("sc_session_refresh")
    assert old_refresh_token is not None

    logout_response = client.post("/session/logout")

    assert logout_response.status_code == 200
    client.cookies.set("sc_session_refresh", old_refresh_token)
    refresh_response = client.post("/session/refresh")
    assert refresh_response.status_code == 401
    assert refresh_response.json()["error"]["code"] == "auth_refresh_invalid"


def test_viewer_session_materializes_denied_capabilities_and_invite_denial() -> None:
    session = _login(
        email="collaborator.local@example.com",
        password="collaborator-local-password",
    )

    assert session["workspace"]["role"] == "viewer"
    assert session["capabilities"]["can_submit_tasks"] is False
    assert session["capabilities"]["can_manage_definitions"] is False
    assert session["capabilities"]["can_manage_datasets"] is False
    assert session["capabilities"]["can_view_audit_logs"] is False
    assert session["workspace"]["allowed_actions"]["invite_members"] is False

    response = client.post(
        "/session/workspace-invitations",
        json={"workspace_id": "ws-modeling", "email": "new.user@example.com", "role": "member"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "workspace_invitation_denied"


def test_workspace_invitation_acceptance_handles_account_mismatch_then_accepts() -> None:
    _login()
    create_response = client.post(
        "/session/workspace-invitations",
        json={
            "workspace_id": "ws-device-lab",
            "email": "collaborator.local@example.com",
            "role": "member",
        },
    )
    invitation = create_response.json()["data"]["invitation"]

    mismatch_response = client.post(
        "/session/workspace-invitations/accept",
        json={"invite_token": invitation["invite_token"]},
    )
    assert mismatch_response.status_code == 409
    assert mismatch_response.json()["error"]["code"] == "workspace_invitation_account_mismatch"

    _logout()
    _login(email="collaborator.local@example.com", password="collaborator-local-password")
    accept_response = client.post(
        "/session/workspace-invitations/accept",
        json={"invite_token": invitation["invite_token"]},
    )

    assert accept_response.status_code == 200
    payload = accept_response.json()["data"]
    assert payload["invitation"]["state"] == "accepted"
    assert payload["switch_available"] is True
    assert any(membership["id"] == "ws-device-lab" for membership in payload["memberships"])


def test_membership_transfer_and_leave_flow_updates_membership_surface() -> None:
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
    _logout()
    _login(email="collaborator.local@example.com", password="collaborator-local-password")
    client.post("/session/workspace-invitations/accept", json={"invite_token": invite_token})
    _logout()
    _login()

    transfer_response = client.post(
        "/session/workspace-memberships/transfer-ownership",
        json={"workspace_id": "ws-device-lab", "new_owner_user_id": "researcher-02"},
    )

    assert transfer_response.status_code == 200
    session_after_transfer = client.get("/session").json()["data"]
    assert session_after_transfer["workspace"]["role"] == "member"
    assert session_after_transfer["capabilities"]["can_transfer_workspace_owner"] is False

    leave_response = client.post(
        "/session/workspace-memberships/leave",
        json={"workspace_id": "ws-device-lab"},
    )
    assert leave_response.status_code == 200
    assert leave_response.json()["data"]["operation"] == "left"


def test_workspace_membership_read_model_exposes_human_readable_member_fields() -> None:
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
    _logout()
    _login(email="collaborator.local@example.com", password="collaborator-local-password")
    accept_response = client.post(
        "/session/workspace-invitations/accept",
        json={"invite_token": invite_token},
    )
    assert accept_response.status_code == 200
    _logout()
    _login()

    membership_response = client.get("/session/workspace-memberships?workspace_id=ws-device-lab")

    assert membership_response.status_code == 200
    payload = membership_response.json()["data"]
    collaborator_row = next(
        row for row in payload["memberships"] if row["user_id"] == "researcher-02"
    )
    current_user_row = next(
        row for row in payload["memberships"] if row["user_id"] == "researcher-01"
    )
    assert collaborator_row["display_name"] == "Collaborator User"
    assert collaborator_row["email"] == "collaborator.local@example.com"
    assert collaborator_row["platform_role"] == "user"
    assert collaborator_row["workspace_role"] == "member"
    assert collaborator_row["is_current_user"] is False
    assert collaborator_row["user"]["display_name"] == "Collaborator User"
    assert collaborator_row["allowed_actions"] == {
        "remove": True,
        "transfer_owner": True,
        "leave": False,
    }
    assert current_user_row["is_current_user"] is True
    assert current_user_row["allowed_actions"]["remove"] is False
    assert current_user_row["allowed_actions"]["leave"] is False


def test_workspace_invitation_read_model_exposes_inviter_and_allowed_actions() -> None:
    _login()

    create_response = client.post(
        "/session/workspace-invitations",
        json={
            "workspace_id": "ws-device-lab",
            "email": "collaborator.local@example.com",
            "role": "viewer",
        },
    )

    assert create_response.status_code == 201
    invitation = create_response.json()["data"]["invitation"]
    assert invitation["inviter"] == {
        "user_id": "researcher-01",
        "display_name": "Rewrite Local User",
        "email": "rewrite.local@example.com",
        "platform_role": "user",
    }
    assert invitation["allowed_actions"] == {
        "revoke": True,
        "accept": False,
        "copy_link": True,
    }
    detail_response = client.get(f"/session/workspace-invitations/{invitation['invite_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["delivery_state"] == "manual_link"
    assert detail["inviter"]["display_name"] == "Rewrite Local User"
    assert detail["allowed_actions"]["revoke"] is True


def test_auth_and_collaboration_actions_are_visible_via_audit_query() -> None:
    failed_login = client.post(
        "/session/login",
        json={"email": "rewrite.local@example.com", "password": "wrong-password"},
    )
    assert failed_login.status_code == 401

    _login()
    invite_response = client.post(
        "/session/workspace-invitations",
        json={
            "workspace_id": "ws-device-lab",
            "email": "collaborator.local@example.com",
            "role": "viewer",
        },
    )
    invite_id = invite_response.json()["data"]["invitation"]["invite_id"]
    client.post(f"/session/workspace-invitations/{invite_id}/revoke")
    _logout()
    _login(email="admin.local@example.com", password="admin-local-password")

    auth_audit = client.get("/audit-logs?workspace_id=auth&action_kind=auth.login_failed")
    assert auth_audit.status_code == 200
    assert auth_audit.json()["data"]["rows"][0]["action_kind"] == "auth.login_failed"

    collaboration_audit = client.get(
        "/audit-logs?workspace_id=ws-device-lab&action_kind=workspace.invite_revoked"
    )
    assert collaboration_audit.status_code == 200
    assert (
        collaboration_audit.json()["data"]["rows"][0]["action_kind"] == "workspace.invite_revoked"
    )


def test_request_scoped_session_binding_overrides_global_session_fallback() -> None:
    collaborator_client = TestClient(app)
    owner_client = TestClient(app)
    try:
        collaborator_login = collaborator_client.post(
            "/session/login",
            json={
                "email": "collaborator.local@example.com",
                "password": "collaborator-local-password",
            },
        )
        assert collaborator_login.status_code == 200

        owner_login = owner_client.post(
            "/session/login",
            json={
                "email": "rewrite.local@example.com",
                "password": "rewrite-local-password",
            },
        )
        assert owner_login.status_code == 200

        audit_response = collaborator_client.get("/audit-logs")

        assert audit_response.status_code == 403
        assert audit_response.json()["error"]["code"] == "audit_access_denied"
    finally:
        collaborator_client.close()
        owner_client.close()


def test_unauthenticated_invitation_acceptance_can_resume_after_login() -> None:
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
    _logout()

    deferred_accept = client.post(
        "/session/workspace-invitations/accept",
        json={"invite_token": invite_token},
    )

    assert deferred_accept.status_code == 200
    deferred_payload = deferred_accept.json()["data"]
    assert deferred_payload["requires_authentication"] is True
    assert deferred_payload["continuation_saved"] is True
    assert deferred_payload["recommended_next_action"] == "sign_in_to_accept"
    assert client.cookies.get("sc_pending_invitation") is not None

    _login(email="collaborator.local@example.com", password="collaborator-local-password")
    resumed_accept = client.post("/session/workspace-invitations/accept", json={})

    assert resumed_accept.status_code == 200
    resumed_payload = resumed_accept.json()["data"]
    assert resumed_payload["requires_authentication"] is False
    assert resumed_payload["invitation"]["state"] == "accepted"
    assert client.cookies.get("sc_pending_invitation") is None


def test_invitation_delivery_failure_uses_canonical_state_and_audit(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SC_ENVIRONMENT", "production")
    monkeypatch.setenv("SC_SESSION_SECRET", "production-session-secret-2026-baseline")
    monkeypatch.setenv("SC_BOOTSTRAP_ADMIN_PASSWORD", "production-bootstrap-password")
    reset_runtime_state()
    client.cookies.clear()
    _login()
    access_token = _cookie_value("sc_session_access")
    assert access_token is not None

    invitation = get_workspace_collaboration_service().create_invitation(
        access_token,
        workspace_id="ws-device-lab",
        email="collaborator.local@example.com",
        role="viewer",
    )
    assert invitation.state == "delivery_failed"
    assert invitation.delivery.status == "delivery_failed"
    assert invitation.delivery.channel == "manual_link"
    assert invitation.delivery.invite_url is not None
    assert invitation.delivery.failure_reason == "smtp_not_configured"

    audit_records = get_task_audit_repository().list_records_for_resource(
        resource_kind="workspace_invitation",
        resource_id=invitation.invite_id,
    )
    assert [record.action_kind for record in audit_records] == [
        "workspace.invite_delivery_failed",
        "workspace.invite_created",
    ]
