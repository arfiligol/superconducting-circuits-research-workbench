"""Repository for UserRecord operations."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, col, select

from core.shared.persistence.models import UserRecord, normalize_user_role


class UserRepository:
    """Repository for local user records."""

    def __init__(self, session: Session):
        self._session = session

    def _require_user(self, user_id: int) -> UserRecord:
        user = self._session.get(UserRecord, user_id)
        if user is None:
            raise ValueError(f"User ID {user_id} not found.")
        return user

    def get_by_username(self, username: str) -> UserRecord | None:
        """Get one user by unique username."""
        statement = select(UserRecord).where(col(UserRecord.username) == username)
        return self._session.exec(statement).first()

    def get_by_id(self, user_id: int) -> UserRecord | None:
        """Get one user by ID."""
        return self._session.get(UserRecord, user_id)

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str,
        *,
        is_active: bool = True,
    ) -> UserRecord:
        """Create and flush one local user record."""
        user = UserRecord(
            username=username,
            password_hash=password_hash,
            role=normalize_user_role(role),
            is_active=is_active,
        )
        self._session.add(user)
        self._session.flush()
        return user

    def list_users(self) -> list[UserRecord]:
        """List users in stable username order."""
        statement = select(UserRecord).order_by(col(UserRecord.username))
        return list(self._session.exec(statement).all())

    def set_password(self, user_id: int, password_hash: str) -> UserRecord:
        """Replace one user's stored password hash."""
        user = self._require_user(user_id)
        user.password_hash = password_hash
        self._session.add(user)
        self._session.flush()
        return user

    def set_role(self, user_id: int, role: str) -> UserRecord:
        """Replace one user's role."""
        user = self._require_user(user_id)
        user.role = normalize_user_role(role)
        self._session.add(user)
        self._session.flush()
        return user

    def set_active(self, user_id: int, is_active: bool) -> UserRecord:
        """Enable or disable one user."""
        user = self._require_user(user_id)
        user.is_active = is_active
        self._session.add(user)
        self._session.flush()
        return user

    def mark_login(self, user_id: int, *, logged_in_at: datetime) -> UserRecord:
        """Update one user's last successful login timestamp."""
        user = self._require_user(user_id)
        user.last_login_at = logged_in_at
        self._session.add(user)
        self._session.flush()
        return user
