from __future__ import annotations

import logging
from typing import Protocol

from src.app.domain.audit import AuditOutcome, AuditRecord
from src.app.domain.authorization import AuthorizationResourceEnvelope
from src.app.domain.session import SessionState
from src.app.domain.workspace_collaboration import (
    WorkspaceInvitation,
    WorkspaceInvitationAcceptance,
    WorkspaceInvitationAllowedActions,
    WorkspaceInvitationListView,
    WorkspaceMemberAllowedActions,
    WorkspaceMemberRecord,
    WorkspaceMemberRow,
    WorkspaceMembershipListView,
)
from src.app.infrastructure.audit_records import build_audit_record
from src.app.infrastructure.invitation_delivery import (
    InvitationDeliveryAttempt,
    WorkspaceInvitationDeliveryService,
)
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import ServiceError, service_error
from src.app.services.session_service import SessionService

logger = logging.getLogger(__name__)


class CollaborationRepository(Protocol):
    def list_workspace_invitations(self, workspace_id: str) -> tuple[WorkspaceInvitation, ...]: ...

    def create_workspace_invitation(
        self,
        *,
        workspace_id: str,
        workspace_name: str,
        email: str,
        role: str,
        created_by_user_id: str,
    ) -> WorkspaceInvitation: ...

    def update_workspace_invitation_delivery(
        self,
        *,
        invite_id: str,
        state: str,
        delivery_status: str,
        delivery_channel: str,
        invite_url: str | None,
        delivery_error: str | None,
    ) -> WorkspaceInvitation | None: ...

    def get_workspace_invitation(self, invite_id: str) -> WorkspaceInvitation | None: ...

    def get_workspace_invitation_by_token(
        self, invite_token: str
    ) -> WorkspaceInvitation | None: ...

    def revoke_workspace_invitation(self, invite_id: str) -> WorkspaceInvitation | None: ...

    def accept_workspace_invitation(
        self,
        *,
        invite_token: str,
        user_email: str,
    ) -> WorkspaceInvitation | None: ...

    def create_pending_invitation_acceptance(self, invite_token: str) -> str: ...

    def consume_pending_invitation_acceptance(self, continuation_token: str) -> str | None: ...

    def list_workspace_memberships(
        self,
        workspace_id: str,
    ) -> tuple[WorkspaceMemberRecord, ...]: ...

    def remove_workspace_member(self, workspace_id: str, user_id: str) -> bool: ...

    def transfer_workspace_owner(
        self,
        workspace_id: str,
        new_owner_user_id: str,
        current_owner_user_id: str,
    ) -> bool: ...


class CollaborationAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class WorkspaceCollaborationService:
    def __init__(
        self,
        repository: CollaborationRepository,
        session_service: SessionService,
        authorization_service: AuthorizationService,
        delivery_service: WorkspaceInvitationDeliveryService,
        audit_repository: CollaborationAuditRepository | None = None,
    ) -> None:
        self._repository = repository
        self._session_service = session_service
        self._authorization_service = authorization_service
        self._delivery_service = delivery_service
        self._audit_repository = audit_repository

    def list_invitations(
        self,
        session_token: str | None,
        workspace_id: str | None = None,
    ) -> WorkspaceInvitationListView:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        self._authorization_service.authorize(
            state,
            "invite_member",
            resource=self._workspace_resource(resolved_workspace_id),
            denied_code="workspace_invitation_denied",
            denied_message="The current session cannot list invitations for this workspace.",
        )
        rows = tuple(
            self._materialize_invitation(row, state)
            for row in self._repository.list_workspace_invitations(resolved_workspace_id)
        )
        return WorkspaceInvitationListView(rows=rows, total_count=len(rows))

    def create_invitation(
        self,
        session_token: str | None,
        *,
        workspace_id: str | None,
        email: str,
        role: str,
    ) -> WorkspaceInvitation:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        self._authorization_service.authorize(
            state,
            "invite_member",
            resource=self._workspace_resource(resolved_workspace_id),
            denied_code="workspace_invitation_denied",
            denied_message="The current session cannot invite members to this workspace.",
        )
        membership = next(
            membership_item
            for membership_item in state.memberships
            if membership_item.workspace_id == resolved_workspace_id
        )
        invitation = self._repository.create_workspace_invitation(
            workspace_id=resolved_workspace_id,
            workspace_name=membership.display_name,
            email=email.strip().lower(),
            role=role,
            created_by_user_id=state.user.user_id if state.user is not None else "anonymous",
        )
        logger.info(
            "Workspace invitation created invite_id=%s workspace_id=%s",
            invitation.invite_id,
            invitation.workspace_id,
        )
        self._append_audit_record(
            state,
            action_kind="workspace.invite_created",
            resource_kind="workspace_invitation",
            resource_id=invitation.invite_id,
            outcome="accepted",
            payload={
                "email": invitation.email,
                "role": invitation.role,
                "workspace_id": invitation.workspace_id,
            },
            workspace_id=invitation.workspace_id,
        )
        delivery_attempt = self._delivery_service.deliver(invitation)
        delivered = self._repository.update_workspace_invitation_delivery(
            invite_id=invitation.invite_id,
            state=delivery_attempt.invitation_state,
            delivery_status=delivery_attempt.delivery_status,
            delivery_channel=delivery_attempt.delivery_channel,
            invite_url=delivery_attempt.invite_url,
            delivery_error=delivery_attempt.delivery_error,
        )
        if delivered is None:
            return self._materialize_invitation(invitation, state)
        self._append_delivery_audit_record(
            state=state,
            invitation=delivered,
            delivery_attempt=delivery_attempt,
        )
        if delivery_attempt.delivery_error is None:
            logger.info(
                (
                    "Workspace invitation delivery resolved invite_id=%s "
                    "delivery_channel=%s delivery_status=%s"
                ),
                delivered.invite_id,
                delivered.delivery.channel,
                delivered.delivery.status,
            )
        else:
            logger.warning(
                "Workspace invitation delivery failed invite_id=%s delivery_error=%s",
                delivered.invite_id,
                delivery_attempt.delivery_error,
            )
        return self._materialize_invitation(delivered, state)

    def get_invitation_detail(
        self,
        session_token: str | None,
        invite_id: str,
    ) -> WorkspaceInvitation:
        state = self._session_service.require_authenticated_session_state(session_token)
        invitation = self._repository.get_workspace_invitation(invite_id)
        if invitation is None:
            raise service_error(
                404,
                code="workspace_invitation_not_found",
                category="not_found",
                message="The requested workspace invitation was not found.",
            )
        self._authorization_service.authorize(
            state,
            "invite_member",
            resource=self._workspace_resource(invitation.workspace_id),
            denied_code="workspace_invitation_denied",
            denied_message="The current session cannot view this workspace invitation.",
        )
        return self._materialize_invitation(invitation, state)

    def revoke_invitation(
        self,
        session_token: str | None,
        invite_id: str,
    ) -> WorkspaceInvitation:
        state = self._session_service.require_authenticated_session_state(session_token)
        invitation = self._repository.get_workspace_invitation(invite_id)
        if invitation is None:
            raise service_error(
                404,
                code="workspace_invitation_not_found",
                category="not_found",
                message="The requested workspace invitation was not found.",
            )
        self._authorization_service.authorize(
            state,
            "revoke_invite",
            resource=_invitation_resource(invitation),
            denied_code="workspace_invitation_denied",
            denied_message="The current session cannot revoke this workspace invitation.",
        )
        revoked = self._repository.revoke_workspace_invitation(invite_id)
        if revoked is None:
            raise service_error(
                404,
                code="workspace_invitation_not_found",
                category="not_found",
                message="The requested workspace invitation was not found.",
            )
        logger.info("Workspace invitation revoked invite_id=%s", revoked.invite_id)
        self._append_audit_record(
            state,
            action_kind="workspace.invite_revoked",
            resource_kind="workspace_invitation",
            resource_id=revoked.invite_id,
            outcome="completed",
            payload={"workspace_id": revoked.workspace_id},
            workspace_id=revoked.workspace_id,
        )
        return self._materialize_invitation(revoked, state)

    def accept_invitation(
        self,
        session_token: str | None,
        *,
        invite_token: str | None = None,
        continuation_token: str | None = None,
    ) -> tuple[WorkspaceInvitationAcceptance, str | None]:
        resolved_invite_token = invite_token
        if resolved_invite_token is None and continuation_token is not None:
            resolved_invite_token = self._repository.consume_pending_invitation_acceptance(
                continuation_token
            )
        if resolved_invite_token is None:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message=(
                    "invite_token must be provided when no saved invitation continuation exists."
                ),
            )

        invitation = self._repository.get_workspace_invitation_by_token(resolved_invite_token)
        if invitation is None:
            raise service_error(
                404,
                code="workspace_invitation_not_found",
                category="not_found",
                message="The requested workspace invitation was not found.",
            )
        if invitation.state == "revoked":
            raise service_error(
                409,
                code="workspace_invitation_revoked",
                category="conflict",
                message="The workspace invitation has been revoked.",
            )
        if invitation.state == "expired":
            raise service_error(
                409,
                code="workspace_invitation_expired",
                category="conflict",
                message="The workspace invitation has expired.",
            )

        try:
            state = self._session_service.require_authenticated_session_state(session_token)
        except ServiceError as exc:
            if exc.code not in {"auth_required", "auth_session_expired"}:
                raise
            continuation = self._repository.create_pending_invitation_acceptance(
                resolved_invite_token
            )
            logger.info(
                "Workspace invitation acceptance deferred until authentication invite_id=%s",
                invitation.invite_id,
            )
            return WorkspaceInvitationAcceptance(
                invitation=self._materialize_invitation(invitation, None),
                memberships=(),
                switch_available=False,
                post_accept_context="sign_in_to_accept",
                requires_authentication=True,
                continuation_saved=True,
            ), continuation

        if state.user is None or state.user.email is None:
            raise service_error(
                401,
                code="auth_required",
                category="auth_required",
                message="Accepting an invitation requires an authenticated session.",
            )
        if state.user.email.casefold() != invitation.email.casefold():
            logger.warning(
                "Workspace invitation acceptance rejected due to account mismatch invite_id=%s",
                invitation.invite_id,
            )
            raise service_error(
                409,
                code="workspace_invitation_account_mismatch",
                category="conflict",
                message="The current account does not match the invitation email.",
            )
        accepted = self._repository.accept_workspace_invitation(
            invite_token=resolved_invite_token,
            user_email=state.user.email.casefold(),
        )
        if accepted is None:
            raise service_error(
                404,
                code="workspace_invitation_not_found",
                category="not_found",
                message="The requested workspace invitation was not found.",
            )
        switch_available = state.workspace_id != accepted.workspace_id
        result = WorkspaceInvitationAcceptance(
            invitation=self._materialize_invitation(accepted, state),
            memberships=self._session_service.require_authenticated_session_state(
                session_token
            ).memberships,
            switch_available=switch_available,
            post_accept_context="switch_available" if switch_available else "stay_current",
        )
        logger.info(
            "Workspace invitation accepted invite_id=%s workspace_id=%s",
            accepted.invite_id,
            accepted.workspace_id,
        )
        self._append_audit_record(
            state,
            action_kind="workspace.invite_accepted",
            resource_kind="workspace_invitation",
            resource_id=accepted.invite_id,
            outcome="completed",
            payload={"workspace_id": accepted.workspace_id, "email": accepted.email},
            workspace_id=accepted.workspace_id,
        )
        return result, None

    def list_memberships(
        self,
        session_token: str | None,
        workspace_id: str | None = None,
    ) -> WorkspaceMembershipListView:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        self._require_workspace_membership(state, resolved_workspace_id)
        memberships = self._repository.list_workspace_memberships(resolved_workspace_id)
        workspace_name = next(
            (
                membership.display_name
                for membership in state.memberships
                if membership.workspace_id == resolved_workspace_id
            ),
            resolved_workspace_id,
        )
        return WorkspaceMembershipListView(
            workspace_id=resolved_workspace_id,
            workspace_name=workspace_name,
            memberships=self._materialize_member_rows(
                memberships,
                state=state,
                workspace_id=resolved_workspace_id,
            ),
        )

    def leave_workspace(
        self,
        session_token: str | None,
        workspace_id: str | None = None,
    ) -> WorkspaceMembershipListView:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        active_membership = next(
            (
                membership
                for membership in state.memberships
                if membership.workspace_id == resolved_workspace_id
            ),
            None,
        )
        if active_membership is None:
            raise service_error(
                403,
                code="workspace_membership_required",
                category="permission_denied",
                message="The current session does not belong to the selected workspace.",
            )
        self._authorization_service.authorize(
            state,
            "leave_workspace",
            resource=self._workspace_resource(resolved_workspace_id),
            denied_code="workspace_leave_denied",
            denied_message="The current session cannot leave this workspace.",
        )
        if active_membership.role == "owner":
            raise service_error(
                409,
                code="workspace_owner_leave_blocked",
                category="conflict",
                message="Transfer workspace ownership before leaving the workspace.",
            )
        removed = self._repository.remove_workspace_member(
            resolved_workspace_id,
            state.user.user_id if state.user is not None else "",
        )
        if not removed:
            raise service_error(
                404,
                code="workspace_membership_not_found",
                category="not_found",
                message="The workspace membership was not found.",
            )
        result = WorkspaceMembershipListView(
            workspace_id=resolved_workspace_id,
            workspace_name=active_membership.display_name,
            memberships=self._materialize_member_rows(
                self._repository.list_workspace_memberships(resolved_workspace_id),
                state=state,
                workspace_id=resolved_workspace_id,
            ),
        )
        logger.info(
            "Workspace left workspace_id=%s user_id=%s",
            resolved_workspace_id,
            state.user.user_id if state.user is not None else "anonymous",
        )
        self._append_audit_record(
            state,
            action_kind="workspace.left",
            resource_kind="workspace_membership",
            resource_id=state.user.user_id if state.user is not None else "anonymous",
            outcome="completed",
            payload={"workspace_id": resolved_workspace_id},
            workspace_id=resolved_workspace_id,
        )
        return result

    def remove_member(
        self,
        session_token: str | None,
        *,
        workspace_id: str | None,
        user_id: str,
    ) -> WorkspaceMembershipListView:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        self._authorization_service.authorize(
            state,
            "remove_member",
            resource=_membership_resource(resolved_workspace_id, user_id),
            denied_code="workspace_membership_remove_denied",
            denied_message="The current session cannot remove members from this workspace.",
        )
        if not self._repository.remove_workspace_member(resolved_workspace_id, user_id):
            raise service_error(
                404,
                code="workspace_membership_not_found",
                category="not_found",
                message="The workspace membership was not found.",
            )
        workspace_name = next(
            (
                membership.display_name
                for membership in state.memberships
                if membership.workspace_id == resolved_workspace_id
            ),
            resolved_workspace_id,
        )
        result = WorkspaceMembershipListView(
            workspace_id=resolved_workspace_id,
            workspace_name=workspace_name,
            memberships=self._materialize_member_rows(
                self._repository.list_workspace_memberships(resolved_workspace_id),
                state=state,
                workspace_id=resolved_workspace_id,
            ),
        )
        logger.info(
            "Workspace member removed workspace_id=%s user_id=%s",
            resolved_workspace_id,
            user_id,
        )
        self._append_audit_record(
            state,
            action_kind="workspace.member_removed",
            resource_kind="workspace_membership",
            resource_id=user_id,
            outcome="completed",
            payload={"workspace_id": resolved_workspace_id},
            workspace_id=resolved_workspace_id,
        )
        return result

    def transfer_ownership(
        self,
        session_token: str | None,
        *,
        workspace_id: str | None,
        new_owner_user_id: str,
    ) -> WorkspaceMembershipListView:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        self._authorization_service.authorize(
            state,
            "transfer_workspace_owner",
            resource=_membership_resource(resolved_workspace_id, new_owner_user_id),
            denied_code="workspace_transfer_owner_denied",
            denied_message="The current session cannot transfer workspace ownership.",
        )
        if state.user is None:
            raise service_error(
                401,
                code="auth_required",
                category="auth_required",
                message="The current request requires an authenticated session.",
            )
        transferred = self._repository.transfer_workspace_owner(
            resolved_workspace_id,
            new_owner_user_id=new_owner_user_id,
            current_owner_user_id=state.user.user_id,
        )
        if not transferred:
            raise service_error(
                404,
                code="workspace_membership_not_found",
                category="not_found",
                message="The new workspace owner membership was not found.",
            )
        workspace_name = next(
            (
                membership.display_name
                for membership in state.memberships
                if membership.workspace_id == resolved_workspace_id
            ),
            resolved_workspace_id,
        )
        result = WorkspaceMembershipListView(
            workspace_id=resolved_workspace_id,
            workspace_name=workspace_name,
            memberships=self._materialize_member_rows(
                self._repository.list_workspace_memberships(resolved_workspace_id),
                state=state,
                workspace_id=resolved_workspace_id,
            ),
        )
        logger.info(
            "Workspace ownership transferred workspace_id=%s new_owner_user_id=%s",
            resolved_workspace_id,
            new_owner_user_id,
        )
        self._append_audit_record(
            state,
            action_kind="workspace.ownership_transferred",
            resource_kind="workspace_membership",
            resource_id=new_owner_user_id,
            outcome="completed",
            payload={"workspace_id": resolved_workspace_id},
            workspace_id=resolved_workspace_id,
        )
        return result

    def _workspace_resource(self, workspace_id: str) -> AuthorizationResourceEnvelope:
        return AuthorizationResourceEnvelope(
            resource_kind="workspace",
            workspace_id=workspace_id,
            owner_user_id=None,
            visibility_scope="workspace",
            lifecycle_state="active",
        )

    def _materialize_invitation(
        self,
        invitation: WorkspaceInvitation,
        state: SessionState | None,
    ) -> WorkspaceInvitation:
        can_revoke = False
        if state is not None:
            can_revoke = self._authorization_service.is_allowed(
                state,
                "revoke_invite",
                resource=_invitation_resource(invitation),
            )
        can_accept = (
            state is not None
            and state.user is not None
            and state.user.email is not None
            and state.user.email.casefold() == invitation.email.casefold()
            and invitation.state in {"pending", "delivered"}
        )
        return WorkspaceInvitation(
            invite_id=invitation.invite_id,
            invite_token=invitation.invite_token,
            workspace_id=invitation.workspace_id,
            workspace_name=invitation.workspace_name,
            email=invitation.email,
            role=invitation.role,
            state=invitation.state,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
            delivery=invitation.delivery,
            inviter=invitation.inviter,
            allowed_actions=WorkspaceInvitationAllowedActions(
                revoke=can_revoke,
                accept=can_accept,
                copy_link=can_revoke and invitation.delivery.invite_url is not None,
            ),
            created_by_user_id=invitation.created_by_user_id,
            delivery_error=invitation.delivery_error,
        )

    def _materialize_member_rows(
        self,
        memberships: tuple[WorkspaceMemberRecord, ...],
        *,
        state: SessionState,
        workspace_id: str,
    ) -> tuple[WorkspaceMemberRow, ...]:
        rows: list[WorkspaceMemberRow] = []
        current_user_id = state.user.user_id if state.user is not None else None
        for membership in memberships:
            is_current_user = membership.user.user_id == current_user_id
            can_remove = (not is_current_user) and self._authorization_service.is_allowed(
                state,
                "remove_member",
                resource=_membership_resource(workspace_id, membership.user.user_id),
            )
            can_transfer_owner = (
                not is_current_user
                and membership.workspace_role != "owner"
                and self._authorization_service.is_allowed(
                    state,
                    "transfer_workspace_owner",
                    resource=_membership_resource(workspace_id, membership.user.user_id),
                )
            )
            can_leave = (
                is_current_user
                and membership.workspace_role != "owner"
                and self._authorization_service.is_allowed(
                    state,
                    "leave_workspace",
                    resource=self._workspace_resource(workspace_id),
                )
            )
            rows.append(
                WorkspaceMemberRow(
                    user=membership.user,
                    workspace_role=membership.workspace_role,
                    is_current_user=is_current_user,
                    allowed_actions=WorkspaceMemberAllowedActions(
                        remove=can_remove,
                        transfer_owner=can_transfer_owner,
                        leave=can_leave,
                    ),
                )
            )
        return tuple(rows)

    def _require_workspace_membership(
        self,
        state: SessionState,
        workspace_id: str,
    ) -> None:
        if any(membership.workspace_id == workspace_id for membership in state.memberships):
            return
        raise service_error(
            403,
            code="workspace_membership_required",
            category="permission_denied",
            message="The current session does not belong to the selected workspace.",
        )

    def _append_delivery_audit_record(
        self,
        *,
        state: SessionState,
        invitation: WorkspaceInvitation,
        delivery_attempt: InvitationDeliveryAttempt,
    ) -> None:
        if delivery_attempt.delivery_error is None:
            self._append_audit_record(
                state,
                action_kind="workspace.invite_delivered",
                resource_kind="workspace_invitation",
                resource_id=invitation.invite_id,
                outcome="completed",
                payload={
                    "workspace_id": invitation.workspace_id,
                    "delivery_channel": invitation.delivery.channel,
                    "delivery_status": invitation.delivery.status,
                },
                workspace_id=invitation.workspace_id,
            )
            return
        self._append_audit_record(
            state,
            action_kind="workspace.invite_delivery_failed",
            resource_kind="workspace_invitation",
            resource_id=invitation.invite_id,
            outcome="failed",
            payload={
                "workspace_id": invitation.workspace_id,
                "delivery_channel": invitation.delivery.channel,
                "delivery_status": invitation.delivery.status,
                "reason": delivery_attempt.delivery_error,
            },
            workspace_id=invitation.workspace_id,
        )

    def _append_audit_record(
        self,
        state: SessionState,
        *,
        action_kind: str,
        resource_kind: str,
        resource_id: str,
        outcome: AuditOutcome,
        payload: dict[str, object],
        workspace_id: str | None = None,
    ) -> None:
        if self._audit_repository is None:
            return
        self._audit_repository.append(
            build_audit_record(
                state=state,
                action_kind=action_kind,
                resource_kind=resource_kind,
                resource_id=resource_id,
                outcome=outcome,
                payload=payload,
                workspace_id=workspace_id,
            )
        )


def _invitation_resource(invitation: WorkspaceInvitation) -> AuthorizationResourceEnvelope:
    return AuthorizationResourceEnvelope(
        resource_kind="workspace_invitation",
        workspace_id=invitation.workspace_id,
        owner_user_id=invitation.created_by_user_id,
        visibility_scope="workspace",
        lifecycle_state="archived" if invitation.state in {"revoked", "expired"} else "active",
    )


def _membership_resource(workspace_id: str, user_id: str) -> AuthorizationResourceEnvelope:
    return AuthorizationResourceEnvelope(
        resource_kind="workspace_membership",
        workspace_id=workspace_id,
        owner_user_id=user_id,
        visibility_scope="workspace",
        lifecycle_state="active",
    )
