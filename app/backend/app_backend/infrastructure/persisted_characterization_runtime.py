from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import lru_cache
from hashlib import sha256
from typing import Any

from app_backend.domain.admittance_result_contract import (
    AdmittanceResultSurface,
    parse_admittance_surface,
    query_admittance_artifact_payload,
    serialize_admittance_surface,
)
from app_backend.domain.datasets import (
    CharacterizationAppliedTag,
    CharacterizationArtifactAxisSpec,
    CharacterizationArtifactMetricSpec,
    CharacterizationArtifactPayload,
    CharacterizationArtifactPayloadQuery,
    CharacterizationArtifactPreset,
    CharacterizationArtifactQuerySpec,
    CharacterizationArtifactRef,
    CharacterizationArtifactViewModeDefault,
    CharacterizationDesignatedMetricOption,
    CharacterizationDiagnostic,
    CharacterizationIdentifySurface,
    CharacterizationInputResultRef,
    CharacterizationResultDetail,
    CharacterizationResultSummary,
    CharacterizationRunHistoryRow,
    CharacterizationSourceParameterOption,
    TaggedCoreMetricSummary,
)
from app_backend.infrastructure.persistence.storage_metadata_repository import (
    SqliteRewriteStorageMetadataRepository,
)


class PersistedCharacterizationRepository:
    def __init__(
        self,
        storage_metadata_repository: SqliteRewriteStorageMetadataRepository,
    ) -> None:
        self._storage_metadata_repository = storage_metadata_repository

    def list_result_summaries(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationResultSummary, ...]:
        rows = [
            summary
            for run in self._list_runs_for_design(dataset_id, design_id)
            if (summary := _summary_from_run(run)) is not None
        ]
        rows.sort(key=lambda row: row.updated_at, reverse=True)
        return tuple(rows)

    def list_run_history(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationRunHistoryRow, ...]:
        rows = [
            row
            for run in self._list_runs_for_design(dataset_id, design_id)
            if (row := _run_history_from_run(run)) is not None
        ]
        rows.sort(key=lambda row: row.updated_at, reverse=True)
        return tuple(rows)

    def get_result_detail(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
    ) -> CharacterizationResultDetail | None:
        run = self._find_run(dataset_id, design_id, result_id)
        if run is None:
            return None
        return _detail_from_run(run)

    def get_artifact_payload(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        artifact_id: str,
        query: CharacterizationArtifactPayloadQuery,
    ) -> CharacterizationArtifactPayload | None:
        run = self._find_run(dataset_id, design_id, result_id)
        if run is None:
            return None
        surface = parse_admittance_surface(run.summary_payload.get("admittance_surface"))
        if surface is None:
            return None
        return query_admittance_artifact_payload(
            surface=surface,
            artifact_id=artifact_id,
            query=query,
        )

    def list_tagged_core_metrics(
        self,
        dataset_id: str,
    ) -> tuple[TaggedCoreMetricSummary, ...]:
        metrics_by_pair: dict[tuple[str, str], TaggedCoreMetricSummary] = {}
        for run in self._list_runs_for_dataset(dataset_id):
            detail = _detail_from_run(run)
            if detail is None:
                continue
            for applied_tag in detail.identify_surface.applied_tags:
                key = (applied_tag.source_parameter, applied_tag.designated_metric)
                metrics_by_pair[key] = TaggedCoreMetricSummary(
                    metric_id=_build_tagged_metric_id(dataset_id, applied_tag.designated_metric),
                    label=applied_tag.designated_metric_label,
                    source_parameter=applied_tag.source_parameter,
                    designated_metric=applied_tag.designated_metric,
                    tagged_at=applied_tag.tagged_at,
                )
        metrics = list(metrics_by_pair.values())
        metrics.sort(key=lambda metric: metric.tagged_at, reverse=True)
        return tuple(metrics)

    def apply_tagging(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        *,
        artifact_id: str,
        source_parameter: str,
        designated_metric: str,
    ) -> CharacterizationTaggingResultPayload | None:
        run = self._find_run(dataset_id, design_id, result_id)
        if run is None:
            return None
        detail = _detail_from_run(run)
        if detail is None:
            return None

        metric_option = next(
            (
                option
                for option in detail.identify_surface.designated_metrics
                if option.metric_key == designated_metric
            ),
            None,
        )
        if metric_option is None:
            raise ValueError("Designated metric is not available for this result.")

        tagged_at = _utc_timestamp(datetime.now(UTC))
        tagged_metric = TaggedCoreMetricSummary(
            metric_id=_build_tagged_metric_id(dataset_id, designated_metric),
            label=metric_option.label,
            source_parameter=source_parameter,
            designated_metric=designated_metric,
            tagged_at=tagged_at,
        )
        updated_detail = _detail_with_applied_tag(
            detail,
            artifact_id=artifact_id,
            source_parameter=source_parameter,
            metric_option=metric_option,
            tagged_at=tagged_at,
        )
        updated_payload = copy.deepcopy(run.summary_payload)
        updated_payload["result_detail"] = _detail_to_payload(updated_detail)
        run.summary_payload = updated_payload
        _save_analysis_run(run)
        return CharacterizationTaggingResultPayload(
            dataset_id=dataset_id,
            design_id=design_id,
            result_id=result_id,
            artifact_id=artifact_id,
            source_parameter=source_parameter,
            designated_metric=designated_metric,
            tagged_metric=tagged_metric,
        )

    def upsert_seed_result(
        self,
        *,
        summary: CharacterizationResultSummary,
        run_history: CharacterizationRunHistoryRow,
        detail: CharacterizationResultDetail,
        artifact_surface: AdmittanceResultSurface | None = None,
    ) -> None:
        existing = self._find_run(summary.dataset_id, summary.design_id, summary.result_id)
        payload = {
            "result_id": summary.result_id,
            "result_summary": _summary_to_payload(summary),
            "run_history_row": _run_history_to_payload(run_history),
            "result_detail": _detail_to_payload(detail),
        }
        if artifact_surface is not None:
            payload["admittance_surface"] = serialize_admittance_surface(artifact_surface)
        if existing is not None:
            existing.summary_payload = payload
            _save_analysis_run(existing)
            return

        updated_at = datetime.fromisoformat(summary.updated_at.replace("Z", "+00:00"))
        analysis_run_record = _core_symbols()["AnalysisRunRecord"](
            dataset_id=_stable_positive_int(summary.dataset_id),
            design_id=_stable_positive_int(summary.dataset_id, summary.design_id),
            analysis_id=summary.analysis_id,
            analysis_label=summary.title,
            run_id=run_history.run_id,
            status=summary.status,
            input_trace_ids=[
                _stable_positive_int(summary.dataset_id, summary.design_id, trace_id)
                for trace_id in detail.input_trace_ids
            ],
            input_batch_ids=[],
            input_scope="seeded_catalog",
            trace_mode_group="base",
            config_payload={},
            summary_payload=payload,
            created_at=updated_at,
            completed_at=updated_at,
        )
        with _core_symbols()["get_unit_of_work"]() as uow:
            uow.result_bundles.analysis_runs.add(analysis_run_record)
            uow.commit()

    def _find_run(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
    ) -> Any | None:
        for run in self._list_runs_for_design(dataset_id, design_id):
            persisted_result_id = run.summary_payload.get("result_id")
            if isinstance(persisted_result_id, str) and persisted_result_id == result_id:
                return run
            summary = run.summary_payload.get("result_summary")
            if isinstance(summary, Mapping) and summary.get("result_id") == result_id:
                return run
        return None

    def _list_runs_for_design(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[Any, ...]:
        design_scope_id = _stable_positive_int(dataset_id, design_id)
        with _core_symbols()["get_unit_of_work"]() as uow:
            runs = uow.result_bundles.analysis_runs.list_by_design(design_scope_id)
        return tuple(
            run
            for run in runs
            if _matches_dataset_scope(run.summary_payload, dataset_id, design_id)
        )

    def _list_runs_for_dataset(
        self,
        dataset_id: str,
    ) -> tuple[Any, ...]:
        dataset_scope_id = _stable_positive_int(dataset_id)
        with _core_symbols()["get_unit_of_work"]() as uow:
            runs = uow.result_bundles.analysis_runs.list_by_dataset(dataset_scope_id)
        return tuple(
            run for run in runs if _matches_dataset_scope(run.summary_payload, dataset_id, None)
        )


@dataclass(frozen=True)
class CharacterizationTaggingResultPayload:
    dataset_id: str
    design_id: str
    result_id: str
    artifact_id: str
    source_parameter: str
    designated_metric: str
    tagged_metric: TaggedCoreMetricSummary


@lru_cache(maxsize=1)
def _core_symbols() -> dict[str, Any]:
    from core.shared.persistence import get_unit_of_work
    from core.shared.persistence.models import AnalysisRunRecord

    return {
        "AnalysisRunRecord": AnalysisRunRecord,
        "get_unit_of_work": get_unit_of_work,
    }


def _save_analysis_run(run: Any) -> None:
    with _core_symbols()["get_unit_of_work"]() as uow:
        uow.result_bundles.analysis_runs.save(run)
        uow.commit()


def _summary_from_run(run: Any) -> CharacterizationResultSummary | None:
    payload = run.summary_payload.get("result_summary")
    if not isinstance(payload, Mapping):
        return None
    return CharacterizationResultSummary(
        result_id=str(payload["result_id"]),
        dataset_id=str(payload["dataset_id"]),
        design_id=str(payload["design_id"]),
        analysis_id=str(payload["analysis_id"]),
        title=str(payload["title"]),
        status=str(payload["status"]),
        freshness_summary=str(payload["freshness_summary"]),
        provenance_summary=str(payload["provenance_summary"]),
        trace_count=int(payload["trace_count"]),
        artifact_count=int(payload["artifact_count"]),
        updated_at=str(payload["updated_at"]),
    )


def _run_history_from_run(run: Any) -> CharacterizationRunHistoryRow | None:
    payload = run.summary_payload.get("run_history_row")
    if not isinstance(payload, Mapping):
        return None
    result_id = payload.get("result_id")
    return CharacterizationRunHistoryRow(
        run_id=str(payload["run_id"]),
        dataset_id=str(payload["dataset_id"]),
        design_id=str(payload["design_id"]),
        analysis_id=str(payload["analysis_id"]),
        label=str(payload["label"]),
        status=str(payload["status"]),
        scope=str(payload["scope"]),
        trace_count=int(payload["trace_count"]),
        sources_summary=str(payload["sources_summary"]),
        provenance_summary=str(payload["provenance_summary"]),
        updated_at=str(payload["updated_at"]),
        result_id=str(result_id) if isinstance(result_id, str) else None,
        input_result_refs=tuple(
            CharacterizationInputResultRef(
                analysis_id=str(item.get("analysis_id", "")),
                result_id=str(item.get("result_id", "")),
                run_id=str(item.get("run_id")) if isinstance(item.get("run_id"), str) else None,
                artifact_id=(
                    str(item.get("artifact_id"))
                    if isinstance(item.get("artifact_id"), str)
                    else None
                ),
                contract_version=(
                    str(item.get("contract_version"))
                    if isinstance(item.get("contract_version"), str)
                    else None
                ),
                title=str(item.get("title")) if isinstance(item.get("title"), str) else None,
            )
            for item in payload.get("input_result_refs", ())
            if isinstance(item, Mapping)
        ),
    )


def _detail_from_run(run: Any) -> CharacterizationResultDetail | None:
    payload = run.summary_payload.get("result_detail")
    if not isinstance(payload, Mapping):
        return None
    diagnostics = payload.get("diagnostics", ())
    artifact_refs = payload.get("artifact_refs", ())
    identify_surface = payload.get("identify_surface", {})
    source_parameters = identify_surface.get("source_parameters", [])
    designated_metrics = identify_surface.get("designated_metrics", [])
    applied_tags = identify_surface.get("applied_tags", [])
    input_trace_ids = payload.get("input_trace_ids", ())
    input_result_refs = payload.get("input_result_refs", ())
    downstream_unlock_analysis_ids = payload.get("downstream_unlock_analysis_ids", ())
    return CharacterizationResultDetail(
        result_id=str(payload["result_id"]),
        dataset_id=str(payload["dataset_id"]),
        design_id=str(payload["design_id"]),
        analysis_id=str(payload["analysis_id"]),
        title=str(payload["title"]),
        status=str(payload["status"]),
        freshness_summary=str(payload["freshness_summary"]),
        provenance_summary=str(payload["provenance_summary"]),
        trace_count=int(payload["trace_count"]),
        updated_at=str(payload["updated_at"]),
        input_trace_ids=tuple(
            str(trace_id) for trace_id in input_trace_ids if isinstance(trace_id, str)
        ),
        input_result_refs=tuple(
            CharacterizationInputResultRef(
                analysis_id=str(item.get("analysis_id", "")),
                result_id=str(item.get("result_id", "")),
                run_id=str(item.get("run_id")) if isinstance(item.get("run_id"), str) else None,
                artifact_id=(
                    str(item.get("artifact_id"))
                    if isinstance(item.get("artifact_id"), str)
                    else None
                ),
                contract_version=(
                    str(item.get("contract_version"))
                    if isinstance(item.get("contract_version"), str)
                    else None
                ),
                title=str(item.get("title")) if isinstance(item.get("title"), str) else None,
            )
            for item in input_result_refs
            if isinstance(item, Mapping)
        ),
        payload=dict(payload.get("payload", {})),
        diagnostics=tuple(
            CharacterizationDiagnostic(
                severity=str(item["severity"]),
                code=str(item["code"]),
                message=str(item["message"]),
                blocking=bool(item["blocking"]),
            )
            for item in diagnostics
            if isinstance(item, Mapping)
        ),
        artifact_refs=tuple(
            CharacterizationArtifactRef(
                artifact_id=str(item["artifact_id"]),
                category=str(item["category"]),
                view_kind=str(item["view_kind"]),
                title=str(item["title"]),
                payload_format=str(item["payload_format"]),
                payload_locator=(
                    str(item["payload_locator"])
                    if isinstance(item.get("payload_locator"), str)
                    else None
                ),
                axes=tuple(
                    CharacterizationArtifactAxisSpec(
                        axis_key=str(axis["axis_key"]),
                        label=str(axis["label"]),
                        role=str(axis["role"]),
                        unit=str(axis["unit"]) if isinstance(axis.get("unit"), str) else None,
                        length=int(axis["length"]),
                    )
                    for axis in item.get("axes", ())
                    if isinstance(axis, Mapping)
                ),
                metric=(
                    CharacterizationArtifactMetricSpec(
                        metric_key=str(item["metric"]["metric_key"]),
                        label=str(item["metric"]["label"]),
                        unit=(
                            str(item["metric"]["unit"])
                            if isinstance(item["metric"].get("unit"), str)
                            else None
                        ),
                    )
                    if isinstance(item.get("metric"), Mapping)
                    else None
                ),
                presets=tuple(
                    CharacterizationArtifactPreset(
                        preset_id=str(preset["preset_id"]),
                        label=str(preset["label"]),
                        view_kind=str(preset["view_kind"]),
                        rows_axis=(
                            str(preset["rows_axis"])
                            if isinstance(preset.get("rows_axis"), str)
                            else None
                        ),
                        columns_axis=(
                            str(preset["columns_axis"])
                            if isinstance(preset.get("columns_axis"), str)
                            else None
                        ),
                        cell_metric=(
                            str(preset["cell_metric"])
                            if isinstance(preset.get("cell_metric"), str)
                            else None
                        ),
                        x_axis=(
                            str(preset["x_axis"]) if isinstance(preset.get("x_axis"), str) else None
                        ),
                        y_metric=(
                            str(preset["y_metric"])
                            if isinstance(preset.get("y_metric"), str)
                            else None
                        ),
                        series_axis=(
                            str(preset["series_axis"])
                            if isinstance(preset.get("series_axis"), str)
                            else None
                        ),
                        compare_axis=(
                            str(preset["compare_axis"])
                            if isinstance(preset.get("compare_axis"), str)
                            else None
                        ),
                    )
                    for preset in item.get("presets", ())
                    if isinstance(preset, Mapping)
                ),
                default_preset_id=(
                    str(item["default_preset_id"])
                    if isinstance(item.get("default_preset_id"), str)
                    else None
                ),
                query_spec=(
                    CharacterizationArtifactQuerySpec(
                        query_style=str(item["query_spec"]["query_style"]),
                        supported_query_fields=tuple(
                            str(field)
                            for field in item["query_spec"].get("supported_query_fields", ())
                            if isinstance(field, str)
                        ),
                        supported_view_modes=tuple(
                            str(mode)
                            for mode in item["query_spec"].get("supported_view_modes", ())
                            if isinstance(mode, str)
                        ),
                        supported_preset_ids=tuple(
                            str(preset_id)
                            for preset_id in item["query_spec"].get("supported_preset_ids", ())
                            if isinstance(preset_id, str)
                        ),
                        default_preset_id=(
                            str(item["query_spec"]["default_preset_id"])
                            if isinstance(item["query_spec"].get("default_preset_id"), str)
                            else None
                        ),
                        default_presets_by_view_mode=tuple(
                            CharacterizationArtifactViewModeDefault(
                                view_mode=str(default_item["view_mode"]),
                                preset_id=str(default_item["preset_id"]),
                            )
                            for default_item in item["query_spec"].get(
                                "default_presets_by_view_mode",
                                (),
                            )
                            if isinstance(default_item, Mapping)
                        ),
                    )
                    if isinstance(item.get("query_spec"), Mapping)
                    else None
                ),
                identify_source=bool(item.get("identify_source", False)),
            )
            for item in artifact_refs
            if isinstance(item, Mapping)
        ),
        identify_surface=CharacterizationIdentifySurface(
            source_parameters=tuple(
                CharacterizationSourceParameterOption(
                    artifact_id=str(item["artifact_id"]),
                    source_parameter=str(item["source_parameter"]),
                    label=str(item["label"]),
                    artifact_title=str(item["artifact_title"]),
                    current_designated_metric=(
                        str(item["current_designated_metric"])
                        if isinstance(item.get("current_designated_metric"), str)
                        else None
                    ),
                )
                for item in source_parameters
                if isinstance(item, Mapping)
            ),
            designated_metrics=tuple(
                CharacterizationDesignatedMetricOption(
                    metric_key=str(item["metric_key"]),
                    label=str(item["label"]),
                )
                for item in designated_metrics
                if isinstance(item, Mapping)
            ),
            applied_tags=tuple(
                CharacterizationAppliedTag(
                    artifact_id=str(item["artifact_id"]),
                    source_parameter=str(item["source_parameter"]),
                    designated_metric=str(item["designated_metric"]),
                    designated_metric_label=str(item["designated_metric_label"]),
                    tagged_at=str(item["tagged_at"]),
                )
                for item in applied_tags
                if isinstance(item, Mapping)
            ),
        ),
        downstream_unlock_analysis_ids=tuple(
            str(analysis_id)
            for analysis_id in downstream_unlock_analysis_ids
            if isinstance(analysis_id, str)
        ),
    )


def _detail_with_applied_tag(
    detail: CharacterizationResultDetail,
    *,
    artifact_id: str,
    source_parameter: str,
    metric_option: CharacterizationDesignatedMetricOption,
    tagged_at: str,
) -> CharacterizationResultDetail:
    updated_source_parameters = tuple(
        replace(
            option,
            current_designated_metric=metric_option.metric_key,
        )
        if option.artifact_id == artifact_id and option.source_parameter == source_parameter
        else option
        for option in detail.identify_surface.source_parameters
    )
    updated_tags = (
        *(
            tag
            for tag in detail.identify_surface.applied_tags
            if not (tag.artifact_id == artifact_id and tag.source_parameter == source_parameter)
        ),
        CharacterizationAppliedTag(
            artifact_id=artifact_id,
            source_parameter=source_parameter,
            designated_metric=metric_option.metric_key,
            designated_metric_label=metric_option.label,
            tagged_at=tagged_at,
        ),
    )
    return replace(
        detail,
        identify_surface=replace(
            detail.identify_surface,
            source_parameters=updated_source_parameters,
            applied_tags=updated_tags,
        ),
    )


def _summary_to_payload(summary: CharacterizationResultSummary) -> dict[str, object]:
    return {
        "result_id": summary.result_id,
        "dataset_id": summary.dataset_id,
        "design_id": summary.design_id,
        "analysis_id": summary.analysis_id,
        "title": summary.title,
        "status": summary.status,
        "freshness_summary": summary.freshness_summary,
        "provenance_summary": summary.provenance_summary,
        "trace_count": summary.trace_count,
        "artifact_count": summary.artifact_count,
        "updated_at": summary.updated_at,
    }


def _run_history_to_payload(row: CharacterizationRunHistoryRow) -> dict[str, object]:
    return {
        "run_id": row.run_id,
        "dataset_id": row.dataset_id,
        "design_id": row.design_id,
        "analysis_id": row.analysis_id,
        "label": row.label,
        "status": row.status,
        "scope": row.scope,
        "trace_count": row.trace_count,
        "sources_summary": row.sources_summary,
        "provenance_summary": row.provenance_summary,
        "updated_at": row.updated_at,
        "result_id": row.result_id,
        "input_result_refs": [
            {
                "analysis_id": ref.analysis_id,
                "result_id": ref.result_id,
                "run_id": ref.run_id,
                "artifact_id": ref.artifact_id,
                "contract_version": ref.contract_version,
                "title": ref.title,
            }
            for ref in row.input_result_refs
        ],
    }


def _detail_to_payload(detail: CharacterizationResultDetail) -> dict[str, object]:
    return {
        "result_id": detail.result_id,
        "dataset_id": detail.dataset_id,
        "design_id": detail.design_id,
        "analysis_id": detail.analysis_id,
        "title": detail.title,
        "status": detail.status,
        "freshness_summary": detail.freshness_summary,
        "provenance_summary": detail.provenance_summary,
        "trace_count": detail.trace_count,
        "updated_at": detail.updated_at,
        "input_trace_ids": list(detail.input_trace_ids),
        "input_result_refs": [
            {
                "analysis_id": ref.analysis_id,
                "result_id": ref.result_id,
                "run_id": ref.run_id,
                "artifact_id": ref.artifact_id,
                "contract_version": ref.contract_version,
                "title": ref.title,
            }
            for ref in detail.input_result_refs
        ],
        "payload": dict(detail.payload),
        "diagnostics": [
            {
                "severity": diagnostic.severity,
                "code": diagnostic.code,
                "message": diagnostic.message,
                "blocking": diagnostic.blocking,
            }
            for diagnostic in detail.diagnostics
        ],
        "artifact_refs": [
            {
                "artifact_id": artifact.artifact_id,
                "category": artifact.category,
                "view_kind": artifact.view_kind,
                "title": artifact.title,
                "payload_format": artifact.payload_format,
                "payload_locator": artifact.payload_locator,
                "axes": [
                    {
                        "axis_key": axis.axis_key,
                        "label": axis.label,
                        "role": axis.role,
                        "unit": axis.unit,
                        "length": axis.length,
                    }
                    for axis in artifact.axes
                ],
                "metric": (
                    {
                        "metric_key": artifact.metric.metric_key,
                        "label": artifact.metric.label,
                        "unit": artifact.metric.unit,
                    }
                    if artifact.metric is not None
                    else None
                ),
                "presets": [
                    {
                        "preset_id": preset.preset_id,
                        "label": preset.label,
                        "view_kind": preset.view_kind,
                        "rows_axis": preset.rows_axis,
                        "columns_axis": preset.columns_axis,
                        "cell_metric": preset.cell_metric,
                        "x_axis": preset.x_axis,
                        "y_metric": preset.y_metric,
                        "series_axis": preset.series_axis,
                        "compare_axis": preset.compare_axis,
                    }
                    for preset in artifact.presets
                ],
                "default_preset_id": artifact.default_preset_id,
                "query_spec": (
                    {
                        "query_style": artifact.query_spec.query_style,
                        "supported_query_fields": list(artifact.query_spec.supported_query_fields),
                        "supported_view_modes": list(artifact.query_spec.supported_view_modes),
                        "supported_preset_ids": list(artifact.query_spec.supported_preset_ids),
                        "default_preset_id": artifact.query_spec.default_preset_id,
                        "default_presets_by_view_mode": [
                            {
                                "view_mode": default_item.view_mode,
                                "preset_id": default_item.preset_id,
                            }
                            for default_item in artifact.query_spec.default_presets_by_view_mode
                        ],
                    }
                    if artifact.query_spec is not None
                    else None
                ),
                "identify_source": artifact.identify_source,
            }
            for artifact in detail.artifact_refs
        ],
        "identify_surface": {
            "source_parameters": [
                {
                    "artifact_id": option.artifact_id,
                    "source_parameter": option.source_parameter,
                    "label": option.label,
                    "artifact_title": option.artifact_title,
                    "current_designated_metric": option.current_designated_metric,
                }
                for option in detail.identify_surface.source_parameters
            ],
            "designated_metrics": [
                {
                    "metric_key": option.metric_key,
                    "label": option.label,
                }
                for option in detail.identify_surface.designated_metrics
            ],
            "applied_tags": [
                {
                    "artifact_id": tag.artifact_id,
                    "source_parameter": tag.source_parameter,
                    "designated_metric": tag.designated_metric,
                    "designated_metric_label": tag.designated_metric_label,
                    "tagged_at": tag.tagged_at,
                }
                for tag in detail.identify_surface.applied_tags
            ],
        },
        "downstream_unlock_analysis_ids": list(detail.downstream_unlock_analysis_ids),
    }


def _matches_dataset_scope(
    summary_payload: Mapping[str, object],
    dataset_id: str,
    design_id: str | None,
) -> bool:
    summary = summary_payload.get("result_summary")
    if not isinstance(summary, Mapping):
        return False
    if str(summary.get("dataset_id")) != dataset_id:
        return False
    if design_id is None:
        return True
    return str(summary.get("design_id")) == design_id


def _build_tagged_metric_id(dataset_id: str, designated_metric: str) -> str:
    normalized_dataset = dataset_id.replace("_", "-")
    normalized_metric = designated_metric.replace("_", "-")
    return f"metric-{normalized_dataset}-{normalized_metric}"


def _utc_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _stable_positive_int(*parts: object) -> int:
    token = "|".join(str(part) for part in parts)
    digest = sha256(token.encode("utf-8")).hexdigest()
    return (int(digest[:12], 16) % 900_000_000) + 1
