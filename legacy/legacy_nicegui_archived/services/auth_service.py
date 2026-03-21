"""Local auth/session helpers for WS5 phase-1 auth surfaces."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import UserRecord, normalize_user_role

_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 600_000
_DEFAULT_BOOTSTRAP_ADMIN_USERNAME = "admin"
_DEFAULT_BOOTSTRAP_ADMIN_PASSWORD = "admin"


def _utcnow() -> datetime:
    """Return one naive UTC timestamp without using deprecated utcnow()."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class SessionPrincipal:
    """Authenticated user payload stored in the session cookie."""

    user_id: int
    username: str
    role: str

    def to_session_payload(self) -> dict[str, Any]:
        """Serialize the principal to a JSON-safe session structure."""
        return {
            "user_id": int(self.user_id),
            "username": str(self.username),
            "role": str(self.role),
        }


def _detach_user(user: UserRecord) -> UserRecord:
    """Return a detached copy of one persisted user record."""
    return UserRecord(
        id=user.id,
        username=user.username,
        password_hash=user.password_hash,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def hash_password(password: str) -> str:
    """Hash one local password with PBKDF2-HMAC-SHA256."""
    normalized = str(password)
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        normalized.encode("utf-8"),
        salt.encode("utf-8"),
        _PASSWORD_ITERATIONS,
    )
    return f"{_PASSWORD_SCHEME}${_PASSWORD_ITERATIONS}${salt}${derived.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify one plaintext password against the stored PBKDF2 hash."""
    parts = str(password_hash).split("$")
    if len(parts) != 4:
        return False
    scheme, raw_iterations, salt, expected_hash = parts
    if scheme != _PASSWORD_SCHEME:
        return False
    try:
        iterations = int(raw_iterations)
    except ValueError:
        return False
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return hmac.compare_digest(derived.hex(), expected_hash)


def bootstrap_admin_credentials() -> tuple[str, str]:
    """Return the local bootstrap-admin credential pair."""
    username = (
        os.getenv("SC_BOOTSTRAP_ADMIN_USERNAME", _DEFAULT_BOOTSTRAP_ADMIN_USERNAME).strip()
        or _DEFAULT_BOOTSTRAP_ADMIN_USERNAME
    )
    password = (
        os.getenv("SC_BOOTSTRAP_ADMIN_PASSWORD", _DEFAULT_BOOTSTRAP_ADMIN_PASSWORD).strip()
        or _DEFAULT_BOOTSTRAP_ADMIN_PASSWORD
    )
    return (username, password)


def ensure_bootstrap_admin() -> UserRecord:
    """Ensure at least one active, login-capable admin exists for phase-1 local auth."""
    username, password = bootstrap_admin_credentials()
    bootstrap_password_hash = hash_password(password)
    with get_unit_of_work() as uow:
        existing = uow.users.get_by_username(username)
        if existing is not None:
            changed = False
            if existing.role != "admin":
                existing = uow.users.set_role(existing.id or 0, "admin")
                changed = True
            if not existing.is_active:
                existing = uow.users.set_active(existing.id or 0, True)
                changed = True
            if not verify_password(password, existing.password_hash):
                existing = uow.users.set_password(existing.id or 0, bootstrap_password_hash)
                changed = True
            if changed:
                uow.audit_logs.append_log(
                    actor_id=existing.id,
                    action_kind="auth.bootstrap_admin_recovered",
                    resource_kind="user",
                    resource_id=existing.id or username,
                    summary=f"Bootstrap admin user '{username}' recovered.",
                    payload={"username": username, "role": "admin", "is_active": True},
                )
                uow.commit()
            return _detach_user(existing)

        for user in uow.users.list_users():
            if user.role == "admin" and user.is_active:
                return _detach_user(user)

        created = uow.users.create_user(
            username=username,
            password_hash=bootstrap_password_hash,
            role="admin",
            is_active=True,
        )
        uow.audit_logs.append_log(
            actor_id=created.id,
            action_kind="auth.bootstrap_admin_created",
            resource_kind="user",
            resource_id=created.id or username,
            summary=f"Bootstrap admin user '{username}' created.",
            payload={"username": username, "role": "admin"},
        )
        uow.commit()
        return _detach_user(created)


def authenticate_user(username: str, password: str) -> UserRecord | None:
    """Return the authenticated user or ``None`` for bad credentials."""
    normalized_username = str(username).strip()
    if not normalized_username:
        return None
    with get_unit_of_work() as uow:
        user = uow.users.get_by_username(normalized_username)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        if user.id is None:
            return None
        updated = uow.users.mark_login(user.id, logged_in_at=_utcnow())
        uow.commit()
        return _detach_user(updated)


def get_active_user(user_id: int) -> UserRecord | None:
    """Load one active local user by ID."""
    with get_unit_of_work() as uow:
        user = uow.users.get_by_id(user_id)
        if user is None or not user.is_active:
            return None
        return _detach_user(user)


def get_active_user_by_username(username: str) -> UserRecord | None:
    """Load one active local user by username."""
    normalized_username = str(username).strip()
    if not normalized_username:
        return None
    with get_unit_of_work() as uow:
        user = uow.users.get_by_username(normalized_username)
        if user is None or not user.is_active:
            return None
        return _detach_user(user)


def build_session_principal(user: UserRecord) -> SessionPrincipal:
    """Project one persisted user into the session principal contract."""
    if user.id is None:
        raise ValueError("Authenticated user must have a persisted ID.")
    return SessionPrincipal(
        user_id=int(user.id),
        username=str(user.username),
        role=normalize_user_role(user.role),
    )
