from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Mapping, Sequence
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import pbkdf2_hmac
from hmac import compare_digest
from secrets import token_bytes, token_urlsafe

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app_backend.domain.session import (
    ServerTargetSummary,
    SessionState,
    SessionUser,
    WorkspaceAllowedActions,
    WorkspaceMembership,
)
from app_backend.domain.tasks import TaskDetail
from app_backend.domain.workspace_collaboration import (
    CollaborationUserSummary,
    WorkspaceInvitation,
    WorkspaceInvitationAllowedActions,
    WorkspaceInvitationDelivery,
    WorkspaceMemberRecord,
)
from app_backend.infrastructure.persistence.models import (
    RewriteAppContextRecord,
    RewriteAuthAccountRecord,
    RewriteAuthenticatedSessionRecord,
    RewritePendingInvitationAcceptanceRecord,
    RewriteRefreshTokenRecord,
    RewriteServerTargetRecord,
    RewriteWorkspaceDefaultDatasetRecord,
    RewriteWorkspaceInvitationRecord,
)

DEFAULT_REFRESH_TOKEN_LIFETIME_SECONDS = 60 * 60 * 24 * 14
PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 600_000
PASSWORD_HASH_SALT_BYTES = 16
DEFAULT_APP_CONTEXT_ID = "app-context:default"
_REQUEST_SESSION_STATE: ContextVar[SessionState | None] = ContextVar(
    "request_session_state",
    default=None,
)
_REQUEST_APP_CONTEXT_ID: ContextVar[str | None] = ContextVar(
    "request_app_context_id",
    default=None,
)


@dataclass(frozen=True)
class SeedServerTarget:
    origin: str
    label: str
    validation_status: str
    last_checked_at: str | None


@dataclass(frozen=True)
class SeedAuthAccount:
    email: str
    password: str
    prototype: SessionState


class AppStateRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def ensure_app_context(self, app_context_id: str | None) -> str:
        resolved_app_context_id = (
            app_context_id.strip()
            if app_context_id is not None and len(app_context_id.strip()) > 0
            else f"app-context:{token_urlsafe(16)}"
        )
        with self._session_factory() as session:
            self._get_or_create_app_context_row(session, resolved_app_context_id)
            session.commit()
        return resolved_app_context_id

    def get_app_context_state(self, app_context_id: str) -> SessionState:
        with self._session_factory() as session:
            row = self._get_or_create_app_context_row(session, app_context_id)
            session.commit()
            return _session_state_from_json(row.state_json)

    def bind_request_session_state(self, session_state: SessionState) -> Token[SessionState | None]:
        return _REQUEST_SESSION_STATE.set(session_state)

    def reset_request_session_state(self, token: Token[SessionState | None]) -> None:
        _REQUEST_SESSION_STATE.reset(token)

    def bind_request_app_context_id(self, app_context_id: str) -> Token[str | None]:
        return _REQUEST_APP_CONTEXT_ID.set(app_context_id)

    def reset_request_app_context_id(self, token: Token[str | None]) -> None:
        _REQUEST_APP_CONTEXT_ID.reset(token)

    def get_session_state(self) -> SessionState:
        request_state = _REQUEST_SESSION_STATE.get()
        if request_state is not None:
            return request_state
        return self._current_app_context_state()

    def build_public_request_session_state(self, auth_state: str) -> SessionState:
        current_state = self._current_app_context_state()
        return _build_online_public_session_state(
            auth_state=auth_state,
            server_target_origin=current_state.server_target_origin,
            server_target_label=current_state.server_target_label,
        )

    def get_runtime_mode(self) -> str:
        return self.get_session_state().runtime_mode

    def list_server_targets(self) -> tuple[ServerTargetSummary, ...]:
        active_target_origin = self._current_app_context_state().server_target_origin
        with self._session_factory() as session:
            rows = session.scalars(
                select(RewriteServerTargetRecord).order_by(RewriteServerTargetRecord.origin.asc())
            ).all()
            return tuple(
                _to_server_target_summary(
                    row,
                    is_active=row.origin == active_target_origin,
                )
                for row in rows
            )

    def remember_server_target(self, origin: str, label: str | None = None) -> ServerTargetSummary:
        with self._session_factory() as session:
            existing_row = session.scalar(
                select(RewriteServerTargetRecord).where(RewriteServerTargetRecord.origin == origin)
            )
            row = self._upsert_server_target_row(
                session,
                origin=origin,
                label=label or _default_server_target_label(origin),
                validation_status=(
                    existing_row.validation_status if existing_row is not None else "validated"
                ),
                last_checked_at=_now_iso(),
            )
            session.commit()
            return _to_server_target_summary(
                row,
                is_active=row.origin == self._current_app_context_state().server_target_origin,
            )

    def set_server_target_validation_status(
        self,
        *,
        origin: str,
        label: str | None,
        validation_status: str,
    ) -> ServerTargetSummary:
        with self._session_factory() as session:
            row = self._upsert_server_target_row(
                session,
                origin=origin,
                label=label or _default_server_target_label(origin),
                validation_status=validation_status,
                last_checked_at=_now_iso(),
            )
            session.commit()
            return _to_server_target_summary(
                row,
                is_active=row.origin == self._current_app_context_state().server_target_origin,
            )

    def switch_runtime_mode(
        self,
        *,
        runtime_mode: str,
        server_target_origin: str | None = None,
    ) -> SessionState:
        current_app_context_id = self._current_app_context_id()
        with self._session_factory() as session:
            app_context_row = self._get_or_create_app_context_row(session, current_app_context_id)
            current_state = _session_state_from_json(app_context_row.state_json)
            if runtime_mode == "local":
                updated_state = build_local_session_state()
                self._save_app_context_state(
                    session,
                    current_app_context_id,
                    updated_state,
                    bound_session_id=None,
                )
                session.commit()
                return updated_state

            active_target_origin = server_target_origin or current_state.server_target_origin
            if active_target_origin is None:
                updated_state = _build_online_public_session_state(
                    auth_state="anonymous",
                    server_target_origin=None,
                    server_target_label=None,
                )
                self._save_app_context_state(
                    session,
                    current_app_context_id,
                    updated_state,
                    bound_session_id=None,
                )
                session.commit()
                return updated_state

            target_row = session.scalar(
                select(RewriteServerTargetRecord).where(
                    RewriteServerTargetRecord.origin == active_target_origin
                )
            )
            updated_state = _build_online_public_session_state(
                auth_state="anonymous",
                server_target_origin=active_target_origin,
                server_target_label=(
                    target_row.label
                    if target_row is not None
                    else _default_server_target_label(active_target_origin)
                ),
            )
            self._save_app_context_state(
                session,
                current_app_context_id,
                updated_state,
                bound_session_id=None,
            )
            session.commit()
            return updated_state

    def create_authenticated_session(
        self,
        *,
        email: str,
        password: str,
    ) -> SessionState | None:
        normalized_email = email.strip().lower()
        with self._session_factory() as session:
            account_row = session.scalar(
                select(RewriteAuthAccountRecord).where(
                    RewriteAuthAccountRecord.email == normalized_email
                )
            )
            if account_row is None or not _verify_password(password, account_row.password_hash):
                return None

            prototype = _session_state_from_json(account_row.prototype_state_json)
            current_state = self._current_app_context_state()
            default_dataset_ids = self._workspace_default_dataset_ids(session)
            session_id = f"auth-session:{token_urlsafe(16)}"
            session_state = replace(
                prototype,
                session_id=session_id,
                runtime_mode="online",
                auth_state="authenticated",
                auth_mode="jwt_refresh_cookie",
                server_target_origin=current_state.server_target_origin,
                server_target_label=current_state.server_target_label,
                active_dataset_id=_resolve_authenticated_default_dataset_id(
                    prototype=prototype,
                    default_dataset_ids=default_dataset_ids,
                ),
            )
            last_active_dataset_ids = dict(default_dataset_ids)
            if len(session_state.workspace_id) > 0 and session_state.active_dataset_id is not None:
                last_active_dataset_ids[session_state.workspace_id] = (
                    session_state.active_dataset_id
                )
            self._save_authenticated_session_row(
                session,
                session_state=session_state,
                last_active_dataset_ids=last_active_dataset_ids,
            )
            self._save_app_context_state(
                session,
                self._current_app_context_id(),
                session_state,
                bound_session_id=session_id,
            )
            session.commit()
            return session_state

    def get_authenticated_session_state(self, session_id: str) -> SessionState | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteAuthenticatedSessionRecord).where(
                    RewriteAuthenticatedSessionRecord.session_id == session_id
                )
            )
            if row is None:
                return None
            return _session_state_from_json(row.state_json)

    def invalidate_authenticated_session(self, session_id: str) -> bool:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteAuthenticatedSessionRecord).where(
                    RewriteAuthenticatedSessionRecord.session_id == session_id
                )
            )
            if row is None:
                return False
            removed_state = _session_state_from_json(row.state_json)
            session.delete(row)
            self.revoke_refresh_family_for_session(session_id, _session=session)
            self._replace_app_contexts_for_session(
                session,
                session_id,
                _build_online_public_session_state(
                    auth_state="anonymous",
                    server_target_origin=removed_state.server_target_origin,
                    server_target_label=removed_state.server_target_label,
                ),
            )
            session.commit()
            return True

    def issue_refresh_token(self, session_id: str) -> str | None:
        with self._session_factory() as session:
            session_row = session.scalar(
                select(RewriteAuthenticatedSessionRecord).where(
                    RewriteAuthenticatedSessionRecord.session_id == session_id
                )
            )
            if session_row is None:
                return None
            family_id = f"refresh-family:{session_id}"
            self._revoke_family_tokens(session, family_id)
            token = token_urlsafe(32)
            session.add(
                RewriteRefreshTokenRecord(
                    token=token,
                    session_id=session_id,
                    family_id=family_id,
                    expires_at=_expires_at(DEFAULT_REFRESH_TOKEN_LIFETIME_SECONDS),
                    revoked=False,
                )
            )
            session.commit()
            return token

    def rotate_refresh_token(
        self,
        refresh_token: str,
    ) -> tuple[SessionState | None, str | None, str]:
        with self._session_factory() as session:
            record = session.scalar(
                select(RewriteRefreshTokenRecord).where(
                    RewriteRefreshTokenRecord.token == refresh_token
                )
            )
            if record is None or record.revoked:
                return None, None, "invalid"
            if _is_expired(record.expires_at):
                record.revoked = True
                session.commit()
                return None, None, "expired"
            session_row = session.scalar(
                select(RewriteAuthenticatedSessionRecord).where(
                    RewriteAuthenticatedSessionRecord.session_id == record.session_id
                )
            )
            if session_row is None:
                return None, None, "expired"
            record.revoked = True
            rotated_token = token_urlsafe(32)
            session.add(
                RewriteRefreshTokenRecord(
                    token=rotated_token,
                    session_id=record.session_id,
                    family_id=record.family_id,
                    expires_at=_expires_at(DEFAULT_REFRESH_TOKEN_LIFETIME_SECONDS),
                    revoked=False,
                )
            )
            session.commit()
            return _session_state_from_json(session_row.state_json), rotated_token, "valid"

    def revoke_refresh_family_for_session(
        self,
        session_id: str,
        *,
        _session: Session | None = None,
    ) -> None:
        family_id = f"refresh-family:{session_id}"
        if _session is not None:
            self._revoke_family_tokens(_session, family_id)
            return
        with self._session_factory() as session:
            self._revoke_family_tokens(session, family_id)
            session.commit()

    def list_workspace_invitations(self, workspace_id: str) -> tuple[WorkspaceInvitation, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(RewriteWorkspaceInvitationRecord)
                .where(RewriteWorkspaceInvitationRecord.workspace_id == workspace_id)
                .order_by(
                    RewriteWorkspaceInvitationRecord.created_at_iso.desc(),
                    RewriteWorkspaceInvitationRecord.invite_id.desc(),
                )
            ).all()
            changed = False
            invitations: list[WorkspaceInvitation] = []
            for row in rows:
                if self._refresh_invitation_state(row):
                    changed = True
                invitations.append(self._to_workspace_invitation(session, row))
            if changed:
                session.commit()
            return tuple(invitations)

    def create_workspace_invitation(
        self,
        *,
        workspace_id: str,
        workspace_name: str,
        email: str,
        role: str,
        created_by_user_id: str,
    ) -> WorkspaceInvitation:
        with self._session_factory() as session:
            row = RewriteWorkspaceInvitationRecord(
                invite_id=f"invite:{token_urlsafe(12)}",
                invite_token=token_urlsafe(24),
                workspace_id=workspace_id,
                workspace_name=workspace_name,
                email=email,
                role=role,
                state="pending",
                expires_at=_expires_at(DEFAULT_REFRESH_TOKEN_LIFETIME_SECONDS),
                created_at_iso=_now_iso(),
                delivery_status="queued_for_delivery",
                delivery_channel="manual_link",
                invite_url=None,
                created_by_user_id=created_by_user_id,
                delivery_error=None,
            )
            session.add(row)
            session.commit()
            return self._to_workspace_invitation(session, row)

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
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteWorkspaceInvitationRecord).where(
                    RewriteWorkspaceInvitationRecord.invite_id == invite_id
                )
            )
            if row is None:
                return None
            row.state = state
            row.delivery_status = delivery_status
            row.delivery_channel = delivery_channel
            row.invite_url = invite_url
            row.delivery_error = delivery_error
            session.commit()
            return self._to_workspace_invitation(session, row)

    def get_workspace_invitation(self, invite_id: str) -> WorkspaceInvitation | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteWorkspaceInvitationRecord).where(
                    RewriteWorkspaceInvitationRecord.invite_id == invite_id
                )
            )
            if row is None:
                return None
            changed = self._refresh_invitation_state(row)
            if changed:
                session.commit()
            return self._to_workspace_invitation(session, row)

    def get_workspace_invitation_by_token(self, invite_token: str) -> WorkspaceInvitation | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteWorkspaceInvitationRecord).where(
                    RewriteWorkspaceInvitationRecord.invite_token == invite_token
                )
            )
            if row is None:
                return None
            changed = self._refresh_invitation_state(row)
            if changed:
                session.commit()
            return self._to_workspace_invitation(session, row)

    def revoke_workspace_invitation(self, invite_id: str) -> WorkspaceInvitation | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteWorkspaceInvitationRecord).where(
                    RewriteWorkspaceInvitationRecord.invite_id == invite_id
                )
            )
            if row is None:
                return None
            row.state = "revoked"
            session.commit()
            return self._to_workspace_invitation(session, row)

    def accept_workspace_invitation(
        self,
        *,
        invite_token: str,
        user_email: str,
    ) -> WorkspaceInvitation | None:
        with self._session_factory() as session:
            invitation_row = session.scalar(
                select(RewriteWorkspaceInvitationRecord).where(
                    RewriteWorkspaceInvitationRecord.invite_token == invite_token
                )
            )
            if invitation_row is None:
                return None
            self._refresh_invitation_state(invitation_row)
            if invitation_row.state not in {"pending", "delivered"}:
                session.commit()
                return self._to_workspace_invitation(session, invitation_row)

            account_row = session.scalar(
                select(RewriteAuthAccountRecord).where(RewriteAuthAccountRecord.email == user_email)
            )
            if account_row is None:
                session.commit()
                return self._to_workspace_invitation(session, invitation_row)

            prototype = _session_state_from_json(account_row.prototype_state_json)
            if prototype.user is None:
                session.commit()
                return self._to_workspace_invitation(session, invitation_row)

            updated_prototype = _upsert_membership(
                prototype,
                workspace_id=invitation_row.workspace_id,
                workspace_slug=_workspace_slug(invitation_row.workspace_id),
                workspace_name=invitation_row.workspace_name,
                role=invitation_row.role,
                default_task_scope="workspace" if invitation_row.role == "owner" else "owned",
            )
            account_row.prototype_state_json = _session_state_to_json(updated_prototype)
            account_row.user_id = updated_prototype.user.user_id
            self._update_authenticated_sessions_for_user(
                session,
                user_id=updated_prototype.user.user_id,
                prototype=updated_prototype,
            )
            invitation_row.state = "accepted"
            session.commit()
            return self._to_workspace_invitation(session, invitation_row)

    def create_pending_invitation_acceptance(self, invite_token: str) -> str:
        with self._session_factory() as session:
            continuation_token = token_urlsafe(24)
            session.add(
                RewritePendingInvitationAcceptanceRecord(
                    continuation_token=continuation_token,
                    invite_token=invite_token,
                    created_at_iso=_now_iso(),
                )
            )
            session.commit()
            return continuation_token

    def consume_pending_invitation_acceptance(self, continuation_token: str) -> str | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewritePendingInvitationAcceptanceRecord).where(
                    RewritePendingInvitationAcceptanceRecord.continuation_token
                    == continuation_token
                )
            )
            if row is None:
                return None
            invite_token = row.invite_token
            session.delete(row)
            session.commit()
            return invite_token

    def list_workspace_memberships(self, workspace_id: str) -> tuple[WorkspaceMemberRecord, ...]:
        with self._session_factory() as session:
            rows = session.scalars(select(RewriteAuthAccountRecord)).all()
            memberships: list[WorkspaceMemberRecord] = []
            for row in rows:
                prototype = _session_state_from_json(row.prototype_state_json)
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
        with self._session_factory() as session:
            account_row = session.scalar(
                select(RewriteAuthAccountRecord).where(RewriteAuthAccountRecord.user_id == user_id)
            )
            if account_row is None:
                return False
            prototype = _session_state_from_json(account_row.prototype_state_json)
            updated_memberships = tuple(
                membership
                for membership in prototype.memberships
                if membership.workspace_id != workspace_id
            )
            if len(updated_memberships) == len(prototype.memberships):
                return False
            active_membership = updated_memberships[0] if len(updated_memberships) > 0 else None
            updated_prototype = replace(
                prototype,
                memberships=updated_memberships,
                workspace_id=(
                    active_membership.workspace_id if active_membership is not None else ""
                ),
                workspace_slug=active_membership.slug if active_membership is not None else "",
                workspace_display_name=active_membership.display_name
                if active_membership is not None
                else "",
                workspace_role=(
                    active_membership.role if active_membership is not None else "viewer"
                ),
                default_task_scope=active_membership.default_task_scope
                if active_membership is not None
                else "owned",
                active_dataset_id=_resolve_rebound_dataset_id(
                    current_workspace_id=prototype.workspace_id,
                    current_dataset_id=prototype.active_dataset_id,
                    target_workspace_id=active_membership.workspace_id
                    if active_membership is not None
                    else None,
                    last_active_dataset_ids=self._workspace_default_dataset_ids(session),
                    default_dataset_ids=self._workspace_default_dataset_ids(session),
                ),
            )
            account_row.prototype_state_json = _session_state_to_json(updated_prototype)
            self._update_authenticated_sessions_for_user(
                session,
                user_id=user_id,
                prototype=updated_prototype,
            )
            session.commit()
            return True

    def transfer_workspace_owner(
        self,
        workspace_id: str,
        new_owner_user_id: str,
        current_owner_user_id: str,
    ) -> bool:
        with self._session_factory() as session:
            new_owner_row = session.scalar(
                select(RewriteAuthAccountRecord).where(
                    RewriteAuthAccountRecord.user_id == new_owner_user_id
                )
            )
            current_owner_row = session.scalar(
                select(RewriteAuthAccountRecord).where(
                    RewriteAuthAccountRecord.user_id == current_owner_user_id
                )
            )
            if new_owner_row is None or current_owner_row is None:
                return False
            new_owner_prototype = _replace_membership_role(
                _session_state_from_json(new_owner_row.prototype_state_json),
                workspace_id,
                "owner",
            )
            current_owner_prototype = _replace_membership_role(
                _session_state_from_json(current_owner_row.prototype_state_json),
                workspace_id,
                "member",
            )
            new_owner_row.prototype_state_json = _session_state_to_json(new_owner_prototype)
            current_owner_row.prototype_state_json = _session_state_to_json(current_owner_prototype)
            self._update_authenticated_sessions_for_user(
                session,
                user_id=new_owner_user_id,
                prototype=new_owner_prototype,
            )
            self._update_authenticated_sessions_for_user(
                session,
                user_id=current_owner_user_id,
                prototype=current_owner_prototype,
            )
            session.commit()
            return True

    def set_authenticated_active_workspace_id(
        self,
        session_id: str,
        workspace_id: str,
    ) -> SessionState | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteAuthenticatedSessionRecord).where(
                    RewriteAuthenticatedSessionRecord.session_id == session_id
                )
            )
            if row is None:
                return None
            session_state = _session_state_from_json(row.state_json)
            session_dataset_state = dict(row.last_active_dataset_ids_json)
            if session_state.active_dataset_id is not None:
                session_dataset_state[session_state.workspace_id] = session_state.active_dataset_id

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
            row.state_json = _session_state_to_json(updated_state)
            row.last_active_dataset_ids_json = session_dataset_state
            self._replace_app_contexts_for_session(session, session_id, updated_state)
            session.commit()
            return updated_state

    def set_authenticated_active_dataset_id(
        self,
        session_id: str,
        dataset_id: str | None,
    ) -> SessionState | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteAuthenticatedSessionRecord).where(
                    RewriteAuthenticatedSessionRecord.session_id == session_id
                )
            )
            if row is None:
                return None
            session_state = _session_state_from_json(row.state_json)
            updated_state = replace(session_state, active_dataset_id=dataset_id)
            session_dataset_state = dict(row.last_active_dataset_ids_json)
            if dataset_id is None:
                session_dataset_state.pop(updated_state.workspace_id, None)
            else:
                session_dataset_state[updated_state.workspace_id] = dataset_id
            row.state_json = _session_state_to_json(updated_state)
            row.last_active_dataset_ids_json = session_dataset_state
            self._replace_app_contexts_for_session(session, session_id, updated_state)
            session.commit()
            return updated_state

    def set_active_dataset_id(self, dataset_id: str | None) -> SessionState:
        current_app_context_id = self._current_app_context_id()
        with self._session_factory() as session:
            row = self._get_or_create_app_context_row(session, current_app_context_id)
            current_state = _session_state_from_json(row.state_json)
            updated_state = replace(current_state, active_dataset_id=dataset_id)
            self._save_app_context_state(
                session,
                current_app_context_id,
                updated_state,
                bound_session_id=row.bound_session_id,
            )
            session.commit()
            return updated_state

    def get_authenticated_last_active_dataset_id(
        self,
        session_id: str,
        workspace_id: str,
    ) -> str | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteAuthenticatedSessionRecord).where(
                    RewriteAuthenticatedSessionRecord.session_id == session_id
                )
            )
            if row is None:
                return None
            return dict(row.last_active_dataset_ids_json).get(workspace_id)

    def get_default_dataset_id(self, workspace_id: str) -> str | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteWorkspaceDefaultDatasetRecord).where(
                    RewriteWorkspaceDefaultDatasetRecord.workspace_id == workspace_id
                )
            )
            return row.default_dataset_id if row is not None else None

    def list_tasks(self) -> list[TaskDetail]:
        return []

    def get_task(self, task_id: int) -> TaskDetail | None:
        return None

    def upsert_seed_app_context(
        self,
        *,
        app_context_id: str,
        state: SessionState,
        bound_session_id: str | None = None,
    ) -> None:
        with self._session_factory() as session:
            self._save_app_context_state(
                session,
                app_context_id,
                state,
                bound_session_id=bound_session_id,
            )
            session.commit()

    def upsert_seed_auth_account(
        self,
        *,
        email: str,
        password: str,
        prototype: SessionState,
    ) -> None:
        with self._session_factory() as session:
            self._upsert_auth_account_row(
                session,
                email=email,
                password=password,
                prototype=prototype,
            )
            session.commit()

    def upsert_seed_server_target(
        self,
        *,
        origin: str,
        label: str,
        validation_status: str,
        last_checked_at: str | None,
    ) -> None:
        with self._session_factory() as session:
            self._upsert_server_target_row(
                session,
                origin=origin,
                label=label,
                validation_status=validation_status,
                last_checked_at=last_checked_at,
            )
            session.commit()

    def upsert_workspace_default_dataset(
        self,
        *,
        workspace_id: str,
        default_dataset_id: str,
    ) -> None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteWorkspaceDefaultDatasetRecord).where(
                    RewriteWorkspaceDefaultDatasetRecord.workspace_id == workspace_id
                )
            )
            if row is None:
                row = RewriteWorkspaceDefaultDatasetRecord(
                    workspace_id=workspace_id,
                    default_dataset_id=default_dataset_id,
                )
                session.add(row)
            else:
                row.default_dataset_id = default_dataset_id
            session.commit()

    def _current_app_context_id(self) -> str:
        return _REQUEST_APP_CONTEXT_ID.get() or DEFAULT_APP_CONTEXT_ID

    def _current_app_context_state(self) -> SessionState:
        with self._session_factory() as session:
            row = self._get_or_create_app_context_row(session, self._current_app_context_id())
            session.commit()
            return _session_state_from_json(row.state_json)

    def _get_or_create_app_context_row(
        self,
        session: Session,
        app_context_id: str,
    ) -> RewriteAppContextRecord:
        row = session.scalar(
            select(RewriteAppContextRecord).where(
                RewriteAppContextRecord.app_context_id == app_context_id
            )
        )
        if row is None:
            row = RewriteAppContextRecord(
                app_context_id=app_context_id,
                bound_session_id=None,
                runtime_mode="local",
                state_json=_session_state_to_json(build_local_session_state()),
            )
            session.add(row)
            session.flush()
        return row

    def _save_app_context_state(
        self,
        session: Session,
        app_context_id: str,
        state: SessionState,
        *,
        bound_session_id: str | None,
    ) -> None:
        row = self._get_or_create_app_context_row(session, app_context_id)
        row.bound_session_id = bound_session_id
        row.runtime_mode = state.runtime_mode
        row.state_json = _session_state_to_json(state)

    def _save_authenticated_session_row(
        self,
        session: Session,
        *,
        session_state: SessionState,
        last_active_dataset_ids: Mapping[str, str],
    ) -> None:
        row = session.scalar(
            select(RewriteAuthenticatedSessionRecord).where(
                RewriteAuthenticatedSessionRecord.session_id == session_state.session_id
            )
        )
        if row is None:
            row = RewriteAuthenticatedSessionRecord(
                session_id=session_state.session_id,
                user_id=session_state.user.user_id if session_state.user is not None else "",
                state_json=_session_state_to_json(session_state),
                last_active_dataset_ids_json=dict(last_active_dataset_ids),
            )
            session.add(row)
            return
        row.user_id = session_state.user.user_id if session_state.user is not None else ""
        row.state_json = _session_state_to_json(session_state)
        row.last_active_dataset_ids_json = dict(last_active_dataset_ids)

    def _replace_app_contexts_for_session(
        self,
        session: Session,
        session_id: str,
        state: SessionState,
    ) -> None:
        rows = session.scalars(
            select(RewriteAppContextRecord).where(
                RewriteAppContextRecord.bound_session_id == session_id
            )
        ).all()
        for row in rows:
            row.bound_session_id = None if state.auth_state != "authenticated" else session_id
            row.runtime_mode = state.runtime_mode
            row.state_json = _session_state_to_json(state)

    def _revoke_family_tokens(self, session: Session, family_id: str) -> None:
        rows = session.scalars(
            select(RewriteRefreshTokenRecord).where(
                RewriteRefreshTokenRecord.family_id == family_id
            )
        ).all()
        for row in rows:
            row.revoked = True

    def _refresh_invitation_state(self, row: RewriteWorkspaceInvitationRecord) -> bool:
        if row.state != "pending":
            return False
        if not _is_expired(row.expires_at):
            return False
        row.state = "expired"
        return True

    def _to_workspace_invitation(
        self,
        session: Session,
        row: RewriteWorkspaceInvitationRecord,
    ) -> WorkspaceInvitation:
        inviter = self._resolve_user_summary(session, row.created_by_user_id)
        return WorkspaceInvitation(
            invite_id=row.invite_id,
            invite_token=row.invite_token,
            workspace_id=row.workspace_id,
            workspace_name=row.workspace_name,
            email=row.email,
            role=row.role,  # type: ignore[arg-type]
            state=row.state,  # type: ignore[arg-type]
            expires_at=row.expires_at,
            created_at=row.created_at_iso,
            delivery=WorkspaceInvitationDelivery(
                status=row.delivery_status,  # type: ignore[arg-type]
                channel=row.delivery_channel,  # type: ignore[arg-type]
                invite_url=row.invite_url,
                failure_reason=row.delivery_error,
            ),
            inviter=inviter,
            allowed_actions=WorkspaceInvitationAllowedActions(
                revoke=False,
                accept=False,
                copy_link=False,
            ),
            created_by_user_id=row.created_by_user_id,
            delivery_error=row.delivery_error,
        )

    def _resolve_user_summary(
        self,
        session: Session,
        user_id: str,
    ) -> CollaborationUserSummary | None:
        account_row = session.scalar(
            select(RewriteAuthAccountRecord).where(RewriteAuthAccountRecord.user_id == user_id)
        )
        if account_row is None:
            return None
        prototype = _session_state_from_json(account_row.prototype_state_json)
        if prototype.user is None:
            return None
        return _to_user_summary(prototype.user)

    def _update_authenticated_sessions_for_user(
        self,
        session: Session,
        *,
        user_id: str,
        prototype: SessionState,
    ) -> None:
        rows = session.scalars(
            select(RewriteAuthenticatedSessionRecord).where(
                RewriteAuthenticatedSessionRecord.user_id == user_id
            )
        ).all()
        default_dataset_ids = self._workspace_default_dataset_ids(session)
        for row in rows:
            session_state = _session_state_from_json(row.state_json)
            active_membership = _membership_for_workspace(
                prototype.memberships,
                session_state.workspace_id,
            ) or (prototype.memberships[0] if len(prototype.memberships) > 0 else None)
            session_dataset_state = dict(row.last_active_dataset_ids_json)
            if session_state.active_dataset_id is not None and len(session_state.workspace_id) > 0:
                session_dataset_state[session_state.workspace_id] = session_state.active_dataset_id
            updated_state = replace(
                prototype,
                session_id=session_state.session_id,
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
                    default_dataset_ids=default_dataset_ids,
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
            row.state_json = _session_state_to_json(updated_state)
            row.last_active_dataset_ids_json = session_dataset_state
            self._replace_app_contexts_for_session(session, row.session_id, updated_state)

    def _workspace_default_dataset_ids(self, session: Session) -> dict[str, str]:
        rows = session.scalars(select(RewriteWorkspaceDefaultDatasetRecord)).all()
        return {row.workspace_id: row.default_dataset_id for row in rows}

    def _upsert_server_target_row(
        self,
        session: Session,
        *,
        origin: str,
        label: str,
        validation_status: str,
        last_checked_at: str | None,
    ) -> RewriteServerTargetRecord:
        row = session.scalar(
            select(RewriteServerTargetRecord).where(RewriteServerTargetRecord.origin == origin)
        )
        if row is None:
            row = RewriteServerTargetRecord(
                origin=origin,
                label=label,
                validation_status=validation_status,
                last_checked_at=last_checked_at,
            )
            session.add(row)
            session.flush()
            return row
        row.label = label
        row.validation_status = validation_status
        row.last_checked_at = last_checked_at
        return row

    def _upsert_auth_account_row(
        self,
        session: Session,
        *,
        email: str,
        password: str,
        prototype: SessionState,
    ) -> RewriteAuthAccountRecord:
        normalized_email = email.strip().lower()
        row = session.scalar(
            select(RewriteAuthAccountRecord).where(
                RewriteAuthAccountRecord.email == normalized_email
            )
        )
        if row is None:
            row = RewriteAuthAccountRecord(
                email=normalized_email,
                password_hash=_hash_password(password),
                user_id=prototype.user.user_id if prototype.user is not None else None,
                prototype_state_json=_session_state_to_json(prototype),
            )
            session.add(row)
            session.flush()
            return row
        row.password_hash = _hash_password(password)
        row.user_id = prototype.user.user_id if prototype.user is not None else None
        row.prototype_state_json = _session_state_to_json(prototype)
        return row


def build_local_session_state() -> SessionState:
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


def build_seed_server_targets() -> tuple[SeedServerTarget, ...]:
    return (
        SeedServerTarget(
            origin="http://127.0.0.1:8000",
            label="Default Local Server",
            validation_status="validated",
            last_checked_at="2026-03-17T09:00:00Z",
        ),
    )


def build_workspace_default_dataset_ids() -> dict[str, str]:
    return {
        "local-space": "local-dataset-001",
        "ws-device-lab": "fluxonium-2025-031",
        "ws-modeling": "transmon-coupler-014",
    }


def build_seed_auth_accounts() -> tuple[SeedAuthAccount, ...]:
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
        server_target_label="Default Local Server",
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
        server_target_label="Default Local Server",
        workspace_id="ws-device-lab",
        workspace_slug="device-lab",
        workspace_display_name="Device Lab Workspace",
        workspace_role="owner",
        default_task_scope="workspace",
        memberships=admin_memberships,
        active_dataset_id="fluxonium-2025-031",
    )
    return (
        SeedAuthAccount(
            email="rewrite.local@example.com",
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
                server_target_label="Default Local Server",
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
        SeedAuthAccount(
            email="collaborator.local@example.com",
            password="collaborator-local-password",
            prototype=collaborator_state,
        ),
        SeedAuthAccount(
            email="admin.local@example.com",
            password="admin-local-password",
            prototype=admin_state,
        ),
    )


def _session_state_to_json(state: SessionState) -> dict[str, object]:
    return asdict(state)


def _session_state_from_json(payload: Mapping[str, object]) -> SessionState:
    user_payload = payload.get("user")
    memberships_payload = payload.get("memberships") or ()
    memberships = tuple(
        _workspace_membership_from_json(item)
        for item in memberships_payload
        if isinstance(item, Mapping)
    )
    return SessionState(
        session_id=str(payload.get("session_id", "")),
        runtime_mode=str(payload.get("runtime_mode", "local")),  # type: ignore[arg-type]
        auth_state=str(payload.get("auth_state", "local_bypass")),  # type: ignore[arg-type]
        auth_mode=str(payload.get("auth_mode", "local_bypass")),  # type: ignore[arg-type]
        user=_session_user_from_json(user_payload) if isinstance(user_payload, Mapping) else None,
        server_target_origin=_optional_str(payload.get("server_target_origin")),
        server_target_label=_optional_str(payload.get("server_target_label")),
        workspace_id=str(payload.get("workspace_id", "")),
        workspace_slug=str(payload.get("workspace_slug", "")),
        workspace_display_name=str(payload.get("workspace_display_name", "")),
        workspace_role=str(payload.get("workspace_role", "viewer")),  # type: ignore[arg-type]
        default_task_scope=str(payload.get("default_task_scope", "owned")),  # type: ignore[arg-type]
        memberships=memberships,
        active_dataset_id=_optional_str(payload.get("active_dataset_id")),
    )


def _session_user_from_json(payload: Mapping[str, object]) -> SessionUser:
    return SessionUser(
        user_id=str(payload.get("user_id", "")),
        display_name=str(payload.get("display_name", "")),
        email=_optional_str(payload.get("email")),
        platform_role=str(payload.get("platform_role", "user")),  # type: ignore[arg-type]
    )


def _workspace_membership_from_json(payload: Mapping[str, object]) -> WorkspaceMembership:
    allowed_actions_payload = payload.get("allowed_actions")
    return WorkspaceMembership(
        workspace_id=str(payload.get("workspace_id", "")),
        slug=str(payload.get("slug", "")),
        display_name=str(payload.get("display_name", "")),
        role=str(payload.get("role", "viewer")),  # type: ignore[arg-type]
        default_task_scope=str(payload.get("default_task_scope", "owned")),  # type: ignore[arg-type]
        is_active=bool(payload.get("is_active", False)),
        allowed_actions=_workspace_allowed_actions_from_json(allowed_actions_payload),
    )


def _workspace_allowed_actions_from_json(payload: object) -> WorkspaceAllowedActions:
    mapping = payload if isinstance(payload, Mapping) else {}
    return WorkspaceAllowedActions(
        switch_to=bool(mapping.get("switch_to", False)),
        activate_dataset=bool(mapping.get("activate_dataset", False)),
        invite_members=bool(mapping.get("invite_members", False)),
        remove_members=bool(mapping.get("remove_members", False)),
        transfer_owner=bool(mapping.get("transfer_owner", False)),
        leave_workspace=bool(mapping.get("leave_workspace", False)),
        view_audit_logs=bool(mapping.get("view_audit_logs", False)),
        manage_definitions=bool(mapping.get("manage_definitions", False)),
        manage_datasets=bool(mapping.get("manage_datasets", False)),
        manage_tasks=bool(mapping.get("manage_tasks", False)),
    )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _membership_for_workspace(
    memberships: Sequence[WorkspaceMembership],
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
    return datetime.now(UTC) >= datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))


