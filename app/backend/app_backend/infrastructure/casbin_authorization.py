from __future__ import annotations

from pathlib import Path

import casbin

from app_backend.domain.authorization import (
    AuthorizationAction,
    AuthorizationDecision,
    AuthorizationResourceEnvelope,
    AuthorizationSubject,
)


class CasbinAuthorizationAdapter:
    def __init__(
        self,
        *,
        model_path: str | None = None,
        policy_path: str | None = None,
    ) -> None:
        base_path = Path(__file__).resolve().parent / "authorization"
        self._enforcer = casbin.Enforcer(
            model_path or str(base_path / "casbin_model.conf"),
            policy_path or str(base_path / "casbin_policy.csv"),
        )

    def decide(
        self,
        *,
        subject: AuthorizationSubject,
        action: AuthorizationAction,
        resource: AuthorizationResourceEnvelope,
    ) -> AuthorizationDecision:
        if subject.user_id is None:
            return AuthorizationDecision(allowed=False, action=action, reason="auth_required")
        if subject.platform_role != "admin" and (
            subject.workspace_id is None or subject.workspace_role is None
        ):
            return AuthorizationDecision(allowed=False, action=action, reason="auth_required")
        if (
            subject.platform_role != "admin"
            and resource.workspace_id is not None
            and resource.workspace_id != subject.workspace_id
        ):
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

        for effective_subject in _effective_subjects(subject, resource):
            if self._enforcer.enforce(
                effective_subject,
                resource.workspace_id or subject.workspace_id or "*",
                resource.resource_kind,
                action,
            ):
                return AuthorizationDecision(allowed=True, action=action)
        return AuthorizationDecision(
            allowed=False,
            action=action,
            reason="authorization_denied",
        )


def _effective_subjects(
    subject: AuthorizationSubject,
    resource: AuthorizationResourceEnvelope,
) -> tuple[str, ...]:
    effective_subjects: list[str] = []
    if subject.platform_role == "admin":
        effective_subjects.append("admin")
    if subject.workspace_role is not None:
        effective_subjects.append(subject.workspace_role)
    if subject.user_id is not None and resource.owner_user_id == subject.user_id:
        effective_subjects.append("resource_owner")
    return tuple(dict.fromkeys(effective_subjects))
