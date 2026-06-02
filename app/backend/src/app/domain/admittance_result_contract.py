from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from src.app.domain.datasets import (
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
    CharacterizationSourceParameterOption,
)

ADMITTANCE_RESULT_CONTRACT_VERSION = "admittance_member_phase1_v1"
ADMITTANCE_GRID_ARTIFACT_SUFFIX = "mode-frequency-grid"
ADMITTANCE_IDENTIFY_ARTIFACT_SUFFIX = "identify-summary"
ADMITTANCE_REPORT_ARTIFACT_SUFFIX = "report"
ADMITTANCE_TABLE_PRESET_ID = "mode_by_input_table"
ADMITTANCE_MODE_PROFILE_PRESET_ID = "mode_profile_plot"
ADMITTANCE_SWEEP_PROFILE_PRESET_ID = "sweep_profile_plot"
ADMITTANCE_IDENTIFY_PRESET_ID = "summary_table"
ADMITTANCE_METRIC_KEY = "frequency_ghz"
ADMITTANCE_METRIC_LABEL = "Frequency"
ADMITTANCE_METRIC_UNIT = "GHz"
ADMITTANCE_MODE_AXIS_KEY = "mode_index"
ADMITTANCE_MODE_AXIS_LABEL = "Mode index"
ADMITTANCE_MEMBER_AXIS_KEY = "member_key"
ADMITTANCE_MEMBER_AXIS_LABEL = "Collection member"


@dataclass(frozen=True)
class AdmittanceResultMember:
    member_key: str
    label: str
    trace_id: str
    source_kind: str
    trace_mode_group: str
    parameter: str
    representation: str
    provenance_summary: str


@dataclass(frozen=True)
class AdmittanceSummaryMetric:
    parameter: str
    label: str
    value: float | int | None
    unit: str | None


@dataclass(frozen=True)
class AdmittanceResultSurface:
    input_axis_key: str
    input_axis_label: str
    input_axis_unit: str | None
    input_axis_values: tuple[float, ...]
    members: tuple[AdmittanceResultMember, ...]
    frequency_grid_by_member: tuple[tuple[tuple[float | None, ...], ...], ...]
    residual_rms_by_member: tuple[tuple[float | None, ...], ...]
    fit_window_ghz: tuple[float, float]
    masked_input_indices_by_member: tuple[tuple[int, ...], ...]
    diagnostics: tuple[CharacterizationDiagnostic, ...] = ()

    @property
    def derived_axis_values(self) -> tuple[int, ...]:
        mode_count = 0
        if len(self.frequency_grid_by_member) > 0:
            mode_count = max(
                (
                    len(row)
                    for member_grid in self.frequency_grid_by_member
                    for row in member_grid
                ),
                default=0,
            )
        return tuple(range(mode_count))

    @property
    def input_axis_spec(self) -> CharacterizationArtifactAxisSpec:
        return CharacterizationArtifactAxisSpec(
            axis_key=self.input_axis_key,
            label=self.input_axis_label,
            role="input",
            unit=self.input_axis_unit,
            length=len(self.input_axis_values),
        )

    @property
    def mode_axis_spec(self) -> CharacterizationArtifactAxisSpec:
        return CharacterizationArtifactAxisSpec(
            axis_key=ADMITTANCE_MODE_AXIS_KEY,
            label=ADMITTANCE_MODE_AXIS_LABEL,
            role="derived",
            unit=None,
            length=len(self.derived_axis_values),
        )

    @property
    def member_axis_spec(self) -> CharacterizationArtifactAxisSpec:
        return CharacterizationArtifactAxisSpec(
            axis_key=ADMITTANCE_MEMBER_AXIS_KEY,
            label=ADMITTANCE_MEMBER_AXIS_LABEL,
            role="member",
            unit=None,
            length=len(self.members),
        )

    @property
    def metric_spec(self) -> CharacterizationArtifactMetricSpec:
        return CharacterizationArtifactMetricSpec(
            metric_key=ADMITTANCE_METRIC_KEY,
            label=ADMITTANCE_METRIC_LABEL,
            unit=ADMITTANCE_METRIC_UNIT,
        )


