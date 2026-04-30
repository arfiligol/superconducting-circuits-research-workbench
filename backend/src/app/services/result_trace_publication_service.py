from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from src.app.domain.audit import AuditRecord
from src.app.domain.datasets import (
    DatasetDetail,
    DesignBrowseRow,
    ResultTracePublicationDraft,
    ResultTracePublicationResult,
    SimulationResultPublicationDraft,
)
from src.app.domain.result_traces import ResultTraceSelection
from src.app.domain.session import SessionState
from src.app.domain.tasks import TaskDetail, TaskPublicationSummary
from src.app.infrastructure.audit_records import build_audit_record
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.infrastructure.persisted_runtime import (
    available_sources_for_task_family,
    port_options_for_task,
)
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import service_error


class ResultTracePublicationRepository(Protocol):
    def merge_task_event_metadata(
        self,
        task_id: int,
        event_key: str,
        metadata: dict[str, object],
    ) -> None: ...


class ResultTracePublicationDatasetRepository(Protocol):
    def get_dataset(self, dataset_id: str) -> DatasetDetail | None: ...

    def get_design(self, dataset_id: str, design_id: str) -> DesignBrowseRow | None: ...

    def list_designs(self, dataset_id: str) -> tuple[DesignBrowseRow, ...]: ...

    def publish_result_trace(
        self,
        *,
        task: TaskDetail,
        basis_task: TaskDetail,
        dataset: DatasetDetail,
        design: DesignBrowseRow,
        draft: ResultTracePublicationDraft,
    ) -> ResultTracePublicationResult | None: ...


class ResultTracePublicationSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class ResultTracePublicationAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class ResultTracePublicationHost(Protocol):
    def get_task(self, task_id: int) -> TaskDetail: ...

    def get_task_publication_summary(self, task_id: int) -> TaskPublicationSummary: ...

    def get_circuit_definition(self, definition_id: str | None) -> object | None: ...


@dataclass(frozen=True)
class _ResultTraceValidationContext:
    task: TaskDetail
    basis_task: TaskDetail
    port_options: dict[int, str]
    sweep_count: int
    has_parameter_sweep: bool


