from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Protocol

from sc_core.execution import TaskResultHandle

from src.app.domain.session import (
    ServerTargetSummary,
    SessionState,
    SessionUser,
    WorkspaceAllowedActions,
    WorkspaceMembership,
)
from src.app.domain.storage import (
    MetadataRecordRef,
    ResultHandleKind,
    ResultHandleRef,
    TracePayloadRef,
)
from src.app.domain.tasks import (
    TaskCreateDraft,
    TaskDetail,
    TaskEvent,
    TaskHistoryView,
    TaskLifecycleUpdate,
    TaskProgress,
    TaskResultRefs,
    resolve_retry_of_task_id,
    resolve_task_control_state,
)
from src.app.domain.workspace_collaboration import (
    CollaborationUserSummary,
    WorkspaceInvitation,
    WorkspaceInvitationAllowedActions,
    WorkspaceInvitationDelivery,
    WorkspaceMemberRecord,
)
from src.app.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)

DEFAULT_REFRESH_TOKEN_LIFETIME_SECONDS = 60 * 60 * 24 * 14
_REQUEST_SESSION_STATE: ContextVar[SessionState | None] = ContextVar(
    "rewrite_request_session_state",
    default=None,
)


@dataclass(frozen=True)
class _RefreshTokenRecord:
    token: str
    session_id: str
    family_id: str
    expires_at: str
    revoked: bool = False


@dataclass(frozen=True)
class _AccountSeed:
    password: str
    prototype: SessionState


@dataclass(frozen=True)
class _WorkspaceInvitationRecord:
    invite_id: str
    invite_token: str
    workspace_id: str
    workspace_name: str
    email: str
    role: str
    state: str
    expires_at: str
    created_at: str
    delivery_status: str
    delivery_channel: str
    invite_url: str | None
    created_by_user_id: str
    delivery_error: str | None = None


@dataclass(frozen=True)
class _PendingInvitationAcceptanceRecord:
    continuation_token: str
    invite_token: str
    created_at: str


@dataclass(frozen=True)
class _ServerTargetRecord:
    origin: str
    label: str
    validation_status: str
    last_checked_at: str | None


class StorageMetadataRepository(Protocol):
    def get_storage_record(self, record_id: str) -> MetadataRecordRef | None: ...

    def get_trace_payload_for_owner_record(
        self,
        owner_record_id: str,
    ) -> TracePayloadRef | None: ...

    def get_result_handle(self, handle_id: str) -> ResultHandleRef | None: ...

    def list_result_handles_for_task(self, task_id: int) -> tuple[ResultHandleRef, ...]: ...

    def save_storage_record(self, record: MetadataRecordRef) -> MetadataRecordRef: ...

    def save_trace_payload(
        self,
        owner_record: MetadataRecordRef,
        trace_payload: TracePayloadRef,
        *,
        writer_version: str | None = None,
    ) -> TracePayloadRef: ...

    def save_result_handle(self, result_handle: ResultHandleRef) -> ResultHandleRef: ...


class TaskSnapshotRepository(Protocol):
    def has_tasks(self) -> bool: ...

    def list_tasks(self) -> tuple[TaskDetail, ...]: ...

    def get_task(self, task_id: int) -> TaskDetail | None: ...

    def create_task(self, draft: TaskCreateDraft) -> TaskDetail: ...

    def save_task_snapshot(self, task: TaskDetail) -> TaskDetail: ...

    def append_task_event(self, task_id: int, event: TaskEvent) -> None: ...