def summarize_admittance_surface(
    *,
    analysis_run_id: int,
    analysis_config: Mapping[str, object],
    surface: AdmittanceResultSurface,
) -> dict[str, object]:
    return {
        "contract_version": ADMITTANCE_RESULT_CONTRACT_VERSION,
        "analysis_run_id": analysis_run_id,
        "analysis_config": dict(analysis_config),
        "input_axis": {
            "axis_key": surface.input_axis_key,
            "label": surface.input_axis_label,
            "unit": surface.input_axis_unit,
            "length": len(surface.input_axis_values),
        },
        "member_axis": {
            "axis_key": ADMITTANCE_MEMBER_AXIS_KEY,
            "label": ADMITTANCE_MEMBER_AXIS_LABEL,
            "length": len(surface.members),
        },
        "derived_axis": {
            "axis_key": ADMITTANCE_MODE_AXIS_KEY,
            "label": ADMITTANCE_MODE_AXIS_LABEL,
            "length": len(surface.derived_axis_values),
        },
        "metric": {
            "metric_key": ADMITTANCE_METRIC_KEY,
            "label": ADMITTANCE_METRIC_LABEL,
            "unit": ADMITTANCE_METRIC_UNIT,
        },
        "fit_window_ghz": list(surface.fit_window_ghz),
        "member_count": len(surface.members),
        "masked_input_indices_by_member": [
            list(indices) for indices in surface.masked_input_indices_by_member
        ],
        "masked_member_count": sum(
            1 for indices in surface.masked_input_indices_by_member if len(indices) > 0
        ),
        "mode_capacity": len(surface.derived_axis_values),
    }


def build_admittance_artifact_refs(
    *,
    result_id: str,
) -> tuple[CharacterizationArtifactRef, ...]:
    input_axis = CharacterizationArtifactAxisSpec(
        axis_key="input_axis",
        label="Input sweep axis",
        role="input",
        unit=None,
        length=0,
    )
    metric = CharacterizationArtifactMetricSpec(
        metric_key=ADMITTANCE_METRIC_KEY,
        label=ADMITTANCE_METRIC_LABEL,
        unit=ADMITTANCE_METRIC_UNIT,
    )
    return (
        CharacterizationArtifactRef(
            artifact_id=admittance_grid_artifact_id(result_id),
            category="result_tensor",
            view_kind="preset_query",
            title="Mode frequency grid",
            payload_format="json",
            payload_locator=f"characterization/{result_id}/mode-frequency-grid.json",
            axes=(input_axis, _member_axis_spec(), _mode_axis_spec()),
            metric=metric,
            presets=(
                CharacterizationArtifactPreset(
                    preset_id=ADMITTANCE_TABLE_PRESET_ID,
                    label="Mode by input table",
                    view_kind="table",
                    rows_axis=ADMITTANCE_MODE_AXIS_KEY,
                    columns_axis="input_axis",
                    cell_metric=ADMITTANCE_METRIC_KEY,
                    compare_axis=ADMITTANCE_MEMBER_AXIS_KEY,
                ),
                CharacterizationArtifactPreset(
                    preset_id=ADMITTANCE_MODE_PROFILE_PRESET_ID,
                    label="Mode profile plot",
                    view_kind="plot",
                    x_axis=ADMITTANCE_MODE_AXIS_KEY,
                    y_metric=ADMITTANCE_METRIC_KEY,
                    series_axis="input_axis",
                    compare_axis=ADMITTANCE_MEMBER_AXIS_KEY,
                ),
                CharacterizationArtifactPreset(
                    preset_id=ADMITTANCE_SWEEP_PROFILE_PRESET_ID,
                    label="Sweep profile plot",
                    view_kind="plot",
                    x_axis="input_axis",
                    y_metric=ADMITTANCE_METRIC_KEY,
                    series_axis=ADMITTANCE_MODE_AXIS_KEY,
                    compare_axis=ADMITTANCE_MEMBER_AXIS_KEY,
                ),
            ),
            default_preset_id=ADMITTANCE_TABLE_PRESET_ID,
            query_spec=CharacterizationArtifactQuerySpec(
                query_style="preset_driven",
                supported_query_fields=("view_mode", "preset_id"),
                supported_view_modes=("table", "plot"),
                supported_preset_ids=(
                    ADMITTANCE_TABLE_PRESET_ID,
                    ADMITTANCE_MODE_PROFILE_PRESET_ID,
                    ADMITTANCE_SWEEP_PROFILE_PRESET_ID,
                ),
                default_preset_id=ADMITTANCE_TABLE_PRESET_ID,
                default_presets_by_view_mode=(
                    CharacterizationArtifactViewModeDefault(
                        view_mode="table",
                        preset_id=ADMITTANCE_TABLE_PRESET_ID,
                    ),
                    CharacterizationArtifactViewModeDefault(
                        view_mode="plot",
                        preset_id=ADMITTANCE_MODE_PROFILE_PRESET_ID,
                    ),
                ),
            ),
        ),
        CharacterizationArtifactRef(
            artifact_id=admittance_identify_artifact_id(result_id),
            category="summary_table",
            view_kind="table",
            title="Admittance identify summary",
            payload_format="json",
            payload_locator=f"characterization/{result_id}/identify-summary.json",
            presets=(
                CharacterizationArtifactPreset(
                    preset_id=ADMITTANCE_IDENTIFY_PRESET_ID,
                    label="Identify summary table",
                    view_kind="table",
                ),
            ),
            default_preset_id=ADMITTANCE_IDENTIFY_PRESET_ID,
            query_spec=CharacterizationArtifactQuerySpec(
                query_style="preset_driven",
                supported_query_fields=("view_mode", "preset_id"),
                supported_view_modes=("table",),
                supported_preset_ids=(ADMITTANCE_IDENTIFY_PRESET_ID,),
                default_preset_id=ADMITTANCE_IDENTIFY_PRESET_ID,
                default_presets_by_view_mode=(
                    CharacterizationArtifactViewModeDefault(
                        view_mode="table",
                        preset_id=ADMITTANCE_IDENTIFY_PRESET_ID,
                    ),
                ),
            ),
            identify_source=True,
        ),
        CharacterizationArtifactRef(
            artifact_id=admittance_report_artifact_id(result_id),
            category="report",
            view_kind="json",
            title="Admittance extraction report",
            payload_format="json",
            payload_locator=f"characterization/{result_id}/report.json",
            query_spec=CharacterizationArtifactQuerySpec(
                query_style="static",
                supported_query_fields=(),
                supported_view_modes=("json",),
            ),
        ),
    )


