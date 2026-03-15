from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timezone
from typing import Literal, Protocol

from src.app.domain.audit import AuditRecord
from src.app.domain.datasets import DatasetDetail
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.domain.session import (
    ActiveDatasetContext,
    AppSession,
    DatasetResolution,
    SessionAuth,
    SessionLoginResult,
    SessionCapabilities,
    SessionRefreshResult,
    SessionState,
    WorkspaceAllowedActions,
    WorkspaceContext,
    WorkspaceMembership,
    WorkspaceSwitchResult,
)
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import service_error

TokenVerificationStatus = Literal["valid", "expired", "invalid"]
RefreshVerificationStatus = Literal["valid", "expired", "invalid"]


class VerifiedSessionToken(Protocol):
    status: TokenVerificationStatus
    session_id: str | None


class SessionRepository(Protocol):
    def create_authenticated_session(
        self,
        *,
        email: str,
        password: str,
    ) -> SessionState | None: ...

    def get_authenticated_session_state(self, session_id: str) -> SessionState | None: ...

    def invalidate_authenticated_session(self, session_id: str) -> bool: ...

    def issue_refresh_token(self, session_id: str) -> str | None: ...

    def rotate_refresh_token(
        self,
        refresh_token: str,
    ) -> tuple[SessionState | None, str | None, RefreshVerificationStatus]: ...

    def revoke_refresh_family_for_session(self, session_id: str) -> None: ...

    def set_authenticated_active_workspace_id(
        self,
        session_id: str,
        workspace_id: str,
    ) -> SessionState | None: ...

    def set_authenticated_active_dataset_id(
        self,
        session_id: str,
        dataset_id: str | None,
    ) -> SessionState | None: ...

    def get_authenticated_last_active_dataset_id(
        self,
        session_id: str,
        workspace_id: str,
    ) -> str | None: ...

    def get_default_dataset_id(self, workspace_id: str) -> str | None: ...


class SessionDatasetRepository(Protocol):
    def get_dataset(self, dataset_id: str) -> DatasetDetail | None: ...

    def list_dataset_details(self) -> Sequence[DatasetDetail]: ...


class SessionTokenTransport(Protocol):
    def issue_token(self, session_id: str) -> str: ...

    def verify_token(self, token: str) -> VerifiedSessionToken: ...


class SessionAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class SessionService:
    def __init__(
        self,
        repository: SessionRepository,
        dataset_repository: SessionDatasetRepository,
        token_transport: SessionTokenTransport,
        authorization_service: AuthorizationService | None = None,
        audit_repository: SessionAuditRepository | None = None,
    ) -> None:
        self._repository = repository
        self._dataset_repository = dataset_repository
        self._token_transport = token_transport
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )
        self._audit_repository = audit_repository

    def get_session(self, session_token: str | None) -> AppSession:
        state, auth_state, auth_reason = self._resolve_session_context(session_token)
        if state is None:
            return _build_public_session(auth_state=auth_state, auth_reason=auth_reason)
        return self._build_authenticated_session(state)

    def require_authenticated_session_state(self, session_token: str | None) -> SessionState:
        state, auth_state, _auth_reason = self._resolve_session_context(session_token)
        if auth_state == "anonymous":
            raise service_error(
                401,
                code="auth_required",
                category="auth_required",
                message="The current request requires an authenticated session.",
            )
        if auth_state == "degraded" or state is None or state.user is None:
            raise _auth_session_expired_error()
        return state

    def login(
        self,
        *,
        email: str,
        password: str,
    ) -> SessionLoginResult:
        state = self._repository.create_authenticated_session(
            email=email,
            password=password,
        )
        if state is None:
            self._append_audit_record(
                state=None,
                action_kind="auth.login_failed",
                outcome="rejected",
                payload={"email": email.strip().lower()},
            )
            raise service_error(
                401,
                code="auth_invalid_credentials",
                category="auth_required",
                message="The supplied email or password is invalid.",
            )

        access_token = self._token_transport.issue_token(state.session_id)
        refresh_token = self._repository.issue_refresh_token(state.session_id)
        if refresh_token is None:
            raise _auth_session_expired_error()
        self._append_audit_record(
            state=state,
            action_kind="auth.login_succeeded",
            outcome="accepted",
            payload={"email": email.strip().lower()},
        )
        return SessionLoginResult(
            session=self._build_authenticated_session(state),
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def refresh(self, refresh_token: str | None) -> SessionRefreshResult:
        if refresh_token is None:
            self._append_audit_record(
                state=None,
                action_kind="auth.refresh_failed",
                outcome="rejected",
                payload={"reason": "missing_refresh_token"},
            )
            raise service_error(
                401,
                code="auth_refresh_invalid",
                category="auth_required",
                message="The refresh token is missing or invalid.",
            )
        state, rotated_token, refresh_status = self._repository.rotate_refresh_token(refresh_token)
        if refresh_status == "invalid":
            self._append_audit_record(
                state=None,
                action_kind="auth.refresh_failed",
                outcome="rejected",
                payload={"reason": "invalid_refresh_token"},
            )
            raise service_error(
                401,
                code="auth_refresh_invalid",
                category="auth_required",
                message="The refresh token is missing or invalid.",
            )
        if refresh_status == "expired" or state is None or rotated_token is None:
            self._append_audit_record(
                state=state,
                action_kind="auth.refresh_failed",
                outcome="failed",
                payload={"reason": "expired_refresh_token"},
            )
            raise service_error(
                401,
                code="auth_refresh_expired",
                category="auth_required",
                message="The refresh token family has expired.",
            )
        self._append_audit_record(
            state=state,
            action_kind="auth.refresh_succeeded",
            outcome="accepted",
            payload={"reason": "rotated"},
        )
        return SessionRefreshResult(
            session=self._build_authenticated_session(state),
            access_token=self._token_transport.issue_token(state.session_id),
            refresh_token=rotated_token,
        )

    def logout(
        self,
        session_token: str | None,
    ) -> AppSession:
        if session_token is not None:
            verified = self._token_transport.verify_token(session_token)
            if verified.status == "valid" and verified.session_id is not None:
                state = self._repository.get_authenticated_session_state(verified.session_id)
                self._repository.invalidate_authenticated_session(verified.session_id)
                self._append_audit_record(
                    state=state,
                    action_kind="auth.logout",
                    outcome="completed",
                    payload={"reason": "user_requested"},
                )
        return _build_public_session(auth_state="anonymous", auth_reason=None)

    def switch_active_workspace(
        self,
        session_token: str | None,
        workspace_id: str,
    ) -> WorkspaceSwitchResult:
        current_state = self.require_authenticated_session_state(session_token)
        target_membership = _membership_for_workspace(current_state, workspace_id)
        if target_membership is None:
            raise service_error(
                403,
                code="workspace_membership_required",
                category="permission_denied",
                message="The requested workspace is not available to the current session.",
            )

        previous_dataset_id = current_state.active_dataset_id
        switched_state = self._repository.set_authenticated_active_workspace_id(
            current_state.session_id,
            workspace_id,
        )
        if switched_state is None:
            raise _auth_session_expired_error()

        resolved_dataset_id, resolution = self._resolve_workspace_dataset(
            state=switched_state,
            previous_dataset_id=previous_dataset_id,
        )
        final_state = self._repository.set_authenticated_active_dataset_id(
            switched_state.session_id,
            resolved_dataset_id,
        )
        if final_state is None:
            raise _auth_session_expired_error()

        return WorkspaceSwitchResult(
            session=self._build_authenticated_session(final_state),
            active_dataset_resolution=resolution,
            detached_task_ids=(),
        )

    def set_active_dataset(
        self,
        session_token: str | None,
        dataset_id: str | None,
    ) -> AppSession:
        state = self.require_authenticated_session_state(session_token)
        if dataset_id is None:
            cleared_state = self._repository.set_authenticated_active_dataset_id(
                state.session_id,
                None,
            )
            if cleared_state is None:
                raise _auth_session_expired_error()
            return self._build_authenticated_session(cleared_state)

        dataset = self._dataset_repository.get_dataset(dataset_id)
        if dataset is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        if dataset.lifecycle_state == "archived":
            raise service_error(
                409,
                code="dataset_archived",
                category="conflict",
                message=f"Dataset {dataset_id} is archived and cannot be activated.",
            )
        if not self._authorization_service.is_visible_dataset(dataset, state):
            raise service_error(
                403,
                code="dataset_not_visible_in_workspace",
                category="permission_denied",
                message="The selected dataset is not visible in the active workspace.",
            )
        self._authorization_service.authorize(
            state,
            "switch_dataset",
            resource=_dataset_resource(dataset),
            denied_code="dataset_not_visible_in_workspace",
            denied_message="The selected dataset is not visible in the active workspace.",
        )

        updated_state = self._repository.set_authenticated_active_dataset_id(
            state.session_id,
            dataset_id,
        )
        if updated_state is None:
            raise _auth_session_expired_error()
        return self._build_authenticated_session(updated_state)

    def _resolve_workspace_dataset(
        self,
        *,
        state: SessionState,
        previous_dataset_id: str | None,
    ) -> tuple[str | None, DatasetResolution]:
        if previous_dataset_id is not None:
            previous_dataset = self._dataset_repository.get_dataset(previous_dataset_id)
            if previous_dataset is not None and self._authorization_service.is_visible_dataset(
                previous_dataset,
                state,
            ):
                return previous_dataset_id, "preserved"

        last_active_dataset_id = self._repository.get_authenticated_last_active_dataset_id(
            state.session_id,
            state.workspace_id,
        )
        if last_active_dataset_id is not None:
            rebound_dataset = self._dataset_repository.get_dataset(last_active_dataset_id)
            if rebound_dataset is not None and self._authorization_service.is_visible_dataset(
                rebound_dataset,
                state,
            ):
                return last_active_dataset_id, "rebound"

        default_dataset_id = self._repository.get_default_dataset_id(state.workspace_id)
        if default_dataset_id is not None:
            default_dataset = self._dataset_repository.get_dataset(default_dataset_id)
            if default_dataset is not None and self._authorization_service.is_visible_dataset(
                default_dataset,
                state,
            ):
                return default_dataset_id, "rebound"

        visible_datasets = sorted(
            (
                dataset
                for dataset in self._dataset_repository.list_dataset_details()
                if self._authorization_service.is_visible_dataset(dataset, state)
            ),
            key=lambda dataset: dataset.updated_at,
            reverse=True,
        )
        if len(visible_datasets) == 0:
            return None, "cleared"
        return visible_datasets[0].dataset_id, "rebound"

    def _build_authenticated_session(self, state: SessionState) -> AppSession:
        membership = _membership_for_workspace(state, state.workspace_id)
        if membership is None:
            raise service_error(
                403,
                code="workspace_membership_required",
                category="permission_denied",
                message="The active workspace is not available to the current session.",
            )

        active_dataset = None
        if state.active_dataset_id is not None:
            dataset = self._dataset_repository.get_dataset(state.active_dataset_id)
            if dataset is None or not self._authorization_service.is_visible_dataset(dataset, state):
                raise service_error(
                    409,
                    code="context_rebind_required",
                    category="conflict",
                    message="Session context must be rebound before continuing.",
                )
            active_dataset = ActiveDatasetContext(
                dataset_id=dataset.dataset_id,
                name=dataset.name,
                family=dataset.family,
                status=dataset.status,
                owner_user_id=dataset.owner_user_id,
                owner_display_name=dataset.owner,
                workspace_id=dataset.workspace_id,
                visibility_scope=dataset.visibility_scope,
                lifecycle_state=dataset.lifecycle_state,
            )

        memberships = tuple(
            _with_active_membership_flag(
                replace(
                    membership_item,
                    allowed_actions=self._authorization_service.build_workspace_allowed_actions(
                        state,
                        membership_item,
                    ),
                ),
                state=state,
            )
            for membership_item in state.memberships
        )
        active_membership = next(
            item for item in memberships if item.workspace_id == membership.workspace_id
        )
        capabilities = self._authorization_service.build_session_capabilities(
            replace(state, memberships=memberships),
        )
        return AppSession(
            session_id=state.session_id,
            auth=SessionAuth(
                state="authenticated",
                mode="jwt_refresh_cookie",
                reason=None,
            ),
            user=state.user,
            memberships=memberships,
            workspace=WorkspaceContext(
                workspace_id=active_membership.workspace_id,
                slug=active_membership.slug,
                display_name=active_membership.display_name,
                role=active_membership.role,
                default_task_scope=active_membership.default_task_scope,
                allowed_actions=active_membership.allowed_actions,
            ),
            active_dataset=active_dataset,
            capabilities=capabilities,
        )

    def _resolve_session_context(
        self,
        session_token: str | None,
    ) -> tuple[SessionState | None, Literal["authenticated", "anonymous", "degraded"], str | None]:
        if session_token is None:
            return None, "anonymous", None

        verified = self._token_transport.verify_token(session_token)
        if verified.status == "invalid":
            return None, "degraded", "session_invalid"
        if verified.status == "expired" or verified.session_id is None:
            return None, "degraded", "session_expired"

        state = self._repository.get_authenticated_session_state(verified.session_id)
        if state is None or state.user is None or state.auth_state != "authenticated":
            return None, "degraded", "session_expired"
        return state, "authenticated", None

    def _append_audit_record(
        self,
        *,
        state: SessionState | None,
        action_kind: str,
        outcome: str,
        payload: dict[str, object],
    ) -> None:
        if self._audit_repository is None:
            return
        session_id = state.session_id if state is not None else "anonymous"
        actor_user_id = state.user.user_id if state is not None and state.user is not None else "anonymous"
        actor_display_name = (
            state.user.display_name if state is not None and state.user is not None else "anonymous"
        )
        workspace_id = state.workspace_id if state is not None else "auth"
        occurred_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self._audit_repository.append(
            AuditRecord(
                audit_id=f"audit:{action_kind}:{session_id}:{occurred_at}",
                occurred_at=occurred_at,
                actor_user_id=actor_user_id,
                actor_display_name=actor_display_name,
                session_id=session_id,
                correlation_id=f"corr:{action_kind}:{session_id}",
                workspace_id=workspace_id,
                action_kind=action_kind,
                resource_kind="session",
                resource_id=session_id,
                outcome=outcome,  # type: ignore[arg-type]
                payload=payload,
                debug_ref=f"debug:{action_kind}:{session_id}",
            )
        )


def _dataset_resource(dataset: DatasetDetail):
    from src.app.domain.authorization import AuthorizationResourceEnvelope

    return AuthorizationResourceEnvelope(
        resource_kind="dataset",
        workspace_id=dataset.workspace_id,
        owner_user_id=dataset.owner_user_id,
        visibility_scope=dataset.visibility_scope,
        lifecycle_state=dataset.lifecycle_state,
    )


def _build_public_session(
    *,
    auth_state: Literal["anonymous", "degraded"],
    auth_reason: str | None,
) -> AppSession:
    return AppSession(
        session_id=None,
        auth=SessionAuth(
            state=auth_state,
            mode="jwt_refresh_cookie",
            reason=auth_reason,
        ),
        user=None,
        memberships=(),
        workspace=WorkspaceContext(
            workspace_id=None,
            slug=None,
            display_name=None,
            role=None,
            default_task_scope=None,
            allowed_actions=WorkspaceAllowedActions(
                switch_to=False,
                activate_dataset=False,
                invite_members=False,
                remove_members=False,
                transfer_owner=False,
                leave_workspace=False,
                view_audit_logs=False,
                manage_definitions=False,
                manage_datasets=False,
                manage_tasks=False,
            ),
        ),
        active_dataset=None,
        capabilities=_anonymous_capabilities(),
    )


def _anonymous_capabilities():
    return SessionCapabilities(
        can_switch_workspace=False,
        can_switch_dataset=False,
        can_invite_members=False,
        can_remove_members=False,
        can_transfer_workspace_owner=False,
        can_leave_workspace=False,
        can_submit_tasks=False,
        can_manage_workspace_tasks=False,
        can_cancel_own_tasks=False,
        can_cancel_workspace_tasks=False,
        can_terminate_workspace_tasks=False,
        can_retry_own_tasks=False,
        can_retry_workspace_tasks=False,
        can_manage_definitions=False,
        can_manage_datasets=False,
        can_view_audit_logs=False,
    )


def _auth_session_expired_error():
    return service_error(
        401,
        code="auth_session_expired",
        category="auth_required",
        message="The current session could not be restored. Please sign in again.",
    )


def _with_active_membership_flag(
    membership: WorkspaceMembership,
    *,
    state: SessionState,
) -> WorkspaceMembership:
    return WorkspaceMembership(
        workspace_id=membership.workspace_id,
        slug=membership.slug,
        display_name=membership.display_name,
        role=membership.role,
        default_task_scope=membership.default_task_scope,
        is_active=membership.workspace_id == state.workspace_id,
        allowed_actions=membership.allowed_actions,
    )


def _membership_for_workspace(
    state: SessionState,
    workspace_id: str,
) -> WorkspaceMembership | None:
    for membership in state.memberships:
        if membership.workspace_id == workspace_id:
            return membership
    return None