class InMemoryRewriteAppStateRepository:
    def __init__(
        self,
        storage_metadata_repository: StorageMetadataRepository | None = None,
        task_snapshot_repository: TaskSnapshotRepository | None = None,
        *,
        include_task_scaffold: bool = True,
    ) -> None:
        self._storage_metadata_repository = storage_metadata_repository
        self._task_snapshot_repository = task_snapshot_repository
        self._session_state = _seed_session_state()
        self._default_dataset_ids = {
            "local-space": "local-dataset-001",
            "ws-device-lab": "fluxonium-2025-031",
            "ws-modeling": "transmon-coupler-014",
        }
        self._last_active_dataset_ids = {
            "local-space": "local-dataset-001",
            "ws-device-lab": "fluxonium-2025-031",
            "ws-modeling": "transmon-coupler-014",
        }
        self._server_targets: dict[str, _ServerTargetRecord] = {
            "http://127.0.0.1:8000": _ServerTargetRecord(
                origin="http://127.0.0.1:8000",
                label="Default Rewrite Server",
                validation_status="validated",
                last_checked_at="2026-03-17T09:00:00Z",
            ),
        }
        self._active_server_target_origin: str | None = None
        self._auth_accounts = _seed_auth_accounts()
        self._users_by_id = {
            account.prototype.user.user_id: email
            for email, account in self._auth_accounts.items()
            if account.prototype.user is not None
        }
        self._authenticated_sessions: dict[str, SessionState] = {}
        self._session_last_active_dataset_ids: dict[str, dict[str, str]] = {}
        self._next_transport_session_id = 1
        self._refresh_tokens: dict[str, _RefreshTokenRecord] = {}
        self._refresh_family_index: dict[str, set[str]] = {}
        self._workspace_invitations: dict[str, _WorkspaceInvitationRecord] = {}
        self._pending_invitation_acceptances: dict[str, _PendingInvitationAcceptanceRecord] = {}
        self._next_invite_id = 1
        self._tasks = (
            {task.task_id: task for task in build_seed_tasks()} if include_task_scaffold else {}
        )
        self._next_task_id = max(self._tasks, default=305) + 1
        self._persist_seed_task_snapshots()
        self._persist_seed_storage_metadata()

    def get_session_state(self) -> SessionState:
        request_state = _REQUEST_SESSION_STATE.get()
        if request_state is not None:
            return request_state
        return self._session_state

    def build_public_request_session_state(self, auth_state: str) -> SessionState:
        target = self._server_targets.get(self._active_server_target_origin or "")
        return _build_online_public_session_state(
            auth_state=auth_state,
            server_target_origin=self._active_server_target_origin,
            server_target_label=target.label if target is not None else None,
        )

    def get_runtime_mode(self) -> str:
        return self._session_state.runtime_mode

    def list_server_targets(self) -> tuple[ServerTargetSummary, ...]:
        return tuple(
            _to_server_target_summary(
                record,
                is_active=record.origin == self._active_server_target_origin,
            )
            for record in sorted(self._server_targets.values(), key=lambda item: item.origin)
        )

    def remember_server_target(self, origin: str, label: str | None = None) -> ServerTargetSummary:
        record = _ServerTargetRecord(
            origin=origin,
            label=label or _default_server_target_label(origin),
            validation_status=self._server_targets.get(origin, None).validation_status
            if origin in self._server_targets
            else "validated",
            last_checked_at=_now_iso(),
        )
        self._server_targets[origin] = record
        return _to_server_target_summary(
            record,
            is_active=record.origin == self._active_server_target_origin,
        )

    def set_server_target_validation_status(
        self,
        *,
        origin: str,
        label: str | None,
        validation_status: str,
    ) -> ServerTargetSummary:
        record = _ServerTargetRecord(
            origin=origin,
            label=label or _default_server_target_label(origin),
            validation_status=validation_status,
            last_checked_at=_now_iso(),
        )
        self._server_targets[origin] = record
        return _to_server_target_summary(
            record,
            is_active=record.origin == self._active_server_target_origin,
        )

    def switch_runtime_mode(
        self,
        *,
        runtime_mode: str,
        server_target_origin: str | None = None,
    ) -> SessionState:
        if runtime_mode == "local":
            self.revoke_all_authenticated_sessions()
            self._active_server_target_origin = None
            self._session_state = _seed_session_state()
            return self._session_state

        active_target_origin = server_target_origin or self._active_server_target_origin
        if active_target_origin is None:
            self._session_state = _build_online_public_session_state(
                auth_state="anonymous",
                server_target_origin=None,
                server_target_label=None,
            )
            return self._session_state

        target_record = self._server_targets.get(active_target_origin)
        self.revoke_all_authenticated_sessions()
        self._active_server_target_origin = active_target_origin
        self._session_state = _build_online_public_session_state(
            auth_state="anonymous",
            server_target_origin=active_target_origin,
            server_target_label=(
                target_record.label
                if target_record is not None
                else _default_server_target_label(active_target_origin)
            ),
        )
        return self._session_state

    def revoke_all_authenticated_sessions(self) -> None:
        for session_id in list(self._authenticated_sessions):
            self.invalidate_authenticated_session(session_id)

    def bind_request_session_state(self, session_state: SessionState) -> Token[SessionState | None]:
        return _REQUEST_SESSION_STATE.set(session_state)

    def reset_request_session_state(self, token: Token[SessionState | None]) -> None:
        _REQUEST_SESSION_STATE.reset(token)

    def create_authenticated_session(
        self,
        *,
        email: str,
        password: str,
    ) -> SessionState | None:
        normalized_email = email.strip().lower()
        account = self._auth_accounts.get(normalized_email)
        if account is None or account.password != password:
            return None

        session_id = f"rewrite-auth-session-{self._next_transport_session_id}"
        self._next_transport_session_id += 1
        session_state = replace(
            account.prototype,
            session_id=session_id,
            runtime_mode="online",
            auth_state="authenticated",
            auth_mode="jwt_refresh_cookie",
            server_target_origin=self._active_server_target_origin,
            server_target_label=(
                self._server_targets[self._active_server_target_origin].label
                if self._active_server_target_origin in self._server_targets
                else None
            ),
        )
        self._authenticated_sessions[session_id] = session_state
        self._session_last_active_dataset_ids[session_id] = dict(self._last_active_dataset_ids)
        self._session_state = session_state
        return session_state

    def get_authenticated_session_state(self, session_id: str) -> SessionState | None:
        return self._authenticated_sessions.get(session_id)

    def invalidate_authenticated_session(self, session_id: str) -> bool:
        removed = self._authenticated_sessions.pop(session_id, None)
        self.revoke_refresh_family_for_session(session_id)
        self._session_last_active_dataset_ids.pop(session_id, None)
        return removed is not None

    def issue_refresh_token(self, session_id: str) -> str | None:
        if session_id not in self._authenticated_sessions:
            return None
        family_id = f"refresh-family:{session_id}"
        self._revoke_family_tokens(family_id)
        token = token_urlsafe(32)
        record = _RefreshTokenRecord(
            token=token,
            session_id=session_id,
            family_id=family_id,
            expires_at=_expires_at(DEFAULT_REFRESH_TOKEN_LIFETIME_SECONDS),
        )
        self._refresh_tokens[token] = record
        self._refresh_family_index[family_id] = {token}
        return token

    def rotate_refresh_token(
        self,
        refresh_token: str,
    ) -> tuple[SessionState | None, str | None, str]:
        record = self._refresh_tokens.get(refresh_token)
        if record is None:
            return None, None, "invalid"
        if record.revoked:
            return None, None, "invalid"
        if _is_expired(record.expires_at):
            self._refresh_tokens[refresh_token] = replace(record, revoked=True)
            return None, None, "expired"
        session_state = self._authenticated_sessions.get(record.session_id)
        if session_state is None:
            return None, None, "expired"
        self._refresh_tokens[refresh_token] = replace(record, revoked=True)
        rotated_token = token_urlsafe(32)
        rotated_record = _RefreshTokenRecord(
            token=rotated_token,
            session_id=record.session_id,
            family_id=record.family_id,
            expires_at=_expires_at(DEFAULT_REFRESH_TOKEN_LIFETIME_SECONDS),
        )
        self._refresh_tokens[rotated_token] = rotated_record
        self._refresh_family_index.setdefault(record.family_id, set()).add(rotated_token)
        return session_state, rotated_token, "valid"

    def revoke_refresh_family_for_session(self, session_id: str) -> None:
        family_id = f"refresh-family:{session_id}"
        self._revoke_family_tokens(family_id)

    def list_workspace_invitations(self, workspace_id: str) -> tuple[WorkspaceInvitation, ...]:
        return tuple(
            _to_workspace_invitation(record, self._resolve_user_summary(record.created_by_user_id))
            for record in sorted(
                self._workspace_invitations.values(),
                key=lambda item: (item.created_at, item.invite_id),
                reverse=True,
            )
            if record.workspace_id == workspace_id
        )

    def create_workspace_invitation(
        self,
        *,
        workspace_id: str,
        workspace_name: str,
        email: str,
        role: str,
        created_by_user_id: str,
    ) -> WorkspaceInvitation:
        invite_id = f"invite:{self._next_invite_id}"
        self._next_invite_id += 1
        record = _WorkspaceInvitationRecord(
            invite_id=invite_id,
            invite_token=token_urlsafe(24),
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            email=email,
            role=role,
            state="pending",
            expires_at=_expires_at(DEFAULT_REFRESH_TOKEN_LIFETIME_SECONDS),
            created_at=_now_iso(),
            delivery_status="queued_for_delivery",
            delivery_channel="manual_link",
            invite_url=None,
            created_by_user_id=created_by_user_id,
        )
        self._workspace_invitations[invite_id] = record
        return _to_workspace_invitation(record, self._resolve_user_summary(created_by_user_id))

    def update_workspace_invitation_delivery(
        self,
        *,
        invite_id: str,
        state: str,
        delivery_status: str,
        delivery_channel: str,
        invite_url: str | None,
        delivery_error: str | None,
    ) -> WorkspaceInvitation | None:
        record = self._workspace_invitations.get(invite_id)
        if record is None:
            return None
        updated = replace(
            record,
            state=state,
            delivery_status=delivery_status,
            delivery_channel=delivery_channel,
            invite_url=invite_url,
            delivery_error=delivery_error,
        )
        self._workspace_invitations[invite_id] = updated
        return _to_workspace_invitation(
            updated,
            self._resolve_user_summary(updated.created_by_user_id),
        )

    def get_workspace_invitation(self, invite_id: str) -> WorkspaceInvitation | None:
        record = self._workspace_invitations.get(invite_id)
        if record is None:
            return None
        refreshed = self._refresh_invitation_state(record)
        return _to_workspace_invitation(
            refreshed,
            self._resolve_user_summary(refreshed.created_by_user_id),
        )

    def get_workspace_invitation_by_token(self, invite_token: str) -> WorkspaceInvitation | None:
        for record in self._workspace_invitations.values():
            if record.invite_token == invite_token:
                refreshed = self._refresh_invitation_state(record)
                return _to_workspace_invitation(
                    refreshed,
                    self._resolve_user_summary(refreshed.created_by_user_id),
                )
        return None

    def revoke_workspace_invitation(self, invite_id: str) -> WorkspaceInvitation | None:
        record = self._workspace_invitations.get(invite_id)
        if record is None:
            return None
        updated = replace(record, state="revoked")
        self._workspace_invitations[invite_id] = updated
        return _to_workspace_invitation(
            updated,
            self._resolve_user_summary(updated.created_by_user_id),
        )

    def accept_workspace_invitation(
        self,
        *,
        invite_token: str,
        user_email: str,
    ) -> WorkspaceInvitation | None:
        for invite_id, record in self._workspace_invitations.items():
            if record.invite_token != invite_token:
                continue
            refreshed = self._refresh_invitation_state(record)
            self._workspace_invitations[invite_id] = refreshed
            if refreshed.state not in {"pending", "delivered"}:
                return _to_workspace_invitation(
                    refreshed,
                    self._resolve_user_summary(refreshed.created_by_user_id),
                )
            account = self._auth_accounts.get(user_email)
            if account is None or account.prototype.user is None:
                return _to_workspace_invitation(
                    refreshed,
                    self._resolve_user_summary(refreshed.created_by_user_id),
                )
            updated_prototype = _upsert_membership(
                account.prototype,
                workspace_id=refreshed.workspace_id,
                workspace_slug=_workspace_slug(refreshed.workspace_id),
                workspace_name=refreshed.workspace_name,
                role=refreshed.role,
                default_task_scope="workspace" if refreshed.role == "owner" else "owned",
            )
            self._auth_accounts[user_email] = _AccountSeed(
                password=account.password,
                prototype=updated_prototype,
            )
            self._users_by_id[updated_prototype.user.user_id] = user_email
            self._update_authenticated_sessions_for_user(
                updated_prototype.user.user_id, updated_prototype
            )
            accepted = replace(refreshed, state="accepted")
            self._workspace_invitations[invite_id] = accepted
            return _to_workspace_invitation(
                accepted,
                self._resolve_user_summary(accepted.created_by_user_id),
            )
        return None

    def create_pending_invitation_acceptance(self, invite_token: str) -> str:
        continuation_token = token_urlsafe(24)
        self._pending_invitation_acceptances[continuation_token] = (
            _PendingInvitationAcceptanceRecord(
                continuation_token=continuation_token,
                invite_token=invite_token,
                created_at=_now_iso(),
            )
        )
        return continuation_token

    def consume_pending_invitation_acceptance(self, continuation_token: str) -> str | None:
        record = self._pending_invitation_acceptances.pop(continuation_token, None)
        if record is None:
            return None
        return record.invite_token

    def list_workspace_memberships(self, workspace_id: str) -> tuple[WorkspaceMemberRecord, ...]:
        memberships: list[WorkspaceMemberRecord] = []
        for account in self._auth_accounts.values():
            prototype = account.prototype
            if prototype.user is None:
                continue
            for membership in prototype.memberships:
                if membership.workspace_id == workspace_id:
                    memberships.append(
                        WorkspaceMemberRecord(
                            user=_to_user_summary(prototype.user),
                            workspace_role=membership.role,
                        )
                    )
        return tuple(
            sorted(
                memberships,
                key=lambda item: (
                    _workspace_role_sort_key(item.workspace_role),
                    item.user.display_name,
                ),
            )
        )

    def remove_workspace_member(self, workspace_id: str, user_id: str) -> bool:
        email = self._users_by_id.get(user_id)
        if email is None:
            return False
        account = self._auth_accounts.get(email)
        if account is None:
            return False
        updated_memberships = tuple(
            membership
            for membership in account.prototype.memberships
            if membership.workspace_id != workspace_id
        )
        if len(updated_memberships) == len(account.prototype.memberships):
            return False
        active_membership = updated_memberships[0] if len(updated_memberships) > 0 else None
        updated_prototype = replace(
            account.prototype,
            memberships=updated_memberships,
            workspace_id=active_membership.workspace_id if active_membership is not None else "",
            workspace_slug=active_membership.slug if active_membership is not None else "",
            workspace_display_name=active_membership.display_name
            if active_membership is not None
            else "",
            workspace_role=active_membership.role if active_membership is not None else "viewer",
            default_task_scope=active_membership.default_task_scope
            if active_membership is not None
            else "owned",
            active_dataset_id=_resolve_rebound_dataset_id(
                current_workspace_id=account.prototype.workspace_id,
                current_dataset_id=account.prototype.active_dataset_id,
                target_workspace_id=active_membership.workspace_id
                if active_membership is not None
                else None,
                last_active_dataset_ids=self._last_active_dataset_ids,
                default_dataset_ids=self._default_dataset_ids,
            ),
        )
        self._auth_accounts[email] = _AccountSeed(
            password=account.password,
            prototype=updated_prototype,
        )
        self._update_authenticated_sessions_for_user(user_id, updated_prototype)
        return True

    def transfer_workspace_owner(
        self,
        workspace_id: str,
        new_owner_user_id: str,
        current_owner_user_id: str,
    ) -> bool:
        new_owner_email = self._users_by_id.get(new_owner_user_id)
        current_owner_email = self._users_by_id.get(current_owner_user_id)
        if new_owner_email is None or current_owner_email is None:
            return False
        new_owner = self._auth_accounts.get(new_owner_email)
        current_owner = self._auth_accounts.get(current_owner_email)
        if new_owner is None or current_owner is None:
            return False
        self._auth_accounts[new_owner_email] = _AccountSeed(
            password=new_owner.password,
            prototype=_replace_membership_role(new_owner.prototype, workspace_id, "owner"),
        )
        self._auth_accounts[current_owner_email] = _AccountSeed(
            password=current_owner.password,
            prototype=_replace_membership_role(current_owner.prototype, workspace_id, "member"),
        )
        self._update_authenticated_sessions_for_user(
            new_owner_user_id,
            self._auth_accounts[new_owner_email].prototype,
        )
        self._update_authenticated_sessions_for_user(
            current_owner_user_id,
            self._auth_accounts[current_owner_email].prototype,
        )
        return True

    def set_authenticated_active_workspace_id(
        self,
        session_id: str,
        workspace_id: str,
    ) -> SessionState | None:
        session_state = self._authenticated_sessions.get(session_id)
        if session_state is None:
            return None
        current_workspace_id = session_state.workspace_id
        session_dataset_state = self._session_last_active_dataset_ids.setdefault(
            session_id,
            dict(self._last_active_dataset_ids),
        )
        if session_state.active_dataset_id is not None:
            session_dataset_state[current_workspace_id] = session_state.active_dataset_id

        membership = _membership_for_workspace(session_state.memberships, workspace_id)
        if membership is None:
            return session_state

        memberships = tuple(
            WorkspaceMembership(
                workspace_id=item.workspace_id,
                slug=item.slug,
                display_name=item.display_name,
                role=item.role,
                default_task_scope=item.default_task_scope,
                is_active=item.workspace_id == workspace_id,
                allowed_actions=item.allowed_actions,
            )
            for item in session_state.memberships
        )
        updated_state = replace(
            session_state,
            workspace_id=membership.workspace_id,
            workspace_slug=membership.slug,
            workspace_display_name=membership.display_name,
            workspace_role=membership.role,
            default_task_scope=membership.default_task_scope,
            memberships=memberships,
            active_dataset_id=None,
        )
        self._authenticated_sessions[session_id] = updated_state
        self._session_state = updated_state
        return updated_state

    def set_authenticated_active_dataset_id(
        self,
        session_id: str,
        dataset_id: str | None,
    ) -> SessionState | None:
        session_state = self._authenticated_sessions.get(session_id)
        if session_state is None:
            return None

        updated_state = replace(session_state, active_dataset_id=dataset_id)
        self._authenticated_sessions[session_id] = updated_state
        self._session_state = updated_state
        session_dataset_state = self._session_last_active_dataset_ids.setdefault(
            session_id,
            dict(self._last_active_dataset_ids),
        )
        if dataset_id is None:
            session_dataset_state.pop(updated_state.workspace_id, None)
        else:
            session_dataset_state[updated_state.workspace_id] = dataset_id
        return updated_state

    def _resolve_user_summary(self, user_id: str) -> CollaborationUserSummary | None:
        email = self._users_by_id.get(user_id)
        if email is None:
            return None
        account = self._auth_accounts.get(email)
        if account is None or account.prototype.user is None:
            return None
        return _to_user_summary(account.prototype.user)

    def get_authenticated_last_active_dataset_id(
        self,
        session_id: str,
        workspace_id: str,
    ) -> str | None:
        return self._session_last_active_dataset_ids.get(session_id, {}).get(workspace_id)

    def set_active_workspace_id(self, workspace_id: str) -> SessionState:
        current_workspace_id = self._session_state.workspace_id
        if self._session_state.active_dataset_id is not None:
            self._last_active_dataset_ids[current_workspace_id] = (
                self._session_state.active_dataset_id
            )

        membership = _membership_for_workspace(self._session_state.memberships, workspace_id)
        if membership is None:
            return self._session_state

        memberships = tuple(
            WorkspaceMembership(
                workspace_id=item.workspace_id,
                slug=item.slug,
                display_name=item.display_name,
                role=item.role,
                default_task_scope=item.default_task_scope,
                is_active=item.workspace_id == workspace_id,
                allowed_actions=item.allowed_actions,
            )
            for item in self._session_state.memberships
        )
        self._session_state = replace(
            self._session_state,
            workspace_id=membership.workspace_id,
            workspace_slug=membership.slug,
            workspace_display_name=membership.display_name,
            workspace_role=membership.role,
            default_task_scope=membership.default_task_scope,
            memberships=memberships,
            active_dataset_id=None,
        )
        return self._session_state

    def set_active_dataset_id(self, dataset_id: str | None) -> SessionState:
        self._session_state = replace(self._session_state, active_dataset_id=dataset_id)
        if dataset_id is None:
            self._last_active_dataset_ids.pop(self._session_state.workspace_id, None)
        else:
            self._last_active_dataset_ids[self._session_state.workspace_id] = dataset_id
        return self._session_state

    def get_last_active_dataset_id(self, workspace_id: str) -> str | None:
        return self._last_active_dataset_ids.get(workspace_id)

    def get_default_dataset_id(self, workspace_id: str) -> str | None:
        return self._default_dataset_ids.get(workspace_id)

    def override_session_state(self, **changes: object) -> SessionState:
        self._session_state = replace(self._session_state, **changes)
        return self._session_state

    def _revoke_family_tokens(self, family_id: str) -> None:
        for token in self._refresh_family_index.get(family_id, set()):
            record = self._refresh_tokens.get(token)
            if record is not None:
                self._refresh_tokens[token] = replace(record, revoked=True)

    def _refresh_invitation_state(
        self,
        record: _WorkspaceInvitationRecord,
    ) -> _WorkspaceInvitationRecord:
        if record.state != "pending":
            return record
        if _is_expired(record.expires_at):
            return replace(record, state="expired")
        return record

    def _update_authenticated_sessions_for_user(
        self,
        user_id: str,
        prototype: SessionState,
    ) -> None:
        for session_id, session_state in list(self._authenticated_sessions.items()):
            if session_state.user is None or session_state.user.user_id != user_id:
                continue
            active_membership = _membership_for_workspace(
                prototype.memberships,
                session_state.workspace_id,
            ) or (prototype.memberships[0] if len(prototype.memberships) > 0 else None)
            session_dataset_state = self._session_last_active_dataset_ids.setdefault(
                session_id,
                dict(self._last_active_dataset_ids),
            )
            if session_state.active_dataset_id is not None and len(session_state.workspace_id) > 0:
                session_dataset_state[session_state.workspace_id] = session_state.active_dataset_id
            updated_state = replace(
                prototype,
                session_id=session_id,
                runtime_mode="online",
                auth_state=session_state.auth_state,
                auth_mode=session_state.auth_mode,
                server_target_origin=session_state.server_target_origin,
                server_target_label=session_state.server_target_label,
                active_dataset_id=_resolve_rebound_dataset_id(
                    current_workspace_id=session_state.workspace_id,
                    current_dataset_id=session_state.active_dataset_id,
                    target_workspace_id=active_membership.workspace_id
                    if active_membership is not None
                    else None,
                    last_active_dataset_ids=session_dataset_state,
                    default_dataset_ids=self._default_dataset_ids,
                ),
                workspace_id=active_membership.workspace_id
                if active_membership is not None
                else "",
                workspace_slug=active_membership.slug if active_membership is not None else "",
                workspace_display_name=active_membership.display_name
                if active_membership is not None
                else "",
                workspace_role=active_membership.role
                if active_membership is not None
                else "viewer",
                default_task_scope=active_membership.default_task_scope
                if active_membership is not None
                else "owned",
            )
            self._authenticated_sessions[session_id] = updated_state
            self._session_state = updated_state

    def list_tasks(self) -> list[TaskDetail]:
        if self._task_snapshot_repository is not None:
            return [
                self._hydrate_task(task) for task in self._task_snapshot_repository.list_tasks()
            ]
        return [self._hydrate_task(task) for task in self._tasks.values()]

    def get_task(self, task_id: int) -> TaskDetail | None:
        if self._task_snapshot_repository is not None:
            task = self._task_snapshot_repository.get_task(task_id)
            if task is None:
                return None
            return self._hydrate_task(task)

        task = self._tasks.get(task_id)
        if task is None:
            return None
        hydrated_task = self._hydrate_task(task)
        self._tasks[task_id] = hydrated_task
        return hydrated_task

    def list_task_events(self, task_id: int) -> tuple[TaskEvent, ...]:
        task = self.get_task(task_id)
        if task is None:
            return ()
        return task.events

    def get_task_history_view(self, task_id: int) -> TaskHistoryView | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        latest_event = task.events[-1] if len(task.events) > 0 else None
        return TaskHistoryView(
            task=task,
            event_count=len(task.events),
            latest_event=latest_event,
        )

    def create_task(self, draft: TaskCreateDraft) -> TaskDetail:
        if self._task_snapshot_repository is not None:
            task_snapshot = self._task_snapshot_repository.create_task(draft)
            task_with_result_refs = replace(
                task_snapshot,
                result_refs=build_pending_result_refs(
                    task_id=task_snapshot.task_id,
                    draft=draft,
                ),
            )
            self._persist_result_refs(task_with_result_refs.result_refs)
            return self._hydrate_task(task_with_result_refs)

        task_id = self._next_task_id
        task = TaskDetail(
            task_id=task_id,
            kind=draft.kind,
            lane=draft.lane,
            execution_mode=draft.execution_mode,
            status="queued",
            submitted_at="2026-03-12 10:30:00",
            owner_user_id=draft.owner_user_id,
            owner_display_name=draft.owner_display_name,
            workspace_id=draft.workspace_id,
            workspace_slug=draft.workspace_slug,
            visibility_scope=draft.visibility_scope,
            dataset_id=draft.dataset_id,
            definition_id=draft.definition_id,
            summary=draft.summary,
            queue_backend="in_memory_scaffold",
            worker_task_name=draft.worker_task_name,
            request_ready=draft.request_ready,
            submitted_from_active_dataset=draft.submitted_from_active_dataset,
            progress=TaskProgress(
                phase="queued",
                percent_complete=0,
                summary="Task accepted by rewrite in-memory scaffold.",
                updated_at="2026-03-12 10:30:00",
            ),
            result_refs=build_pending_result_refs(task_id=task_id, draft=draft),
        )
        self._tasks[task.task_id] = task
        self._next_task_id += 1
        self._persist_result_refs(task.result_refs)
        hydrated_task = self._hydrate_task(task)
        self._tasks[task.task_id] = hydrated_task
        return hydrated_task

    def update_task_lifecycle(self, update: TaskLifecycleUpdate) -> TaskDetail | None:
        current_task = self.get_task(update.task_id)
        if current_task is None:
            return None

        updated_task = replace(
            current_task,
            status=update.status,
            summary=update.summary or current_task.summary,
            dispatch=update.dispatch or current_task.dispatch,
            progress=replace(
                current_task.progress,
                phase=update.status,
                percent_complete=update.progress_percent_complete,
                summary=update.progress_summary,
                updated_at=update.progress_updated_at,
            ),
            result_refs=update.result_refs or current_task.result_refs,
        )
        if self._task_snapshot_repository is not None:
            persisted_snapshot = self._task_snapshot_repository.save_task_snapshot(updated_task)
            if update.result_refs is not None:
                self._persist_result_refs(update.result_refs)
            return self._hydrate_task(persisted_snapshot)

        if update.result_refs is not None:
            updated_task = replace(updated_task, result_refs=update.result_refs)
            self._persist_result_refs(update.result_refs)

        hydrated_task = self._hydrate_task(updated_task)
        self._tasks[update.task_id] = hydrated_task
        return hydrated_task

    def append_task_event(self, task_id: int, event: TaskEvent) -> None:
        current_task = self.get_task(task_id)
        if current_task is None:
            return
        updated_task = replace(
            current_task,
            control_state=resolve_task_control_state(
                current_task.status,
                (*current_task.events, event),
            ),
            retry_of_task_id=resolve_retry_of_task_id((*current_task.events, event)),
            events=(*current_task.events, event),
        )
        if self._task_snapshot_repository is not None:
            self._task_snapshot_repository.append_task_event(task_id, event)
            persisted_task = self._task_snapshot_repository.get_task(task_id)
            if persisted_task is not None:
                self._tasks[task_id] = persisted_task
            return
        self._tasks[task_id] = updated_task

    def _persist_seed_task_snapshots(self) -> None:
        if self._task_snapshot_repository is None:
            return
        if self._task_snapshot_repository.has_tasks():
            return

        for task in self._tasks.values():
            self._task_snapshot_repository.save_task_snapshot(task)

    def _persist_seed_storage_metadata(self) -> None:
        if self._storage_metadata_repository is None:
            return

        for task in self._tasks.values():
            self._ensure_result_refs(task.result_refs)

    def _persist_result_refs(self, result_refs: TaskResultRefs) -> None:
        if self._storage_metadata_repository is None:
            return

        for record in result_refs.metadata_records:
            self._storage_metadata_repository.save_storage_record(record)

        trace_owner_record = _trace_owner_record(result_refs)
        if result_refs.trace_payload is not None and trace_owner_record is not None:
            self._storage_metadata_repository.save_trace_payload(
                trace_owner_record,
                result_refs.trace_payload,
                writer_version="rewrite-backend.runtime",
            )

        for result_handle in result_refs.result_handles:
            self._storage_metadata_repository.save_result_handle(result_handle)

    def _ensure_result_refs(self, result_refs: TaskResultRefs) -> None:
        if self._storage_metadata_repository is None:
            return

        for record in result_refs.metadata_records:
            if self._storage_metadata_repository.get_storage_record(record.record_id) is None:
                self._storage_metadata_repository.save_storage_record(record)

        trace_owner_record = _trace_owner_record(result_refs)
        if (
            result_refs.trace_payload is not None
            and trace_owner_record is not None
            and self._storage_metadata_repository.get_trace_payload_for_owner_record(
                trace_owner_record.record_id
            )
            is None
        ):
            self._storage_metadata_repository.save_trace_payload(
                trace_owner_record,
                result_refs.trace_payload,
                writer_version="rewrite-backend.runtime",
            )

        for result_handle in result_refs.result_handles:
            if self._storage_metadata_repository.get_result_handle(result_handle.handle_id) is None:
                self._storage_metadata_repository.save_result_handle(result_handle)

    def _hydrate_task(self, task: TaskDetail) -> TaskDetail:
        if self._storage_metadata_repository is None:
            return task

        persisted_result_handles = self._storage_metadata_repository.list_result_handles_for_task(
            task.task_id
        )
        if len(persisted_result_handles) == 0:
            return task

        primary_result_handle = persisted_result_handles[0]
        owner_record = (
            primary_result_handle.provenance.trace_batch_record
            or primary_result_handle.provenance.analysis_run_record
        )
        trace_payload = task.result_refs.trace_payload
        if owner_record is not None:
            trace_payload = (
                self._storage_metadata_repository.get_trace_payload_for_owner_record(
                    owner_record.record_id
                )
                or trace_payload
            )
        metadata_records = _build_metadata_records_for_hydration(
            owner_record=owner_record,
            primary_result_handle=primary_result_handle,
        )
        return replace(
            task,
            result_refs=TaskResultRefs(
                result_handle=_build_storage_linkage_handle(
                    owner_record=owner_record,
                    current_handle=task.result_refs.result_handle,
                ),
                metadata_records=metadata_records,
                trace_payload=trace_payload,
                result_handles=persisted_result_handles,
            ),
        )


