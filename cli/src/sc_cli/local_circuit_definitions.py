"""CLI-local standalone circuit-definition contracts and persisted catalog."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Literal, cast

from pydantic import BaseModel
from sc_core import inspect_circuit_definition_source

from sc_cli.local_errors import CliContractError, build_contract_error
from sc_cli.local_store import definition_catalog_path, read_json, write_model

LocalValidationLevel = Literal["ok", "warning", "invalid"]
LocalCircuitDefinitionSortBy = Literal["created_at", "name", "element_count"]
LocalSortOrder = Literal["asc", "desc"]


class LocalValidationNotice(BaseModel):
    level: LocalValidationLevel
    message: str


class LocalValidationSummary(BaseModel):
    status: LocalValidationLevel
    notice_count: int
    warning_count: int
    invalid_count: int


class LocalDefinitionLineage(BaseModel):
    source_runtime: str
    source_definition_id: int | None = None
    source_bundle_id: str | None = None
    parent_bundle_id: str | None = None
    imported_from_bundle_id: str | None = None


class LocalCircuitDefinitionSummary(BaseModel):
    definition_id: int
    name: str
    created_at: str
    element_count: int
    validation_status: LocalValidationLevel
    preview_artifact_count: int


class LocalCircuitDefinitionDetail(LocalCircuitDefinitionSummary):
    source_text: str
    normalized_output: str
    validation_notices: list[LocalValidationNotice]
    validation_summary: LocalValidationSummary
    preview_artifacts: list[str]
    lineage: LocalDefinitionLineage | None = None


class LocalCircuitDefinitionInspection(BaseModel):
    source_file: str
    circuit_name: str
    family: str
    element_count: int
    validation_status: LocalValidationLevel
    preview_artifact_count: int
    preview_artifacts: list[str]
    normalized_output: str
    validation_notices: list[LocalValidationNotice]
    validation_summary: LocalValidationSummary


class LocalDefinitionBundleMetadata(BaseModel):
    bundle_family: str
    bundle_version: str
    bundle_id: str
    exported_at: str
    source_runtime: str


class LocalDefinitionBundle(BaseModel):
    metadata: LocalDefinitionBundleMetadata
    definition: LocalCircuitDefinitionDetail


class LocalDefinitionBundleExportReceipt(BaseModel):
    bundle_file: str
    bundle: LocalDefinitionBundle


class LocalDefinitionBundleImportReceipt(BaseModel):
    bundle_file: str
    bundle: LocalDefinitionBundle
    imported_definition: LocalCircuitDefinitionDetail


@dataclass
class _CatalogState:
    definitions: dict[int, LocalCircuitDefinitionDetail] = field(default_factory=dict)
    next_definition_id: int = 19


class _PersistedDefinitionCatalog(BaseModel):
    next_definition_id: int
    definitions: list[LocalCircuitDefinitionDetail]


def _contract_error(
    *,
    code: str,
    category: Literal["not_found", "validation", "forbidden", "conflict"],
    message: str,
    status: int,
    field_errors: list[dict[str, str]] | None = None,
) -> CliContractError:
    return build_contract_error(
        code=code,
        category=category,
        message=message,
        status=status,
        field_errors=field_errors,
    )


def normalize_validation_level(level: str) -> LocalValidationLevel:
    if level == "ok":
        return "ok"
    if level == "warning":
        return "warning"
    return "invalid"


def build_local_validation_notices(
    notices: Iterable[object],
) -> list[LocalValidationNotice]:
    local_notices: list[LocalValidationNotice] = []
    for notice in notices:
        notice_obj = cast(Any, notice)
        local_notices.append(
            LocalValidationNotice(
                level=normalize_validation_level(str(notice_obj.level)),
                message=str(notice_obj.message),
            )
        )
    return local_notices


def derive_validation_status(
    notices: Iterable[LocalValidationNotice],
) -> LocalValidationLevel:
    levels = {notice.level for notice in notices}
    if "invalid" in levels:
        return "invalid"
    if "warning" in levels:
        return "warning"
    return "ok"


def build_validation_summary(
    notices: list[LocalValidationNotice],
) -> LocalValidationSummary:
    return LocalValidationSummary(
        status=derive_validation_status(notices),
        notice_count=len(notices),
        warning_count=sum(1 for notice in notices if notice.level == "warning"),
        invalid_count=sum(1 for notice in notices if notice.level == "invalid"),
    )


def _normalize_lineage_payload(payload: object | None) -> LocalDefinitionLineage | None:
    if payload is None:
        return None
    if isinstance(payload, LocalDefinitionLineage):
        return payload.model_copy(deep=True)
    return LocalDefinitionLineage.model_validate(payload)


def build_local_circuit_definition_summary(
    payload: object,
) -> LocalCircuitDefinitionSummary:
    payload_obj = cast(Any, payload)
    return LocalCircuitDefinitionSummary(
        definition_id=int(payload_obj.definition_id),
        name=str(payload_obj.name),
        created_at=str(payload_obj.created_at),
        element_count=int(payload_obj.element_count),
        validation_status=normalize_validation_level(str(payload_obj.validation_status)),
        preview_artifact_count=int(payload_obj.preview_artifact_count),
    )


def build_local_circuit_definition_detail(
    payload: object,
) -> LocalCircuitDefinitionDetail:
    payload_obj = cast(Any, payload)
    validation_notices = build_local_validation_notices(payload_obj.validation_notices)
    validation_summary = build_validation_summary(validation_notices)
    summary = build_local_circuit_definition_summary(payload)
    lineage = _normalize_lineage_payload(getattr(payload_obj, "lineage", None))
    return LocalCircuitDefinitionDetail(
        definition_id=summary.definition_id,
        name=summary.name,
        created_at=summary.created_at,
        element_count=summary.element_count,
        validation_status=validation_summary.status,
        preview_artifact_count=summary.preview_artifact_count,
        source_text=str(payload_obj.source_text),
        normalized_output=str(payload_obj.normalized_output),
        validation_notices=validation_notices,
        validation_summary=validation_summary,
        preview_artifacts=[str(artifact) for artifact in payload_obj.preview_artifacts],
        lineage=lineage,
    )


def build_local_circuit_definition_inspection(
    *,
    source_file: str,
    inspection: object,
    preview_artifacts: Iterable[str],
) -> LocalCircuitDefinitionInspection:
    inspection_obj = cast(Any, inspection)
    validation_notices = build_local_validation_notices(inspection_obj.validation_notices)
    validation_summary = build_validation_summary(validation_notices)
    preview_artifact_list = [str(artifact) for artifact in preview_artifacts]
    return LocalCircuitDefinitionInspection(
        source_file=source_file,
        circuit_name=str(inspection_obj.circuit_name),
        family=str(inspection_obj.family),
        element_count=int(inspection_obj.element_count),
        validation_status=validation_summary.status,
        preview_artifact_count=len(preview_artifact_list),
        preview_artifacts=preview_artifact_list,
        normalized_output=str(inspection_obj.normalized_output),
        validation_notices=validation_notices,
        validation_summary=validation_summary,
    )


def build_definition_bundle(
    definition: LocalCircuitDefinitionDetail,
) -> LocalDefinitionBundle:
    return LocalDefinitionBundle(
        metadata=LocalDefinitionBundleMetadata(
            bundle_family="definition_bundle",
            bundle_version="1.0",
            bundle_id=f"bundle:definition:{definition.definition_id}",
            exported_at=_bundle_exported_at(definition.definition_id),
            source_runtime="standalone_cli",
        ),
        definition=definition.model_copy(deep=True),
    )


def _bundle_exported_at(definition_id: int) -> str:
    return f"2026-03-16T00:{definition_id % 60:02d}:00Z"


def _created_at(definition_id: int) -> str:
    return f"2026-03-15T12:{definition_id % 60:02d}:00Z"


def _preview_artifacts_from_inspection(inspection: object) -> list[str]:
    preview_artifacts = getattr(inspection, "preview_artifacts", ())
    return [str(artifact) for artifact in preview_artifacts]


def _validate_source_text(source_text: str) -> str:
    normalized_source_text = source_text.strip()
    if normalized_source_text:
        return source_text
    raise _contract_error(
        code="request_validation_failed",
        category="validation",
        message="Request validation failed.",
        status=422,
        field_errors=[
            {
                "field": "source_text",
                "message": "Circuit-definition source_text must not be blank.",
            }
        ],
    )


def _build_detail_from_source(
    *,
    definition_id: int,
    name: str,
    created_at: str,
    source_text: str,
    lineage: LocalDefinitionLineage | None = None,
) -> LocalCircuitDefinitionDetail:
    validated_source_text = _validate_source_text(source_text)
    inspection = inspect_circuit_definition_source(validated_source_text)
    payload = SimpleNamespace(
        definition_id=definition_id,
        name=name,
        created_at=created_at,
        element_count=int(inspection.element_count),
        validation_status=derive_validation_status(
            build_local_validation_notices(inspection.validation_notices)
        ),
        preview_artifact_count=len(_preview_artifacts_from_inspection(inspection)),
        source_text=validated_source_text,
        normalized_output=str(inspection.normalized_output),
        validation_notices=inspection.validation_notices,
        preview_artifacts=_preview_artifacts_from_inspection(inspection),
        lineage=lineage,
    )
    return build_local_circuit_definition_detail(payload)


def _seed_source_text(name: str) -> str:
    return "\n".join(
        [
            f"name: {name}",
            "components:",
            "  - name: R1",
            "    default: 50.0",
            "    unit: Ohm",
            "  - name: C1",
            "    default: 100.0",
            "    unit: fF",
            "  - name: Lj1",
            "    default: 1000.0",
            "    unit: pH",
            "  - name: C2",
            "    default: 1000.0",
            "    unit: fF",
            "topology:",
            '  - [P1, "1", "0", 1]',
            '  - [R1, "1", "0", "R1"]',
            '  - [C1, "1", "2", "C1"]',
            '  - [Lj1, "2", "0", "Lj1"]',
            '  - [C2, "2", "0", "C2"]',
        ]
    )


def _seed_catalog_state() -> _CatalogState:
    definitions = {
        7: _build_detail_from_source(
            definition_id=7,
            name="CoupledReadoutResonator",
            created_at=_created_at(7),
            source_text=_seed_source_text("CoupledReadoutResonator"),
        ),
        12: _build_detail_from_source(
            definition_id=12,
            name="ReadoutChainWithBus",
            created_at=_created_at(12),
            source_text=_seed_source_text("ReadoutChainWithBus"),
        ),
        18: _build_detail_from_source(
            definition_id=18,
            name="FloatingQubitWithXYLine",
            created_at=_created_at(18),
            source_text=_seed_source_text("FloatingQubitWithXYLine"),
        ),
    }
    return _CatalogState(definitions=definitions, next_definition_id=19)


def _persist_catalog_state(state: _CatalogState) -> None:
    write_model(
        definition_catalog_path(),
        _PersistedDefinitionCatalog(
            next_definition_id=state.next_definition_id,
            definitions=[
                definition.model_copy(deep=True)
                for definition in state.definitions.values()
            ],
        ),
    )


def _load_persisted_catalog_state() -> _CatalogState | None:
    payload = read_json(definition_catalog_path())
    if not isinstance(payload, dict):
        return None
    catalog = _PersistedDefinitionCatalog.model_validate(payload)
    return _CatalogState(
        definitions={
            definition.definition_id: definition.model_copy(deep=True)
            for definition in catalog.definitions
        },
        next_definition_id=catalog.next_definition_id,
    )


def _load_or_seed_catalog_state() -> _CatalogState:
    persisted_state = _load_persisted_catalog_state()
    if persisted_state is not None:
        return persisted_state
    seeded_state = _seed_catalog_state()
    _persist_catalog_state(seeded_state)
    return seeded_state


_STATE = _load_or_seed_catalog_state()


def reset_local_circuit_definition_state() -> None:
    global _STATE
    _STATE = _seed_catalog_state()
    _persist_catalog_state(_STATE)


def reload_local_circuit_definition_state() -> None:
    global _STATE
    _STATE = _load_or_seed_catalog_state()


def list_local_circuit_definitions(
    *,
    search: str | None = None,
    sort_by: LocalCircuitDefinitionSortBy = "created_at",
    sort_order: LocalSortOrder = "desc",
) -> list[LocalCircuitDefinitionSummary]:
    definitions = list(_STATE.definitions.values())
    if search:
        search_key = search.lower()
        definitions = [
            definition
            for definition in definitions
            if search_key in definition.name.lower()
        ]
    reverse = sort_order == "desc"
    if sort_by == "name":
        definitions.sort(key=lambda definition: definition.name.lower(), reverse=reverse)
    elif sort_by == "element_count":
        definitions.sort(key=lambda definition: definition.element_count, reverse=reverse)
    else:
        definitions.sort(key=lambda definition: definition.created_at, reverse=reverse)
    return [
        build_local_circuit_definition_summary(definition)
        for definition in definitions
    ]


def get_local_circuit_definition(definition_id: int) -> LocalCircuitDefinitionDetail:
    definition = _STATE.definitions.get(definition_id)
    if definition is None:
        raise _contract_error(
            code="definition_not_found",
            category="not_found",
            message=f"Circuit definition {definition_id} was not found.",
            status=404,
        )
    return definition.model_copy(deep=True)


def create_local_circuit_definition(
    *,
    name: str,
    source_text: str,
) -> LocalCircuitDefinitionDetail:
    definition_id = _STATE.next_definition_id
    _STATE.next_definition_id += 1
    definition = _build_detail_from_source(
        definition_id=definition_id,
        name=name,
        created_at=_created_at(definition_id),
        source_text=source_text,
    )
    _STATE.definitions[definition_id] = definition
    _persist_catalog_state(_STATE)
    return definition.model_copy(deep=True)


def update_local_circuit_definition(
    definition_id: int,
    *,
    name: str,
    source_text: str,
) -> LocalCircuitDefinitionDetail:
    existing_definition = get_local_circuit_definition(definition_id)
    updated_definition = _build_detail_from_source(
        definition_id=definition_id,
        name=name,
        created_at=existing_definition.created_at,
        source_text=source_text,
        lineage=existing_definition.lineage,
    )
    _STATE.definitions[definition_id] = updated_definition
    _persist_catalog_state(_STATE)
    return updated_definition.model_copy(deep=True)


def delete_local_circuit_definition(definition_id: int) -> None:
    if definition_id not in _STATE.definitions:
        raise _contract_error(
            code="definition_not_found",
            category="not_found",
            message=f"Circuit definition {definition_id} was not found.",
            status=404,
        )
    del _STATE.definitions[definition_id]
    _persist_catalog_state(_STATE)


def export_definition_bundle(definition_id: int) -> LocalDefinitionBundle:
    return build_definition_bundle(get_local_circuit_definition(definition_id))


def import_definition_bundle(bundle: LocalDefinitionBundle) -> LocalCircuitDefinitionDetail:
    definition_id = _STATE.next_definition_id
    _STATE.next_definition_id += 1
    previous_lineage = bundle.definition.lineage
    imported_lineage = LocalDefinitionLineage(
        source_runtime=(
            bundle.metadata.source_runtime
            if previous_lineage is None
            else previous_lineage.source_runtime
        ),
        source_definition_id=(
            bundle.definition.definition_id
            if previous_lineage is None or previous_lineage.source_definition_id is None
            else previous_lineage.source_definition_id
        ),
        source_bundle_id=(
            bundle.metadata.bundle_id
            if previous_lineage is None or previous_lineage.source_bundle_id is None
            else previous_lineage.source_bundle_id
        ),
        parent_bundle_id=bundle.metadata.bundle_id,
        imported_from_bundle_id=bundle.metadata.bundle_id,
    )
    imported_definition = _build_detail_from_source(
        definition_id=definition_id,
        name=bundle.definition.name,
        created_at=_created_at(definition_id),
        source_text=bundle.definition.source_text,
        lineage=imported_lineage,
    )
    _STATE.definitions[definition_id] = imported_definition
    _persist_catalog_state(_STATE)
    return imported_definition.model_copy(deep=True)