def annotate_admittance_artifact_refs(
    refs: Sequence[CharacterizationArtifactRef],
    surface: AdmittanceResultSurface,
) -> tuple[CharacterizationArtifactRef, ...]:
    annotated: list[CharacterizationArtifactRef] = []
    for ref in refs:
        if ref.artifact_id.endswith(ADMITTANCE_GRID_ARTIFACT_SUFFIX):
            annotated.append(
                CharacterizationArtifactRef(
                    artifact_id=ref.artifact_id,
                    category=ref.category,
                    view_kind=ref.view_kind,
                    title=ref.title,
                    payload_format=ref.payload_format,
                    payload_locator=ref.payload_locator,
                    axes=(
                        surface.input_axis_spec,
                        surface.member_axis_spec,
                        surface.mode_axis_spec,
                    ),
                    metric=surface.metric_spec,
                    presets=tuple(
                        CharacterizationArtifactPreset(
                            preset_id=preset.preset_id,
                            label=preset.label,
                            view_kind=preset.view_kind,
                            rows_axis=(
                                surface.input_axis_key
                                if preset.rows_axis == "input_axis"
                                else preset.rows_axis
                            ),
                            columns_axis=(
                                surface.input_axis_key
                                if preset.columns_axis == "input_axis"
                                else preset.columns_axis
                            ),
                            cell_metric=preset.cell_metric,
                            x_axis=(
                                surface.input_axis_key
                                if preset.x_axis == "input_axis"
                                else preset.x_axis
                            ),
                            y_metric=preset.y_metric,
                            series_axis=(
                                surface.input_axis_key
                                if preset.series_axis == "input_axis"
                                else preset.series_axis
                            ),
                            compare_axis=preset.compare_axis,
                        )
                        for preset in ref.presets
                    ),
                    default_preset_id=ref.default_preset_id,
                    query_spec=ref.query_spec,
                    identify_source=ref.identify_source,
                )
            )
            continue
        annotated.append(ref)
    return tuple(annotated)


