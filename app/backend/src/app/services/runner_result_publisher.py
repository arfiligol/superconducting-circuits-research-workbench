from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from sc_core.execution import TaskResultHandle
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.app.domain.storage import ResultHandleRef, TracePayloadRef
from src.app.domain.tasks import TaskDetail, TaskLifecycleUpdate, TaskResultRefs
from src.app.infrastructure.persistence.models import (
    RewriteDatasetDesignRecord,
    RewriteDatasetRecord,
    RewritePublishedSimulationResultRecord,
    RewritePublishedSimulationTraceRecord,
)
from src.app.infrastructure.persistence.storage_metadata_repository import (
    SqliteRewriteStorageMetadataRepository,
)
from src.app.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)
from src.app.services.service_errors import service_error
from src.app.services.task_service import TaskService
from src.app.settings import AppSettings


@dataclass(frozen=True)
class RunnerPublicationResult:
    task_id: int
    dataset_id: str
    design_id: str
    batch_id: str
    store_key: str
    store_uri: str
    manifest_artifact_path: str
    trace_ids: tuple[str, ...]


@dataclass(frozen=True)
class _TraceManifest:
    trace_key: str
    family: str
    parameter: str
    representation: str
    real_path: str
    imag_path: str
    shape: tuple[int, ...]
    chunk_shape: tuple[int, ...]
    dtype: str
    axes: tuple[dict[str, object], ...]


