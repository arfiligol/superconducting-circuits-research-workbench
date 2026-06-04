from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app_backend.domain.datasets import (
    TraceAnalysisCapability,
    TraceCapabilityReason,
)
from app_backend.infrastructure.persistence.models import RewriteTraceCapabilityRecord


def replace_trace_capabilities(
    session: Session,
    *,
    dataset_id: str,
    design_id: str,
    trace_id: str,
    capabilities: Sequence[TraceAnalysisCapability],
) -> None:
    session.query(RewriteTraceCapabilityRecord).filter(
        RewriteTraceCapabilityRecord.dataset_id == dataset_id,
        RewriteTraceCapabilityRecord.design_id == design_id,
        RewriteTraceCapabilityRecord.trace_id == trace_id,
    ).delete()
    for capability in capabilities:
        session.add(
            RewriteTraceCapabilityRecord(
                dataset_id=dataset_id,
                design_id=design_id,
                trace_id=trace_id,
                capability_id=capability.capability_id,
                analysis_id=capability.analysis_id,
                analysis_label=capability.analysis_label,
                input_role=capability.input_role,
                input_role_label=capability.input_role_label,
                status=capability.status,
                summary=capability.summary,
                reasons_json=[
                    {
                        "code": reason.code,
                        "message": reason.message,
                        "evidence": dict(reason.evidence),
                    }
                    for reason in capability.reasons
                ],
            )
        )


def delete_trace_capabilities(
    session: Session,
    *,
    dataset_id: str,
    design_id: str,
    trace_ids: Sequence[str],
) -> None:
    if len(trace_ids) == 0:
        return
    session.query(RewriteTraceCapabilityRecord).filter(
        RewriteTraceCapabilityRecord.dataset_id == dataset_id,
        RewriteTraceCapabilityRecord.design_id == design_id,
        RewriteTraceCapabilityRecord.trace_id.in_(tuple(trace_ids)),
    ).delete(synchronize_session=False)


def load_trace_capability_map(
    session: Session,
    *,
    dataset_id: str,
    design_id: str,
    trace_ids: Sequence[str] | None = None,
) -> dict[str, tuple[TraceAnalysisCapability, ...]]:
    query = select(RewriteTraceCapabilityRecord).where(
        RewriteTraceCapabilityRecord.dataset_id == dataset_id,
        RewriteTraceCapabilityRecord.design_id == design_id,
    )
    if trace_ids is not None:
        if len(trace_ids) == 0:
            return {}
        query = query.where(RewriteTraceCapabilityRecord.trace_id.in_(tuple(trace_ids)))
    rows = session.scalars(
        query.order_by(
            RewriteTraceCapabilityRecord.trace_id.asc(),
            RewriteTraceCapabilityRecord.analysis_id.asc(),
            RewriteTraceCapabilityRecord.input_role.asc(),
        )
    ).all()
    capabilities: dict[str, list[TraceAnalysisCapability]] = {}
    for row in rows:
        capabilities.setdefault(row.trace_id, []).append(_to_trace_capability(row))
    return {trace_id: tuple(items) for trace_id, items in capabilities.items()}


def trace_capabilities_equal(
    left: Sequence[TraceAnalysisCapability],
    right: Sequence[TraceAnalysisCapability],
) -> bool:
    return len(left) == len(right) and all(
        _trace_capability_equal(left_item, right_item)
        for left_item, right_item in zip(left, right, strict=False)
    )


def _to_trace_capability(row: RewriteTraceCapabilityRecord) -> TraceAnalysisCapability:
    return TraceAnalysisCapability(
        capability_id=row.capability_id,
        analysis_id=row.analysis_id,
        analysis_label=row.analysis_label,
        input_role=row.input_role,
        input_role_label=row.input_role_label,
        status=row.status,
        summary=row.summary,
        reasons=tuple(
            TraceCapabilityReason(
                code=str(item.get("code", "")),
                message=str(item.get("message", "")),
                evidence=(dict(item["evidence"]) if isinstance(item.get("evidence"), dict) else {}),
            )
            for item in row.reasons_json
            if isinstance(item, dict)
        ),
    )


def _trace_capability_equal(
    left: TraceAnalysisCapability,
    right: TraceAnalysisCapability,
) -> bool:
    return (
        left.capability_id == right.capability_id
        and left.analysis_id == right.analysis_id
        and left.analysis_label == right.analysis_label
        and left.input_role == right.input_role
        and left.input_role_label == right.input_role_label
        and left.status == right.status
        and left.summary == right.summary
        and len(left.reasons) == len(right.reasons)
        and all(
            _trace_capability_reason_equal(left_reason, right_reason)
            for left_reason, right_reason in zip(
                left.reasons,
                right.reasons,
                strict=False,
            )
        )
    )


def _trace_capability_reason_equal(
    left: TraceCapabilityReason,
    right: TraceCapabilityReason,
) -> bool:
    return (
        left.code == right.code
        and left.message == right.message
        and left.evidence == right.evidence
    )