def build_admittance_identify_surface(
    *,
    result_id: str,
    surface: AdmittanceResultSurface,
    applied_tags: Sequence[CharacterizationAppliedTag] = (),
) -> CharacterizationIdentifySurface:
    artifact_id = admittance_identify_artifact_id(result_id)
    metric_options = _identify_designated_metrics()
    applied_tag_map = {
        (tag.artifact_id, tag.source_parameter): tag.designated_metric for tag in applied_tags
    }
    source_parameters = tuple(
        CharacterizationSourceParameterOption(
            artifact_id=artifact_id,
            source_parameter=metric.parameter,
            label=metric.label,
            artifact_title="Admittance identify summary",
            current_designated_metric=applied_tag_map.get((artifact_id, metric.parameter)),
        )
        for metric in build_admittance_summary_metrics(surface)
        if metric.value is not None
    )
    return CharacterizationIdentifySurface(
        source_parameters=source_parameters,
        designated_metrics=metric_options,
        applied_tags=tuple(applied_tags),
    )


def build_admittance_summary_metrics(
    surface: AdmittanceResultSurface,
) -> tuple[AdmittanceSummaryMetric, ...]:
    values = [
        value
        for member_grid in surface.frequency_grid_by_member
        for row in member_grid
        for value in row
        if value is not None
    ]
    residuals = [
        value
        for member_residuals in surface.residual_rms_by_member
        for value in member_residuals
        if value is not None
    ]
    return (
        AdmittanceSummaryMetric(
            parameter="lowest_observed_frequency_ghz",
            label="Lowest observed frequency",
            value=min(values) if values else None,
            unit="GHz",
        ),
        AdmittanceSummaryMetric(
            parameter="highest_observed_frequency_ghz",
            label="Highest observed frequency",
            value=max(values) if values else None,
            unit="GHz",
        ),
        AdmittanceSummaryMetric(
            parameter="residual_rms_max",
            label="Max residual RMS",
            value=max(residuals) if residuals else None,
            unit="S",
        ),
    )


def serialize_admittance_surface(
    surface: AdmittanceResultSurface,
) -> dict[str, object]:
    return {
        "contract_version": ADMITTANCE_RESULT_CONTRACT_VERSION,
        "input_axis_key": surface.input_axis_key,
        "input_axis_label": surface.input_axis_label,
        "input_axis_unit": surface.input_axis_unit,
        "input_axis_values": list(surface.input_axis_values),
        "members": [
            {
                "member_key": member.member_key,
                "label": member.label,
                "trace_id": member.trace_id,
                "source_kind": member.source_kind,
                "trace_mode_group": member.trace_mode_group,
                "parameter": member.parameter,
                "representation": member.representation,
                "provenance_summary": member.provenance_summary,
            }
            for member in surface.members
        ],
        "frequency_grid_by_member": [
            [
                [float(value) if value is not None else None for value in row]
                for row in member_grid
            ]
            for member_grid in surface.frequency_grid_by_member
        ],
        "residual_rms_by_member": [
            [float(value) if value is not None else None for value in member_residuals]
            for member_residuals in surface.residual_rms_by_member
        ],
        "fit_window_ghz": list(surface.fit_window_ghz),
        "masked_input_indices_by_member": [
            list(indices) for indices in surface.masked_input_indices_by_member
        ],
        "diagnostics": [
            {
                "severity": diagnostic.severity,
                "code": diagnostic.code,
                "message": diagnostic.message,
                "blocking": diagnostic.blocking,
            }
            for diagnostic in surface.diagnostics
        ],
    }


