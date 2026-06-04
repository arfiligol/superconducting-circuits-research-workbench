import logging
from collections.abc import Sequence
from typing import Protocol

from app_backend.domain.audit import AuditRecord
from app_backend.domain.datasets import (
    DatasetAllowedActions,
    DatasetCatalogRow,
    DatasetCreateDraft,
    DatasetDesignMutationResult,
    DatasetDetail,
    DatasetLifecycleMutationResult,
    DatasetProfileField,
    DatasetProfileUpdate,
    DatasetProfileUpdateResult,
    DesignBrowseQuery,
    DesignBrowseRow,
    DesignCreateDraft,
    DesignMergeDraft,
    DesignRenameDraft,
    DesignScopeMergeResult,
    RawDataIngestionDraft,
    RawDataIngestionResult,
    TaggedCoreMetricSummary,
)
from app_backend.domain.session import SessionState
from app_backend.infrastructure.audit_records import build_audit_record
from app_backend.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from app_backend.services.authorization_service import AuthorizationService
from app_backend.services.service_errors import service_error

logger = logging.getLogger(__name__)


class DatasetCatalogRepository(Protocol):
    def list_dataset_details(self) -> Sequence[DatasetDetail]: ...

    def get_dataset(self, dataset_id: str) -> DatasetDetail | None: ...

    def create_dataset(
        self,
        *,
        workspace_id: str,
        visibility_scope: str,
        owner_user_id: str,
        owner_display_name: str,
        draft: DatasetCreateDraft,
    ) -> DatasetDetail: ...

    def update_dataset_profile(
        self,
        dataset_id: str,
        update: DatasetProfileUpdate,
    ) -> DatasetDetail | None: ...

    def set_dataset_lifecycle_state(
        self,
        dataset_id: str,
        lifecycle_state: str,
    ) -> DatasetDetail | None: ...

    def ingest_raw_data(
        self,
        dataset_id: str,
        draft: RawDataIngestionDraft,
    ) -> RawDataIngestionResult | None: ...

    def create_design(
        self,
        dataset_id: str,
        draft: DesignCreateDraft,
    ) -> DatasetDesignMutationResult | None: ...

    def rename_design(
        self,
        dataset_id: str,
        design_id: str,
        draft: DesignRenameDraft,
    ) -> DatasetDesignMutationResult | None: ...

    def set_design_lifecycle_state(
        self,
        dataset_id: str,
        design_id: str,
        lifecycle_state: str,
    ) -> DatasetDesignMutationResult | None: ...

    def merge_design_scopes(
        self,
        dataset_id: str,
        source_design_id: str,
        target_design_id: str,
    ) -> DesignScopeMergeResult | None: ...

    def list_tagged_core_metrics(
        self,
        dataset_id: str,
    ) -> Sequence[TaggedCoreMetricSummary]: ...

    def list_designs(
        self,
        dataset_id: str,
    ) -> Sequence[DesignBrowseRow]: ...


class DatasetCatalogSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class DatasetCatalogAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class DatasetCatalogService:
    def __init__(
        self,
        repository: DatasetCatalogRepository,
        session_repository: DatasetCatalogSessionRepository,
        authorization_service: AuthorizationService | None = None,
        audit_repository: DatasetCatalogAuditRepository | None = None,
    ) -> None:
        self._repository = repository
        self._session_repository = session_repository
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )
        self._audit_repository = audit_repository

    def list_dataset_catalog(self) -> list[DatasetCatalogRow]:
        state = self._session_repository.get_session_state()
        return [
            DatasetCatalogRow(
                dataset_id=dataset.dataset_id,
                name=dataset.name,
                visibility_scope=dataset.visibility_scope,
                lifecycle_state=dataset.lifecycle_state,
                device_type=dataset.device_type,
                updated_at=dataset.updated_at,
                allowed_actions=self._allowed_actions(dataset, state),
                family=dataset.family,
                owner_display_name=dataset.owner,
            )
            for dataset in self._visible_datasets(state)
        ]

    def create_dataset(self, draft: DatasetCreateDraft) -> DatasetLifecycleMutationResult:
        state = self._session_repository.get_session_state()
        if not self._can_manage_datasets(state):
            raise service_error(
                403,
                code="dataset_create_denied",
                category="permission_denied",
                message="The active session cannot create datasets in the current context.",
            )
        visibility_scope = "local" if state.runtime_mode == "local" else "private"
        owner_user_id = state.user.user_id if state.user is not None else "local-operator"
        owner_display_name = state.user.display_name if state.user is not None else "Local Operator"
        created = self._repository.create_dataset(
            workspace_id=state.workspace_id,
            visibility_scope=visibility_scope,
            owner_user_id=owner_user_id,
            owner_display_name=owner_display_name,
            draft=draft,
        )
        dataset = self._with_allowed_actions(created, state)
        self._append_audit_record(
            state=state,
            action_kind="dataset.created",
            dataset=dataset,
            payload={
                "dataset_id": dataset.dataset_id,
                "visibility_scope": dataset.visibility_scope,
            },
        )
        return DatasetLifecycleMutationResult(
            dataset=dataset,
            catalog_row=self._catalog_row(dataset, state),
        )

    def get_dataset_profile(self, dataset_id: str) -> DatasetDetail:
        return self._require_visible_dataset(dataset_id)

    def update_dataset_profile(
        self,
        dataset_id: str,
        update: DatasetProfileUpdate,
    ) -> DatasetProfileUpdateResult:
        current = self._require_visible_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        allowed_actions = self._allowed_actions(current, state)
        if not allowed_actions.update_profile:
            raise service_error(
                403,
                code="dataset_profile_update_denied",
                category="permission_denied",
                message="The active session cannot update this dataset profile.",
            )

        updated = self._repository.update_dataset_profile(dataset_id, update)
        if updated is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        updated = self._with_allowed_actions(updated, state)
        updated_fields = self._updated_fields(current, updated)
        logger.info("Dataset profile updated dataset_id=%s", dataset_id)
        self._append_audit_record(
            state=state,
            action_kind="dataset.profile_updated",
            dataset=updated,
            payload={
                "dataset_id": dataset_id,
                "updated_fields": [
                    field if isinstance(field, str) else field.value for field in updated_fields
                ],
            },
        )
        return DatasetProfileUpdateResult(
            dataset=updated,
            updated_fields=updated_fields,
        )

    def archive_dataset(self, dataset_id: str) -> DatasetLifecycleMutationResult:
        dataset = self._require_visible_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        allowed_actions = self._allowed_actions(dataset, state)
        if not allowed_actions.archive:
            raise service_error(
                403,
                code="dataset_archive_denied",
                category="permission_denied",
                message="The active session cannot archive this dataset.",
            )
        updated = self._repository.set_dataset_lifecycle_state(dataset_id, "archived")
        if updated is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        dataset = self._with_allowed_actions(updated, state)
        self._append_audit_record(
            state=state,
            action_kind="dataset.archived",
            dataset=dataset,
            payload={"dataset_id": dataset_id},
        )
        return DatasetLifecycleMutationResult(
            dataset=dataset,
            catalog_row=self._catalog_row(dataset, state),
        )

    def delete_dataset(self, dataset_id: str) -> DatasetLifecycleMutationResult:
        dataset = self._require_manageable_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        if not self._can_manage_datasets(state):
            raise service_error(
                403,
                code="dataset_delete_denied",
                category="permission_denied",
                message="The active session cannot delete this dataset.",
            )
        updated = self._repository.set_dataset_lifecycle_state(dataset_id, "deleted")
        if updated is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        dataset = self._with_allowed_actions(updated, state)
        self._append_audit_record(
            state=state,
            action_kind="dataset.deleted",
            dataset=dataset,
            payload={"dataset_id": dataset_id},
        )
        return DatasetLifecycleMutationResult(
            dataset=dataset,
            catalog_row=self._catalog_row(dataset, state),
        )

    def ingest_raw_data(
        self,
        dataset_id: str,
        draft: RawDataIngestionDraft,
    ) -> RawDataIngestionResult:
        dataset = self._require_visible_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        allowed_actions = self._allowed_actions(dataset, state)
        if not allowed_actions.ingest_raw_data:
            raise service_error(
                403,
                code="dataset_ingestion_denied",
                category="permission_denied",
                message="The active session cannot ingest raw data into this dataset.",
            )
        draft = self._resolve_raw_ingestion_target(dataset_id, draft)
        result = self._repository.ingest_raw_data(dataset_id, draft)
        if result is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        materialized_dataset = self._with_allowed_actions(result.dataset, state)
        self._append_audit_record(
            state=state,
            action_kind="dataset.raw_data_ingested",
            dataset=materialized_dataset,
            payload={
                "dataset_id": dataset_id,
                "ingestion_kind": draft.kind,
                "design_id": result.design.design_id,
                "trace_ids": [trace.trace_id for trace in result.traces],
            },
        )
        return RawDataIngestionResult(
            dataset=materialized_dataset,
            design=result.design,
            traces=result.traces,
        )

    def create_design(
        self,
        dataset_id: str,
        draft: DesignCreateDraft,
    ) -> DatasetDesignMutationResult:
        dataset = self._require_visible_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        allowed_actions = self._allowed_actions(dataset, state)
        if not allowed_actions.ingest_raw_data:
            raise service_error(
                403,
                code="dataset_design_create_denied",
                category="permission_denied",
                message="The active session cannot create designs in this dataset.",
            )

        requested_design_id = _build_design_id(draft.name)
        conflict = next(
            (
                row
                for row in self._repository.list_designs(dataset_id)
                if row.lifecycle_state == "active"
                if row.design_id == requested_design_id
                or row.name.casefold() == draft.name.casefold()
            ),
            None,
        )
        if conflict is not None:
            raise service_error(
                409,
                code="design_scope_name_conflict",
                category="conflict",
                message=(
                    "A design with this name already exists in the selected dataset. "
                    "Select the existing design instead of creating a duplicate."
                ),
            )

        try:
            result = self._repository.create_design(dataset_id, draft)
        except ValueError as exc:
            raise service_error(
                409,
                code="design_scope_name_conflict",
                category="conflict",
                message=(
                    "A design with this name already exists in the selected dataset. "
                    "Select the existing design instead of creating a duplicate."
                ),
            ) from exc
        if result is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )

        updated_dataset = self._with_allowed_actions(result.dataset, state)
        self._append_audit_record(
            state=state,
            action_kind="dataset.design_created",
            dataset=updated_dataset,
            payload={
                "dataset_id": dataset_id,
                "design_id": result.design.design_id,
                "design_name": result.design.name,
            },
        )
        return DatasetDesignMutationResult(
            dataset=updated_dataset,
            design=result.design,
        )

    def rename_design(
        self,
        dataset_id: str,
        design_id: str,
        draft: DesignRenameDraft,
    ) -> DatasetDesignMutationResult:
        dataset = self._require_visible_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        self._require_active_design_scope(dataset_id, design_id, for_target=False)
        self._ensure_active_design_name_available(
            dataset_id,
            draft.name,
            exclude_design_id=design_id,
        )
        result = self._repository.rename_design(dataset_id, design_id, draft)
        if result is None:
            raise service_error(
                404,
                code="target_design_scope_invalid",
                category="not_found",
                message=f"Design {design_id} was not found in dataset {dataset_id}.",
            )
        self._append_audit_record(
            state=state,
            action_kind="dataset.design_renamed",
            dataset=dataset,
            payload={"dataset_id": dataset_id, "design_id": design_id, "name": draft.name},
        )
        return result

    def archive_design(
        self,
        dataset_id: str,
        design_id: str,
    ) -> DatasetDesignMutationResult:
        return self._set_design_lifecycle_state(dataset_id, design_id, "archived")

    def delete_design(
        self,
        dataset_id: str,
        design_id: str,
    ) -> DatasetDesignMutationResult:
        return self._set_design_lifecycle_state(dataset_id, design_id, "deleted")

    def merge_design_scopes(
        self,
        dataset_id: str,
        source_design_id: str,
        draft: DesignMergeDraft,
    ) -> DesignScopeMergeResult:
        self._require_visible_dataset(dataset_id)
        if source_design_id == draft.target_design_id:
            raise service_error(
                409,
                code="design_scope_merge_denied",
                category="conflict",
                message="Source and target design scopes must be different.",
            )
        self._require_active_design_scope(dataset_id, source_design_id, for_target=False)
        self._require_active_design_scope(dataset_id, draft.target_design_id, for_target=False)
        try:
            result = self._repository.merge_design_scopes(
                dataset_id,
                source_design_id,
                draft.target_design_id,
            )
        except ValueError as exc:
            raise service_error(
                409,
                code="design_scope_merge_conflict",
                category="conflict",
                message=str(exc) or "Design scope merge could not be completed.",
            ) from exc
        if result is None:
            raise service_error(
                404,
                code="target_design_scope_invalid",
                category="not_found",
                message="The requested design scope merge target was not found.",
            )
        return result

    def list_tagged_core_metrics(self, dataset_id: str) -> list[TaggedCoreMetricSummary]:
        self._require_visible_dataset(dataset_id)
        return list(self._repository.list_tagged_core_metrics(dataset_id))

    def list_designs(
        self,
        dataset_id: str,
        query: DesignBrowseQuery,
    ) -> list[DesignBrowseRow]:
        self._require_visible_dataset(dataset_id)
        rows = [
            row
            for row in self._repository.list_designs(dataset_id)
            if query.include_archived or row.lifecycle_state == "active"
        ]
        if query.search is None:
            return rows
        token = query.search.casefold()
        return [row for row in rows if token in row.name.casefold()]

    def _resolve_raw_ingestion_target(
        self,
        dataset_id: str,
        draft: RawDataIngestionDraft,
    ) -> RawDataIngestionDraft:
        if draft.design_id is not None:
            design = self._require_active_design_scope(dataset_id, draft.design_id)
            return RawDataIngestionDraft(
                kind=draft.kind,
                design_name=design.name,
                design_id=design.design_id,
                provenance_label=draft.provenance_label,
                traces=draft.traces,
            )
        self._ensure_active_design_name_available(dataset_id, draft.design_name)
        return draft

    def _ensure_active_design_name_available(
        self,
        dataset_id: str,
        name: str,
        *,
        exclude_design_id: str | None = None,
    ) -> None:
        requested_design_id = _build_design_id(name)
        conflict = next(
            (
                row
                for row in self._repository.list_designs(dataset_id)
                if row.lifecycle_state == "active"
                if row.design_id != exclude_design_id
                if row.design_id == requested_design_id or row.name.casefold() == name.casefold()
            ),
            None,
        )
        if conflict is None:
            return
        raise service_error(
            409,
            code="design_scope_name_conflict",
            category="conflict",
            message=(
                "A design scope with this active name already exists. "
                "Select the existing design scope instead of relying on a free-text match."
            ),
        )

    def _require_active_design_scope(
        self,
        dataset_id: str,
        design_id: str,
        *,
        for_target: bool = True,
    ) -> DesignBrowseRow:
        design = next(
            (
                row
                for row in self._repository.list_designs(dataset_id)
                if row.design_id == design_id
            ),
            None,
        )
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
                message=(
                    f"Design {design_id} was merged or redirected to {design.redirect_design_id}."
                ),
                details={
                    "dataset_id": dataset_id,
                    "design_id": design_id,
                    "redirect_design_id": design.redirect_design_id,
                    "target_required": for_target,
                },
            )
        raise service_error(
            409,
            code="target_design_scope_invalid",
            category="conflict",
            message=(
                f"Design {design_id} is {design.lifecycle_state} and cannot be used "
                "as a normal target."
            ),
            details={
                "dataset_id": dataset_id,
                "design_id": design_id,
                "lifecycle_state": design.lifecycle_state,
                "target_required": for_target,
            },
        )

    def _set_design_lifecycle_state(
        self,
        dataset_id: str,
        design_id: str,
        lifecycle_state: str,
    ) -> DatasetDesignMutationResult:
        dataset = self._require_visible_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        self._require_active_design_scope(dataset_id, design_id, for_target=False)
        result = self._repository.set_design_lifecycle_state(
            dataset_id,
            design_id,
            lifecycle_state,
        )
        if result is None:
            raise service_error(
                404,
                code="target_design_scope_invalid",
                category="not_found",
                message=f"Design {design_id} was not found in dataset {dataset_id}.",
            )
        self._append_audit_record(
            state=state,
            action_kind=f"dataset.design_{lifecycle_state}",
            dataset=dataset,
            payload={
                "dataset_id": dataset_id,
                "design_id": design_id,
                "lifecycle_state": lifecycle_state,
            },
        )
        return result

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
        return self._with_allowed_actions(dataset, state)

    def _require_manageable_dataset(self, dataset_id: str) -> DatasetDetail:
        state = self._session_repository.get_session_state()
        dataset = self._repository.get_dataset(dataset_id)
        if dataset is None or dataset.lifecycle_state == "deleted":
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        if not self._is_dataset_manageable_in_context(dataset, state):
            raise service_error(
                403,
                code="dataset_not_visible_in_workspace",
                category="permission_denied",
                message="The selected dataset is not visible in the active workspace.",
            )
        return self._with_allowed_actions(dataset, state)

    def _visible_datasets(self, state: SessionState) -> list[DatasetDetail]:
        rows = [
            dataset
            for dataset in self._repository.list_dataset_details()
            if dataset.lifecycle_state != "deleted"
            if self._authorization_service.is_visible_dataset(dataset, state)
        ]
        return sorted(rows, key=lambda dataset: dataset.updated_at, reverse=True)

    def _allowed_actions(
        self,
        dataset: DatasetDetail,
        state: SessionState,
    ) -> DatasetAllowedActions:
        return self._authorization_service.build_dataset_allowed_actions(dataset, state)

    def _is_dataset_manageable_in_context(
        self,
        dataset: DatasetDetail,
        state: SessionState,
    ) -> bool:
        if state.runtime_mode == "local":
            return (
                dataset.workspace_id == state.workspace_id and dataset.visibility_scope == "local"
            )
        if dataset.workspace_id != state.workspace_id:
            return False
        if dataset.visibility_scope == "workspace":
            return True
        if state.user is not None and state.user.platform_role == "admin":
            return True
        return dataset.owner_user_id == state.user.user_id if state.user is not None else False

    def _updated_fields(
        self,
        current: DatasetDetail,
        updated: DatasetDetail,
    ) -> tuple[DatasetProfileField, ...]:
        changed_fields: list[DatasetProfileField] = []
        if current.device_type != updated.device_type:
            changed_fields.append("device_type")
        if current.capabilities != updated.capabilities:
            changed_fields.append("capabilities")
        if current.source != updated.source:
            changed_fields.append("source")
        return tuple(changed_fields)

    def _with_allowed_actions(self, dataset: DatasetDetail, state: SessionState) -> DatasetDetail:
        return DatasetDetail(
            **{
                **dataset.__dict__,
                "allowed_actions": self._allowed_actions(dataset, state),
            }
        )

    def _catalog_row(
        self,
        dataset: DatasetDetail,
        state: SessionState,
    ) -> DatasetCatalogRow:
        return DatasetCatalogRow(
            dataset_id=dataset.dataset_id,
            name=dataset.name,
            visibility_scope=dataset.visibility_scope,
            lifecycle_state=dataset.lifecycle_state,
            device_type=dataset.device_type,
            updated_at=dataset.updated_at,
            allowed_actions=self._allowed_actions(dataset, state),
            family=dataset.family,
            owner_display_name=dataset.owner,
        )

    def _can_manage_datasets(self, state: SessionState) -> bool:
        if state.runtime_mode == "local":
            return True
        return self._authorization_service.build_session_capabilities(state).can_manage_datasets

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


def _build_design_id(name: str) -> str:
    return f"design_{_slugify(name)}"


def _slugify(value: str) -> str:
    return "-".join(
        token
        for token in "".join(
            character.lower() if character.isalnum() else "-" for character in value.strip()
        ).split("-")
        if token
    )
