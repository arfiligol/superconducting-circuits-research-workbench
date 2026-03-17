from __future__ import annotations

import logging

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

logger = logging.getLogger(__name__)


class AuthorizationService:
    def __init__(self, adapter: CasbinAuthorizationAdapter) -> None:
        self._adapter = adapter

    def build_session_capabilities(self, state: SessionState) -> SessionCapabilities:
        if state.runtime_mode == "local":
            return SessionCapabilities(
                can_switch_runtime_mode=True,
                can_switch_workspace=False,
                can_switch_dataset=True,
                can_import_datasets=True,
                can_export_datasets=True,
                can_invite_members=False,
                can_remove_members=False,
                can_transfer_workspace_owner=False,
                can_leave_workspace=False,
                can_submit_tasks=True,
                can_cancel_local_tasks=True,
                can_terminate_local_tasks=True,
                can_retry_local_tasks=True,
                can_manage_workspace_tasks=False,
                can_cancel_own_tasks=False,
                can_cancel_workspace_tasks=False,
                can_terminate_workspace_tasks=False,
                can_retry_own_tasks=False,
                can_retry_workspace_tasks=False,
                can_manage_definitions=True,
                can_publish_definitions=False,
                can_manage_datasets=True,
                can_view_audit_logs=False,
            )

        workspace_actions = self.build_workspace_allowed_actions(
            state, self._active_membership(state)
        )
        return SessionCapabilities(
            can_switch_runtime_mode=True,
            can_switch_workspace=len(state.memberships) > 1,
            can_switch_dataset=workspace_actions.activate_dataset,
            can_import_datasets=True,
            can_export_datasets=True,
            can_invite_members=workspace_actions.invite_members,
            can_remove_members=workspace_actions.remove_members,
            can_transfer_workspace_owner=workspace_actions.transfer_owner,
            can_leave_workspace=workspace_actions.leave_workspace,
            can_submit_tasks=self.is_allowed(
                state,
                "submit_task",
                resource=self._resource("task", workspace_id=state.workspace_id),
            ),
            can_cancel_local_tasks=False,
            can_terminate_local_tasks=False,
            can_retry_local_tasks=False,
            can_manage_workspace_tasks=self.is_allowed(
                state,
                "cancel_workspace_task",
                resource=self._resource("task", workspace_id=state.workspace_id),
            ),
            can_cancel_own_tasks=self.is_allowed(
                state,
                "cancel_own_task",
                resource=self._resource(
                    "task",
                    workspace_id=state.workspace_id,
                    owner_user_id=state.user.user_id if state.user is not None else None,
                ),
            ),
            can_cancel_workspace_tasks=self.is_allowed(
                state,
                "cancel_workspace_task",
                resource=self._resource("task", workspace_id=state.workspace_id),
            ),
            can_terminate_workspace_tasks=self.is_allowed(
                state,
                "terminate_workspace_task",
                resource=self._resource("task", workspace_id=state.workspace_id),
            ),
            can_retry_own_tasks=self.is_allowed(
                state,
                "retry_own_task",
                resource=self._resource(
                    "task",
                    workspace_id=state.workspace_id,
                    owner_user_id=state.user.user_id if state.user is not None else None,
                ),
            ),
            can_retry_workspace_tasks=self.is_allowed(
                state,
                "retry_workspace_task",
                resource=self._resource("task", workspace_id=state.workspace_id),
            ),
            can_manage_definitions=self.is_allowed(
                state,
                "manage_definition",
                resource=self._resource("definition", workspace_id=state.workspace_id),
            ),
            can_publish_definitions=self.is_allowed(
                state,
                "manage_definition",
                resource=self._resource("definition", workspace_id=state.workspace_id),
            ),
            can_manage_datasets=self.is_allowed(
                state,
                "manage_dataset",
                resource=self._resource("dataset", workspace_id=state.workspace_id),
            ),
            can_view_audit_logs=self.is_allowed(
                state,
                "view_audit_log",
                resource=self._resource("audit_log", workspace_id=state.workspace_id),
            ),
        )

    def build_workspace_allowed_actions(
        self,
        state: SessionState,
        membership: WorkspaceMembership | None,
    ) -> WorkspaceAllowedActions:
        if state.runtime_mode == "local":
            return WorkspaceAllowedActions(
                switch_to=False,
                activate_dataset=True,
                invite_members=False,
                remove_members=False,
                transfer_owner=False,
                leave_workspace=False,
                view_audit_logs=False,
                manage_definitions=True,
                manage_datasets=True,
                manage_tasks=True,
            )

        workspace_id = membership.workspace_id if membership is not None else state.workspace_id
        return WorkspaceAllowedActions(
            switch_to=membership is not None,
            activate_dataset=membership is not None
            and self.is_allowed(
                state,
                "switch_dataset",
                resource=self._resource("dataset", workspace_id=workspace_id),
            ),
            invite_members=membership is not None
            and self.is_allowed(
                state,
                "invite_member",
                resource=self._workspace_resource(workspace_id),
            ),
            remove_members=membership is not None
            and self.is_allowed(
                state,
                "remove_member",
                resource=self._resource("workspace_membership", workspace_id=workspace_id),
            ),
            transfer_owner=membership is not None
            and self.is_allowed(
                state,
                "transfer_workspace_owner",
                resource=self._resource("workspace_membership", workspace_id=workspace_id),
            ),
            leave_workspace=membership is not None
            and membership.role != "owner"
            and self.is_allowed(
                state,
                "leave_workspace",
                resource=self._workspace_resource(workspace_id),
            ),
            view_audit_logs=membership is not None
            and self.is_allowed(
                state,
                "view_audit_log",
                resource=self._resource("audit_log", workspace_id=workspace_id),
            ),
            manage_definitions=membership is not None
            and self.is_allowed(
                state,
                "manage_definition",
                resource=self._resource("definition", workspace_id=workspace_id),
            ),
            manage_datasets=membership is not None
            and self.is_allowed(
                state,
                "manage_dataset",
                resource=self._resource("dataset", workspace_id=workspace_id),
            ),
            manage_tasks=membership is not None
            and self.is_allowed(
                state,
                "cancel_workspace_task",
                resource=self._resource("task", workspace_id=workspace_id),
            ),
        )

    def build_dataset_allowed_actions(
        self,
        dataset: DatasetDetail,
        state: SessionState,
    ) -> DatasetAllowedActions:
        if state.runtime_mode == "local":
            can_manage = self.is_visible_dataset(dataset, state)
            return DatasetAllowedActions(
                select=can_manage,
                update_profile=can_manage,
                publish=False,
                archive=can_manage,
                delete=can_manage,
                ingest_raw_data=can_manage,
            )

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
            publish=can_manage and dataset.visibility_scope != "workspace",
            archive=can_manage,
            delete=can_manage,
            ingest_raw_data=can_manage,
        )

    def build_definition_allowed_actions(
        self,
        definition: CircuitDefinitionRecord,
        state: SessionState,
    ) -> DefinitionAllowedActions:
        if state.runtime_mode == "local":
            can_manage = self.is_visible_definition(definition, state)
            return DefinitionAllowedActions(
                update=can_manage and definition.lifecycle_state == "active",
                delete=can_manage and definition.lifecycle_state != "deleted",
                publish=False,
                clone=can_manage,
            )

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
            publish=can_manage
            and definition.lifecycle_state == "active"
            and definition.visibility_scope != "workspace",
            clone=True,
        )

    def build_task_allowed_actions(
        self,
        task: TaskDetail,
        state: SessionState,
    ) -> TaskAllowedActions:
        if state.runtime_mode == "local":
            visible = self.is_visible_task(task, state)
            return TaskAllowedActions(
                attach=visible,
                cancel=visible,
                terminate=visible,
                retry=visible,
                rejection_reason=None,
            )

        task_resource = AuthorizationResourceEnvelope(
            resource_kind="task",
            workspace_id=task.workspace_id,
            owner_user_id=task.owner_user_id,
            visibility_scope=task.visibility_scope,
            lifecycle_state="active",
        )
        can_cancel = self.is_allowed(
            state,
            "cancel_workspace_task"
            if task.owner_user_id != state.user.user_id
            else "cancel_own_task",
            resource=task_resource,
        )
        can_terminate = self.is_allowed(
            state,
            "terminate_workspace_task",
            resource=task_resource,
        )
        can_retry = self.is_allowed(
            state,
            "retry_workspace_task"
            if task.owner_user_id != state.user.user_id
            else "retry_own_task",
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
            logger.warning(
                (
                    "Authorization denied action=%s runtime_mode=%s workspace_id=%s "
                    "resource_kind=%s resource_workspace_id=%s user_id=%s"
                ),
                action,
                state.runtime_mode,
                state.workspace_id,
                resource.resource_kind,
                resource.workspace_id,
                state.user.user_id if state.user is not None else "anonymous",
            )
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
        if state.runtime_mode == "local":
            return self._is_allowed_local(action, resource)
        return self._adapter.decide(
            subject=self._subject(state),
            action=action,
            resource=resource,
        ).allowed

    def is_visible_dataset(self, dataset: DatasetDetail, state: SessionState) -> bool:
        if dataset.lifecycle_state != "active":
            return False
        if state.runtime_mode == "local":
            return (
                dataset.visibility_scope == "local"
                and dataset.workspace_id == state.workspace_id
            )
        if dataset.workspace_id != state.workspace_id:
            return False
        if dataset.visibility_scope == "workspace":
            return True
        if state.user is not None and state.user.platform_role == "admin":
            return True
        return dataset.owner_user_id == state.user.user_id if state.user is not None else False

    def is_visible_definition(
        self, definition: CircuitDefinitionRecord, state: SessionState
    ) -> bool:
        if definition.lifecycle_state == "deleted":
            return False
        if state.runtime_mode == "local":
            return (
                definition.visibility_scope == "local"
                and definition.workspace_id == state.workspace_id
            )
        if definition.workspace_id != state.workspace_id:
            return False
        if definition.visibility_scope == "workspace":
            return True
        if state.user is not None and state.user.platform_role == "admin":
            return True
        return definition.owner_user_id == state.user.user_id if state.user is not None else False

    def is_visible_task(self, task: TaskDetail, state: SessionState) -> bool:
        if state.runtime_mode == "local":
            return task.workspace_id == state.workspace_id and task.visibility_scope == "local"
        if state.user is None:
            return False
        if task.workspace_id != state.workspace_id:
            return False
        if task.visibility_scope == "workspace":
            return True
        return task.owner_user_id == state.user.user_id

    def _is_allowed_local(
        self,
        action: AuthorizationAction,
        resource: AuthorizationResourceEnvelope,
    ) -> bool:
        if resource.workspace_id not in {None, "local-space"}:
            return False
        if action in {
            "switch_runtime_mode",
            "switch_dataset",
            "submit_task",
            "cancel_own_task",
            "terminate_workspace_task",
            "retry_own_task",
            "manage_definition",
            "manage_dataset",
        }:
            return True
        if action in {
            "switch_workspace",
            "invite_member",
            "revoke_invite",
            "leave_workspace",
            "remove_member",
            "transfer_workspace_owner",
            "cancel_workspace_task",
            "retry_workspace_task",
            "view_audit_log",
        }:
            return False
        return False

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

    def _resource(
        self,
        resource_kind: str,
        *,
        workspace_id: str | None,
        owner_user_id: str | None = None,
    ) -> AuthorizationResourceEnvelope:
        return AuthorizationResourceEnvelope(
            resource_kind=resource_kind,  # type: ignore[arg-type]
            workspace_id=workspace_id,
            owner_user_id=owner_user_id,
            visibility_scope="workspace",
            lifecycle_state="active",
        )

    def _active_membership(self, state: SessionState) -> WorkspaceMembership | None:
        for membership in state.memberships:
            if membership.workspace_id == state.workspace_id:
                return membership
        return None