def _seed_session_state() -> SessionState:
    memberships = (
        WorkspaceMembership(
            workspace_id="local-space",
            slug="local-space",
            display_name="Local Space",
            role="owner",
            default_task_scope="local",
            is_active=True,
            allowed_actions=WorkspaceAllowedActions(
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
            ),
        ),
    )
    return SessionState(
        session_id="local-session",
        runtime_mode="local",
        auth_state="local_bypass",
        auth_mode="local_bypass",
        user=SessionUser(
            user_id="local-operator",
            display_name="Local Operator",
            email=None,
            platform_role="user",
        ),
        server_target_origin=None,
        server_target_label=None,
        workspace_id="local-space",
        workspace_slug="local-space",
        workspace_display_name="Local Space",
        workspace_role="owner",
        default_task_scope="local",
        memberships=memberships,
        active_dataset_id="local-dataset-001",
    )


def _seed_auth_accounts() -> dict[str, _AccountSeed]:
    collaborator_memberships = (
        WorkspaceMembership(
            workspace_id="ws-modeling",
            slug="modeling",
            display_name="Modeling Workspace",
            role="viewer",
            default_task_scope="owned",
            is_active=True,
            allowed_actions=WorkspaceAllowedActions(
                switch_to=True,
                activate_dataset=True,
                invite_members=False,
                remove_members=False,
                transfer_owner=False,
                leave_workspace=True,
                view_audit_logs=False,
                manage_definitions=False,
                manage_datasets=False,
                manage_tasks=False,
            ),
        ),
    )
    admin_memberships = (
        WorkspaceMembership(
            workspace_id="ws-device-lab",
            slug="device-lab",
            display_name="Device Lab Workspace",
            role="owner",
            default_task_scope="workspace",
            is_active=True,
            allowed_actions=WorkspaceAllowedActions(
                switch_to=True,
                activate_dataset=True,
                invite_members=True,
                remove_members=True,
                transfer_owner=True,
                leave_workspace=False,
                view_audit_logs=True,
                manage_definitions=True,
                manage_datasets=True,
                manage_tasks=True,
            ),
        ),
        WorkspaceMembership(
            workspace_id="ws-modeling",
            slug="modeling",
            display_name="Modeling Workspace",
            role="owner",
            default_task_scope="workspace",
            is_active=False,
            allowed_actions=WorkspaceAllowedActions(
                switch_to=True,
                activate_dataset=True,
                invite_members=True,
                remove_members=True,
                transfer_owner=True,
                leave_workspace=False,
                view_audit_logs=True,
                manage_definitions=True,
                manage_datasets=True,
                manage_tasks=True,
            ),
        ),
    )
    collaborator_state = SessionState(
        session_id="rewrite-collaborator-session",
        runtime_mode="online",
        auth_state="authenticated",
        auth_mode="jwt_refresh_cookie",
        user=SessionUser(
            user_id="researcher-02",
            display_name="Collaborator User",
            email="collaborator.local@example.com",
            platform_role="user",
        ),
        server_target_origin="http://127.0.0.1:8000",
        server_target_label="Default Rewrite Server",
        workspace_id="ws-modeling",
        workspace_slug="modeling",
        workspace_display_name="Modeling Workspace",
        workspace_role="viewer",
        default_task_scope="owned",
        memberships=collaborator_memberships,
        active_dataset_id=None,
    )
    admin_state = SessionState(
        session_id="rewrite-admin-session",
        runtime_mode="online",
        auth_state="authenticated",
        auth_mode="jwt_refresh_cookie",
        user=SessionUser(
            user_id="admin-01",
            display_name="Rewrite Admin",
            email="admin.local@example.com",
            platform_role="admin",
        ),
        server_target_origin="http://127.0.0.1:8000",
        server_target_label="Default Rewrite Server",
        workspace_id="ws-device-lab",
        workspace_slug="device-lab",
        workspace_display_name="Device Lab Workspace",
        workspace_role="owner",
        default_task_scope="workspace",
        memberships=admin_memberships,
        active_dataset_id="fluxonium-2025-031",
    )
    return {
        "rewrite.local@example.com": _AccountSeed(
            password="rewrite-local-password",
            prototype=SessionState(
                session_id="rewrite-user-session",
                runtime_mode="online",
                auth_state="authenticated",
                auth_mode="jwt_refresh_cookie",
                user=SessionUser(
                    user_id="researcher-01",
                    display_name="Rewrite Local User",
                    email="rewrite.local@example.com",
                    platform_role="user",
                ),
                server_target_origin="http://127.0.0.1:8000",
                server_target_label="Default Rewrite Server",
                workspace_id="ws-device-lab",
                workspace_slug="device-lab",
                workspace_display_name="Device Lab Workspace",
                workspace_role="owner",
                default_task_scope="workspace",
                memberships=(
                    WorkspaceMembership(
                        workspace_id="ws-device-lab",
                        slug="device-lab",
                        display_name="Device Lab Workspace",
                        role="owner",
                        default_task_scope="workspace",
                        is_active=True,
                        allowed_actions=WorkspaceAllowedActions(
                            switch_to=True,
                            activate_dataset=True,
                            invite_members=True,
                            remove_members=True,
                            transfer_owner=True,
                            leave_workspace=False,
                            view_audit_logs=True,
                            manage_definitions=True,
                            manage_datasets=True,
                            manage_tasks=True,
                        ),
                    ),
                    WorkspaceMembership(
                        workspace_id="ws-modeling",
                        slug="modeling",
                        display_name="Modeling Workspace",
                        role="member",
                        default_task_scope="owned",
                        is_active=False,
                        allowed_actions=WorkspaceAllowedActions(
                            switch_to=True,
                            activate_dataset=True,
                            invite_members=False,
                            remove_members=False,
                            transfer_owner=False,
                            leave_workspace=True,
                            view_audit_logs=False,
                            manage_definitions=False,
                            manage_datasets=False,
                            manage_tasks=False,
                        ),
                    ),
                ),
                active_dataset_id="fluxonium-2025-031",
            ),
        ),
        "collaborator.local@example.com": _AccountSeed(
            password="collaborator-local-password",
            prototype=collaborator_state,
        ),
        "admin.local@example.com": _AccountSeed(
            password="admin-local-password",
            prototype=admin_state,
        ),
    }


