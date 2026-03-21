"""Design-scope trace workflow summaries for Raw Data and Simulation UI."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from core.shared.persistence.models import TraceBatchRecord
from core.shared.persistence.repositories.contracts import TraceBatchSnapshot

CompareStatus = Literal["ready", "inspect-only", "blocked"]


@dataclass(frozen=True)
class TraceBatchMembershipSummary:
    """One trace-to-batch provenance summary row for UI display."""

    batch_id: int
    source_kind: str
    stage_kind: str
    setup_kind: str | None
    provenance_summary: str


@dataclass(frozen=True)
class DesignSourceSummary:
    """Aggregated source summary under one design scope."""

    source_kind: str
    stage_kinds: tuple[str, ...]
    batch_count: int
    trace_count: int
    latest_batch_id: int
    latest_provenance_summary: str


@dataclass(frozen=True)
class DesignTraceWorkflowSummary:
    """Design-level cross-source workflow state for product-facing UI."""

    design_id: int
    design_name: str
    total_trace_count: int
    provenance_batch_count: int
    source_kind_count: int
    compare_status: CompareStatus
    compare_message: str
    trace_store_read_path: str
    source_summaries: tuple[DesignSourceSummary, ...]
    trace_membership_by_id: dict[int, tuple[TraceBatchMembershipSummary, ...]]


@runtime_checkable
class _TraceBatchSummaryRepository(Protocol):
    def list_provenance_by_design(self, design_id: int) -> list[TraceBatchRecord]: ...

    def get_trace_batch_snapshot(self, id: int) -> TraceBatchSnapshot | None: ...

    def list_data_record_index(self, bundle_id: int) -> list[dict[str, str | int]]: ...


@runtime_checkable
class _TraceSummaryRepository(Protocol):
    def count_by_design(self, design_id: int) -> int: ...


def _resolved_latest_timestamp(batch: TraceBatchRecord) -> datetime:
    completed_at = getattr(batch, "completed_at", None)
    if isinstance(completed_at, datetime):
        return completed_at
    created_at = getattr(batch, "created_at", None)
    if isinstance(created_at, datetime):
        return created_at
    return datetime.min


def _batch_trace_count(
    snapshot: Mapping[str, object] | None,
    trace_rows: list[dict[str, str | int]],
) -> int:
    if trace_rows:
        return len({int(row["id"]) for row in trace_rows if "id" in row})
    if isinstance(snapshot, Mapping):
        summary_payload = snapshot.get("summary_payload")
        if isinstance(summary_payload, Mapping):
            raw_trace_count = summary_payload.get("trace_count")
            if raw_trace_count is not None:
                return int(raw_trace_count)
    return 0


def _provenance_summary(
    *,
    batch_id: int,
    source_kind: str,
    stage_kind: str,
    setup_kind: str | None,
    snapshot: Mapping[str, object] | None,
) -> str:
    tokens = [f"batch #{batch_id}", f"{source_kind}/{stage_kind}"]
    if setup_kind:
        tokens.append(setup_kind)
    if isinstance(snapshot, Mapping):
        raw_parent_batch_id = snapshot.get("parent_batch_id")
        if isinstance(raw_parent_batch_id, int | str):
            tokens.append(f"parent #{int(raw_parent_batch_id)}")
        raw_provenance_payload = snapshot.get("provenance_payload")
        provenance_payload: Mapping[str, object] = (
            raw_provenance_payload if isinstance(raw_provenance_payload, Mapping) else {}
        )
        input_source = str(provenance_payload.get("input_source_type", "")).strip()
        if input_source:
            tokens.append(f"input={input_source}")
        run_kind = str(provenance_payload.get("run_kind", "")).strip()
        if run_kind:
            tokens.append(run_kind)
        raw_summary_payload = snapshot.get("summary_payload")
        summary_payload: Mapping[str, object] = (
            raw_summary_payload if isinstance(raw_summary_payload, Mapping) else {}
        )
        point_count = summary_payload.get("point_count")
        if isinstance(point_count, int | str) and point_count not in ("", 0, 1):
            tokens.append(f"points={int(point_count)}")
    return " | ".join(tokens)


def _compare_status(
    *,
    total_trace_count: int,
    source_kind_count: int,
) -> tuple[CompareStatus, str]:
    if total_trace_count <= 0:
        return (
            "blocked",
            "No persisted traces are available in this Design scope yet.",
        )
    if source_kind_count >= 2:
        return (
            "ready",
            "Multiple trace sources are present. Browse here and use Analyze This Design "
            "for trace-first compare.",
        )
    return (
        "inspect-only",
        "Only one trace source is available in this Design scope. Import or save "
        "another source to compare.",
    )


def summarize_design_trace_workflow(
    *,
    design_id: int,
    design_name: str,
    trace_repo: _TraceSummaryRepository,
    trace_batch_repo: _TraceBatchSummaryRepository,
) -> DesignTraceWorkflowSummary:
    """Build one design-scoped workflow summary from trace-first metadata only."""

    batches = list(trace_batch_repo.list_provenance_by_design(design_id))
    total_trace_count = int(trace_repo.count_by_design(design_id))

    source_accumulator: dict[str, dict[str, Any]] = {}
    trace_membership: dict[int, list[TraceBatchMembershipSummary]] = {}

    for batch in batches:
        if batch.id is None:
            continue
        batch_id = int(batch.id)
        snapshot = trace_batch_repo.get_trace_batch_snapshot(batch_id)
        snapshot_payload = snapshot or {}
        source_kind = str(
            snapshot_payload.get("source_kind")
            or getattr(batch, "source_kind", "")
            or getattr(batch, "bundle_type", "")
            or "unknown"
        ).strip()
        stage_kind = str(
            snapshot_payload.get("stage_kind")
            or getattr(batch, "stage_kind", "")
            or getattr(batch, "role", "")
            or "unknown"
        ).strip()
        setup_kind = snapshot_payload.get("setup_kind")
        resolved_setup_kind = str(setup_kind).strip() if setup_kind else None
        trace_rows = trace_batch_repo.list_data_record_index(batch_id)
        trace_count = _batch_trace_count(snapshot, trace_rows)
        provenance_summary = _provenance_summary(
            batch_id=batch_id,
            source_kind=source_kind,
            stage_kind=stage_kind,
            setup_kind=resolved_setup_kind,
            snapshot=snapshot,
        )
        latest_timestamp = _resolved_latest_timestamp(batch)

        source_bucket = source_accumulator.setdefault(
            source_kind,
            {
                "stage_kinds": set(),
                "batch_count": 0,
                "trace_count": 0,
                "latest_batch_id": batch_id,
                "latest_provenance_summary": provenance_summary,
                "latest_timestamp": latest_timestamp,
            },
        )
        source_bucket["stage_kinds"].add(stage_kind)
        source_bucket["batch_count"] += 1
        source_bucket["trace_count"] += trace_count
        if latest_timestamp >= source_bucket["latest_timestamp"]:
            source_bucket["latest_batch_id"] = batch_id
            source_bucket["latest_provenance_summary"] = provenance_summary
            source_bucket["latest_timestamp"] = latest_timestamp

        membership = TraceBatchMembershipSummary(
            batch_id=batch_id,
            source_kind=source_kind,
            stage_kind=stage_kind,
            setup_kind=resolved_setup_kind,
            provenance_summary=provenance_summary,
        )
        for row in trace_rows:
            trace_id = int(row["id"])
            trace_membership.setdefault(trace_id, []).append(membership)

    compare_status, compare_message = _compare_status(
        total_trace_count=total_trace_count,
        source_kind_count=len(source_accumulator),
    )

    source_summaries = tuple(
        DesignSourceSummary(
            source_kind=source_kind,
            stage_kinds=tuple(sorted(bucket["stage_kinds"])),
            batch_count=int(bucket["batch_count"]),
            trace_count=int(bucket["trace_count"]),
            latest_batch_id=int(bucket["latest_batch_id"]),
            latest_provenance_summary=str(bucket["latest_provenance_summary"]),
        )
        for source_kind, bucket in sorted(source_accumulator.items())
    )
    normalized_membership = {
        trace_id: tuple(
            sorted(
                memberships,
                key=lambda item: (item.batch_id, item.source_kind, item.stage_kind),
            )
        )
        for trace_id, memberships in trace_membership.items()
    }
    return DesignTraceWorkflowSummary(
        design_id=design_id,
        design_name=design_name,
        total_trace_count=total_trace_count,
        provenance_batch_count=len(batches),
        source_kind_count=len(source_accumulator),
        compare_status=compare_status,
        compare_message=compare_message,
        trace_store_read_path=(
            "TraceStore-first read path: visualization fetches one selected trace at a time."
        ),
        source_summaries=source_summaries,
        trace_membership_by_id=normalized_membership,
    )


__all__ = [
    "CompareStatus",
    "DesignSourceSummary",
    "DesignTraceWorkflowSummary",
    "TraceBatchMembershipSummary",
    "summarize_design_trace_workflow",
]