class ResultTracePublicationService:
    def __init__(
        self,
        repository: ResultTracePublicationRepository,
        dataset_repository: ResultTracePublicationDatasetRepository,
        session_repository: ResultTracePublicationSessionRepository,
        authorization_service: AuthorizationService | None = None,
        audit_repository: ResultTracePublicationAuditRepository | None = None,
    ) -> None:
        self._repository = repository
        self._dataset_repository = dataset_repository
        self._session_repository = session_repository
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )
        self._audit_repository = audit_repository

    def publish_result_trace(
        self,
        task_id: int,
        draft: ResultTracePublicationDraft,
        *,
        host: ResultTracePublicationHost,
    ) -> ResultTracePublicationResult:
        task = host.get_task(task_id)
        state = self._session_repository.get_session_state()
        self._ensure_publishable_result_task(task)
        basis_task = self._resolve_result_trace_basis_task(task, host=host)
        source_dataset_id = task.dataset_id
        if source_dataset_id is None:
            raise service_error(
                422,
                code="result_trace_publish_target_required",
                category="validation",
                message="Result trace publication requires a source dataset binding.",
            )
        target_dataset = self._dataset_repository.get_dataset(source_dataset_id)
        if target_dataset is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {source_dataset_id} was not found.",
            )
        if not self._authorization_service.is_visible_dataset(target_dataset, state):
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {source_dataset_id} was not found.",
            )
        dataset_actions = self._authorization_service.build_dataset_allowed_actions(
            target_dataset,
            state,
        )
        if not dataset_actions.ingest_raw_data:
            raise service_error(
                403,
                code="result_trace_publish_denied",
                category="permission_denied",
                message="The active session cannot save result traces into the target dataset.",
            )
        resolved_design = self._resolve_publication_design_target(
            target_dataset_id=source_dataset_id,
            draft=SimulationResultPublicationDraft(design_id=draft.design_id),
        )
        existing_publication = host.get_task_publication_summary(task_id)
        if existing_publication.state == "published" and (
            existing_publication.target_dataset_id != source_dataset_id
            or existing_publication.target_design_id != resolved_design.design_id
        ):
            raise service_error(
                409,
                code="result_trace_publish_target_conflict",
                category="conflict",
                message=(
                    "This task already published traces to a different design target. "
                    "Choose the existing design or start from a different task."
                ),
            )
        self._validate_result_trace_selections(
            task=task,
            basis_task=basis_task,
            trace_keys=draft.trace_keys,
            host=host,
        )
        try:
            result = self._dataset_repository.publish_result_trace(
                task=task,
                basis_task=basis_task,
                dataset=target_dataset,
                design=resolved_design,
                draft=draft,
            )
        except ValueError as exc:
            raise service_error(
                409,
                code="result_trace_publish_unavailable",
                category="conflict",
                message="Result trace publish target could not be materialized.",
            ) from exc
        except Exception as exc:
            raise service_error(
                500,
                code="result_trace_publication_persistence_failed",
                category="persistence_error",
                message="Result trace publication could not be persisted.",
            ) from exc
        if result is None:
            raise service_error(
                409,
                code="result_trace_publish_unavailable",
                category="conflict",
                message="Result trace publish target could not be materialized.",
            )
        publication_summary = host.get_task_publication_summary(task_id)
        if len(task.events) > 0:
            self._repository.merge_task_event_metadata(
                task.task_id,
                task.events[0].event_key,
                {
                    "publication_summary": json.dumps(
                        _serialize_publication_summary(publication_summary)
                    ),
                },
            )
        self._append_audit_record(
            action_kind="task.result_trace_published",
            resource_id=str(task.task_id),
            outcome="completed",
            payload={
                "dataset_id": result.dataset.dataset_id,
                "design_id": result.design.design_id,
                "trace_ids": [trace.trace_id for trace in result.traces],
                "trace_keys": list(result.trace_keys),
                "publication_key": result.publication_key,
                "state": result.state,
            },
        )
        return result

    def _resolve_publication_design_target(
        self,
        *,
        target_dataset_id: str,
        draft: SimulationResultPublicationDraft,
    ) -> DesignBrowseRow:
        if draft.design_id is not None:
            design = self._dataset_repository.get_design(target_dataset_id, draft.design_id)
            if design is None:
                raise service_error(
                    404,
                    code="target_design_scope_invalid",
                    category="not_found",
                    message=(
                        "The selected design is not available in the target dataset. "
                        "Create it first or choose an existing design."
                    ),
                )
            if design.lifecycle_state == "active":
                return design
            if design.redirect_design_id is not None:
                raise service_error(
                    409,
                    code="design_scope_redirected",
                    category="conflict",
                    message=(
                        f"Design {draft.design_id} was redirected to "
                        f"{design.redirect_design_id}."
                    ),
                    details={
                        "dataset_id": target_dataset_id,
                        "design_id": draft.design_id,
                        "redirect_design_id": design.redirect_design_id,
                    },
                )
            raise service_error(
                409,
                code="target_design_scope_invalid",
                category="conflict",
                message=(
                    f"Design {draft.design_id} is {design.lifecycle_state} and cannot "
                    "be used as a publication target."
                ),
                details={
                    "dataset_id": target_dataset_id,
                    "design_id": draft.design_id,
                    "lifecycle_state": design.lifecycle_state,
                },
            )
        if draft.design_name is None:
            raise service_error(
                422,
                code="target_design_scope_required",
                category="validation",
                message="Simulation result publication requires design_id or design_name.",
            )
        requested_design_id = _build_publication_design_id(draft.design_name)
        conflict = next(
            (
                row
                for row in self._dataset_repository.list_designs(target_dataset_id)
                if row.lifecycle_state == "active"
                if row.design_id == requested_design_id
                or row.name.casefold() == draft.design_name.casefold()
            ),
            None,
        )
        if conflict is not None:
            raise service_error(
                409,
                code="design_scope_name_conflict",
                category="conflict",
                message=(
                    "A design scope with this active name already exists. "
                    "Select the existing design scope explicitly instead of relying "
                    "on a free-text name."
                ),
            )
        return DesignBrowseRow(
            design_id=requested_design_id,
            dataset_id=target_dataset_id,
            name=draft.design_name,
            source_coverage={},
            compare_readiness="blocked",
            trace_count=0,
            updated_at="",
        )

    def _ensure_publishable_result_task(self, task: TaskDetail) -> None:
        if task.kind not in {"simulation", "post_processing"}:
            raise service_error(
                409,
                code="result_trace_publish_task_invalid",
                category="conflict",
                message="Only simulation and post-processing tasks can publish result traces.",
            )
        if task.status != "completed" or _result_availability_for(task) != "ready":
            raise service_error(
                409,
                code="result_trace_publish_not_ready",
                category="conflict",
                message="Only completed tasks with ready results can be published.",
            )
        if task.kind == "simulation" and task.simulation_setup is None:
            raise service_error(
                409,
                code="result_trace_publish_not_ready",
                category="conflict",
                message="Only completed simulation tasks with persisted setup can be published.",
            )

    def _resolve_result_trace_basis_task(
        self,
        task: TaskDetail,
        *,
        host: ResultTracePublicationHost,
    ) -> TaskDetail:
        if task.kind == "simulation":
            if task.simulation_setup is None:
                raise service_error(
                    409,
                    code="result_trace_publish_not_ready",
                    category="conflict",
                    message="Simulation result publication requires persisted setup.",
                )
            return task
        if task.kind != "post_processing" or task.upstream_task_id is None:
            raise service_error(
                409,
                code="result_trace_publish_task_invalid",
                category="conflict",
                message="Only simulation and post-processing tasks can publish result traces.",
            )
        upstream_task = host.get_task(task.upstream_task_id)
        if upstream_task.kind != "simulation" or upstream_task.simulation_setup is None:
            raise service_error(
                409,
                code="result_trace_publish_upstream_invalid",
                category="conflict",
                message=(
                    "Post-processing result publication requires an upstream "
                    "simulation task with persisted setup."
                ),
            )
        return upstream_task

    def _validate_result_trace_selections(
        self,
        *,
        task: TaskDetail,
        basis_task: TaskDetail,
        trace_keys: tuple[str, ...],
        host: ResultTracePublicationHost,
    ) -> None:
        if len(trace_keys) == 0:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="At least one trace_key is required.",
            )

        validation_context = _ResultTraceValidationContext(
            task=task,
            basis_task=basis_task,
            port_options=port_options_for_task(
                task,
                basis_task=basis_task,
                definition=host.get_circuit_definition(basis_task.definition_id),
            ),
            sweep_count=_result_trace_sweep_count(basis_task),
            has_parameter_sweep=len(basis_task.simulation_setup.parameter_sweeps) > 0,
        )

        for trace_key in trace_keys:
            self._validate_result_trace_selection(
                trace_key=trace_key,
                validation_context=validation_context,
            )

    def _validate_result_trace_selection(
        self,
        *,
        trace_key: str,
        validation_context: _ResultTraceValidationContext,
    ) -> None:
        try:
            selection = ResultTraceSelection.from_trace_key(trace_key)
        except ValueError as exc:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message=str(exc),
            ) from exc
        if selection.source not in available_sources_for_task_family(
            validation_context.task,
            selection.family,
        ):
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message=(
                    f"source {selection.source} is not available for family "
                    f"{selection.family}."
                ),
            )
        if (
            selection.output_port not in validation_context.port_options
            or selection.input_port not in validation_context.port_options
        ):
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="Requested trace selection ports are not available for this result.",
            )
        if selection.trace_mode_group != "base":
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="Only base trace selections are supported.",
            )
        if selection.output_mode != "mode_0" or selection.input_mode != "mode_0":
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="Only mode_0 trace selections are supported.",
            )
        if not validation_context.has_parameter_sweep:
            if selection.sweep_index is not None:
                raise service_error(
                    400,
                    code="request_validation_failed",
                    category="validation_error",
                    message="Requested trace selection does not expose parameter sweep points.",
                )
            return
        if (
            selection.sweep_index is None
            or selection.sweep_index < 0
            or selection.sweep_index >= validation_context.sweep_count
        ):
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="Requested trace selection parameter sweep point is invalid.",
            )

    def _append_audit_record(
        self,
        *,
        action_kind: str,
        resource_id: str,
        outcome: str,
        payload: dict[str, object],
    ) -> None:
        if self._audit_repository is None:
            return
        session = self._session_repository.get_session_state()
        self._audit_repository.append(
            build_audit_record(
                state=session,
                action_kind=action_kind,
                resource_kind="task",
                resource_id=resource_id,
                outcome=outcome,
                payload=payload,
            )
        )


def _serialize_publication_summary(summary: TaskPublicationSummary) -> dict[str, object]:
    return summary.to_mapping()


def _build_publication_design_id(design_name: str) -> str:
    slug = "-".join(
        token
        for token in "".join(
            character.lower() if character.isalnum() else " "
            for character in design_name
        ).split()
        if len(token) > 0
    )
    return f"design_{slug}" if len(slug) > 0 else "design_simulation_result"


def _result_trace_sweep_count(task: TaskDetail) -> int:
    total = 1
    for axis in task.simulation_setup.parameter_sweeps:
        total *= max(len(axis.values), 1)
    return total


def _result_availability_for(task: TaskDetail) -> str:
    if task.result_refs.trace_payload is not None:
        return "ready"
    if any(handle.status == "materialized" for handle in task.result_refs.result_handles):
        return "ready"
    if task.status in {"completed", "failed", "cancelled", "terminated"}:
        return "none"
    return "pending"