def _membership_for_workspace(
    memberships: tuple[WorkspaceMembership, ...],
    workspace_id: str,
) -> WorkspaceMembership | None:
    for membership in memberships:
        if membership.workspace_id == workspace_id:
            return membership
    return None


def _workspace_slug(workspace_id: str) -> str:
    return {
        "ws-device-lab": "device-lab",
        "ws-modeling": "modeling",
    }.get(workspace_id, workspace_id)


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _expires_at(lifetime_seconds: int) -> str:
    return (
        (datetime.now(UTC) + timedelta(seconds=lifetime_seconds))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _is_expired(iso_timestamp: str) -> bool:
    normalized = iso_timestamp.replace("Z", "+00:00")
    return datetime.now(UTC) >= datetime.fromisoformat(normalized)


def _to_workspace_invitation(
    record: _WorkspaceInvitationRecord,
    inviter: CollaborationUserSummary | None,
) -> WorkspaceInvitation:
    return WorkspaceInvitation(
        invite_id=record.invite_id,
        invite_token=record.invite_token,
        workspace_id=record.workspace_id,
        workspace_name=record.workspace_name,
        email=record.email,
        role=record.role,  # type: ignore[arg-type]
        state=record.state,  # type: ignore[arg-type]
        expires_at=record.expires_at,
        created_at=record.created_at,
        delivery=WorkspaceInvitationDelivery(
            status=record.delivery_status,  # type: ignore[arg-type]
            channel=record.delivery_channel,  # type: ignore[arg-type]
            invite_url=record.invite_url,
            failure_reason=record.delivery_error,
        ),
        inviter=inviter,
        allowed_actions=WorkspaceInvitationAllowedActions(
            revoke=False,
            accept=False,
            copy_link=False,
        ),
        created_by_user_id=record.created_by_user_id,
        delivery_error=record.delivery_error,
    )


def _to_user_summary(user: SessionUser) -> CollaborationUserSummary:
    return CollaborationUserSummary(
        user_id=user.user_id,
        display_name=user.display_name,
        email=user.email,
        platform_role=user.platform_role,
    )


def _build_public_request_session_state(auth_state: str) -> SessionState:
    return SessionState(
        session_id=f"request-{auth_state}",
        runtime_mode="online",
        auth_state=auth_state,  # type: ignore[arg-type]
        auth_mode="jwt_refresh_cookie",
        user=None,
        server_target_origin="http://127.0.0.1:8000",
        server_target_label="Default Rewrite Server",
        workspace_id="",
        workspace_slug="",
        workspace_display_name="",
        workspace_role="viewer",
        default_task_scope="owned",
        memberships=(),
        active_dataset_id=None,
    )


def _build_online_public_session_state(
    *,
    auth_state: str,
    server_target_origin: str | None,
    server_target_label: str | None,
) -> SessionState:
    return SessionState(
        session_id="online-public-session",
        runtime_mode="online",
        auth_state=auth_state,  # type: ignore[arg-type]
        auth_mode="jwt_refresh_cookie",
        user=None,
        server_target_origin=server_target_origin,
        server_target_label=server_target_label,
        workspace_id="",
        workspace_slug="",
        workspace_display_name="",
        workspace_role="viewer",
        default_task_scope="owned",
        memberships=(),
        active_dataset_id=None,
    )


def _to_server_target_summary(
    record: _ServerTargetRecord,
    *,
    is_active: bool,
) -> ServerTargetSummary:
    return ServerTargetSummary(
        origin=record.origin,
        label=record.label,
        is_active=is_active,
        validation_status=record.validation_status,  # type: ignore[arg-type]
        last_checked_at=record.last_checked_at,
    )


def _default_server_target_label(origin: str) -> str:
    return origin.removeprefix("http://").removeprefix("https://")


def _workspace_role_sort_key(role: str) -> int:
    return {
        "owner": 0,
        "member": 1,
        "viewer": 2,
    }.get(role, 99)


def _upsert_membership(
    state: SessionState,
    *,
    workspace_id: str,
    workspace_slug: str,
    workspace_name: str,
    role: str,
    default_task_scope: str,
) -> SessionState:
    existing = _membership_for_workspace(state.memberships, workspace_id)
    updated_membership = WorkspaceMembership(
        workspace_id=workspace_id,
        slug=workspace_slug,
        display_name=workspace_name,
        role=role,  # type: ignore[arg-type]
        default_task_scope=default_task_scope,  # type: ignore[arg-type]
        is_active=existing.is_active if existing is not None else False,
        allowed_actions=existing.allowed_actions
        if existing is not None
        else WorkspaceAllowedActions(
            switch_to=True,
            activate_dataset=True,
            invite_members=False,
            remove_members=False,
            transfer_owner=False,
            leave_workspace=True,
            view_audit_logs=False,
            manage_definitions=False,
            manage_datasets=False,
            manage_tasks=False,
        ),
    )
    memberships = tuple(
        [
            *(
                membership
                for membership in state.memberships
                if membership.workspace_id != workspace_id
            ),
            updated_membership,
        ]
    )
    return replace(state, memberships=memberships)


def _replace_membership_role(state: SessionState, workspace_id: str, role: str) -> SessionState:
    memberships = []
    active_membership: WorkspaceMembership | None = None
    for membership in state.memberships:
        if membership.workspace_id == workspace_id:
            updated = replace(membership, role=role)  # type: ignore[arg-type]
            memberships.append(updated)
            if membership.is_active:
                active_membership = updated
            continue
        memberships.append(membership)
        if membership.is_active:
            active_membership = membership
    updated_state = replace(state, memberships=tuple(memberships))
    if active_membership is not None:
        return replace(
            updated_state,
            workspace_role=active_membership.role,
            default_task_scope=active_membership.default_task_scope,
        )
    return updated_state


def _resolve_rebound_dataset_id(
    *,
    current_workspace_id: str,
    current_dataset_id: str | None,
    target_workspace_id: str | None,
    last_active_dataset_ids: dict[str, str],
    default_dataset_ids: dict[str, str],
) -> str | None:
    if target_workspace_id is None or len(target_workspace_id) == 0:
        return None
    if target_workspace_id == current_workspace_id:
        return current_dataset_id
    rebound_dataset_id = last_active_dataset_ids.get(target_workspace_id)
    if rebound_dataset_id is not None:
        return rebound_dataset_id
    return default_dataset_ids.get(target_workspace_id)


def build_seed_tasks() -> tuple[TaskDetail, ...]:
    return (
        TaskDetail(
            task_id=300,
            kind="simulation",
            lane="simulation",
            execution_mode="run",
            status="running",
            submitted_at="2026-03-17 08:45:00",
            owner_user_id="local-operator",
            owner_display_name="Local Operator",
            workspace_id="local-space",
            workspace_slug="local-space",
            visibility_scope="local",
            dataset_id="local-dataset-001",
            definition_id=3,
            summary="Local Space preview simulation is running.",
            queue_backend="in_memory_scaffold",
            worker_task_name="simulation_run_task",
            request_ready=True,
            submitted_from_active_dataset=True,
            progress=TaskProgress(
                phase="running",
                percent_complete=42,
                summary="simulation_run_task started in the local simulation lane.",
                updated_at="2026-03-17 08:50:00",
            ),
            result_refs=_empty_result_refs(),
        ),
        TaskDetail(
            task_id=301,
            kind="simulation",
            lane="simulation",
            execution_mode="run",
            status="running",
            submitted_at="2026-03-12 09:15:00",
            owner_user_id="researcher-01",
            owner_display_name="Rewrite Local User",
            workspace_id="ws-device-lab",
            workspace_slug="device-lab",
            visibility_scope="workspace",
            dataset_id="fluxonium-2025-031",
            definition_id=18,
            summary="Fluxonium parameter sweep is running.",
            queue_backend="in_memory_scaffold",
            worker_task_name="simulation_run_task",
            request_ready=True,
            submitted_from_active_dataset=True,
            progress=TaskProgress(
                phase="running",
                percent_complete=55,
                summary="simulation_run_task started in the simulation lane.",
                updated_at="2026-03-12 09:22:00",
            ),
            result_refs=_empty_result_refs(),
        ),
        TaskDetail(
            task_id=302,
            kind="characterization",
            lane="characterization",
            execution_mode="run",
            status="queued",
            submitted_at="2026-03-12 08:40:00",
            owner_user_id="researcher-01",
            owner_display_name="Rewrite Local User",
            workspace_id="ws-device-lab",
            workspace_slug="device-lab",
            visibility_scope="workspace",
            dataset_id="transmon-coupler-014",
            definition_id=None,
            summary="Coupler dataset characterization is queued.",
            queue_backend="in_memory_scaffold",
            worker_task_name="characterization_run_task",
            request_ready=True,
            submitted_from_active_dataset=False,
            progress=TaskProgress(
                phase="queued",
                percent_complete=0,
                summary="Task accepted by rewrite in-memory scaffold.",
                updated_at="2026-03-12 08:40:00",
            ),
            result_refs=_empty_result_refs(),
        ),
        TaskDetail(
            task_id=303,
            kind="post_processing",
            lane="simulation",
            execution_mode="run",
            status="completed",
            submitted_at="2026-03-11 19:05:00",
            owner_user_id="researcher-01",
            owner_display_name="Rewrite Local User",
            workspace_id="ws-device-lab",
            workspace_slug="device-lab",
            visibility_scope="owned",
            dataset_id="fluxonium-2025-031",
            definition_id=None,
            summary="Fluxonium fit bundle was post-processed.",
            queue_backend="in_memory_scaffold",
            worker_task_name="post_processing_run_task",
            request_ready=True,
            submitted_from_active_dataset=True,
            progress=TaskProgress(
                phase="completed",
                percent_complete=100,
                summary="post_processing_run_task completed in the simulation lane.",
                updated_at="2026-03-11 19:18:00",
            ),
            result_refs=_fluxonium_completed_result_refs(),
        ),
        TaskDetail(
            task_id=304,
            kind="simulation",
            lane="simulation",
            execution_mode="smoke",
            status="queued",
            submitted_at="2026-03-11 17:40:00",
            owner_user_id="researcher-02",
            owner_display_name="Modeling User",
            workspace_id="ws-device-lab",
            workspace_slug="device-lab",
            visibility_scope="owned",
            dataset_id="fluxonium-2025-031",
            definition_id=12,
            summary="Private simulation draft remains owner-only.",
            queue_backend="in_memory_scaffold",
            worker_task_name="simulation_smoke_task",
            request_ready=False,
            submitted_from_active_dataset=False,
            progress=TaskProgress(
                phase="queued",
                percent_complete=0,
                summary="Task accepted by rewrite in-memory scaffold.",
                updated_at="2026-03-11 17:40:00",
            ),
            result_refs=_empty_result_refs(),
        ),
        TaskDetail(
            task_id=305,
            kind="characterization",
            lane="characterization",
            execution_mode="run",
            status="running",
            submitted_at="2026-03-11 16:55:00",
            owner_user_id="researcher-03",
            owner_display_name="Shared Workspace User",
            workspace_id="ws-modeling",
            workspace_slug="modeling",
            visibility_scope="workspace",
            dataset_id="transmon-coupler-014",
            definition_id=None,
            summary="Modeling workspace characterization is running.",
            queue_backend="in_memory_scaffold",
            worker_task_name="characterization_run_task",
            request_ready=True,
            submitted_from_active_dataset=False,
            progress=TaskProgress(
                phase="running",
                percent_complete=35,
                summary="characterization_run_task started in the characterization lane.",
                updated_at="2026-03-11 17:00:00",
            ),
            result_refs=_characterization_result_refs(),
        ),
    )


def _empty_result_refs() -> TaskResultRefs:
    return TaskResultRefs(
        result_handle=TaskResultHandle(),
        metadata_records=(),
        trace_payload=None,
        result_handles=(),
    )


def _fluxonium_completed_result_refs() -> TaskResultRefs:
    trace_batch_record = build_metadata_record_ref("trace_batch", "trace_batch:88", version=1)
    return TaskResultRefs(
        result_handle=TaskResultHandle(trace_batch_id=88),
        metadata_records=(
            trace_batch_record,
            build_metadata_record_ref("result_handle", "result_handle:501", version=2),
        ),
        trace_payload=build_trace_payload_ref(
            payload_role="task_output",
            store_key="datasets/fluxonium-2025-031/trace-batches/88.zarr",
            store_uri="trace_store/datasets/fluxonium-2025-031/trace-batches/88.zarr",
            group_path="trace_batches/88",
            array_path="signals/iq_real",
            dtype="float64",
            shape=(184, 1024),
            chunk_shape=(16, 1024),
        ),
        result_handles=(
            build_result_handle_ref(
                handle_id="result:fluxonium-2025-031:fit-summary",
                kind="fit_summary",
                status="materialized",
                label="Fluxonium fit summary",
                metadata_record=build_metadata_record_ref(
                    "result_handle",
                    "result_handle:501",
                    version=2,
                ),
                payload_backend="json_artifact",
                payload_format="json",
                payload_role="report_artifact",
                payload_locator="artifacts/fit-summary.json",
                provenance_task_id=303,
                provenance=build_result_provenance_ref(
                    source_dataset_id="fluxonium-2025-031",
                    source_task_id=303,
                    trace_batch_record=trace_batch_record,
                ),
            ),
            build_result_handle_ref(
                handle_id="result:fluxonium-2025-031:plot-bundle",
                kind="plot_bundle",
                status="materialized",
                label="Fluxonium plot bundle",
                metadata_record=build_metadata_record_ref(
                    "result_handle",
                    "result_handle:502",
                    version=1,
                ),
                payload_backend="bundle_archive",
                payload_format="zip",
                payload_role="bundle_artifact",
                payload_locator="artifacts/plot-bundle.zip",
                provenance_task_id=303,
                provenance=build_result_provenance_ref(
                    source_dataset_id="fluxonium-2025-031",
                    source_task_id=303,
                    trace_batch_record=trace_batch_record,
                ),
            ),
        ),
    )


def _characterization_result_refs() -> TaskResultRefs:
    analysis_run_record = build_metadata_record_ref("analysis_run", "analysis_run:12", version=4)
    return TaskResultRefs(
        result_handle=TaskResultHandle(analysis_run_id=12),
        metadata_records=(
            analysis_run_record,
            build_metadata_record_ref("result_handle", "result_handle:612", version=3),
        ),
        trace_payload=build_trace_payload_ref(
            payload_role="analysis_projection",
            store_key="datasets/transmon-coupler-014/analysis-runs/12.zarr",
            store_uri="trace_store/datasets/transmon-coupler-014/analysis-runs/12.zarr",
            group_path="analysis_runs/12",
            array_path="derived/chi_fit",
            dtype="float64",
            shape=(76, 64),
            chunk_shape=(16, 64),
        ),
        result_handles=(
            build_result_handle_ref(
                handle_id="result:transmon-coupler-014:characterization-report",
                kind="characterization_report",
                status="materialized",
                label="Coupler characterization report",
                metadata_record=build_metadata_record_ref(
                    "result_handle",
                    "result_handle:612",
                    version=3,
                ),
                payload_backend="markdown_artifact",
                payload_format="markdown",
                payload_role="report_artifact",
                payload_locator="artifacts/fit-report.md",
                provenance_task_id=305,
                provenance=build_result_provenance_ref(
                    source_dataset_id="transmon-coupler-014",
                    source_task_id=305,
                    analysis_run_record=analysis_run_record,
                ),
            ),
        ),
    )


def build_pending_result_refs(
    *,
    task_id: int,
    draft: TaskCreateDraft,
) -> TaskResultRefs:
    pending_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:pending:{task_id}",
        version=1,
    )
    return TaskResultRefs(
        result_handle=TaskResultHandle(),
        metadata_records=(pending_record,),
        trace_payload=None,
        result_handles=(
            build_result_handle_ref(
                handle_id=f"task-result:{task_id}:primary",
                kind=_default_result_handle_kind(draft.kind),
                status="pending",
                label=_default_result_handle_label(draft.kind),
                metadata_record=pending_record,
                payload_backend=None,
                payload_format=None,
                payload_role=None,
                payload_locator=None,
                provenance_task_id=task_id,
                provenance=build_result_provenance_ref(
                    source_dataset_id=draft.dataset_id,
                    source_task_id=task_id,
                ),
            ),
        ),
    )


