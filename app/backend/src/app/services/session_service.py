from __future__ import annotations

from src.app.domain.session import RuntimeMode
from src.app.services.session_mutation_service import SessionMutationService
from src.app.services.session_projection_service import SessionProjectionService
from src.app.services.session_service_contracts import (
    SessionAuditRepository,
    SessionDatasetRepository,
    SessionRepository,
    SessionTaskRepository,
    SessionTokenTransport,
)


class SessionService:
    def __init__(
        self,
        repository: SessionRepository,
        dataset_repository: SessionDatasetRepository,
        token_transport: SessionTokenTransport,
        projection_service: SessionProjectionService,
        mutation_service: SessionMutationService,
        audit_repository: SessionAuditRepository | None = None,
        task_repository: SessionTaskRepository | None = None,
    ) -> None:
        self._repository = repository
        self._dataset_repository = dataset_repository
        self._token_transport = token_transport
        self._projection_service = projection_service
        self._mutation_service = mutation_service
        self._audit_repository = audit_repository
        self._task_repository = task_repository

    def get_session(self, session_token: str | None):
        return self._projection_service.get_session(session_token)

    def list_server_targets(self):
        return self._mutation_service.list_server_targets()

    def remember_server_target(
        self,
        *,
        server_origin: str,
        label: str | None,
    ):
        return self._mutation_service.remember_server_target(
            server_origin=server_origin,
            label=label,
        )

    def validate_server_target(
        self,
        *,
        server_origin: str,
        label: str | None = None,
    ):
        return self._mutation_service.validate_server_target(
            server_origin=server_origin,
            label=label,
        )

    def switch_runtime_mode(
        self,
        *,
        session_token: str | None,
        runtime_mode: RuntimeMode,
        server_origin: str | None,
        label: str | None = None,
    ):
        return self._mutation_service.switch_runtime_mode(
            session_token=session_token,
            runtime_mode=runtime_mode,
            server_origin=server_origin,
            label=label,
        )

    def require_authenticated_session_state(self, session_token: str | None):
        return self._projection_service.require_authenticated_session_state(session_token)

    def login(
        self,
        *,
        email: str,
        password: str,
    ):
        return self._mutation_service.login(email=email, password=password)

    def refresh(self, refresh_token: str | None):
        return self._mutation_service.refresh(refresh_token)

    def logout(
        self,
        session_token: str | None,
    ):
        return self._mutation_service.logout(session_token)

    def switch_active_workspace(
        self,
        session_token: str | None,
        workspace_id: str,
    ):
        return self._mutation_service.switch_active_workspace(session_token, workspace_id)

    def set_active_dataset(
        self,
        session_token: str | None,
        dataset_id: str | None,
    ):
        return self._mutation_service.set_active_dataset(session_token, dataset_id)