def parse_admittance_surface(
    payload: object,
) -> AdmittanceResultSurface | None:
    if not isinstance(payload, Mapping):
        return None
    input_axis_values = tuple(
        float(value)
        for value in payload.get("input_axis_values", ())
        if isinstance(value, int | float)
    )
    members_payload = payload.get("members", ())
    grid_payload = payload.get("frequency_grid_by_member", ())
    residual_payload = payload.get("residual_rms_by_member", ())
    fit_window = payload.get("fit_window_ghz", ())
    diagnostics = payload.get("diagnostics", ())
    if not (
        isinstance(grid_payload, Sequence)
        and not isinstance(grid_payload, str | bytes)
        and len(grid_payload) > 0
    ):
        legacy_grid_payload = payload.get("frequency_grid_by_input", ())
        if isinstance(legacy_grid_payload, Sequence) and not isinstance(
            legacy_grid_payload, str | bytes
        ):
            grid_payload = (legacy_grid_payload,)
            residual_payload = (payload.get("residual_rms_by_input", ()),)
            members_payload = (
                {
                    "member_key": "selected_scope:0",
                    "label": "Selected trace bundle",
                    "trace_id": "selected_scope",
                    "source_kind": "measurement",
                    "trace_mode_group": "base",
                    "parameter": "member",
                    "representation": "derived",
                    "provenance_summary": "Legacy single-member admittance result",
                },
            )
    masked_input_indices_payload = payload.get("masked_input_indices_by_member", ())
    if not (
        isinstance(masked_input_indices_payload, Sequence)
        and not isinstance(masked_input_indices_payload, str | bytes)
        and len(masked_input_indices_payload) > 0
    ):
        masked_input_indices_payload = (payload.get("masked_input_indices", ()),)
    return AdmittanceResultSurface(
        input_axis_key=str(payload.get("input_axis_key", "input_axis")),
        input_axis_label=str(payload.get("input_axis_label", "Input axis")),
        input_axis_unit=(
            str(payload.get("input_axis_unit"))
            if isinstance(payload.get("input_axis_unit"), str)
            else None
        ),
        input_axis_values=input_axis_values,
        members=_parse_members(members_payload, grid_payload),
        frequency_grid_by_member=tuple(
            tuple(
                tuple(float(value) if isinstance(value, int | float) else None for value in row)
                for row in member_grid
                if isinstance(row, Sequence) and not isinstance(row, str | bytes)
            )
            for member_grid in grid_payload
            if isinstance(member_grid, Sequence) and not isinstance(member_grid, str | bytes)
        ),
        residual_rms_by_member=tuple(
            tuple(
                float(value) if isinstance(value, int | float) else None
                for value in member_residuals
                if value is None or isinstance(value, int | float)
            )
            for member_residuals in residual_payload
            if isinstance(member_residuals, Sequence)
            and not isinstance(member_residuals, str | bytes)
        ),
        fit_window_ghz=tuple(
            float(value) for value in fit_window if isinstance(value, int | float)
        )[:2],
        masked_input_indices_by_member=tuple(
            tuple(
                int(index)
                for index in member_indices
                if isinstance(index, int | float)
            )
            for member_indices in masked_input_indices_payload
            if isinstance(member_indices, Sequence)
            and not isinstance(member_indices, str | bytes)
        ),
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
    )


def query_admittance_artifact_payload(
    *,
    surface: AdmittanceResultSurface,
    artifact_id: str,
    query: CharacterizationArtifactPayloadQuery,
) -> CharacterizationArtifactPayload | None:
    if artifact_id.endswith(ADMITTANCE_GRID_ARTIFACT_SUFFIX):
        resolved_preset_id = _resolve_grid_preset_id(query)
        return _query_grid_artifact_payload(
            artifact_id=artifact_id,
            preset_id=resolved_preset_id,
            surface=surface,
        )
    if artifact_id.endswith(ADMITTANCE_IDENTIFY_ARTIFACT_SUFFIX):
        resolved_preset_id = _resolve_identify_preset_id(query)
        return CharacterizationArtifactPayload(
            artifact_id=artifact_id,
            title="Admittance identify summary",
            preset_id=resolved_preset_id,
            view_kind="table",
            axes=(),
            metric=None,
            payload={
                "rows": [
                    {
                        "parameter": metric.parameter,
                        "label": metric.label,
                        "value": metric.value,
                        "unit": metric.unit,
                    }
                    for metric in build_admittance_summary_metrics(surface)
                ]
            },
        )
    if artifact_id.endswith(ADMITTANCE_REPORT_ARTIFACT_SUFFIX):
        if query.view_mode not in (None, "json"):
            return None
        return CharacterizationArtifactPayload(
            artifact_id=artifact_id,
            title="Admittance extraction report",
            preset_id=query.preset_id or "default",
            view_kind="json",
            axes=(),
            metric=None,
            payload={
                "contract_version": ADMITTANCE_RESULT_CONTRACT_VERSION,
                "input_axis": {
                    "axis_key": surface.input_axis_key,
                    "label": surface.input_axis_label,
                    "unit": surface.input_axis_unit,
                    "length": len(surface.input_axis_values),
                },
                "member_axis": {
                    "axis_key": ADMITTANCE_MEMBER_AXIS_KEY,
                    "label": ADMITTANCE_MEMBER_AXIS_LABEL,
                    "length": len(surface.members),
                },
                "mode_capacity": len(surface.derived_axis_values),
                "member_count": len(surface.members),
                "masked_input_indices_by_member": [
                    list(indices) for indices in surface.masked_input_indices_by_member
                ],
                "fit_window_ghz": list(surface.fit_window_ghz),
            },
            diagnostics=surface.diagnostics,
        )
    return None


