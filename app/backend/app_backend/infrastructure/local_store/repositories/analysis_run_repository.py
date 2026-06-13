"""Logical AnalysisRun repository backed by characterization TraceBatch rows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from sqlmodel import Session, select

from app_backend.domain.runtime_contracts.storage import AnalysisRunProvenance
from app_backend.infrastructure.local_store.models import (
    AnalysisRunRecord,
    TraceBatchRecord,
    require_explicit_scope_ids,
    resolve_scope_ids_for_compatibility_write,
)
from app_backend.infrastructure.local_store.repositories.contracts import AnalysisRunSummary

_ANALYSIS_BUNDLE_TYPE = "characterization"
_ANALYSIS_ROLE = "analysis_run"
_EXECUTION_CONFIG_KEYS = {
    "input_trace_ids",
    "selected_trace_ids",
    "selected_trace_count",
    "trace_mode_group",
    "selected_trace_mode_group",
}


def _analysis_run_batch_query(
    *,
    design_id: int | None = None,
    dataset_id: int | None = None,
):
    """Build the canonical characterization-analysis-run batch query."""
    statement = (
        select(TraceBatchRecord)
        .where(TraceBatchRecord.bundle_type == _ANALYSIS_BUNDLE_TYPE)
        .where(TraceBatchRecord.role == _ANALYSIS_ROLE)
    )
    if design_id is not None:
        statement = statement.where(TraceBatchRecord.design_id == design_id)
    if dataset_id is not None:
        statement = statement.where(TraceBatchRecord.dataset_id == dataset_id)
    return statement.order_by(TraceBatchRecord.id)  # type: ignore[arg-type]


def is_analysis_run_batch(batch: TraceBatchRecord | None) -> bool:
    """Return whether one TraceBatch row is the physical analysis-run carrier."""
    if batch is None:
        return False
    return batch.bundle_type == _ANALYSIS_BUNDLE_TYPE and batch.role == _ANALYSIS_ROLE


def analysis_run_record_from_batch(batch: TraceBatchRecord) -> AnalysisRunRecord:
    """Project one characterization TraceBatch row into the logical run contract."""
    scope_ids = require_explicit_scope_ids(batch)
    source_meta = dict(batch.source_meta) if isinstance(batch.source_meta, dict) else {}
    config_snapshot = dict(batch.config_snapshot) if isinstance(batch.config_snapshot, dict) else {}
    result_payload = dict(batch.result_payload) if isinstance(batch.result_payload, dict) else {}
    provenance = AnalysisRunProvenance.from_payloads(
        source_meta=source_meta,
        config_snapshot=config_snapshot,
    )

    normalized_config_payload = deepcopy(config_snapshot)
    for key in _EXECUTION_CONFIG_KEYS:
        normalized_config_payload.pop(key, None)

    normalized_summary_payload = deepcopy(result_payload)
    selected_trace_count = config_snapshot.get("selected_trace_count")
    if (
        "selected_trace_count" not in normalized_summary_payload
        and isinstance(selected_trace_count, int | float)
        and not isinstance(selected_trace_count, bool)
    ):
        normalized_summary_payload["selected_trace_count"] = int(selected_trace_count)

    return AnalysisRunRecord(
        id=int(batch.id) if batch.id is not None else None,
        dataset_id=scope_ids.dataset_id,
        design_id=scope_ids.design_id,
        analysis_id=provenance.analysis_id,
        analysis_label=provenance.analysis_label,
        run_id=provenance.run_id,
        status=str(batch.status),
        input_trace_ids=list(provenance.input_trace_ids),
        input_batch_ids=list(provenance.input_batch_ids),
        input_scope=provenance.input_scope,
        trace_mode_group=provenance.trace_mode_group,
        config_payload=normalized_config_payload,
        summary_payload=normalized_summary_payload,
        created_at=batch.created_at,
        completed_at=batch.completed_at,
    )


def analysis_run_batch_from_record(record: AnalysisRunRecord) -> TraceBatchRecord:
    """Materialize one logical analysis run into the existing batch-backed storage row."""
    scope_ids = require_explicit_scope_ids(record)
    provenance = AnalysisRunProvenance(
        analysis_id=record.analysis_id,
        analysis_label=record.analysis_label or record.analysis_id,
        run_id=record.run_id,
        input_scope=record.input_scope,
        input_batch_ids=tuple(int(batch_id) for batch_id in record.input_batch_ids),
        input_trace_ids=tuple(int(trace_id) for trace_id in record.input_trace_ids),
        trace_mode_group=record.trace_mode_group,
    )

    return TraceBatchRecord(
        id=record.id,
        dataset_id=scope_ids.dataset_id,
        design_id=scope_ids.design_id,
        bundle_type=_ANALYSIS_BUNDLE_TYPE,
        role=_ANALYSIS_ROLE,
        status=record.status,
        source_meta=cast(dict[str, Any], provenance.to_source_meta_payload()),
        config_snapshot=deepcopy(record.config_payload),
        result_payload=deepcopy(record.summary_payload),
        created_at=record.created_at,
        completed_at=record.completed_at,
    )


class AnalysisRunRepository:
    """Repository for logical analysis runs persisted via TraceBatchRecord rows."""

    def __init__(self, session: Session):
        self._session = session

    def add(self, analysis_run: AnalysisRunRecord) -> AnalysisRunRecord:
        """Persist one logical analysis run using the batch-backed storage row."""
        resolve_scope_ids_for_compatibility_write(analysis_run)
        batch = analysis_run_batch_from_record(analysis_run)
        self._session.add(batch)
        self._session.flush()
        return analysis_run_record_from_batch(batch)

    def save(self, analysis_run: AnalysisRunRecord) -> AnalysisRunRecord:
        """Insert or update one logical analysis run."""
        if analysis_run.id is None:
            return self.add(analysis_run)

        batch = self._session.get(TraceBatchRecord, int(analysis_run.id))
        if batch is None or not is_analysis_run_batch(batch):
            raise ValueError(f"Analysis run ID {analysis_run.id} not found.")

        updated = analysis_run_batch_from_record(analysis_run)
        batch.dataset_id = updated.dataset_id
        batch.design_id = updated.design_id
        batch.bundle_type = updated.bundle_type
        batch.role = updated.role
        batch.status = updated.status
        batch.source_meta = dict(updated.source_meta)
        batch.config_snapshot = dict(updated.config_snapshot)
        batch.result_payload = dict(updated.result_payload)
        batch.created_at = updated.created_at
        batch.completed_at = updated.completed_at
        self._session.add(batch)
        self._session.flush()
        return analysis_run_record_from_batch(batch)

    def get(self, id: int) -> AnalysisRunRecord | None:
        """Load one logical analysis run by ID."""
        batch = self._session.get(TraceBatchRecord, id)
        if batch is None or not is_analysis_run_batch(batch):
            return None
        return analysis_run_record_from_batch(batch)

    def list_by_design(self, design_id: int) -> list[AnalysisRunRecord]:
        """List all logical analysis runs under one design."""
        batches = self._session.exec(_analysis_run_batch_query(design_id=design_id)).all()
        return [analysis_run_record_from_batch(batch) for batch in batches]

    def list_by_dataset(self, dataset_id: int) -> list[AnalysisRunRecord]:
        """List all logical analysis runs under one dataset authority."""
        batches = self._session.exec(_analysis_run_batch_query(dataset_id=dataset_id)).all()
        return [analysis_run_record_from_batch(batch) for batch in batches]

    def list_summaries_by_design(self, design_id: int) -> list[AnalysisRunSummary]:
        """List primitive analysis-run summaries for design-scoped UI history."""
        runs = self.list_by_design(design_id)
        summaries: list[AnalysisRunSummary] = []
        for run in runs:
            if run.id is None or not run.analysis_id:
                continue
            summaries.append(
                {
                    "analysis_run_id": int(run.id),
                    "dataset_id": int(run.dataset_id),
                    "design_id": int(run.design_id),
                    "analysis_id": str(run.analysis_id),
                    "analysis_label": str(run.analysis_label or run.analysis_id),
                    "status": str(run.status),
                }
            )
        return summaries
