from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol

from src.app.domain.audit import AuditRecord
from src.app.domain.datasets import DatasetDetail
from src.app.domain.session import ServerTargetSummary, SessionState
from src.app.domain.tasks import TaskDetail

TokenVerificationStatus = Literal["valid", "expired", "invalid"]
RefreshVerificationStatus = Literal["valid", "expired", "invalid"]


class VerifiedSessionToken(Protocol):
    status: TokenVerificationStatus
    session_id: str | None


class SessionRepository(Protocol):
    def get_runtime_mode(self) -> str: ...

    def get_session_state(self) -> SessionState: ...

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

    def set_active_dataset_id(self, dataset_id: str | None) -> SessionState: ...

    def get_authenticated_last_active_dataset_id(
        self,
        session_id: str,
        workspace_id: str,
    ) -> str | None: ...

    def get_default_dataset_id(self, workspace_id: str) -> str | None: ...

    def list_server_targets(self) -> tuple[ServerTargetSummary, ...]: ...

    def remember_server_target(
        self,
        origin: str,
        label: str | None = None,
    ) -> ServerTargetSummary: ...

    def set_server_target_validation_status(
        self,
        *,
        origin: str,
        label: str | None,
        validation_status: str,
    ) -> ServerTargetSummary: ...

    def switch_runtime_mode(
        self,
        *,
        runtime_mode: str,
        server_target_origin: str | None = None,
    ) -> SessionState: ...


class SessionDatasetRepository(Protocol):
    def get_dataset(self, dataset_id: str) -> DatasetDetail | None: ...

    def list_dataset_details(self) -> Sequence[DatasetDetail]: ...


class SessionTaskRepository(Protocol):
    def list_tasks(self) -> Sequence[TaskDetail]: ...


class SessionTokenTransport(Protocol):
    def issue_token(self, session_id: str) -> str: ...

    def verify_token(self, token: str) -> VerifiedSessionToken: ...


class SessionAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...