def _to_user_summary(user: SessionUser) -> CollaborationUserSummary:
    return CollaborationUserSummary(
        user_id=user.user_id,
        display_name=user.display_name,
        email=user.email,
        platform_role=user.platform_role,
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


def _default_server_target_label(origin: str) -> str:
    return origin.removeprefix("http://").removeprefix("https://")


def _to_server_target_summary(
    row: RewriteServerTargetRecord,
    *,
    is_active: bool,
) -> ServerTargetSummary:
    return ServerTargetSummary(
        origin=row.origin,
        label=row.label,
        is_active=is_active,
        validation_status=row.validation_status,  # type: ignore[arg-type]
        last_checked_at=row.last_checked_at,
    )


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
    memberships: list[WorkspaceMembership] = []
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
    last_active_dataset_ids: Mapping[str, str],
    default_dataset_ids: Mapping[str, str],
) -> str | None:
    if target_workspace_id is None or len(target_workspace_id) == 0:
        return None
    if target_workspace_id == current_workspace_id:
        return current_dataset_id
    rebound_dataset_id = last_active_dataset_ids.get(target_workspace_id)
    if rebound_dataset_id is not None:
        return rebound_dataset_id
    return default_dataset_ids.get(target_workspace_id)


def _resolve_authenticated_default_dataset_id(
    *,
    prototype: SessionState,
    default_dataset_ids: Mapping[str, str],
) -> str | None:
    if len(prototype.workspace_id) == 0:
        return prototype.active_dataset_id
    return default_dataset_ids.get(prototype.workspace_id, prototype.active_dataset_id)


