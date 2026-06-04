from collections.abc import Sequence
from typing import Protocol

from app_backend.domain.audit import AuditRecord
from app_backend.domain.datasets import (
    DatasetDetail,
    DesignBrowseRow,
    TraceBrowseQuery,
    TraceBrowseRow,
    TraceDeleteResult,
    TraceDetail,
    TraceEditDetail,
    TraceMetadataSummary,
    TraceMutationPolicy,
    TraceUpdateDraft,
    TraceUpdateResult,
)
from app_backend.domain.session import SessionState
from app_backend.infrastructure.audit_records import build_audit_record
from app_backend.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from app_backend.services.authorization_service import AuthorizationService
from app_backend.services.service_errors import service_error


class DatasetTraceRepository(Protocol):
    def get_dataset(self, dataset_id: str) -> DatasetDetail | None: ...

    def list_designs(
        self,
        dataset_id: str,
    ) -> Sequence[DesignBrowseRow]: ...

    def list_trace_metadata(
        self,
        dataset_id: str,
        design_id: str,
    ) -> Sequence[TraceMetadataSummary]: ...

    def get_trace_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceDetail | None: ...

    def get_trace_mutation_policy(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceMutationPolicy | None: ...

    def get_trace_edit_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceEditDetail | None: ...

    def update_trace(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
        update: TraceUpdateDraft,
    ) -> TraceUpdateResult | None: ...

    def delete_traces(
        self,
        dataset_id: str,
        design_id: str,
        trace_ids: Sequence[str],
    ) -> tuple[str, ...] | None: ...


class DatasetTraceSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class DatasetTraceAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class DatasetTraceService:
    def __init__(
        self,
        repository: DatasetTraceRepository,
        session_repository: DatasetTraceSessionRepository,
        authorization_service: AuthorizationService | None = None,
        audit_repository: DatasetTraceAuditRepository | None = None,
    ) -> None:
        self._repository = repository
        self._session_repository = session_repository
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )
        self._audit_repository = audit_repository

    def list_trace_metadata(
        self,
        dataset_id: str,
        design_id: str,
        query: TraceBrowseQuery,
    ) -> list[TraceBrowseRow]:
        self._require_visible_dataset(dataset_id)
        self._require_active_design_scope(dataset_id, design_id)
        rows = list(self._repository.list_trace_metadata(dataset_id, design_id))
        filtered = rows
        if query.search is not None:
            token = query.search.casefold()
            filtered = [
                row
                for row in filtered
                if token in row.parameter.casefold() or token in row.provenance_summary.casefold()
            ]
        if query.family is not None:
            filtered = [row for row in filtered if row.family == query.family]
        if query.representation is not None:
            normalized = query.representation.casefold()
            filtered = [row for row in filtered if row.representation.casefold() == normalized]
        if query.source_kind is not None:
            filtered = [row for row in filtered if row.source_kind == query.source_kind]
        if query.trace_mode_group is not None:
            filtered = [row for row in filtered if row.trace_mode_group == query.trace_mode_group]
        if query.axis_name is not None:
            normalized_axis_name = query.axis_name.casefold()
            filtered = [
                row
                for row in filtered
                if any(
                    axis_name.casefold() == normalized_axis_name
                    for axis_name in row.axes_summary.axis_names
                )
            ]
        if query.collection_key is not None:
            filtered = [
                row
                for row in filtered
                if row.collection_projection is not None
                and row.collection_projection.collection_key == query.collection_key
            ]
        return [self._build_trace_browse_row(dataset_id, design_id, row) for row in filtered]

    def get_trace_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceDetail:
        self._require_visible_dataset(dataset_id)
        self._require_active_design_scope(dataset_id, design_id)
        detail = self._repository.get_trace_detail(dataset_id, design_id, trace_id)
        if detail is None:
            raise service_error(
                404,
                code="trace_not_found",
                category="not_found",
                message="The requested trace is not available in the selected design scope.",
            )
        return detail

    def get_trace_edit_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceEditDetail:
        self._require_visible_dataset(dataset_id)
        self._require_active_design_scope(dataset_id, design_id)
        detail = self._repository.get_trace_edit_detail(dataset_id, design_id, trace_id)
        if detail is None:
            raise service_error(
                404,
                code="trace_not_found",
                category="not_found",
                message="The requested trace is not available in the selected design scope.",
            )
        return detail

    def update_trace(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
        update: TraceUpdateDraft,
    ) -> TraceUpdateResult:
        dataset = self._require_visible_dataset(dataset_id)
        self._require_active_design_scope(dataset_id, design_id)
        state = self._session_repository.get_session_state()
        if not dataset.allowed_actions.ingest_raw_data:
            raise service_error(
                403,
                code="trace_update_denied",
                category="permission_denied",
                message="The active session cannot update traces in the selected dataset.",
            )
        self._require_trace_mutation_policy(
            dataset_id,
            design_id,
            trace_id,
            allow_update=True,
            denied_code="trace_update_denied",
            denied_action="updated",
        )
        result = self._repository.update_trace(dataset_id, design_id, trace_id, update)
        if result is None:
            raise service_error(
                404,
                code="trace_not_found",
                category="not_found",
                message="The requested trace is not available in the selected design scope.",
            )
        self._append_audit_record(
            state=state,
            action_kind="dataset.trace_updated",
            dataset=dataset,
            payload={
                "dataset_id": dataset_id,
                "design_id": design_id,
                "trace_id": trace_id,
                "updated_fields": self._updated_trace_fields(update),
            },
        )
        return result

    def delete_trace(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceDeleteResult:
        return self.delete_traces(dataset_id, design_id, (trace_id,))

    def delete_traces(
        self,
        dataset_id: str,
        design_id: str,
        trace_ids: Sequence[str],
    ) -> TraceDeleteResult:
        dataset = self._require_visible_dataset(dataset_id)
        self._require_active_design_scope(dataset_id, design_id)
        state = self._session_repository.get_session_state()
        if not dataset.allowed_actions.ingest_raw_data:
            raise service_error(
                403,
                code="trace_batch_delete_denied" if len(trace_ids) > 1 else "trace_delete_denied",
                category="permission_denied",
                message="The active session cannot delete traces in the selected dataset.",
            )
        denied_code = "trace_batch_delete_denied" if len(trace_ids) > 1 else "trace_delete_denied"
        deleted_trace_ids: list[str] = []
        for trace_id in trace_ids:
            self._require_trace_mutation_policy(
                dataset_id,
                design_id,
                trace_id,
                allow_update=False,
                denied_code=denied_code,
                denied_action="deleted",
            )
            deleted_trace_ids.append(trace_id)
        deleted = self._repository.delete_traces(dataset_id, design_id, tuple(deleted_trace_ids))
        if deleted is None:
            raise service_error(
                404,
                code="trace_not_found",
                category="not_found",
                message="The requested trace is not available in the selected design scope.",
            )
        design = self._current_design_row(dataset_id, design_id)
        if design is None:
            raise service_error(
                404,
                code="design_not_found",
                category="not_found",
                message=f"Design {design_id} was not found in dataset {dataset_id}.",
            )
        self._append_audit_record(
            state=state,
            action_kind="dataset.trace_deleted",
            dataset=dataset,
            payload={
                "dataset_id": dataset_id,
                "design_id": design_id,
                "trace_ids": list(deleted),
            },
        )
        return TraceDeleteResult(
            design=design,
            deleted_trace_ids=deleted,
        )

    def _require_visible_dataset(self, dataset_id: str) -> DatasetDetail:
        state = self._session_repository.get_session_state()
        dataset = self._repository.get_dataset(dataset_id)
        if dataset is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        if not self._authorization_service.is_visible_dataset(dataset, state):
            raise service_error(
                403,
                code="dataset_not_visible_in_workspace",
                category="permission_denied",
                message="The selected dataset is not visible in the active workspace.",
            )
        return DatasetDetail(
            **{
                **dataset.__dict__,
                "allowed_actions": self._authorization_service.build_dataset_allowed_actions(
                    dataset,
                    state,
                ),
            }
        )

    def _current_design_row(
        self,
        dataset_id: str,
        design_id: str,
    ) -> DesignBrowseRow | None:
        design_rows = self._repository.list_designs(dataset_id)
        return next((row for row in design_rows if row.design_id == design_id), None)

    def _require_active_design_scope(
        self,
        dataset_id: str,
        design_id: str,
    ) -> DesignBrowseRow:
        design = self._current_design_row(dataset_id, design_id)
        if design is None:
            raise service_error(
                404,
                code="target_design_scope_invalid",
                category="not_found",
                message=f"Design {design_id} was not found in dataset {dataset_id}.",
            )
        if design.lifecycle_state == "active":
            return design
        if design.redirect_design_id is not None:
            raise service_error(
                409,
                code="design_scope_redirected",
                category="conflict",
                message=(f"Design {design_id} was redirected to {design.redirect_design_id}."),
                details={
                    "dataset_id": dataset_id,
                    "design_id": design_id,
                    "redirect_design_id": design.redirect_design_id,
                },
            )
        raise service_error(
            409,
            code="target_design_scope_invalid",
            category="conflict",
            message=f"Design {design_id} is {design.lifecycle_state} and is not a normal target.",
            details={
                "dataset_id": dataset_id,
                "design_id": design_id,
                "lifecycle_state": design.lifecycle_state,
            },
        )

    def _require_trace_mutation_policy(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
        *,
        allow_update: bool,
        denied_code: str,
        denied_action: str,
    ) -> None:
        policy = self._repository.get_trace_mutation_policy(dataset_id, design_id, trace_id)
        if policy is None:
            raise service_error(
                404,
                code="trace_not_found",
                category="not_found",
                message="The requested trace is not available in the selected design scope.",
            )
        allowed = policy.allowed_actions.edit if allow_update else policy.allowed_actions.delete
        if allowed:
            return
        raise service_error(
            409,
            code=denied_code,
            category="conflict",
            message=f"Trace {trace_id} cannot be {denied_action}. {policy.summary}",
        )

    def _updated_trace_fields(
        self,
        update: TraceUpdateDraft,
    ) -> list[str]:
        updated_fields: list[str] = []
        if update.parameter is not None:
            updated_fields.append("parameter")
        if update.representation is not None:
            updated_fields.append("representation")
        if update.provenance_summary is not None:
            updated_fields.append("provenance_summary")
        if update.numeric_payload is not None:
            updated_fields.append("numeric_payload")
        return updated_fields

    def _build_trace_browse_row(
        self,
        dataset_id: str,
        design_id: str,
        row: TraceMetadataSummary,
    ) -> TraceBrowseRow:
        policy = self._repository.get_trace_mutation_policy(dataset_id, design_id, row.trace_id)
        if policy is None:
            raise service_error(
                404,
                code="trace_not_found",
                category="not_found",
                message="The requested trace is not available in the selected design scope.",
            )
        return TraceBrowseRow(
            trace_id=row.trace_id,
            dataset_id=row.dataset_id,
            design_id=row.design_id,
            family=row.family,
            parameter=row.parameter,
            representation=row.representation,
            trace_mode_group=row.trace_mode_group,
            source_kind=row.source_kind,
            stage_kind=row.stage_kind,
            ndim=row.ndim,
            shape=row.shape,
            axes_summary=row.axes_summary,
            axis_signature=row.axis_signature,
            available_sweep_axes=row.available_sweep_axes,
            collection_projection=row.collection_projection,
            provenance_summary=row.provenance_summary,
            allowed_actions=policy.allowed_actions,
            mutation_policy_summary=policy.summary,
            analysis_capabilities=row.analysis_capabilities,
        )

    def _append_audit_record(
        self,
        *,
        state: SessionState,
        action_kind: str,
        dataset: DatasetDetail,
        payload: dict[str, object],
    ) -> None:
        if self._audit_repository is None:
            return
        self._audit_repository.append(
            build_audit_record(
                state=state,
                action_kind=action_kind,
                resource_kind="dataset",
                resource_id=dataset.dataset_id,
                outcome="completed",
                payload=payload,
                workspace_id=dataset.workspace_id,
            )
        )
