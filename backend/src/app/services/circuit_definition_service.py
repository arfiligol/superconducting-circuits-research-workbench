import logging
from collections.abc import Sequence
from typing import Protocol

from src.app.domain.audit import AuditRecord
from src.app.domain.circuit_definitions import (
    AllowedActions,
    CircuitDefinitionCatalogPage,
    CircuitDefinitionCloneDraft,
    CircuitDefinitionDetail,
    CircuitDefinitionDraft,
    CircuitDefinitionListQuery,
    CircuitDefinitionRecord,
    CircuitDefinitionSummary,
    CircuitDefinitionUpdate,
)
from src.app.domain.session import SessionState
from src.app.infrastructure.audit_records import build_audit_record
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import service_error

logger = logging.getLogger(__name__)


class CircuitDefinitionRepository(Protocol):
    def list_circuit_definitions(self) -> Sequence[CircuitDefinitionRecord]: ...

    def get_circuit_definition(self, definition_id: int) -> CircuitDefinitionRecord | None: ...

    def create_circuit_definition(
        self,
        *,
        workspace_id: str,
        owner_user_id: str,
        owner_display_name: str,
        draft: CircuitDefinitionDraft,
    ) -> CircuitDefinitionRecord: ...

    def update_circuit_definition(
        self,
        definition_id: int,
        update: CircuitDefinitionUpdate,
    ) -> CircuitDefinitionRecord | None: ...

    def publish_circuit_definition(
        self,
        definition_id: int,
    ) -> CircuitDefinitionRecord | None: ...

    def clone_circuit_definition(
        self,
        *,
        source_definition_id: int,
        workspace_id: str,
        owner_user_id: str,
        owner_display_name: str,
        draft: CircuitDefinitionCloneDraft,
    ) -> CircuitDefinitionRecord | None: ...

    def delete_circuit_definition(self, definition_id: int) -> bool: ...


class CircuitDefinitionSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class CircuitDefinitionAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class CircuitDefinitionService:
    def __init__(
        self,
        *,
        repository: CircuitDefinitionRepository,
        session_repository: CircuitDefinitionSessionRepository,
        authorization_service: AuthorizationService | None = None,
        audit_repository: CircuitDefinitionAuditRepository | None = None,
    ) -> None:
        self._repository = repository
        self._session_repository = session_repository
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )
        self._audit_repository = audit_repository

    def list_circuit_definitions(
        self,
        query: CircuitDefinitionListQuery,
    ) -> CircuitDefinitionCatalogPage:
        session = self._session_repository.get_session_state()
        visible_records = [
            record
            for record in self._repository.list_circuit_definitions()
            if self._authorization_service.is_visible_definition(record, session)
        ]
        filtered_records = [
            record
            for record in visible_records
            if query.search_query is None or query.search_query.casefold() in record.name.casefold()
        ]
        ordered_records = _sort_records(filtered_records, query)
        page_records, next_cursor, prev_cursor, has_more = _slice_records(ordered_records, query)
        return CircuitDefinitionCatalogPage(
            rows=tuple(
                _build_summary(record, self._allowed_actions(record, session))
                for record in page_records
            ),
            total_count=len(filtered_records),
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
            has_more=has_more,
        )

    def get_circuit_definition(self, definition_id: int) -> CircuitDefinitionDetail:
        session = self._session_repository.get_session_state()
        record = self._repository.get_circuit_definition(definition_id)
        if record is None:
            raise service_error(
                404,
                code="definition_not_found",
                category="not_found",
                message=f"Definition {definition_id} was not found.",
            )
        if not self._authorization_service.is_visible_definition(record, session):
            raise service_error(
                403,
                code="definition_not_visible",
                category="permission_denied",
                message=f"Definition {definition_id} is not visible in the active workspace.",
            )
        return _build_detail(record, self._allowed_actions(record, session))

    def create_circuit_definition(self, draft: CircuitDefinitionDraft) -> CircuitDefinitionDetail:
        session = self._session_repository.get_session_state()
        try:
            record = self._repository.create_circuit_definition(
                workspace_id=session.workspace_id,
                owner_user_id=_session_user_id(session),
                owner_display_name=_session_user_name(session),
                draft=draft,
            )
        except ValueError as exc:
            raise service_error(
                400,
                code="definition_source_invalid",
                category="validation_error",
                message=str(exc),
            ) from exc
        self._append_audit_record(
            session,
            action_kind="definition.created",
            record=record,
            payload={"name": record.name},
        )
        return _build_detail(record, self._allowed_actions(record, session))

    def update_circuit_definition(
        self,
        definition_id: int,
        update: CircuitDefinitionUpdate,
    ) -> CircuitDefinitionDetail:
        session = self._session_repository.get_session_state()
        current = self._repository.get_circuit_definition(definition_id)
        if current is None:
            raise service_error(
                404,
                code="definition_not_found",
                category="not_found",
                message=f"Definition {definition_id} was not found.",
            )
        if not self._authorization_service.is_visible_definition(current, session):
            raise service_error(
                403,
                code="definition_not_visible",
                category="permission_denied",
                message=f"Definition {definition_id} is not visible in the active workspace.",
            )
        if not self._allowed_actions(current, session).update:
            raise service_error(
                409,
                code="definition_conflict",
                category="conflict",
                message="The selected definition cannot be updated by the current session.",
            )
        try:
            record = self._repository.update_circuit_definition(definition_id, update)
        except ValueError as exc:
            raise service_error(
                400,
                code="definition_source_invalid",
                category="validation_error",
                message=str(exc),
            ) from exc
        if record is None:
            if update.concurrency_token is not None:
                raise service_error(
                    409,
                    code="definition_conflict",
                    category="conflict",
                    message=(
                        "The provided concurrency token does not match the persisted definition."
                    ),
                )
            raise service_error(
                404,
                code="definition_not_found",
                category="not_found",
                message=f"Definition {definition_id} was not found.",
            )
        self._append_audit_record(
            session,
            action_kind="definition.updated",
            record=record,
            payload={"definition_id": definition_id},
        )
        return _build_detail(record, self._allowed_actions(record, session))

    def publish_circuit_definition(self, definition_id: int) -> CircuitDefinitionDetail:
        session = self._session_repository.get_session_state()
        current = self._repository.get_circuit_definition(definition_id)
        if current is None:
            raise service_error(
                404,
                code="definition_not_found",
                category="not_found",
                message=f"Definition {definition_id} was not found.",
            )
        if not self._authorization_service.is_visible_definition(current, session):
            raise service_error(
                403,
                code="definition_not_visible",
                category="permission_denied",
                message=f"Definition {definition_id} is not visible in the active workspace.",
            )
        if not self._allowed_actions(current, session).publish:
            raise service_error(
                409,
                code="definition_conflict",
                category="conflict",
                message="The selected definition cannot be published in the current state.",
            )
        record = self._repository.publish_circuit_definition(definition_id)
        if record is None:
            raise service_error(
                404,
                code="definition_not_found",
                category="not_found",
                message=f"Definition {definition_id} was not found.",
            )
        self._append_audit_record(
            session,
            action_kind="definition.published",
            record=record,
            payload={"definition_id": definition_id},
        )
        return _build_detail(record, self._allowed_actions(record, session))

    def clone_circuit_definition(
        self,
        definition_id: int,
        draft: CircuitDefinitionCloneDraft,
    ) -> CircuitDefinitionDetail:
        session = self._session_repository.get_session_state()
        current = self._repository.get_circuit_definition(definition_id)
        if current is None:
            raise service_error(
                404,
                code="definition_not_found",
                category="not_found",
                message=f"Definition {definition_id} was not found.",
            )
        if not self._authorization_service.is_visible_definition(current, session):
            raise service_error(
                403,
                code="definition_not_visible",
                category="permission_denied",
                message=f"Definition {definition_id} is not visible in the active workspace.",
            )
        record = self._repository.clone_circuit_definition(
            source_definition_id=definition_id,
            workspace_id=session.workspace_id,
            owner_user_id=_session_user_id(session),
            owner_display_name=_session_user_name(session),
            draft=draft,
        )
        if record is None:
            raise service_error(
                404,
                code="definition_not_found",
                category="not_found",
                message=f"Definition {definition_id} was not found.",
            )
        self._append_audit_record(
            session,
            action_kind="definition.cloned",
            record=record,
            payload={"source_definition_id": definition_id},
        )
        return _build_detail(record, self._allowed_actions(record, session))

    def delete_circuit_definition(self, definition_id: int) -> None:
        session = self._session_repository.get_session_state()
        current = self._repository.get_circuit_definition(definition_id)
        if current is None:
            raise service_error(
                404,
                code="definition_not_found",
                category="not_found",
                message=f"Definition {definition_id} was not found.",
            )
        if not self._authorization_service.is_visible_definition(current, session):
            raise service_error(
                403,
                code="definition_not_visible",
                category="permission_denied",
                message=f"Definition {definition_id} is not visible in the active workspace.",
            )
        if not self._allowed_actions(current, session).delete:
            raise service_error(
                409,
                code="definition_delete_blocked",
                category="conflict",
                message="The selected definition cannot be deleted by the current session.",
            )
        if not self._repository.delete_circuit_definition(definition_id):
            raise service_error(
                404,
                code="definition_not_found",
                category="not_found",
                message=f"Definition {definition_id} was not found.",
            )
        self._append_audit_record(
            session,
            action_kind="definition.deleted",
            record=current,
            payload={"definition_id": definition_id},
        )

    def _allowed_actions(
        self,
        record: CircuitDefinitionRecord,
        session: SessionState,
    ) -> AllowedActions:
        return self._authorization_service.build_definition_allowed_actions(record, session)

    def _append_audit_record(
        self,
        session: SessionState,
        *,
        action_kind: str,
        record: CircuitDefinitionRecord,
        payload: dict[str, object],
    ) -> None:
        if self._audit_repository is None:
            return
        logger.info(
            "Circuit definition mutation action=%s definition_id=%s",
            action_kind,
            record.definition_id,
        )
        self._audit_repository.append(
            build_audit_record(
                state=session,
                action_kind=action_kind,
                resource_kind="definition",
                resource_id=str(record.definition_id),
                outcome="completed",
                payload=payload,
                workspace_id=record.workspace_id,
            )
        )


