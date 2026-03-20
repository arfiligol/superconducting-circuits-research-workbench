"""Service for saving trace-first dataset payloads to persistent storage."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from sc_core.storage import DATASET_IMPORT_TRACE_WRITER_VERSION

from core.analysis.application.preprocessing.dataset_payload import DataPayload, DatasetPayload
from core.shared.logging import get_logger
from core.shared.persistence import (
    DataRecord,
    DatasetRecord,
    LocalZarrTraceStore,
    ResultBundleRecord,
    TraceStore,
    get_unit_of_work,
)

logger = get_logger(__name__)


def _trace_axes(payload: DataPayload) -> list[dict[str, object]]:
    return [
        {
            "name": axis.name,
            "unit": axis.unit,
            "values": list(axis.values),
        }
        for axis in payload.axes
    ]


def _trace_record(payload: DataPayload) -> DataRecord:
    return DataRecord(
        dataset_id=0,  # Bound after the DesignRecord is allocated.
        data_type=payload.data_type,
        parameter=payload.parameter,
        representation=payload.representation,
        axes=[
            {
                "name": axis.name,
                "unit": axis.unit,
                "length": len(axis.values),
            }
            for axis in payload.axes
        ],
        values=[],
    )


def _source_kind(source_meta: dict[str, Any]) -> str:
    token = str(
        source_meta.get("source_kind")
        or source_meta.get("origin")
        or source_meta.get("source")
        or "imported"
    ).strip()
    return token or "imported"


def _stage_kind(source_meta: dict[str, Any]) -> str:
    token = str(source_meta.get("stage_kind") or source_meta.get("role") or "raw").strip()
    return token or "raw"


def _trace_shape(payload: DataPayload) -> tuple[int, ...]:
    values = np.asarray(payload.values)
    if values.ndim == 0:
        raise ValueError("Trace payload must be at least 1D.")
    expected_shape = tuple(len(axis.values) for axis in payload.axes)
    if values.shape != expected_shape:
        raise ValueError(
            "Trace payload shape does not match axis definitions: "
            f"values={values.shape}, axes={expected_shape}."
        )
    return expected_shape


def _remove_replaced_traces(
    *,
    dataset_record: DatasetRecord,
    uow: Any,
    replacements: Sequence[DataPayload],
) -> None:
    stale_batch_ids: set[int] = set()
    replacements_by_identity = {
        (payload.data_type, payload.parameter, payload.representation) for payload in replacements
    }
    for record in list(dataset_record.data_records):
        identity = (record.data_type, record.parameter, record.representation)
        if identity not in replacements_by_identity or record.id is None:
            continue
        stale_batch_ids.update(
            int(batch.id) for batch in record.result_bundles if batch.id is not None
        )
        uow.result_bundles.detach_trace(int(record.id))
        uow.data_records.delete(record)
    uow.flush()
    for batch_id in stale_batch_ids:
        if uow.result_bundles.count_traces(batch_id) != 0:
            continue
        empty_batch = uow.result_bundles.get(batch_id)
        if empty_batch is not None:
            uow.result_bundles.delete(empty_batch)


def _trace_batch_record(
    *,
    dataset_id: int,
    source_meta: dict[str, Any],
    raw_files: list[str],
    trace_count: int,
) -> ResultBundleRecord:
    source_kind = _source_kind(source_meta)
    stage_kind = _stage_kind(source_meta)
    provenance_payload = dict(source_meta)
    if raw_files:
        provenance_payload["raw_files"] = list(raw_files)
    return ResultBundleRecord(
        dataset_id=dataset_id,
        bundle_type=source_kind,
        role=stage_kind,
        status="completed",
        source_meta=provenance_payload,
        config_snapshot={"setup_kind": f"{source_kind}.{stage_kind}"},
        result_payload={"trace_count": trace_count},
    )


def save_dataset_payload_to_db(
    payload: DatasetPayload,
    dataset_name: str,
    tags: list[str] | None = None,
    trace_store: TraceStore | None = None,
) -> DatasetRecord:
    """
    Save a dataset payload to SQLite database.

    Args:
        payload: DatasetPayload from preprocessing
        dataset_name: Unique name for the dataset (e.g., "PF6FQ_Q0_XY_Y11")
        tags: Optional list of tags to attach

    Returns:
        The created DatasetRecord
    """
    with get_unit_of_work() as uow:
        existing = uow.datasets.get_by_name(dataset_name)
        store = trace_store or LocalZarrTraceStore()

        source_meta: dict = dict(payload.source_meta)
        if payload.raw_files:
            source_meta["raw_files"] = list(payload.raw_files)

        if existing:
            logger.info("Dataset '%s' already exists, appending data...", dataset_name)
            dataset_record = existing

            # Optionally update source meta and parameters if needed
            # dataset_record.source_meta.update(source_meta)

            # Add new tags if any
            if tags:
                for tag_name in tags:
                    tag = uow.tags.get_or_create(tag_name)
                    if tag not in dataset_record.tags:
                        dataset_record.tags.append(tag)
        else:
            # Create DatasetRecord
            dataset_record = DatasetRecord(
                name=dataset_name,
                source_meta=source_meta,
                parameters=dict(payload.parameters),
            )
            if tags:
                for tag_name in tags:
                    tag = uow.tags.get_or_create(tag_name)
                    dataset_record.tags.append(tag)
            uow.datasets.add(dataset_record)
            uow.flush()

        if dataset_record.id is None:
            raise ValueError("Failed to allocate dataset id.")

        _remove_replaced_traces(
            dataset_record=dataset_record,
            uow=uow,
            replacements=payload.data_records,
        )

        batch_record = _trace_batch_record(
            dataset_id=int(dataset_record.id),
            source_meta=source_meta,
            raw_files=list(payload.raw_files),
            trace_count=len(payload.data_records),
        )
        uow.result_bundles.add(batch_record)
        uow.flush()

        if batch_record.id is None:
            raise ValueError("Failed to allocate trace batch id.")

        for payload_ds in payload.data_records:
            _trace_shape(payload_ds)
            data_rec = _trace_record(payload_ds)
            data_rec.dataset_id = int(dataset_record.id)
            uow.data_records.add(data_rec)
            uow.flush()
            if data_rec.id is None:
                raise ValueError("Failed to allocate trace id.")

            write_result = store.write_trace(
                design_id=int(dataset_record.id),
                batch_id=int(batch_record.id),
                trace_id=int(data_rec.id),
                values=payload_ds.values,
                axes=_trace_axes(payload_ds),
                payload_role="raw",
                writer_version=DATASET_IMPORT_TRACE_WRITER_VERSION,
            )
            data_rec.axes = list(write_result.axes)
            data_rec.store_ref = dict(write_result.store_ref)
            uow.result_bundles.attach_traces(
                batch_id=int(batch_record.id),
                trace_ids=[int(data_rec.id)],
            )

        uow.commit()
        dataset_snapshot = DatasetRecord(
            id=int(dataset_record.id),
            name=str(dataset_record.name),
            source_meta=dict(dataset_record.source_meta),
            parameters=dict(dataset_record.parameters),
            created_at=dataset_record.created_at,
        )
        logger.info("Saved to database: %s", dataset_name)
        return dataset_snapshot
