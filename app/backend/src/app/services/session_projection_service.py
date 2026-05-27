from __future__ import annotations

from dataclasses import replace
from typing import Literal

from src.app.domain.datasets import DatasetDetail
from src.app.domain.session import (
    ActiveDatasetContext,
    AppSession,
    ServerTargetSummary,
    SessionAuth,
    SessionConnectionContext,
    SessionState,
    WorkspaceAllowedActions,
    WorkspaceContext,
    WorkspaceMembership,
)
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import service_error
from src.app.services.session_service_contracts import (
    SessionDatasetRepository,
    SessionRepository,
    SessionTaskRepository,
    SessionTokenTransport,
)


class SessionProjectionService:
    def __init__(
        self,
        repository: SessionRepository,
        dataset_repository: SessionDatasetRepository,
        token_transport: SessionTokenTransport,
        authorization_service: AuthorizationService,
        task_repository: SessionTaskRepository | None = None,
    ) -> None:
        self._repository = repository
        self._dataset_repository = dataset_repository
        self._token_transport = token_transport
        self._authorization_service = authorization_service
        self._task_repository = task_repository

    def get_session(self, session_token: str | None) -> AppSession:
        if self._repository.get_runtime_mode() == "local":
            return self.build_local_session(self._repository.get_session_state())

        state, auth_state, auth_reason = self.resolve_online_session_context(session_token)
        if state is None:
            return self.build_online_public_session(
                auth_state=auth_state,
                auth_reason=auth_reason,
                target=self.active_target(),
            )
        return self.build_online_authenticated_session(state)

    def require_authenticated_session_state(self, session_token: str | None) -> SessionState:
        state, auth_state, _auth_reason = self.resolve_online_session_context(session_token)
        if auth_state == "authenticated" and state is not None:
            return state
        if self._repository.get_runtime_mode() != "online":
            raise service_error(
                401,
                code="auth_required",
                category="auth_required",
                message="The current request requires an authenticated online session.",
            )
        if auth_state == "anonymous":
            raise service_error(
                401,
                code="auth_required",
                category="auth_required",
                message="The current request requires an authenticated session.",
            )
        if auth_state == "degraded" or state is None or state.user is None:
            raise auth_session_expired_error()
        return state

    def build_online_authenticated_session(self, state: SessionState) -> AppSession:
        membership = membership_for_workspace(state, state.workspace_id)
        if membership is None:
            raise service_error(
                403,
                code="workspace_membership_required",
                category="permission_denied",
                message="The active workspace is not available to the current session.",
            )

        active_dataset = self.build_active_dataset_context(state)
        memberships = tuple(
            with_active_membership_flag(
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
            runtime_mode="online",
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
            connection=SessionConnectionContext(target=self.active_target()),
        )

    def build_local_session(self, state: SessionState) -> AppSession:
        state, active_dataset = self._resolve_local_active_dataset_context(state)
        membership = membership_for_workspace(state, state.workspace_id)
        if membership is None:
            membership = state.memberships[0]
        memberships = tuple(
            with_active_membership_flag(
                replace(
                    item,
                    allowed_actions=self._authorization_service.build_workspace_allowed_actions(
                        state,
                        item,
                    ),
                ),
                state=state,
            )
            for item in state.memberships
        )
        capabilities = self._authorization_service.build_session_capabilities(
            replace(state, memberships=memberships)
        )
        return AppSession(
            session_id=state.session_id,
            runtime_mode="local",
            auth=SessionAuth(
                state="local_bypass",
                mode="local_bypass",
                reason=None,
            ),
            user=state.user,
            memberships=memberships,
            workspace=WorkspaceContext(
                workspace_id=membership.workspace_id,
                slug=membership.slug,
                display_name=membership.display_name,
                role=membership.role,
                default_task_scope=membership.default_task_scope,
                allowed_actions=membership.allowed_actions,
            ),
            active_dataset=active_dataset,
            capabilities=capabilities,
            connection=SessionConnectionContext(target=None),
        )

    def build_online_public_session(
        self,
        *,
        auth_state: Literal["anonymous", "degraded"],
        auth_reason: str | None,
        target: ServerTargetSummary | None,
    ) -> AppSession:
        return AppSession(
            session_id=None,
            runtime_mode="online",
            auth=SessionAuth(
                state=auth_state,
                mode="jwt_refresh_cookie",
                reason=auth_reason,  # type: ignore[arg-type]
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
            capabilities=public_online_capabilities(),
            connection=SessionConnectionContext(target=target),
        )

    def resolve_online_session_context(
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

    def build_active_dataset_context(
        self,
        state: SessionState,
    ) -> ActiveDatasetContext | None:
        if state.active_dataset_id is None:
            return None
        dataset = self._dataset_repository.get_dataset(state.active_dataset_id)
        if dataset is None or not self._authorization_service.is_visible_dataset(dataset, state):
            raise service_error(
                409,
                code="context_rebind_required",
                category="conflict",
                message="Session context must be rebound before continuing.",
            )
        return self._build_active_dataset_context(dataset)

    def active_target(self) -> ServerTargetSummary | None:
        return next(
            (item for item in self._repository.list_server_targets() if item.is_active),
            None,
        )

    def current_visibility_state(self, session_token: str | None) -> SessionState | None:
        if self._repository.get_runtime_mode() == "local":
            return self._repository.get_session_state()
        state, auth_state, _ = self.resolve_online_session_context(session_token)
        if auth_state == "authenticated":
            return state
        current_state = self._repository.get_session_state()
        return current_state if current_state.runtime_mode == "online" else None

    def detached_task_ids(
        self,
        previous_state: SessionState | None,
        next_state: SessionState,
    ) -> tuple[int, ...]:
        if self._task_repository is None or previous_state is None:
            return ()
        detached = [
            task.task_id
            for task in self._task_repository.list_tasks()
            if self._authorization_service.is_visible_task(task, previous_state)
            and not self._authorization_service.is_visible_task(task, next_state)
        ]
        return tuple(sorted(detached))

    def _resolve_local_active_dataset_context(
        self,
        state: SessionState,
    ) -> tuple[SessionState, ActiveDatasetContext | None]:
        if state.active_dataset_id is None:
            return state, None
        dataset = self._dataset_repository.get_dataset(state.active_dataset_id)
        if dataset is None or not self._authorization_service.is_visible_dataset(dataset, state):
            return self._repository.set_active_dataset_id(None), None
        return state, self._build_active_dataset_context(dataset)

    def _build_active_dataset_context(
        self,
        dataset: DatasetDetail,
    ) -> ActiveDatasetContext:
        return ActiveDatasetContext(
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


def workspace_resource(workspace_id: str):
    from src.app.domain.authorization import AuthorizationResourceEnvelope

    return AuthorizationResourceEnvelope(
        resource_kind="workspace",
        workspace_id=workspace_id,
        owner_user_id=None,
        visibility_scope="workspace",
        lifecycle_state="active",
    )


def dataset_resource(dataset: DatasetDetail):
    from src.app.domain.authorization import AuthorizationResourceEnvelope

    return AuthorizationResourceEnvelope(
        resource_kind="dataset",
        workspace_id=dataset.workspace_id,
        owner_user_id=dataset.owner_user_id,
        visibility_scope=dataset.visibility_scope,
        lifecycle_state=dataset.lifecycle_state,
    )


def public_online_capabilities():
    from src.app.domain.session import SessionCapabilities

    return SessionCapabilities(
        can_switch_runtime_mode=True,
        can_switch_workspace=False,
        can_switch_dataset=False,
        can_import_datasets=False,
        can_export_datasets=False,
        can_invite_members=False,
        can_remove_members=False,
        can_transfer_workspace_owner=False,
        can_leave_workspace=False,
        can_submit_tasks=False,
        can_cancel_local_tasks=False,
        can_terminate_local_tasks=False,
        can_retry_local_tasks=False,
        can_manage_workspace_tasks=False,
        can_cancel_own_tasks=False,
        can_cancel_workspace_tasks=False,
        can_terminate_workspace_tasks=False,
        can_retry_own_tasks=False,
        can_retry_workspace_tasks=False,
        can_manage_definitions=False,
        can_publish_definitions=False,
        can_manage_datasets=False,
        can_view_audit_logs=False,
    )


def auth_session_expired_error():
    return service_error(
        401,
        code="auth_session_expired",
        category="auth_required",
        message="The current session could not be restored. Please sign in again.",
    )


def with_active_membership_flag(
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


def membership_for_workspace(
    state: SessionState,
    workspace_id: str,
) -> WorkspaceMembership | None:
    for membership in state.memberships:
        if membership.workspace_id == workspace_id:
            return membership
    return None