def _seed_tasks() -> tuple[TaskDetail, ...]:
    return build_seed_tasks()


def _default_result_handle_kind(task_kind: str) -> ResultHandleKind:
    if task_kind == "characterization":
        return "characterization_report"
    if task_kind == "post_processing":
        return "fit_summary"
    return "simulation_trace"


def _default_result_handle_label(task_kind: str) -> str:
    if task_kind == "characterization":
        return "Pending characterization report"
    if task_kind == "post_processing":
        return "Pending fit summary"
    return "Pending simulation trace"


def _trace_owner_record(result_refs: TaskResultRefs) -> MetadataRecordRef | None:
    if result_refs.trace_payload is None:
        return None

    for record in result_refs.metadata_records:
        if record.record_type in {"trace_batch", "analysis_run", "dataset"}:
            return record
    return None


def _build_storage_linkage_handle(
    *,
    owner_record: MetadataRecordRef | None,
    current_handle: TaskResultHandle,
) -> TaskResultHandle:
    if owner_record is None:
        return current_handle
    if owner_record.record_type == "trace_batch":
        return TaskResultHandle(trace_batch_id=_parse_record_suffix(owner_record.record_id))
    if owner_record.record_type == "analysis_run":
        return TaskResultHandle(analysis_run_id=_parse_record_suffix(owner_record.record_id))
    return current_handle


def _build_metadata_records_for_hydration(
    *,
    owner_record: MetadataRecordRef | None,
    primary_result_handle: ResultHandleRef,
) -> tuple[MetadataRecordRef, ...]:
    metadata_records: list[MetadataRecordRef] = []
    if owner_record is not None:
        metadata_records.append(owner_record)
    metadata_records.append(primary_result_handle.metadata_record)
    return tuple(_dedupe_metadata_records(metadata_records))


def _dedupe_metadata_records(
    records: list[MetadataRecordRef],
) -> list[MetadataRecordRef]:
    deduped: dict[str, MetadataRecordRef] = {}
    for record in records:
        deduped.setdefault(record.record_id, record)
    return list(deduped.values())


def _parse_record_suffix(record_id: str) -> int:
    _, _, suffix = record_id.partition(":")
    return int(suffix)
