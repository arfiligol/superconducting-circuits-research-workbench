from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from app_backend.domain.workspace_collaboration import WorkspaceInvitation
from app_backend.settings import AppSettings


@dataclass(frozen=True)
class InvitationDeliveryAttempt:
    invitation_state: str
    delivery_status: str
    delivery_channel: str
    invite_url: str | None
    delivery_error: str | None


class WorkspaceInvitationDeliveryService:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def deliver(self, invitation: WorkspaceInvitation) -> InvitationDeliveryAttempt:
        invite_url = (
            f"{self._settings.app_base_url.rstrip('/')}/accept-invite?token="
            f"{quote(invitation.invite_token)}"
        )
        if self._has_smtp_configuration():
            return InvitationDeliveryAttempt(
                invitation_state="delivered",
                delivery_status="sent",
                delivery_channel="smtp",
                invite_url=None,
                delivery_error=None,
            )
        if self._settings.environment in {"development", "test"}:
            return InvitationDeliveryAttempt(
                invitation_state="delivered",
                delivery_status="manual_link",
                delivery_channel="manual_link",
                invite_url=invite_url,
                delivery_error=None,
            )
        return InvitationDeliveryAttempt(
            invitation_state="delivery_failed",
            delivery_status="delivery_failed",
            delivery_channel="manual_link",
            invite_url=invite_url,
            delivery_error="smtp_not_configured",
        )

    def _has_smtp_configuration(self) -> bool:
        return all(
            value is not None and len(str(value).strip()) > 0
            for value in (
                self._settings.smtp_host,
                self._settings.smtp_from_email,
                self._settings.app_base_url,
            )
        )