def admittance_grid_artifact_id(result_id: str) -> str:
    return f"{result_id}:{ADMITTANCE_GRID_ARTIFACT_SUFFIX}"


def admittance_identify_artifact_id(result_id: str) -> str:
    return f"{result_id}:{ADMITTANCE_IDENTIFY_ARTIFACT_SUFFIX}"


def admittance_report_artifact_id(result_id: str) -> str:
    return f"{result_id}:{ADMITTANCE_REPORT_ARTIFACT_SUFFIX}"


def _query_grid_artifact_payload(
    *,
    artifact_id: str,
    preset_id: str,
    surface: AdmittanceResultSurface,
) -> CharacterizationArtifactPayload | None:
    if preset_id == ADMITTANCE_TABLE_PRESET_ID:
        return CharacterizationArtifactPayload(
            artifact_id=artifact_id,
            title="Mode frequency grid",
            preset_id=preset_id,
            view_kind="table",
            axes=(surface.mode_axis_spec, surface.input_axis_spec, surface.member_axis_spec),
            metric=surface.metric_spec,
            payload={
                "layout": {
                    "rows_axis": ADMITTANCE_MODE_AXIS_KEY,
                    "columns_axis": surface.input_axis_key,
                    "cell_metric": ADMITTANCE_METRIC_KEY,
                    "compare_axis": ADMITTANCE_MEMBER_AXIS_KEY,
                },
                "rows": [
                    {"axis_value": mode_index, "label": f"Mode {mode_index}"}
                    for mode_index in surface.derived_axis_values
                ],
                "columns": [
                    {
                        "axis_value": axis_value,
                        "label": _format_axis_value(axis_value, surface.input_axis_unit),
                        "unit": surface.input_axis_unit,
                    }
                    for axis_value in surface.input_axis_values
                ],
                "compare_groups": [
                    {
                        "compare_key": member.member_key,
                        "compare_label": member.label,
                        "member": _member_payload(member),
                        "cells": _table_cells_for_member(surface, member_index=index),
                        "mask": _table_mask_for_member(surface, member_index=index),
                    }
                    for index, member in enumerate(surface.members)
                ],
                **_single_member_table_projection(surface),
            },
            diagnostics=surface.diagnostics,
        )
    if preset_id == ADMITTANCE_MODE_PROFILE_PRESET_ID:
        return CharacterizationArtifactPayload(
            artifact_id=artifact_id,
            title="Mode frequency grid",
            preset_id=preset_id,
            view_kind="plot",
            axes=(surface.mode_axis_spec, surface.input_axis_spec, surface.member_axis_spec),
            metric=surface.metric_spec,
            payload={
                "layout": {
                    "x_axis": ADMITTANCE_MODE_AXIS_KEY,
                    "y_metric": ADMITTANCE_METRIC_KEY,
                    "series_axis": surface.input_axis_key,
                    "compare_axis": ADMITTANCE_MEMBER_AXIS_KEY,
                },
                "compare_groups": [
                    {
                        "compare_key": member.member_key,
                        "compare_label": member.label,
                        "member": _member_payload(member),
                        "series": _mode_profile_series_for_member(
                            surface=surface,
                            member_index=index,
                        ),
                    }
                    for index, member in enumerate(surface.members)
                ],
                "series": [
                    series_payload
                    for index, member in enumerate(surface.members)
                    for series_payload in _series_with_member_context(
                        _mode_profile_series_for_member(surface=surface, member_index=index),
                        member=member,
                    )
                ],
            },
            diagnostics=surface.diagnostics,
        )
    if preset_id == ADMITTANCE_SWEEP_PROFILE_PRESET_ID:
        return CharacterizationArtifactPayload(
            artifact_id=artifact_id,
            title="Mode frequency grid",
            preset_id=preset_id,
            view_kind="plot",
            axes=(surface.input_axis_spec, surface.mode_axis_spec, surface.member_axis_spec),
            metric=surface.metric_spec,
            payload={
                "layout": {
                    "x_axis": surface.input_axis_key,
                    "y_metric": ADMITTANCE_METRIC_KEY,
                    "series_axis": ADMITTANCE_MODE_AXIS_KEY,
                    "compare_axis": ADMITTANCE_MEMBER_AXIS_KEY,
                },
                "compare_groups": [
                    {
                        "compare_key": member.member_key,
                        "compare_label": member.label,
                        "member": _member_payload(member),
                        "series": _sweep_profile_series_for_member(
                            surface=surface,
                            member_index=index,
                        ),
                    }
                    for index, member in enumerate(surface.members)
                ],
                "series": [
                    series_payload
                    for index, member in enumerate(surface.members)
                    for series_payload in _series_with_member_context(
                        _sweep_profile_series_for_member(surface=surface, member_index=index),
                        member=member,
                    )
                ],
            },
            diagnostics=surface.diagnostics,
        )
    return None