def _hash_password(password: str) -> str:
    salt = token_bytes(PASSWORD_HASH_SALT_BYTES)
    digest = pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return (
        f"{PASSWORD_HASH_SCHEME}${PASSWORD_HASH_ITERATIONS}$"
        f"{_urlsafe_b64encode(salt)}${_urlsafe_b64encode(digest)}"
    )


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations_text, salt_text, digest_text = password_hash.split("$", 3)
    except ValueError:
        return False
    if scheme != PASSWORD_HASH_SCHEME:
        return False
    try:
        iterations = int(iterations_text)
    except ValueError:
        return False
    try:
        salt = urlsafe_b64decode(salt_text.encode("ascii"))
        expected_digest = urlsafe_b64decode(digest_text.encode("ascii"))
    except (ValueError, TypeError):
        return False
    computed_digest = pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return compare_digest(computed_digest, expected_digest)


def _urlsafe_b64encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii")


SqliteAppStateRepository = AppStateRepository

__all__ = [
    "DEFAULT_APP_CONTEXT_ID",
    "AppStateRepository",
    "SeedAuthAccount",
    "SeedServerTarget",
    "SqliteAppStateRepository",
    "build_local_session_state",
    "build_seed_auth_accounts",
    "build_seed_server_targets",
    "build_workspace_default_dataset_ids",
]
