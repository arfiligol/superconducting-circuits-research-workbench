from __future__ import annotations

from src.app.domain.authorization import (
    AuthorizationAction,
    AuthorizationResourceEnvelope,
    AuthorizationSubject,
)
from src.app.domain.circuit_definitions import AllowedActions as DefinitionAllowedActions
from src.app.domain.circuit_definitions import CircuitDefinitionRecord
from src.app.domain.datasets import DatasetAllowedActions, DatasetDetail
from src.app.domain.session import (
    SessionCapabilities,
    SessionState,
    WorkspaceAllowedActions,
    WorkspaceMembership,
)
from src.app.domain.tasks import TaskAllowedActions, TaskDetail
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.services.service_errors import service_error


class AuthorizationService:
    def __init__(self, adapter: CasbinAuthorizationAdapter) -> None:
        self._adapter = adapter

    def build_session_capabilities(self, state: SessionState) -> SessionCapabilities:
        workspace_actions = self.build_workspace_allowed_actions(state, self._active_membership(state))
        return SessionCapabilities(
            can_switch_workspace=len(state.memberships) > 1,
            can_switch_dataset=workspace_actions.activate_dataset,
            can_invite_members=workspace_actions.invite_members,
            can_remove_members=workspace_actions.remove_members,
            can_transfer_workspace_owner=workspace_actions.transfer_owner,
            can_leave_workspace=workspace_actions.leave_workspace,
            can_submit_tasks=self.is_allowed(
                state,
                "submit_task",
                resource=self._workspace_resource(state.workspace_id),
            ),
            can_manage_workspace_tasks=self.is_allowed(
                state,
                "cancel_workspace_task",
                resource=self._workspace_resource(state.workspace_id),
            ),
            can_cancel_own_tasks=self.is_allowed(
                state,
                "cancel_own_task",
                resource=self._workspace_resource(state.workspace_id),
            ),
            can_cancel_workspace_tasks=self.is_allowed(
                state,
                "cancel_workspace_task",
                resource=self._workspace_resource(state.workspace_id),
            ),
            can_terminate_workspace_tasks=self.is_allowed(
                state,
                "terminate_workspace_task",
                resource=self._workspace_resource(state.workspace_id),
            ),
            can_retry_own_tasks=self.is_allowed(
                state,
                "retry_own_task",
                resource=self._workspace_resource(state.workspace_id),
            ),
            can_retry_workspace_tasks=self.is_allowed(
                state,
                "retry_workspace_task",
                resource=self._workspace_resource(state.workspace_id),
            ),
            can_manage_definitions=self.is_allowed(
                state,
                "manage_definition",
                resource=self._workspace_resource(state.workspace_id),
            ),
            can_manage_datasets=self.is_allowed(
                state,
                "manage_dataset",
                resource=self._workspace_resource(state.workspace_id),
            ),
            can_view_audit_logs=self.is_allowed(
                state,
                "view_audit_log",
                resource=self._workspace_resource(state.workspace_id),
            ),
        )

    def build_workspace_allowed_actions(
        self,
        state: SessionState,
        membership: WorkspaceMembership | None,
    ) -> WorkspaceAllowedActions:
        workspace_id = membership.workspace_id if membership is not None else state.workspace_id
        resource = self._workspace_resource(workspace_id)
        return WorkspaceAllowedActions(
            switch_to=membership is not None,
            activate_dataset=membership is not None
            and self.is_allowed(state, "switch_dataset", resource=resource),
            invite_members=membership is not None
            and self.is_allowed(state, "invite_member", resource=resource),
            remove_members=membership is not None
            and self.is_allowed(state, "remove_member", resource=resource),
            transfer_owner=membership is not None
            and self.is_allowed(state, "transfer_workspace_owner", resource=resource),
            leave_workspace=membership is not None
            and self.is_allowed(state, "leave_workspace", resource=resource),
            view_audit_logs=membership is not None
            and self.is_allowed(state, "view_audit_log", resource=resource),
            manage_definitions=membership is not None
            and self.is_allowed(state, "manage_definition", resource=resource),
            manage_datasets=membership is not None
            and self.is_allowed(state, "manage_dataset", resource=resource),
            manage_tasks=membership is not None
            and self.is_allowed(state, "cancel_workspace_task", resource=resource),
        )

    def build_dataset_allowed_actions(
        self,
        dataset: DatasetDetail,
        state: SessionState,
    ) -> DatasetAllowedActions:
        resource = AuthorizationResourceEnvelope(
            resource_kind="dataset",
            workspace_id=dataset.workspace_id,
            owner_user_id=dataset.owner_user_id,
            visibility_scope=dataset.visibility_scope,
            lifecycle_state=dataset.lifecycle_state,
        )
        can_manage = self.is_allowed(state, "manage_dataset", resource=resource)
        return DatasetAllowedActions(
            select=self.is_allowed(state, "switch_dataset", resource=resource),
            update_profile=can_manage,
            publish=can_manage,
            archive=can_manage,
        )

    def build_definition_allowed_actions(
        self,
        definition: CircuitDefinitionRecord,
        state: SessionState,
    ) -> DefinitionAllowedActions:
        resource = AuthorizationResourceEnvelope(
            resource_kind="definition",
            workspace_id=definition.workspace_id,
            owner_user_id=definition.owner_user_id,
            visibility_scope=definition.visibility_scope,
            lifecycle_state=definition.lifecycle_state,
        )
        can_manage = self.is_allowed(state, "manage_definition", resource=resource)
        return DefinitionAllowedActions(
            update=can_manage and definition.lifecycle_state == "active",
            delete=can_manage and definition.lifecycle_state != "deleted",
            publish=can_manage and definition.lifecycle_state == "active",
            clone=True,
        )

    def build_task_allowed_actions(
        self,
        task: TaskDetail,
        state: SessionState,
    ) -> TaskAllowedActions:
        task_resource = AuthorizationResourceEnvelope(
            resource_kind="task",
            workspace_id=task.workspace_id,
            owner_user_id=task.owner_user_id,
            visibility_scope=task.visibility_scope,
            lifecycle_state="active",
        )
        can_cancel = self.is_allowed(
            state,
            "cancel_workspace_task" if task.owner_user_id != state.user.user_id else "cancel_own_task",
            resource=task_resource,
        )
        can_terminate = self.is_allowed(
            state,
            "terminate_workspace_task",
            resource=task_resource,
        )
        can_retry = self.is_allowed(
            state,
            "retry_workspace_task" if task.owner_user_id != state.user.user_id else "retry_own_task",
            resource=task_resource,
        )
        return TaskAllowedActions(
            attach=self.is_visible_task(task, state),
            cancel=can_cancel,
            terminate=can_terminate,
            retry=can_retry,
            rejection_reason=None,
        )

    def authorize(
        self,
        state: SessionState,
        action: AuthorizationAction,
        *,
        resource: AuthorizationResourceEnvelope,
        denied_code: str,
        denied_message: str,
    ) -> None:
        if not self.is_allowed(state, action, resource=resource):
            raise service_error(
                403,
                code=denied_code,
                category="permission_denied",
                message=denied_message,
            )

    def is_allowed(
        self,
        state: SessionState,
        action: AuthorizationAction,
        *,
        resource: AuthorizationResourceEnvelope,
    ) -> bool:
        return self._adapter.decide(
            subject=self._subject(state),
            action=action,
            resource=resource,
        ).allowed

    def is_visible_dataset(self, dataset: DatasetDetail, state: SessionState) -> bool:
        if dataset.workspace_id != state.workspace_id:
            return False
        if dataset.lifecycle_state != "active":
            return False
        if dataset.visibility_scope == "workspace" and dataset.workspace_id == state.workspace_id:
            return True
        if state.user is not None and state.user.platform_role == "admin":
            return True
        return dataset.owner_user_id == state.user.user_id if state.user is not None else False

    def is_visible_definition(self, definition: CircuitDefinitionRecord, state: SessionState) -> bool:
        if definition.workspace_id != state.workspace_id:
            return False
        if definition.lifecycle_state == "deleted":
            return False
        if definition.visibility_scope == "workspace" and definition.workspace_id == state.workspace_id:
            return True
        if state.user is not None and state.user.platform_role == "admin":
            return True
        return definition.owner_user_id == state.user.user_id if state.user is not None else False

    def is_visible_task(self, task: TaskDetail, state: SessionState) -> bool:
        if state.user is None:
            return False
        if task.workspace_id != state.workspace_id:
            return False
        if task.visibility_scope == "workspace":
            return True
        return task.owner_user_id == state.user.user_id

    def _subject(self, state: SessionState) -> AuthorizationSubject:
        return AuthorizationSubject(
            user_id=state.user.user_id if state.user is not None else None,
            platform_role=state.user.platform_role if state.user is not None else None,
            workspace_role=state.workspace_role,
            workspace_id=state.workspace_id,
        )

    def _workspace_resource(self, workspace_id: str | None) -> AuthorizationResourceEnvelope:
        return AuthorizationResourceEnvelope(
            resource_kind="workspace",
            workspace_id=workspace_id,
            owner_user_id=None,
            visibility_scope="workspace",
            lifecycle_state="active",
        )

    def _active_membership(self, state: SessionState) -> WorkspaceMembership | None:
        for membership in state.memberships:
            if membership.workspace_id == state.workspace_id:
                return membership
        return None