def _resolve_grid_preset_id(query: CharacterizationArtifactPayloadQuery) -> str | None:
    if query.preset_id is not None:
        if query.view_mode is None:
            return query.preset_id
        preset_view_kind = _grid_preset_view_kind(query.preset_id)
        if preset_view_kind == query.view_mode:
            return query.preset_id
        return None
    if query.view_mode == "plot":
        return ADMITTANCE_MODE_PROFILE_PRESET_ID
    if query.view_mode in (None, "table"):
        return ADMITTANCE_TABLE_PRESET_ID
    return None


def _resolve_identify_preset_id(query: CharacterizationArtifactPayloadQuery) -> str | None:
    if query.view_mode not in (None, "table"):
        return None
    if query.preset_id is None:
        return ADMITTANCE_IDENTIFY_PRESET_ID
    if query.preset_id == ADMITTANCE_IDENTIFY_PRESET_ID:
        return query.preset_id
    return None


def _grid_preset_view_kind(preset_id: str) -> str | None:
    if preset_id == ADMITTANCE_TABLE_PRESET_ID:
        return "table"
    if preset_id in {
        ADMITTANCE_MODE_PROFILE_PRESET_ID,
        ADMITTANCE_SWEEP_PROFILE_PRESET_ID,
    }:
        return "plot"
    return None


def _table_cells_for_member(
    surface: AdmittanceResultSurface,
    *,
    member_index: int,
) -> list[list[float | None]]:
    rows: list[list[float | None]] = []
    member_grid = surface.frequency_grid_by_member[member_index]
    for mode_index in surface.derived_axis_values:
        rows.append(
            [
                row[mode_index] if mode_index < len(row) else None
                for row in member_grid
            ]
        )
    return rows


def _table_mask_for_member(
    surface: AdmittanceResultSurface,
    *,
    member_index: int,
) -> list[list[bool]]:
    return [
        [value is None for value in row]
        for row in _table_cells_for_member(surface, member_index=member_index)
    ]


def _identify_designated_metrics() -> tuple[CharacterizationDesignatedMetricOption, ...]:
    return (
        CharacterizationDesignatedMetricOption(
            metric_key="lowest_observed_frequency_ghz",
            label="Lowest Observed Frequency",
        ),
        CharacterizationDesignatedMetricOption(
            metric_key="highest_observed_frequency_ghz",
            label="Highest Observed Frequency",
        ),
        CharacterizationDesignatedMetricOption(
            metric_key="residual_rms_max",
            label="Max Residual RMS",
        ),
    )


def _format_axis_value(value: float, unit: str | None) -> str:
    if unit:
        return f"{value:g} {unit}"
    return f"{value:g}"


def _mode_axis_spec() -> CharacterizationArtifactAxisSpec:
    return CharacterizationArtifactAxisSpec(
        axis_key=ADMITTANCE_MODE_AXIS_KEY,
        label=ADMITTANCE_MODE_AXIS_LABEL,
        role="derived",
        unit=None,
        length=0,
    )


