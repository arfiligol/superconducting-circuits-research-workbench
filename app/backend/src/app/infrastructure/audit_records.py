from __future__ import annotations

from datetime import UTC, datetime

from src.app.domain.audit import AuditOutcome, AuditRecord
from src.app.domain.session import SessionState
from src.app.infrastructure.request_debug import current_correlation_id, current_debug_ref


def build_audit_record(
    *,
    state: SessionState | None,
    action_kind: str,
    resource_kind: str,
    resource_id: str,
    outcome: AuditOutcome,
    payload: dict[str, object],
    workspace_id: str | None = None,
) -> AuditRecord:
    occurred_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    session_id = state.session_id if state is not None else "anonymous"
    actor_user_id = (
        state.user.user_id if state is not None and state.user is not None else "anonymous"
    )
    actor_display_name = (
        state.user.display_name if state is not None and state.user is not None else "anonymous"
    )
    resolved_workspace_id = workspace_id or (state.workspace_id if state is not None else "auth")
    audit_suffix = occurred_at.replace(":", "-").replace("+", "z")
    return AuditRecord(
        audit_id=f"audit:{action_kind}:{resource_id}:{audit_suffix}",
        occurred_at=occurred_at,
        actor_user_id=actor_user_id,
        actor_display_name=actor_display_name,
        session_id=session_id,
        correlation_id=current_correlation_id(),
        workspace_id=resolved_workspace_id,
        action_kind=action_kind,
        resource_kind=resource_kind,
        resource_id=resource_id,
        outcome=outcome,
        payload=payload,
        debug_ref=current_debug_ref(),
    )
