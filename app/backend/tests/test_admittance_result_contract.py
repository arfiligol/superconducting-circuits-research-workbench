from __future__ import annotations

from app_backend.domain.admittance_result_contract import (
    AdmittanceResultMember,
    AdmittanceResultSurface,
    admittance_grid_artifact_id,
    build_admittance_artifact_refs,
    build_admittance_identify_surface,
    query_admittance_artifact_payload,
)
from app_backend.domain.datasets import (
    CharacterizationAppliedTag,
    CharacterizationArtifactPayloadQuery,
    CharacterizationDiagnostic,
)


def _sample_surface() -> AdmittanceResultSurface:
    return AdmittanceResultSurface(
        input_axis_key="Lj",
        input_axis_label="Lj",
        input_axis_unit="pH",
        input_axis_values=(850.0, 1000.0, 1150.0),
        members=(
            AdmittanceResultMember(
                member_key="measurement:trace_a",
                label="measurement · admittance (complex)",
                trace_id="trace_a",
                source_kind="measurement",
                trace_mode_group="base",
                parameter="admittance",
                representation="complex",
                provenance_summary="Measurement member A",
            ),
            AdmittanceResultMember(
                member_key="layout_simulation:trace_b",
                label="layout simulation · admittance (complex)",
                trace_id="trace_b",
                source_kind="layout_simulation",
                trace_mode_group="base",
                parameter="admittance",
                representation="complex",
                provenance_summary="Layout member B",
            ),
        ),
        frequency_grid_by_member=(
            (
                (4.82, 5.31, 6.08),
                (4.76, 5.28, None),
                (None, None, None),
            ),
            (
                (4.79, 5.29, 6.04),
                (4.73, 5.25, None),
                (None, None, None),
            ),
        ),
        residual_rms_by_member=((0.01, 0.015, None), (0.012, 0.018, None)),
        fit_window_ghz=(4.5, 6.5),
        masked_input_indices_by_member=((2,), (2,)),
        diagnostics=(
            CharacterizationDiagnostic(
                severity="warning",
                code="masked_input_positions_preserved",
                message="One sweep position stayed fully masked.",
                blocking=False,
            ),
        ),
    )


def test_admittance_grid_artifact_supports_multiple_mode_rows_and_preserves_masked_slices() -> None:
    surface = _sample_surface()
    artifact_id = admittance_grid_artifact_id("char-demo")

    table_payload = query_admittance_artifact_payload(
        surface=surface,
        artifact_id=artifact_id,
        query=CharacterizationArtifactPayloadQuery(
            view_mode="table",
            preset_id="mode_by_input_table",
        ),
    )

    assert table_payload is not None
    assert table_payload.view_kind == "table"
    assert [row["axis_value"] for row in table_payload.payload["rows"]] == [0, 1, 2]
    assert [column["axis_value"] for column in table_payload.payload["columns"]] == [
        850.0,
        1000.0,
        1150.0,
    ]
    assert table_payload.payload["compare_groups"][0]["cells"] == [
        [4.82, 4.76, None],
        [5.31, 5.28, None],
        [6.08, None, None],
    ]
    assert table_payload.payload["compare_groups"][0]["mask"] == [
        [False, False, True],
        [False, False, True],
        [False, True, True],
    ]
    assert table_payload.payload["compare_groups"][1]["member"]["trace_id"] == "trace_b"

    plot_payload = query_admittance_artifact_payload(
        surface=surface,
        artifact_id=artifact_id,
        query=CharacterizationArtifactPayloadQuery(view_mode="plot"),
    )
    assert plot_payload is not None
    assert plot_payload.preset_id == "mode_profile_plot"
    assert plot_payload.view_kind == "plot"
    measurement_series = [
        series
        for series in plot_payload.payload["series"]
        if series["compare_key"] == "measurement:trace_a"
    ]
    assert measurement_series[2]["mask"] == [True, True, True]
    assert measurement_series[2]["y_values"] == [None, None, None]


def test_admittance_grid_artifact_manifest_exposes_explicit_query_spec() -> None:
    artifact_refs = build_admittance_artifact_refs(result_id="char-demo")
    grid_artifact = next(
        ref for ref in artifact_refs if ref.artifact_id == "char-demo:mode-frequency-grid"
    )

    assert grid_artifact.view_kind == "preset_query"
    assert grid_artifact.query_spec is not None
    assert grid_artifact.query_spec.query_style == "preset_driven"
    assert grid_artifact.query_spec.supported_query_fields == ("view_mode", "preset_id")
    assert grid_artifact.query_spec.supported_view_modes == ("table", "plot")
    assert grid_artifact.query_spec.default_preset_id == "mode_by_input_table"
    assert [
        (item.view_mode, item.preset_id)
        for item in grid_artifact.query_spec.default_presets_by_view_mode
    ] == [
        ("table", "mode_by_input_table"),
        ("plot", "mode_profile_plot"),
    ]


def test_admittance_identify_surface_uses_explicit_summary_artifact() -> None:
    surface = _sample_surface()
    artifact_refs = build_admittance_artifact_refs(result_id="char-demo")
    identify_artifact = next(ref for ref in artifact_refs if ref.identify_source)

    identify_surface = build_admittance_identify_surface(
        result_id="char-demo",
        surface=surface,
        applied_tags=(
            CharacterizationAppliedTag(
                artifact_id=identify_artifact.artifact_id,
                source_parameter="lowest_observed_frequency_ghz",
                designated_metric="lowest_observed_frequency_ghz",
                designated_metric_label="Lowest Observed Frequency",
                tagged_at="2026-03-30T10:00:00Z",
            ),
        ),
    )

    assert identify_artifact.artifact_id == "char-demo:identify-summary"
    assert identify_surface.source_parameters[0].artifact_id == identify_artifact.artifact_id
    assert identify_surface.source_parameters[0].current_designated_metric == (
        "lowest_observed_frequency_ghz"
    )
    assert identify_surface.designated_metrics[0].metric_key == "lowest_observed_frequency_ghz"