def _member_axis_spec() -> CharacterizationArtifactAxisSpec:
    return CharacterizationArtifactAxisSpec(
        axis_key=ADMITTANCE_MEMBER_AXIS_KEY,
        label=ADMITTANCE_MEMBER_AXIS_LABEL,
        role="member",
        unit=None,
        length=0,
    )


def _member_payload(member: AdmittanceResultMember) -> dict[str, object]:
    return {
        "member_key": member.member_key,
        "label": member.label,
        "trace_id": member.trace_id,
        "source_kind": member.source_kind,
        "trace_mode_group": member.trace_mode_group,
        "parameter": member.parameter,
        "representation": member.representation,
        "provenance_summary": member.provenance_summary,
    }


def _parse_members(
    members_payload: object,
    grid_payload: object,
) -> tuple[AdmittanceResultMember, ...]:
    members = (
        tuple(
            AdmittanceResultMember(
                member_key=str(item.get("member_key", "")),
                label=str(item.get("label", "")),
                trace_id=str(item.get("trace_id", "")),
                source_kind=str(item.get("source_kind", "")),
                trace_mode_group=str(item.get("trace_mode_group", "")),
                parameter=str(item.get("parameter", "")),
                representation=str(item.get("representation", "")),
                provenance_summary=str(item.get("provenance_summary", "")),
            )
            for item in members_payload
            if isinstance(item, Mapping)
        )
        if isinstance(members_payload, Sequence)
        and not isinstance(members_payload, str | bytes)
        else ()
    )
    if len(members) > 0:
        return members
    member_count = (
        len(grid_payload)
        if isinstance(grid_payload, Sequence) and not isinstance(grid_payload, str | bytes)
        else 0
    )
    return tuple(
        AdmittanceResultMember(
            member_key=f"selected_scope:{index}",
            label=f"Selected member {index + 1}",
            trace_id=f"selected_scope:{index}",
            source_kind="measurement",
            trace_mode_group="base",
            parameter="member",
            representation="derived",
            provenance_summary="Backfilled member identity from persisted admittance result.",
        )
        for index in range(member_count)
    )


def _single_member_table_projection(surface: AdmittanceResultSurface) -> dict[str, object]:
    if len(surface.members) != 1:
        return {}
    return {
        "cells": _table_cells_for_member(surface, member_index=0),
        "mask": _table_mask_for_member(surface, member_index=0),
    }


def _mode_profile_series_for_member(
    *,
    surface: AdmittanceResultSurface,
    member_index: int,
) -> list[dict[str, object]]:
    member_grid = surface.frequency_grid_by_member[member_index]
    return [
        {
            "series_key": f"{surface.input_axis_key}:{index}",
            "series_label": _format_axis_value(
                surface.input_axis_values[index],
                surface.input_axis_unit,
            ),
            "series_value": surface.input_axis_values[index],
            "x_values": list(surface.derived_axis_values),
            "y_values": [
                row[mode_index] if mode_index < len(row) else None
                for mode_index in surface.derived_axis_values
            ],
            "mask": [
                mode_index >= len(row) or row[mode_index] is None
                for mode_index in surface.derived_axis_values
            ],
        }
        for index, row in enumerate(member_grid)
    ]


def _sweep_profile_series_for_member(
    *,
    surface: AdmittanceResultSurface,
    member_index: int,
) -> list[dict[str, object]]:
    member_grid = surface.frequency_grid_by_member[member_index]
    return [
        {
            "series_key": f"{ADMITTANCE_MODE_AXIS_KEY}:{mode_index}",
            "series_label": f"Mode {mode_index}",
            "series_value": mode_index,
            "x_values": list(surface.input_axis_values),
            "y_values": [
                row[mode_index] if mode_index < len(row) else None
                for row in member_grid
            ],
            "mask": [
                mode_index >= len(row) or row[mode_index] is None
                for row in member_grid
            ],
        }
        for mode_index in surface.derived_axis_values
    ]


def _series_with_member_context(
    series: list[dict[str, object]],
    *,
    member: AdmittanceResultMember,
) -> list[dict[str, object]]:
    return [
        {
            **item,
            "compare_key": member.member_key,
            "compare_label": member.label,
            "member": _member_payload(member),
        }
        for item in series
    ]
