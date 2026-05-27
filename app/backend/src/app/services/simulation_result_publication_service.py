from __future__ import annotations

import json
from typing import Protocol

from src.app.domain.audit import AuditRecord
from src.app.domain.datasets import (
    DatasetDetail,
    DesignBrowseRow,
    SimulationResultPublicationDraft,
    SimulationResultPublicationResult,
)
from src.app.domain.session import SessionState
from src.app.domain.tasks import TaskDetail, TaskPublicationSummary
from src.app.infrastructure.audit_records import build_audit_record
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import service_error


class SimulationResultPublicationRepository(Protocol):
    def merge_task_event_metadata(
        self,
        task_id: int,
        event_key: str,
        metadata: dict[str, object],
    ) -> None: ...


class SimulationResultPublicationDatasetRepository(Protocol):
    def get_dataset(self, dataset_id: str) -> DatasetDetail | None: ...

    def get_design(self, dataset_id: str, design_id: str) -> DesignBrowseRow | None: ...

    def list_designs(self, dataset_id: str) -> tuple[DesignBrowseRow, ...]: ...

    def publish_simulation_result(
        self,
        *,
        task: TaskDetail,
        dataset_id: str,
        draft: SimulationResultPublicationDraft,
    ) -> SimulationResultPublicationResult | None: ...


class SimulationResultPublicationSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class SimulationResultPublicationAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class SimulationResultPublicationHost(Protocol):
    def get_task(self, task_id: int) -> TaskDetail: ...

    def get_task_publication_summary(self, task_id: int) -> TaskPublicationSummary: ...


class SimulationResultPublicationService:
    def __init__(
        self,
        repository: SimulationResultPublicationRepository,
        dataset_repository: SimulationResultPublicationDatasetRepository,
        session_repository: SimulationResultPublicationSessionRepository,
        authorization_service: AuthorizationService | None = None,
        audit_repository: SimulationResultPublicationAuditRepository | None = None,
    ) -> None:
        self._repository = repository
        self._dataset_repository = dataset_repository
        self._session_repository = session_repository
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )
        self._audit_repository = audit_repository

    def publish_simulation_result(
        self,
        task_id: int,
        draft: SimulationResultPublicationDraft,
        *,
        dataset_id: str | None,
        host: SimulationResultPublicationHost,
    ) -> SimulationResultPublicationResult:
        task = host.get_task(task_id)
        state = self._session_repository.get_session_state()
        self._ensure_publishable_simulation_task(task)
        source_dataset_id = task.dataset_id
        if source_dataset_id is None:
            raise service_error(
                422,
                code="simulation_result_publish_target_required",
                category="validation",
                message="Simulation result publication requires a source dataset binding.",
            )
        if dataset_id is not None and dataset_id != source_dataset_id:
            raise service_error(
                409,
                code="simulation_result_publish_target_unsupported",
                category="conflict",
                message=(
                    "Simulation result publication currently supports only "
                    "the source task dataset as the target."
                ),
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
                code="simulation_result_publish_denied",
                category="permission_denied",
                message=(
                    "The active session cannot save simulation results "
                    "into the target dataset."
                ),
            )

        existing_publication = host.get_task_publication_summary(task_id)
        if (
            existing_publication.state == "published"
            and draft.design_id is None
            and draft.design_name is not None
            and existing_publication.target_dataset_id == source_dataset_id
            and existing_publication.target_design_name.casefold() == draft.design_name.casefold()
        ):
            return self._persist_publication_result(
                task=task,
                dataset_id=source_dataset_id,
                draft=SimulationResultPublicationDraft(
                    design_name=existing_publication.target_design_name,
                    design_id=existing_publication.target_design_id,
                ),
            )
        resolved_design = self._resolve_publication_design_target(
            target_dataset_id=source_dataset_id,
            draft=draft,
        )
        requested_design_id = resolved_design.design_id
        requested_design_name = resolved_design.name
        if existing_publication.state == "published":
            if (
                existing_publication.target_dataset_id == source_dataset_id
                and existing_publication.target_design_id == requested_design_id
            ):
                return self._persist_publication_result(
                    task=task,
                    dataset_id=source_dataset_id,
                    draft=SimulationResultPublicationDraft(
                        design_name=existing_publication.target_design_name
                        or requested_design_name,
                        design_id=requested_design_id,
                    ),
                )
            raise service_error(
                409,
                code="simulation_result_already_published",
                category="conflict",
                message=(
                    "This simulation result was already published "
                    "to a different dataset/design target."
                ),
            )

        result = self._persist_publication_result(
            task=task,
            dataset_id=source_dataset_id,
            draft=SimulationResultPublicationDraft(
                design_name=requested_design_name,
                design_id=requested_design_id,
            ),
        )
        if len(task.events) > 0:
            self._repository.merge_task_event_metadata(
                task.task_id,
                task.events[0].event_key,
                {
                    "publication_summary": json.dumps(
                        _serialize_publication_summary(
                            TaskPublicationSummary(
                                state="published",
                                publish_allowed=False,
                                publication_key=result.publication_key,
                                target_dataset_id=result.dataset.dataset_id,
                                target_design_id=result.design.design_id,
                                target_design_name=result.design.name,
                                published_trace_ids=tuple(
                                    trace.trace_id for trace in result.traces
                                ),
                                published_at=result.published_at,
                                source_task_id=task.task_id,
                                source_result_handle_ids=tuple(
                                    handle.handle_id
                                    for handle in task.result_refs.result_handles
                                ),
                            )
                        )
                    ),
                },
            )
        self._append_audit_record(
            action_kind="task.result_published",
            resource_id=str(task.task_id),
            outcome="completed",
            payload={
                "dataset_id": result.dataset.dataset_id,
                "design_id": result.design.design_id,
                "trace_ids": [trace.trace_id for trace in result.traces],
                "publication_key": result.publication_key,
                "state": result.state,
            },
        )
        return result

    def _persist_publication_result(
        self,
        *,
        task: TaskDetail,
        dataset_id: str,
        draft: SimulationResultPublicationDraft,
    ) -> SimulationResultPublicationResult:
        try:
            result = self._dataset_repository.publish_simulation_result(
                task=task,
                dataset_id=dataset_id,
                draft=draft,
            )
        except Exception as exc:
            raise service_error(
                500,
                code="simulation_result_publication_persistence_failed",
                category="persistence_error",
                message="Simulation result publication could not be persisted.",
            ) from exc
        if result is None:
            raise service_error(
                409,
                code="simulation_result_publish_unavailable",
                category="conflict",
                message="Simulation result publish target could not be materialized.",
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

    def _ensure_publishable_simulation_task(self, task: TaskDetail) -> None:
        if task.kind != "simulation":
            raise service_error(
                409,
                code="simulation_result_publish_task_invalid",
                category="conflict",
                message="Only simulation tasks can publish simulation results.",
            )
        if task.status != "completed" or _result_availability_for(task) != "ready":
            raise service_error(
                409,
                code="simulation_result_publish_not_ready",
                category="conflict",
                message="Only completed simulation tasks with ready results can be published.",
            )
        if task.simulation_setup is None:
            raise service_error(
                409,
                code="simulation_result_publish_not_ready",
                category="conflict",
                message="Only completed simulation tasks with persisted setup can be published.",
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


def _result_availability_for(task: TaskDetail) -> str:
    if task.result_refs.trace_payload is not None:
        return "ready"
    if any(handle.status == "materialized" for handle in task.result_refs.result_handles):
        return "ready"
    if task.status in {"completed", "failed", "cancelled", "terminated"}:
        return "none"
    return "pending"