def _build_summary(
    record: CircuitDefinitionRecord,
    allowed_actions: AllowedActions,
) -> CircuitDefinitionSummary:
    return CircuitDefinitionSummary(
        definition_id=record.definition_id,
        name=record.name,
        created_at=record.created_at,
        visibility_scope=record.visibility_scope,
        owner_display_name=record.owner_display_name,
        allowed_actions=allowed_actions,
    )


def _build_detail(
    record: CircuitDefinitionRecord,
    allowed_actions: AllowedActions,
) -> CircuitDefinitionDetail:
    return CircuitDefinitionDetail(
        definition_id=record.definition_id,
        workspace_id=record.workspace_id,
        visibility_scope=record.visibility_scope,
        lifecycle_state=record.lifecycle_state,
        owner_user_id=record.owner_user_id,
        owner_display_name=record.owner_display_name,
        allowed_actions=allowed_actions,
        name=record.name,
        created_at=record.created_at,
        updated_at=record.updated_at,
        concurrency_token=record.concurrency_token,
        source_hash=record.source_hash,
        source_text=record.source_text,
        normalized_output=record.normalized_output,
        validation_notices=record.validation_notices,
        validation_summary=record.validation_summary,
        preview_artifacts=record.preview_artifacts,
        lineage_parent_id=record.lineage_parent_id,
    )


def _session_user_id(session: SessionState) -> str:
    return session.user.user_id if session.user is not None else "anonymous"


def _session_user_name(session: SessionState) -> str:
    return session.user.display_name if session.user is not None else "anonymous"


def _sort_records(
    records: Sequence[CircuitDefinitionRecord],
    query: CircuitDefinitionListQuery,
) -> list[CircuitDefinitionRecord]:
    reverse = query.sort_order == "desc"
    if query.sort_by == "name":
        return sorted(records, key=lambda record: record.name.casefold(), reverse=reverse)
    if query.sort_by == "created_at":
        return sorted(records, key=lambda record: record.created_at, reverse=reverse)
    return sorted(records, key=lambda record: record.updated_at, reverse=reverse)


def _slice_records(
    records: Sequence[CircuitDefinitionRecord],
    query: CircuitDefinitionListQuery,
) -> tuple[list[CircuitDefinitionRecord], str | None, str | None, bool]:
    limit = max(1, query.limit)
    if len(records) == 0:
        return [], None, None, False

    start_index = 0
    end_index = len(records)

    if query.after is not None:
        start_index = next(
            (
                index + 1
                for index, record in enumerate(records)
                if str(record.definition_id) == query.after
            ),
            len(records),
        )
    if query.before is not None:
        end_index = next(
            (
                index
                for index, record in enumerate(records)
                if str(record.definition_id) == query.before
            ),
            len(records),
        )

    window = list(records[start_index:end_index])
    page = window[:limit]
    has_more = len(window) > limit
    next_cursor = str(page[-1].definition_id) if has_more and len(page) > 0 else None
    prev_cursor = str(records[start_index - 1].definition_id) if start_index > 0 else None
    return page, next_cursor, prev_cursor, has_more
