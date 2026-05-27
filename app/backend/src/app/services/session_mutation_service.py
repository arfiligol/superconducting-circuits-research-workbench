from __future__ import annotations

import logging
from dataclasses import replace
from urllib.parse import urlparse

from src.app.domain.datasets import DatasetDetail
from src.app.domain.session import (
    AppSession,
    DatasetResolution,
    RuntimeMode,
    RuntimeModeSwitchResult,
    ServerTargetListView,
    ServerTargetSummary,
    ServerTargetValidationResult,
    SessionLoginResult,
    SessionRefreshResult,
    SessionState,
    WorkspaceSwitchResult,
)
from src.app.infrastructure.audit_records import build_audit_record
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import service_error
from src.app.services.session_projection_service import (
    SessionProjectionService,
    auth_session_expired_error,
    dataset_resource,
    membership_for_workspace,
    workspace_resource,
)
from src.app.services.session_service_contracts import (
    SessionAuditRepository,
    SessionDatasetRepository,
    SessionRepository,
    SessionTokenTransport,
)

logger = logging.getLogger(__name__)


class SessionMutationService:
    def __init__(
        self,
        repository: SessionRepository,
        dataset_repository: SessionDatasetRepository,
        token_transport: SessionTokenTransport,
        authorization_service: AuthorizationService,
        projection_service: SessionProjectionService,
        audit_repository: SessionAuditRepository | None = None,
    ) -> None:
        self._repository = repository
        self._dataset_repository = dataset_repository
        self._token_transport = token_transport
        self._authorization_service = authorization_service
        self._projection_service = projection_service
        self._audit_repository = audit_repository

    def list_server_targets(self) -> ServerTargetListView:
        targets = self._repository.list_server_targets()
        active_target_origin = next((item.origin for item in targets if item.is_active), None)
        return ServerTargetListView(
            targets=targets,
            active_target_origin=active_target_origin,
        )

    def remember_server_target(
        self,
        *,
        server_origin: str,
        label: str | None,
    ) -> ServerTargetSummary:
        validation = self.validate_server_target(server_origin=server_origin, label=label)
        if validation.status != "validated":
            raise server_target_error(validation)
        return self._repository.remember_server_target(server_origin, label)

    def validate_server_target(
        self,
        *,
        server_origin: str,
        label: str | None = None,
    ) -> ServerTargetValidationResult:
        parsed = urlparse(server_origin)
        if parsed.scheme not in {"http", "https"} or parsed.hostname is None or parsed.port is None:
            target = self._repository.set_server_target_validation_status(
                origin=server_origin,
                label=label,
                validation_status="target_validation_failed",
            )
            return ServerTargetValidationResult(
                target=target,
                status="target_validation_failed",
                message=(
                    "The selected server target must be an http(s) origin with an "
                    "explicit port."
                ),
            )
        if parsed.hostname.endswith(".invalid") or "offline" in parsed.hostname:
            target = self._repository.set_server_target_validation_status(
                origin=server_origin,
                label=label,
                validation_status="target_unreachable",
            )
            return ServerTargetValidationResult(
                target=target,
                status="target_unreachable",
                message="The selected server target could not be reached.",
            )
        if parsed.port == 9999 or "incompatible" in parsed.hostname:
            target = self._repository.set_server_target_validation_status(
                origin=server_origin,
                label=label,
                validation_status="target_incompatible",
            )
            return ServerTargetValidationResult(
                target=target,
                status="target_incompatible",
                message="The selected server target is not compatible with this app build.",
            )
        target = self._repository.set_server_target_validation_status(
            origin=server_origin,
            label=label,
            validation_status="validated",
        )
        return ServerTargetValidationResult(
            target=target,
            status="validated",
            message="The selected server target is ready for online mode.",
        )

    def switch_runtime_mode(
        self,
        *,
        session_token: str | None,
        runtime_mode: RuntimeMode,
        server_origin: str | None,
        label: str | None = None,
    ) -> RuntimeModeSwitchResult:
        previous_state = self._projection_service.current_visibility_state(session_token)
        self._invalidate_caller_continuity(session_token)

        if runtime_mode == "local":
            next_state = self._repository.switch_runtime_mode(runtime_mode="local")
            detached_task_ids = self._projection_service.detached_task_ids(
                previous_state,
                next_state,
            )
            self._append_audit_record(
                state=None,
                action_kind="session.runtime_mode_switched",
                outcome="completed",
                payload={
                    "runtime_mode": "local",
                    "auth_transition": "entered_local_bypass",
                    "detached_task_ids": list(detached_task_ids),
                },
                resource_kind="runtime_mode",
                resource_id="local",
                workspace_id="local-space",
            )
            return RuntimeModeSwitchResult(
                session=self._projection_service.build_local_session(next_state),
                outcome="entered_local",
                auth_transition="entered_local_bypass",
                session_reset=True,
                detached_task_ids=detached_task_ids,
            )

        validation = self.validate_server_target(server_origin=server_origin or "", label=label)
        if validation.status != "validated":
            self._append_audit_record(
                state=previous_state,
                action_kind="session.runtime_mode_switch_rejected",
                outcome="rejected",
                payload={
                    "requested_runtime_mode": "online",
                    "server_origin": server_origin,
                    "validation_status": validation.status,
                },
                resource_kind="runtime_mode",
                resource_id="online",
            )
            raise server_target_error(validation)

        next_state = self._repository.switch_runtime_mode(
            runtime_mode="online",
            server_target_origin=validation.target.origin,
        )
        detached_task_ids = self._projection_service.detached_task_ids(previous_state, next_state)
        self._append_audit_record(
            state=previous_state,
            action_kind="session.runtime_mode_switched",
            outcome="completed",
            payload={
                "runtime_mode": "online",
                "server_origin": validation.target.origin,
                "auth_transition": "online_auth_required",
                "detached_task_ids": list(detached_task_ids),
            },
            resource_kind="runtime_mode",
            resource_id="online",
        )
        return RuntimeModeSwitchResult(
            session=self._projection_service.build_online_public_session(
                auth_state="anonymous",
                auth_reason=None,
                target=self._projection_service.active_target(),
            ),
            outcome="entered_online_auth_required",
            auth_transition="online_auth_required",
            session_reset=True,
            detached_task_ids=detached_task_ids,
        )

    def login(
        self,
        *,
        email: str,
        password: str,
    ) -> SessionLoginResult:
        if self._repository.get_runtime_mode() != "online":
            raise service_error(
                409,
                code="runtime_mode_online_required",
                category="conflict",
                message="Switch to online mode before signing in.",
            )
        state = self._repository.create_authenticated_session(
            email=email,
            password=password,
        )
        if state is None:
            logger.warning("Login failed for email=%s", email.strip().lower())
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
            raise auth_session_expired_error()
        logger.info("Login succeeded for user_id=%s", state.user.user_id if state.user else "none")
        self._append_audit_record(
            state=state,
            action_kind="auth.login_succeeded",
            outcome="accepted",
            payload={"email": email.strip().lower()},
        )
        return SessionLoginResult(
            session=self._projection_service.build_online_authenticated_session(state),
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def refresh(self, refresh_token: str | None) -> SessionRefreshResult:
        if self._repository.get_runtime_mode() != "online":
            raise service_error(
                401,
                code="auth_refresh_invalid",
                category="auth_required",
                message="Refresh tokens are only available in online mode.",
            )
        if refresh_token is None:
            logger.warning("Refresh rejected because refresh token is missing")
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
            session=self._projection_service.build_online_authenticated_session(state),
            access_token=self._token_transport.issue_token(state.session_id),
            refresh_token=rotated_token,
        )

    def logout(
        self,
        session_token: str | None,
    ) -> AppSession:
        if self._repository.get_runtime_mode() != "online":
            return self._projection_service.build_local_session(
                self._repository.get_session_state()
            )
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
        return self._projection_service.build_online_public_session(
            auth_state="anonymous",
            auth_reason=None,
            target=self._projection_service.active_target(),
        )

    def switch_active_workspace(
        self,
        session_token: str | None,
        workspace_id: str,
    ) -> WorkspaceSwitchResult:
        current_state = self._projection_service.require_authenticated_session_state(session_token)
        target_membership = membership_for_workspace(current_state, workspace_id)
        self._authorization_service.authorize(
            replace(
                current_state,
                workspace_id=workspace_id,
                workspace_role=target_membership.role
                if target_membership is not None
                else current_state.workspace_role,
            ),
            "switch_workspace",
            resource=workspace_resource(workspace_id),
            denied_code="workspace_membership_required",
            denied_message="The requested workspace is not available to the current session.",
        )
        if target_membership is None:
            self._append_audit_record(
                state=current_state,
                action_kind="session.active_workspace_switch_rejected",
                outcome="rejected",
                payload={"target_workspace_id": workspace_id},
                resource_kind="workspace",
                resource_id=workspace_id,
                workspace_id=workspace_id,
            )
            raise service_error(
                403,
                code="workspace_membership_required",
                category="permission_denied",
                message="The requested workspace is not available to the current session.",
            )

        previous_dataset_id = current_state.active_dataset_id
        previous_visible_state = current_state
        switched_state = self._repository.set_authenticated_active_workspace_id(
            current_state.session_id,
            workspace_id,
        )
        if switched_state is None:
            raise auth_session_expired_error()

        resolved_dataset_id, resolution = self._resolve_workspace_dataset(
            state=switched_state,
            previous_dataset_id=previous_dataset_id,
        )
        final_state = self._repository.set_authenticated_active_dataset_id(
            switched_state.session_id,
            resolved_dataset_id,
        )
        if final_state is None:
            raise auth_session_expired_error()
        detached_task_ids = self._projection_service.detached_task_ids(
            previous_visible_state,
            final_state,
        )
        self._append_audit_record(
            state=final_state,
            action_kind="session.active_workspace_switched",
            outcome="completed",
            payload={
                "workspace_id": final_state.workspace_id,
                "active_dataset_resolution": resolution,
                "active_dataset_id": resolved_dataset_id,
                "detached_task_ids": list(detached_task_ids),
            },
            resource_kind="workspace",
            resource_id=final_state.workspace_id,
            workspace_id=final_state.workspace_id,
        )

        return WorkspaceSwitchResult(
            session=self._projection_service.build_online_authenticated_session(final_state),
            active_dataset_resolution=resolution,
            detached_task_ids=detached_task_ids,
        )

    def set_active_dataset(
        self,
        session_token: str | None,
        dataset_id: str | None,
    ) -> AppSession:
        if self._repository.get_runtime_mode() == "local":
            return self._set_local_active_dataset(dataset_id)

        state = self._projection_service.require_authenticated_session_state(session_token)
        if dataset_id is None:
            cleared_state = self._repository.set_authenticated_active_dataset_id(
                state.session_id,
                None,
            )
            if cleared_state is None:
                raise auth_session_expired_error()
            self._append_audit_record(
                state=cleared_state,
                action_kind="session.active_dataset_cleared",
                outcome="completed",
                payload={"workspace_id": cleared_state.workspace_id},
                resource_kind="dataset",
                resource_id=state.active_dataset_id or "none",
            )
            return self._projection_service.build_online_authenticated_session(cleared_state)

        dataset = self._require_visible_dataset(dataset_id, state)
        self._authorization_service.authorize(
            state,
            "switch_dataset",
            resource=dataset_resource(dataset),
            denied_code="dataset_not_visible_in_workspace",
            denied_message="The selected dataset is not visible in the active workspace.",
        )

        updated_state = self._repository.set_authenticated_active_dataset_id(
            state.session_id,
            dataset_id,
        )
        if updated_state is None:
            raise auth_session_expired_error()
        self._append_audit_record(
            state=updated_state,
            action_kind="session.active_dataset_switched",
            outcome="completed",
            payload={"dataset_id": dataset_id, "workspace_id": updated_state.workspace_id},
            resource_kind="dataset",
            resource_id=dataset_id,
        )
        return self._projection_service.build_online_authenticated_session(updated_state)

    def _set_local_active_dataset(self, dataset_id: str | None) -> AppSession:
        state = self._repository.get_session_state()
        if dataset_id is None:
            updated_state = self._repository.set_active_dataset_id(None)
            return self._projection_service.build_local_session(updated_state)
        self._require_visible_dataset(dataset_id, state)
        updated_state = self._repository.set_active_dataset_id(dataset_id)
        return self._projection_service.build_local_session(updated_state)

    def _require_visible_dataset(self, dataset_id: str, state: SessionState) -> DatasetDetail:
        dataset = self._dataset_repository.get_dataset(dataset_id)
        if dataset is None:
            self._append_audit_record(
                state=state,
                action_kind="session.active_dataset_switch_rejected",
                outcome="rejected",
                payload={"dataset_id": dataset_id, "reason": "dataset_not_found"},
                resource_kind="dataset",
                resource_id=dataset_id,
            )
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        if dataset.lifecycle_state == "archived":
            self._append_audit_record(
                state=state,
                action_kind="session.active_dataset_switch_rejected",
                outcome="rejected",
                payload={"dataset_id": dataset_id, "reason": "dataset_archived"},
                resource_kind="dataset",
                resource_id=dataset_id,
            )
            raise service_error(
                409,
                code="dataset_archived",
                category="conflict",
                message=f"Dataset {dataset_id} is archived and cannot be activated.",
            )
        if not self._authorization_service.is_visible_dataset(dataset, state):
            self._append_audit_record(
                state=state,
                action_kind="session.active_dataset_switch_rejected",
                outcome="rejected",
                payload={"dataset_id": dataset_id, "reason": "dataset_not_visible_in_workspace"},
                resource_kind="dataset",
                resource_id=dataset_id,
            )
            raise service_error(
                403,
                code="dataset_not_visible_in_workspace",
                category="permission_denied",
                message="The selected dataset is not visible in the active workspace.",
            )
        return dataset

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

    def _invalidate_caller_continuity(self, session_token: str | None) -> None:
        if session_token is None or self._repository.get_runtime_mode() != "online":
            return
        verified = self._token_transport.verify_token(session_token)
        if verified.status != "valid" or verified.session_id is None:
            return
        self._repository.invalidate_authenticated_session(verified.session_id)

    def _append_audit_record(
        self,
        *,
        state: SessionState | None,
        action_kind: str,
        outcome: str,
        payload: dict[str, object],
        resource_kind: str = "session",
        resource_id: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        if self._audit_repository is None:
            return
        resolved_resource_id = resource_id or (
            state.session_id if state is not None else "anonymous"
        )
        self._audit_repository.append(
            build_audit_record(
                state=state,
                action_kind=action_kind,
                resource_kind=resource_kind,
                resource_id=resolved_resource_id,
                outcome=outcome,  # type: ignore[arg-type]
                payload=payload,
                workspace_id=workspace_id,
            )
        )


def server_target_error(result: ServerTargetValidationResult):
    code_map = {
        "target_validation_failed": ("target_validation_failed", 422),
        "target_unreachable": ("target_unreachable", 409),
        "target_incompatible": ("target_incompatible", 409),
        "online_target_rejected": ("online_target_rejected", 409),
    }
    code, status_code = code_map.get(result.status, ("online_target_rejected", 409))
    return service_error(
        status_code,
        code=code,
        category="conflict",
        message=result.message,
    )