class RunnerResultPublisher:
    def __init__(
        self,
        *,
        settings: AppSettings,
        task_service: TaskService,
        storage_metadata_repository: SqliteRewriteStorageMetadataRepository,
        metadata_session_factory: sessionmaker[Session],
    ) -> None:
        self._settings = settings
        self._task_service = task_service
        self._storage_metadata_repository = storage_metadata_repository
        self._metadata_session_factory = metadata_session_factory

    def publish_complete_result(
        self,
        *,
        task_id: int,
        runner_id: str,
        manifest_path: str,
        manifest_sha256: str | None = None,
        output_target: Mapping[str, object] | None = None,
    ) -> RunnerPublicationResult:
        task = self._task_service.get_task(task_id)
        self._update_task(
            task,
            status="staging_result",
            percent=90,
            summary="Runner result staged.",
        )

        manifest_file = self._resolve_relative_path_under(
            manifest_path,
            root=self._staging_root(),
            field="manifest_path",
        )
        if not manifest_file.is_file():
            raise service_error(
                404,
                code="runner_manifest_not_found",
                category="not_found",
                message="Runner manifest was not found.",
            )
        if manifest_sha256 is not None:
            actual_sha256 = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
            if actual_sha256 != manifest_sha256:
                raise service_error(
                    422,
                    code="runner_manifest_checksum_mismatch",
                    category="validation",
                    message="Runner manifest checksum does not match the reported value.",
                )

        manifest = self._load_manifest(manifest_file)
        self._validate_manifest_identity(manifest, task_id=task_id)
        zarr_root = self._resolve_zarr_root(manifest_file, manifest)
        traces = self._validate_zarr_layout(zarr_root, manifest)
        dataset_id, design_id = self._resolve_output_target(task, output_target)

        self._update_task(
            task,
            status="publishing",
            percent=95,
            summary="Publishing runner result.",
        )
        batch_id = f"batch_{task_id}"
        store_key = f"datasets/{dataset_id}/designs/{design_id}/batches/{batch_id}.zarr"
        target_zarr = self._trace_store_root() / store_key
        if target_zarr.exists():
            raise service_error(
                409,
                code="runner_publication_target_exists",
                category="conflict",
                message="Runner publication target already exists.",
                details={"store_key": store_key},
            )
        target_zarr.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(zarr_root, target_zarr)

        artifact_dir = self._artifacts_root() / "tasks" / str(task_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        manifest_artifact = artifact_dir / "manifest.json"
        shutil.copy2(manifest_file, manifest_artifact)
        logs_dir = manifest_file.parent / "logs"
        if logs_dir.exists():
            target_logs_dir = artifact_dir / "logs"
            if target_logs_dir.exists():
                shutil.rmtree(target_logs_dir)
            shutil.copytree(logs_dir, target_logs_dir)

        result_handles, trace_payload = self._persist_publication_metadata(
            task=task,
            traces=traces,
            dataset_id=dataset_id,
            design_id=design_id,
            batch_id=batch_id,
            store_key=store_key,
            store_uri=str(target_zarr),
        )
        trace_batch_record = build_metadata_record_ref(
            "trace_batch",
            f"trace_batch:runner:{task_id}:{batch_id}",
            version=1,
        )
        self._task_service.update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=task_id,
                status="completed",
                progress_percent_complete=100,
                progress_summary=f"Published runner result package from {runner_id}.",
                progress_updated_at=_timestamp_now(),
                result_refs=TaskResultRefs(
                    result_handle=TaskResultHandle(),
                    metadata_records=(trace_batch_record,),
                    trace_payload=trace_payload,
                    result_handles=result_handles,
                ),
            )
        )
        return RunnerPublicationResult(
            task_id=task_id,
            dataset_id=dataset_id,
            design_id=design_id,
            batch_id=batch_id,
            store_key=store_key,
            store_uri=str(target_zarr),
            manifest_artifact_path=str(manifest_artifact),
            trace_ids=tuple(trace.trace_key for trace in traces),
        )

    def _persist_publication_metadata(
        self,
        *,
        task: TaskDetail,
        traces: Sequence[_TraceManifest],
        dataset_id: str,
        design_id: str,
        batch_id: str,
        store_key: str,
        store_uri: str,
    ) -> tuple[tuple[ResultHandleRef, ...], TracePayloadRef]:
        trace_batch_record = build_metadata_record_ref(
            "trace_batch",
            f"trace_batch:runner:{task.task_id}:{batch_id}",
            version=1,
        )
        first_trace = traces[0]
        trace_payload = build_trace_payload_ref(
            payload_role="dataset_primary",
            store_key=store_key,
            store_uri=store_uri,
            group_path=f"/traces/{first_trace.trace_key}",
            array_path="real",
            dtype=first_trace.dtype,
            shape=first_trace.shape,
            chunk_shape=first_trace.chunk_shape,
        )
        self._storage_metadata_repository.save_trace_payload(
            trace_batch_record,
            trace_payload,
            writer_version="runner-publisher.v1",
        )

        published_at = _timestamp_now()
        result_handles: list[ResultHandleRef] = []
        with self._metadata_session_factory() as session:
            self._ensure_dataset_design(session, dataset_id=dataset_id, design_id=design_id)
            publication = session.scalar(
                select(RewritePublishedSimulationResultRecord).where(
                    RewritePublishedSimulationResultRecord.source_task_id == task.task_id
                )
            )
            if publication is None:
                publication = RewritePublishedSimulationResultRecord(
                    publication_key=(
                        f"runner-publication:{task.task_id}:{dataset_id}:{design_id}:{batch_id}"
                    ),
                    source_task_id=task.task_id,
                    source_dataset_id=task.dataset_id,
                    source_result_handle_ids=[],
                    target_dataset_id=dataset_id,
                    target_design_id=design_id,
                    target_design_name=design_id,
                    published_at=published_at,
                )
                session.add(publication)
                session.flush()

            for trace in traces:
                result_record = build_metadata_record_ref(
                    "result_handle",
                    f"result_handle:runner:{task.task_id}:{trace.trace_key}",
                    version=1,
                )
                result_handle = build_result_handle_ref(
                    handle_id=f"runner-result:{task.task_id}:{trace.trace_key}",
                    kind="simulation_trace",
                    status="materialized",
                    label=f"Runner trace {trace.trace_key}",
                    metadata_record=result_record,
                    payload_backend="local_zarr",
                    payload_format="zarr",
                    payload_role="trace_payload",
                    payload_locator=f"{store_uri}{trace.real_path}",
                    provenance_task_id=task.task_id,
                    provenance=build_result_provenance_ref(
                        source_dataset_id=task.dataset_id,
                        source_task_id=task.task_id,
                        trace_batch_record=trace_batch_record,
                    ),
                )
                result_handles.append(result_handle)
                if not _published_trace_exists(
                    session,
                    dataset_id=dataset_id,
                    design_id=design_id,
                    trace_id=trace.trace_key,
                ):
                    session.add(
                        RewritePublishedSimulationTraceRecord(
                            publication_id=publication.id,
                            dataset_id=dataset_id,
                            design_id=design_id,
                            trace_id=trace.trace_key,
                            family=trace.family,
                            parameter=trace.parameter,
                            representation=trace.representation,
                            trace_mode_group="base",
                            source_kind="circuit_simulation",
                            stage_kind="raw",
                            provenance_summary=f"Julia Runner task {task.task_id}.",
                            axes_json=_axis_rows(trace),
                            preview_payload_json={
                                "kind": "zarr_trace",
                                "store_key": store_key,
                                "group_path": f"/traces/{trace.trace_key}",
                                "real_path": trace.real_path,
                                "imag_path": trace.imag_path,
                            },
                            payload_store_key=store_key,
                            result_handle_id=result_handle.handle_id,
                            published_at=published_at,
                        )
                    )
            publication.source_result_handle_ids = [handle.handle_id for handle in result_handles]
            publication.published_at = published_at
            session.commit()
        for result_handle in result_handles:
            self._storage_metadata_repository.save_result_handle(result_handle)
        return tuple(result_handles), trace_payload

    def _ensure_dataset_design(
        self,
        session: Session,
        *,
        dataset_id: str,
        design_id: str,
    ) -> None:
        dataset = session.scalar(
            select(RewriteDatasetRecord).where(RewriteDatasetRecord.dataset_id == dataset_id)
        )
        if dataset is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        design = session.scalar(
            select(RewriteDatasetDesignRecord).where(
                RewriteDatasetDesignRecord.dataset_id == dataset_id,
                RewriteDatasetDesignRecord.design_id == design_id,
            )
        )
        if design is None:
            session.add(
                RewriteDatasetDesignRecord(
                    dataset_id=dataset_id,
                    design_id=design_id,
                    normalized_name=design_id.casefold(),
                    name=design_id,
                    lifecycle_state="active",
                    redirect_design_id=None,
                    updated_at=_timestamp_now(),
                )
            )
            dataset.updated_at = _timestamp_now()
            session.flush()

    def _update_task(
        self,
        task: TaskDetail,
        *,
        status: str,
        percent: int,
        summary: str,
    ) -> None:
        self._task_service.update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=task.task_id,
                status=cast(Any, status),
                progress_percent_complete=percent,
                progress_summary=summary,
                progress_updated_at=_timestamp_now(),
            )
        )

    def _resolve_output_target(
        self,
        task: TaskDetail,
        output_target: Mapping[str, object] | None,
    ) -> tuple[str, str]:
        dataset_id = _optional_string(output_target, "dataset_id") if output_target else None
        design_id = _optional_string(output_target, "design_id") if output_target else None
        dataset_id = dataset_id or task.dataset_id
        design_id = design_id or task.definition_id or f"design_task_{task.task_id}"
        if dataset_id is None:
            raise service_error(
                422,
                code="runner_publication_dataset_required",
                category="validation",
                message="Runner publication requires a dataset_id.",
            )
        return dataset_id, design_id

    def _load_manifest(self, manifest_file: Path) -> Mapping[str, object]:
        try:
            payload = json.loads(manifest_file.read_text())
        except json.JSONDecodeError as exc:
            raise service_error(
                422,
                code="runner_manifest_invalid_json",
                category="validation",
                message="Runner manifest is not valid JSON.",
            ) from exc
        if not isinstance(payload, Mapping):
            raise service_error(
                422,
                code="runner_manifest_invalid",
                category="validation",
                message="Runner manifest must be a JSON object.",
            )
        return payload

    def _validate_manifest_identity(
        self,
        manifest: Mapping[str, object],
        *,
        task_id: int,
    ) -> None:
        if manifest.get("schema_version") != "sc.runner.result.v1":
            raise service_error(
                422,
                code="runner_manifest_schema_unsupported",
                category="validation",
                message="Runner manifest schema_version is not supported.",
            )
        if str(manifest.get("task_id")) != str(task_id):
            raise service_error(
                422,
                code="runner_manifest_task_mismatch",
                category="validation",
                message="Runner manifest task_id does not match the task row.",
            )

    def _resolve_zarr_root(self, manifest_file: Path, manifest: Mapping[str, object]) -> Path:
        array_store = manifest.get("array_store")
        if not isinstance(array_store, Mapping):
            raise service_error(
                422,
                code="runner_manifest_array_store_required",
                category="validation",
                message="Runner manifest requires array_store.",
            )
        if array_store.get("format") != "zarr" or int(array_store.get("zarr_format", 0)) != 2:
            raise service_error(
                422,
                code="runner_manifest_array_store_unsupported",
                category="validation",
                message="Runner manifest must declare local Zarr v2 output.",
            )
        uri = str(array_store.get("uri") or "")
        self._reject_unsafe_relative_path(uri, field="array_store.uri")
        zarr_root = (manifest_file.parent / uri).resolve()
        try:
            zarr_root.relative_to(manifest_file.parent.resolve())
        except ValueError as exc:
            raise service_error(
                422,
                code="runner_manifest_zarr_outside_task_dir",
                category="validation",
                message="Runner Zarr output must stay under the staging task directory.",
            ) from exc
        if not zarr_root.is_dir():
            raise service_error(
                404,
                code="runner_zarr_not_found",
                category="not_found",
                message="Runner Zarr output was not found.",
            )
        return zarr_root

    def _validate_zarr_layout(
        self,
        zarr_root: Path,
        manifest: Mapping[str, object],
    ) -> tuple[_TraceManifest, ...]:
        root_group = _read_json(zarr_root / ".zgroup", field="result.zarr/.zgroup")
        if int(root_group.get("zarr_format", 0)) != 2:
            raise service_error(
                422,
                code="runner_zarr_format_invalid",
                category="validation",
                message="Runner result.zarr must be a Zarr v2 group.",
            )
        raw_traces = manifest.get("traces")
        if not isinstance(raw_traces, list) or len(raw_traces) == 0:
            raise service_error(
                422,
                code="runner_manifest_traces_required",
                category="validation",
                message="Runner manifest requires at least one trace.",
            )
        traces: list[_TraceManifest] = []
        for raw_trace in raw_traces:
            trace = self._coerce_trace_manifest(raw_trace)
            self._validate_trace_arrays(zarr_root, trace)
            traces.append(trace)
        return tuple(traces)

    def _coerce_trace_manifest(self, raw_trace: object) -> _TraceManifest:
        if not isinstance(raw_trace, Mapping):
            raise service_error(
                422,
                code="runner_manifest_trace_invalid",
                category="validation",
                message="Each runner trace manifest entry must be an object.",
            )
        axes = raw_trace.get("axes")
        shape = _int_tuple(raw_trace.get("shape"), field="traces[].shape")
        chunk_shape = _int_tuple(raw_trace.get("chunk_shape"), field="traces[].chunk_shape")
        if not isinstance(axes, list) or len(axes) != len(shape):
            raise service_error(
                422,
                code="runner_manifest_axes_invalid",
                category="validation",
                message="Trace axes must match trace rank.",
            )
        return _TraceManifest(
            trace_key=str(raw_trace["trace_key"]),
            family=str(raw_trace.get("family", "s_matrix")),
            parameter=str(raw_trace.get("parameter", raw_trace["trace_key"])),
            representation=str(raw_trace.get("representation", "complex")),
            real_path=str(raw_trace["real_path"]),
            imag_path=str(raw_trace["imag_path"]),
            shape=shape,
            chunk_shape=chunk_shape,
            dtype=str(raw_trace.get("dtype", "float64")),
            axes=tuple(cast(dict[str, object], axis) for axis in axes),
        )

    def _validate_trace_arrays(self, zarr_root: Path, trace: _TraceManifest) -> None:
        for zarr_path in (trace.real_path, trace.imag_path):
            self._validate_array_path(zarr_root, zarr_path, trace=trace)
        for axis_index, axis in enumerate(trace.axes):
            path = str(axis.get("path") or "")
            self._reject_unsafe_zarr_path(path, field="traces[].axes[].path")
            metadata = _read_array_metadata(zarr_root / _zarr_relative_path(path))
            expected_shape = (trace.shape[axis_index],)
            if tuple(int(value) for value in metadata["shape"]) != expected_shape:
                raise service_error(
                    422,
                    code="runner_axis_shape_mismatch",
                    category="validation",
                    message="Runner axis length does not match declared trace shape.",
                    details={"axis": axis.get("name"), "path": path},
                )

    def _validate_array_path(
        self,
        zarr_root: Path,
        zarr_path: str,
        *,
        trace: _TraceManifest,
    ) -> None:
        self._reject_unsafe_zarr_path(zarr_path, field="traces[].array_path")
        metadata = _read_array_metadata(zarr_root / _zarr_relative_path(zarr_path))
        if tuple(int(value) for value in metadata["shape"]) != trace.shape:
            raise service_error(
                422,
                code="runner_trace_shape_mismatch",
                category="validation",
                message="Runner trace array shape does not match manifest.",
                details={"path": zarr_path},
            )
        if tuple(int(value) for value in metadata["chunks"]) != trace.chunk_shape:
            raise service_error(
                422,
                code="runner_trace_chunk_shape_mismatch",
                category="validation",
                message="Runner trace chunk shape does not match manifest.",
                details={"path": zarr_path},
            )
        if _normalize_dtype(str(metadata["dtype"])) != _normalize_dtype(trace.dtype):
            raise service_error(
                422,
                code="runner_trace_dtype_mismatch",
                category="validation",
                message="Runner trace dtype does not match manifest.",
                details={"path": zarr_path},
            )

    def _resolve_relative_path_under(self, value: str, *, root: Path, field: str) -> Path:
        self._reject_unsafe_relative_path(value, field=field)
        path = (_repo_root() / value).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise service_error(
                422,
                code="runner_path_outside_allowed_root",
                category="validation",
                message=f"{field} must stay under {root}.",
            ) from exc
        return path

    def _reject_unsafe_relative_path(self, value: str, *, field: str) -> None:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise service_error(
                422,
                code="runner_path_invalid",
                category="validation",
                message=f"{field} must be a safe relative path.",
            )

    def _reject_unsafe_zarr_path(self, value: str, *, field: str) -> None:
        if not value.startswith("/"):
            raise service_error(
                422,
                code="runner_zarr_path_invalid",
                category="validation",
                message=f"{field} must be an absolute path inside the Zarr root.",
            )
        self._reject_unsafe_relative_path(value.lstrip("/"), field=field)

    def _trace_store_root(self) -> Path:
        return _path_from_setting(self._settings.trace_store_root)

    def _staging_root(self) -> Path:
        return _path_from_setting(self._settings.staging_root)

    def _artifacts_root(self) -> Path:
        return _path_from_setting(self._settings.artifacts_root)


