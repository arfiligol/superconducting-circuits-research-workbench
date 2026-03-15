from __future__ import annotations

from src.app.domain.authorization import (
    AuthorizationAction,
    AuthorizationDecision,
    AuthorizationResourceEnvelope,
    AuthorizationSubject,
)

_ROLE_POLICIES: dict[str, set[AuthorizationAction]] = {
    "owner": {
        "switch_workspace",
        "switch_dataset",
        "invite_member",
        "revoke_invite",
        "remove_member",
        "transfer_workspace_owner",
        "submit_task",
        "cancel_own_task",
        "cancel_workspace_task",
        "terminate_workspace_task",
        "retry_own_task",
        "retry_workspace_task",
        "manage_definition",
        "manage_dataset",
        "view_audit_log",
    },
    "member": {
        "switch_workspace",
        "switch_dataset",
        "leave_workspace",
        "submit_task",
        "cancel_own_task",
        "retry_own_task",
    },
    "viewer": {
        "switch_workspace",
        "switch_dataset",
        "leave_workspace",
    },
}


class CasbinAuthorizationAdapter:
    def decide(
        self,
        *,
        subject: AuthorizationSubject,
        action: AuthorizationAction,
        resource: AuthorizationResourceEnvelope,
    ) -> AuthorizationDecision:
        if subject.platform_role == "admin":
            return AuthorizationDecision(allowed=True, action=action)
        if subject.user_id is None or subject.workspace_id is None or subject.workspace_role is None:
            return AuthorizationDecision(
                allowed=False,
                action=action,
                reason="auth_required",
            )
        if resource.workspace_id is not None and resource.workspace_id != subject.workspace_id:
            return AuthorizationDecision(
                allowed=False,
                action=action,
                reason="workspace_membership_required",
            )

        if resource.lifecycle_state in {"archived", "deleted"} and action in {
            "manage_dataset",
            "manage_definition",
        }:
            return AuthorizationDecision(
                allowed=False,
                action=action,
                reason="resource_archived",
            )

        if action in _ROLE_POLICIES.get(subject.workspace_role, set()):
            return AuthorizationDecision(allowed=True, action=action)

        if action in {"manage_dataset", "manage_definition"}:
            if resource.owner_user_id == subject.user_id:
                return AuthorizationDecision(allowed=True, action=action)
        if action in {"cancel_own_task", "retry_own_task"}:
            if resource.owner_user_id == subject.user_id:
                return AuthorizationDecision(allowed=True, action=action)
        return AuthorizationDecision(
            allowed=False,
            action=action,
            reason="authorization_denied",
        )
