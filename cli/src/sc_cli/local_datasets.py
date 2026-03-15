"""CLI-local dataset catalog, contracts, and interchange bundles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sc_cli.local_errors import CliContractError, build_contract_error
from sc_cli.local_runtime import LocalSessionDataset
from sc_cli.local_store import dataset_catalog_path, read_json, write_model

LocalDatasetStatus = Literal["Ready", "Queued", "Review"]
LocalDatasetSortBy = Literal["updated_at", "name", "samples"]
LocalSortOrder = Literal["asc", "desc"]


class LocalDatasetLineage(BaseModel):
    source_runtime: str
    source_dataset_id: str | None = None
    source_bundle_id: str | None = None
    parent_bundle_id: str | None = None
    imported_from_bundle_id: str | None = None


class LocalDatasetMetrics(BaseModel):
    capability_count: int
    tag_count: int
    preview_row_count: int
    artifact_count: int
    lineage_depth: int


class LocalDatasetMetadataRecord(BaseModel):
    record_id: str


class LocalDatasetTracePayload(BaseModel):
    store_key: str
    store_uri: str
    payload_role: str
    schema_version: str


class LocalDatasetResultHandle(BaseModel):
    handle_id: str
    kind: str
    payload_locator: str


class LocalDatasetStorage(BaseModel):
    metadata_record: LocalDatasetMetadataRecord
    primary_trace: LocalDatasetTracePayload | None = None
    result_handles: list[LocalDatasetResultHandle] = Field(default_factory=list)


class LocalDatasetSummary(BaseModel):
    dataset_id: str
    name: str
    family: str
    owner: str
    updated_at: str
    device_type: str
    source: str
    samples: int
    status: LocalDatasetStatus
    capability_count: int
    tag_count: int


class LocalDatasetDesignScope(BaseModel):
    design_id: str
    name: str
    trace_batch_ids: list[str] = Field(default_factory=list)
    analysis_run_ids: list[str] = Field(default_factory=list)


class LocalDatasetTraceManifestEntry(BaseModel):
    trace_batch_id: str
    design_id: str
    family: str
    store_key: str
    store_uri: str


class LocalDatasetDetail(LocalDatasetSummary):
    capabilities: list[str]
    tags: list[str]
    preview_columns: list[str]
    preview_rows: list[list[str]]
    artifacts: list[str]
    metrics: LocalDatasetMetrics
    storage: LocalDatasetStorage
    design_scopes: list[LocalDatasetDesignScope] = Field(default_factory=list)
    trace_manifest: list[LocalDatasetTraceManifestEntry] = Field(default_factory=list)
    lineage: LocalDatasetLineage | None = None


class LocalDatasetMetadataUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    device_type: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    source: str = Field(min_length=1)

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, capabilities: list[str]) -> list[str]:
        cleaned = [capability.strip() for capability in capabilities]
        if any(not capability for capability in cleaned):
            raise ValueError("Capabilities must not be blank.")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Capabilities must be unique.")
        return cleaned


class LocalDatasetMetadataUpdateReceipt(BaseModel):
    dataset: LocalDatasetDetail
    updated_fields: list[Literal["device_type", "capabilities", "source"]]


class LocalDatasetBundleMetadata(BaseModel):
    bundle_family: str
    bundle_version: str
    bundle_id: str
    exported_at: str
    source_runtime: str


class LocalDatasetBundle(BaseModel):
    metadata: LocalDatasetBundleMetadata
    dataset: LocalDatasetDetail


class LocalDatasetBundleExportReceipt(BaseModel):
    bundle_file: str
    bundle: LocalDatasetBundle


class LocalDatasetBundleImportReceipt(BaseModel):
    bundle_file: str
    bundle: LocalDatasetBundle
    imported_dataset: LocalDatasetDetail


class _PersistedDatasetCatalog(BaseModel):
    next_import_id: int
    datasets: list[LocalDatasetDetail]


@dataclass
class _DatasetCatalogState:
    datasets: dict[str, LocalDatasetDetail] = field(default_factory=dict)
    next_import_id: int = 1


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


def _build_summary(dataset: LocalDatasetDetail) -> LocalDatasetSummary:
    return LocalDatasetSummary(
        dataset_id=dataset.dataset_id,
        name=dataset.name,
        family=dataset.family,
        owner=dataset.owner,
        updated_at=dataset.updated_at,
        device_type=dataset.device_type,
        source=dataset.source,
        samples=dataset.samples,
        status=dataset.status,
        capability_count=len(dataset.capabilities),
        tag_count=len(dataset.tags),
    )


def _build_metrics(
    *,
    capabilities: list[str],
    tags: list[str],
    preview_rows: list[list[str]],
    artifacts: list[str],
    lineage: LocalDatasetLineage | None,
) -> LocalDatasetMetrics:
    return LocalDatasetMetrics(
        capability_count=len(capabilities),
        tag_count=len(tags),
        preview_row_count=len(preview_rows),
        artifact_count=len(artifacts),
        lineage_depth=0 if lineage is None else 1,
    )


def _build_dataset_detail(
    *,
    dataset_id: str,
    name: str,
    family: str,
    owner: str,
    updated_at: str,
    device_type: str,
    source: str,
    samples: int,
    status: LocalDatasetStatus,
    capabilities: list[str],
    tags: list[str],
    preview_columns: list[str],
    preview_rows: list[list[str]],
    artifacts: list[str],
    metadata_record_id: str,
    primary_trace: LocalDatasetTracePayload | None,
    result_handles: list[LocalDatasetResultHandle],
    design_scopes: list[LocalDatasetDesignScope],
    trace_manifest: list[LocalDatasetTraceManifestEntry],
    lineage: LocalDatasetLineage | None = None,
) -> LocalDatasetDetail:
    metrics = _build_metrics(
        capabilities=capabilities,
        tags=tags,
        preview_rows=preview_rows,
        artifacts=artifacts,
        lineage=lineage,
    )
    summary = LocalDatasetSummary(
        dataset_id=dataset_id,
        name=name,
        family=family,
        owner=owner,
        updated_at=updated_at,
        device_type=device_type,
        source=source,
        samples=samples,
        status=status,
        capability_count=metrics.capability_count,
        tag_count=metrics.tag_count,
    )
    return LocalDatasetDetail(
        **summary.model_dump(mode="json"),
        capabilities=capabilities,
        tags=tags,
        preview_columns=preview_columns,
        preview_rows=preview_rows,
        artifacts=artifacts,
        metrics=metrics,
        storage=LocalDatasetStorage(
            metadata_record=LocalDatasetMetadataRecord(record_id=metadata_record_id),
            primary_trace=primary_trace,
            result_handles=result_handles,
        ),
        design_scopes=design_scopes,
        trace_manifest=trace_manifest,
        lineage=lineage,
    )


def _seed_datasets() -> _DatasetCatalogState:
    fluxonium_trace = LocalDatasetTracePayload(
        store_key="datasets/fluxonium-2025-031/trace-batches/88.zarr",
        store_uri="trace_store/datasets/fluxonium-2025-031/trace-batches/88.zarr",
        payload_role="simulation_trace",
        schema_version="trace-store/v1",
    )
    transmon_trace = LocalDatasetTracePayload(
        store_key="datasets/transmon-coupler-014/trace-batches/42.zarr",
        store_uri="trace_store/datasets/transmon-coupler-014/trace-batches/42.zarr",
        payload_role="characterization_trace",
        schema_version="trace-store/v1",
    )
    datasets = {
        "fluxonium-2025-031": _build_dataset_detail(
            dataset_id="fluxonium-2025-031",
            name="Fluxonium sweep 031",
            family="fluxonium",
            owner="Rewrite Local User",
            updated_at="2026-03-15T10:12:00Z",
            device_type="Fluxonium",
            source="measured",
            samples=184,
            status="Ready",
            capabilities=["simulation", "fit-ready"],
            tags=["fluxonium", "sweep"],
            preview_columns=["frequency_ghz", "s11_real", "s11_imag"],
            preview_rows=[
                ["4.00", "0.10", "0.00"],
                ["4.50", "0.20", "-0.05"],
            ],
            artifacts=["trace-summary.json", "fit-table.csv"],
            metadata_record_id="dataset:fluxonium-2025-031",
            primary_trace=fluxonium_trace,
            result_handles=[
                LocalDatasetResultHandle(
                    handle_id="result:fluxonium-2025-031:fit-summary",
                    kind="analysis_summary",
                    payload_locator="artifacts/fit-summary.json",
                )
            ],
            design_scopes=[
                LocalDatasetDesignScope(
                    design_id="design-fluxonium-main",
                    name="Main Fluxonium Device",
                    trace_batch_ids=["trace-batch:88"],
                    analysis_run_ids=["analysis:fluxonium-2025-031:fit-summary"],
                )
            ],
            trace_manifest=[
                LocalDatasetTraceManifestEntry(
                    trace_batch_id="trace-batch:88",
                    design_id="design-fluxonium-main",
                    family="s_matrix",
                    store_key=fluxonium_trace.store_key,
                    store_uri=fluxonium_trace.store_uri,
                )
            ],
        ),
        "transmon-coupler-014": _build_dataset_detail(
            dataset_id="transmon-coupler-014",
            name="Coupler detuning 014",
            family="transmon",
            owner="Rewrite Local User",
            updated_at="2026-03-15T09:54:00Z",
            device_type="Transmon",
            source="simulated",
            samples=96,
            status="Ready",
            capabilities=["characterization", "cross-resonance"],
            tags=["transmon", "coupler"],
            preview_columns=["frequency_ghz", "coupling_mhz"],
            preview_rows=[
                ["4.10", "12.4"],
                ["4.30", "14.1"],
            ],
            artifacts=["detuning-report.json"],
            metadata_record_id="dataset:transmon-coupler-014",
            primary_trace=transmon_trace,
            result_handles=[
                LocalDatasetResultHandle(
                    handle_id="result:transmon-coupler-014:detuning-report",
                    kind="summary",
                    payload_locator="artifacts/detuning-report.json",
                )
            ],
            design_scopes=[
                LocalDatasetDesignScope(
                    design_id="design-transmon-coupler",
                    name="Coupler Device",
                    trace_batch_ids=["trace-batch:42"],
                    analysis_run_ids=[],
                )
            ],
            trace_manifest=[
                LocalDatasetTraceManifestEntry(
                    trace_batch_id="trace-batch:42",
                    design_id="design-transmon-coupler",
                    family="y_matrix",
                    store_key=transmon_trace.store_key,
                    store_uri=transmon_trace.store_uri,
                )
            ],
        ),
    }
    return _DatasetCatalogState(datasets=datasets, next_import_id=1)


def _persist_catalog_state(state: _DatasetCatalogState) -> None:
    write_model(
        dataset_catalog_path(),
        _PersistedDatasetCatalog(
            next_import_id=state.next_import_id,
            datasets=[dataset.model_copy(deep=True) for dataset in state.datasets.values()],
        ),
    )


def _load_persisted_catalog_state() -> _DatasetCatalogState | None:
    payload = read_json(dataset_catalog_path())
    if not isinstance(payload, dict):
        return None
    catalog = _PersistedDatasetCatalog.model_validate(payload)
    return _DatasetCatalogState(
        datasets={
            dataset.dataset_id: dataset.model_copy(deep=True)
            for dataset in catalog.datasets
        },
        next_import_id=catalog.next_import_id,
    )


def _load_or_seed_catalog_state() -> _DatasetCatalogState:
    persisted_state = _load_persisted_catalog_state()
    if persisted_state is not None:
        return persisted_state
    seeded_state = _seed_datasets()
    _persist_catalog_state(seeded_state)
    return seeded_state


_STATE = _load_or_seed_catalog_state()


def reset_local_dataset_state() -> None:
    global _STATE
    _STATE = _seed_datasets()
    _persist_catalog_state(_STATE)


def reload_local_dataset_state() -> None:
    global _STATE
    _STATE = _load_or_seed_catalog_state()


def has_local_dataset(dataset_id: str) -> bool:
    return dataset_id in _STATE.datasets


def get_local_session_dataset(dataset_id: str) -> LocalSessionDataset:
    dataset = get_local_dataset(dataset_id)
    return LocalSessionDataset(
        dataset_id=dataset.dataset_id,
        name=dataset.name,
        family=dataset.family,
        status=dataset.status.lower(),
        owner=dataset.owner,
        access_scope="workspace",
    )


def list_local_datasets(
    *,
    family: str | None = None,
    status: LocalDatasetStatus | None = None,
    sort_by: LocalDatasetSortBy = "updated_at",
    sort_order: LocalSortOrder = "desc",
) -> list[LocalDatasetSummary]:
    datasets = list(_STATE.datasets.values())
    if family is not None:
        family_key = family.lower()
        datasets = [dataset for dataset in datasets if dataset.family.lower() == family_key]
    if status is not None:
        datasets = [dataset for dataset in datasets if dataset.status == status]
    reverse = sort_order == "desc"
    if sort_by == "name":
        datasets.sort(key=lambda dataset: dataset.name.lower(), reverse=reverse)
    elif sort_by == "samples":
        datasets.sort(key=lambda dataset: dataset.samples, reverse=reverse)
    else:
        datasets.sort(key=lambda dataset: dataset.updated_at, reverse=reverse)
    return [_build_summary(dataset) for dataset in datasets]


def get_local_dataset(dataset_id: str) -> LocalDatasetDetail:
    dataset = _STATE.datasets.get(dataset_id)
    if dataset is None:
        raise _contract_error(
            code="dataset_not_found",
            category="not_found",
            message=f"Dataset {dataset_id} was not found.",
            status=404,
        )
    return dataset.model_copy(deep=True)


def update_local_dataset_metadata(
    dataset_id: str,
    *,
    device_type: str,
    capabilities: tuple[str, ...],
    source: str,
) -> LocalDatasetMetadataUpdateReceipt:
    try:
        request = LocalDatasetMetadataUpdateRequest(
            device_type=device_type,
            capabilities=list(capabilities),
            source=source,
        )
    except Exception as error:
        message = str(error)
        field = "capabilities" if "Capabilities" in message else "request"
        raise _contract_error(
            code="request_validation_failed",
            category="validation",
            message="Request validation failed.",
            status=422,
            field_errors=[{"field": field, "message": message}],
        ) from error

    dataset = get_local_dataset(dataset_id)
    updated_dataset = dataset.model_copy(
        deep=True,
        update={
            "device_type": request.device_type,
            "capabilities": request.capabilities,
            "source": request.source,
            "updated_at": "2026-03-16T09:00:00Z",
            "metrics": _build_metrics(
                capabilities=request.capabilities,
                tags=dataset.tags,
                preview_rows=dataset.preview_rows,
                artifacts=dataset.artifacts,
                lineage=dataset.lineage,
            ),
        },
    )
    updated_dataset.capability_count = len(updated_dataset.capabilities)
    updated_dataset.tag_count = len(updated_dataset.tags)
    _STATE.datasets[dataset_id] = updated_dataset
    _persist_catalog_state(_STATE)
    return LocalDatasetMetadataUpdateReceipt(
        dataset=updated_dataset.model_copy(deep=True),
        updated_fields=["device_type", "capabilities", "source"],
    )


def export_dataset_bundle(dataset_id: str) -> LocalDatasetBundle:
    dataset = get_local_dataset(dataset_id)
    return LocalDatasetBundle(
        metadata=LocalDatasetBundleMetadata(
            bundle_family="dataset_bundle",
            bundle_version="1.0",
            bundle_id=f"bundle:dataset:{dataset.dataset_id}",
            exported_at="2026-03-16T10:00:00Z",
            source_runtime="standalone_cli",
        ),
        dataset=dataset,
    )


def import_dataset_bundle(bundle: LocalDatasetBundle) -> LocalDatasetDetail:
    imported_dataset_id = f"imported-dataset-{_STATE.next_import_id:03d}"
    _STATE.next_import_id += 1
    previous_lineage = bundle.dataset.lineage
    imported_lineage = LocalDatasetLineage(
        source_runtime=(
            bundle.metadata.source_runtime
            if previous_lineage is None
            else previous_lineage.source_runtime
        ),
        source_dataset_id=(
            bundle.dataset.dataset_id
            if previous_lineage is None or previous_lineage.source_dataset_id is None
            else previous_lineage.source_dataset_id
        ),
        source_bundle_id=(
            bundle.metadata.bundle_id
            if previous_lineage is None or previous_lineage.source_bundle_id is None
            else previous_lineage.source_bundle_id
        ),
        parent_bundle_id=bundle.metadata.bundle_id,
        imported_from_bundle_id=bundle.metadata.bundle_id,
    )
    imported_dataset = bundle.dataset.model_copy(
        deep=True,
        update={
            "dataset_id": imported_dataset_id,
            "updated_at": "2026-03-16T10:05:00Z",
            "lineage": imported_lineage,
            "metrics": _build_metrics(
                capabilities=bundle.dataset.capabilities,
                tags=bundle.dataset.tags,
                preview_rows=bundle.dataset.preview_rows,
                artifacts=bundle.dataset.artifacts,
                lineage=imported_lineage,
            ),
        },
    )
    _STATE.datasets[imported_dataset_id] = imported_dataset
    _persist_catalog_state(_STATE)
    return imported_dataset.model_copy(deep=True)