def _published_trace_exists(
    session: Session,
    *,
    dataset_id: str,
    design_id: str,
    trace_id: str,
) -> bool:
    row = session.scalar(
        select(RewritePublishedSimulationTraceRecord.id).where(
            RewritePublishedSimulationTraceRecord.dataset_id == dataset_id,
            RewritePublishedSimulationTraceRecord.design_id == design_id,
            RewritePublishedSimulationTraceRecord.trace_id == trace_id,
        )
    )
    return row is not None


def _axis_rows(trace: _TraceManifest) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for axis, length in zip(trace.axes, trace.shape, strict=True):
        rows.append(
            {
                "name": str(axis.get("name", "")),
                "unit": str(axis.get("unit", "")),
                "length": int(length),
            }
        )
    return rows


def _optional_string(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and len(value) > 0 else None


def _read_array_metadata(array_root: Path) -> Mapping[str, object]:
    return _read_json(array_root / ".zarray", field=str(array_root / ".zarray"))


def _read_json(path: Path, *, field: str) -> Mapping[str, object]:
    if not path.is_file():
        raise service_error(
            422,
            code="runner_zarr_metadata_missing",
            category="validation",
            message=f"Missing Zarr metadata at {field}.",
        )
    payload = json.loads(path.read_text())
    if not isinstance(payload, Mapping):
        raise service_error(
            422,
            code="runner_zarr_metadata_invalid",
            category="validation",
            message=f"Zarr metadata at {field} must be a JSON object.",
        )
    return payload


def _int_tuple(value: object, *, field: str) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) == 0:
        raise service_error(
            422,
            code="runner_manifest_shape_invalid",
            category="validation",
            message=f"{field} must be a non-empty integer array.",
        )
    return tuple(int(item) for item in value)


def _zarr_relative_path(value: str) -> Path:
    return Path(value.lstrip("/"))


def _normalize_dtype(value: str) -> str:
    if value in {"<f8", "|f8", "float64"}:
        return "float64"
    return value


def _path_from_setting(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (_repo_root() / path).resolve()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _timestamp_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
