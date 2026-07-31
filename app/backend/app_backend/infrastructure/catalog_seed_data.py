from app_backend.domain.admittance_result_contract import (
    AdmittanceResultMember,
    AdmittanceResultSurface,
    annotate_admittance_artifact_refs,
    build_admittance_artifact_refs,
    build_admittance_identify_surface,
    summarize_admittance_surface,
)
from app_backend.domain.circuit_definitions import (
    CircuitDefinitionRecord,
)
from app_backend.domain.datasets import (
    CharacterizationAnalysisRegistryRow,
    CharacterizationAnalysisTraceCompatibility,
    CharacterizationAppliedTag,
    CharacterizationArtifactRef,
    CharacterizationDesignatedMetricOption,
    CharacterizationDiagnostic,
    CharacterizationIdentifySurface,
    CharacterizationResultDetail,
    CharacterizationResultSummary,
    CharacterizationRunHistoryRow,
    CharacterizationSourceParameterOption,
    DatasetAllowedActions,
    DatasetDetail,
    DesignBrowseRow,
    TraceAxis,
    TraceDetail,
    TraceMetadataSummary,
)
from app_backend.infrastructure.persistence.circuit_definition_repository import (
    build_circuit_definition_record,
)
from app_backend.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)

LOCAL_SPACE_RESONATOR_DEFINITION_ID = "c8f08463-bf18-4f8e-a5d5-735f3d7b0d6e"
FLOATING_QUBIT_WITH_XY_LINE_DEFINITION_ID = "8f2e5b78-7d1f-4c4f-9f3a-4be4f9e63211"
FLUXONIUM_READOUT_CHAIN_DEFINITION_ID = "3c412c9f-3304-4efe-9f7f-1d0c9a2b7d44"
COUPLER_DETUNING_DEMO_DEFINITION_ID = "f4b9ac3e-8ef1-4a8d-b7ae-6f9d24804d1a"


def build_seed_datasets() -> tuple[DatasetDetail, ...]:
    return (
        DatasetDetail(
            dataset_id="local-dataset-001",
            name="Local Space Flux Sandbox",
            family="Fluxonium",
            owner="Local Space",
            owner_user_id="local-operator",
            workspace_id="local-space",
            visibility_scope="local",
            lifecycle_state="active",
            updated_at="2026-03-17T08:30:00Z",
            device_type="Fluxonium",
            capabilities=("characterization", "simulation_review", "local_runtime"),
            source="manual",
            status="Ready",
            allowed_actions=DatasetAllowedActions(
                select=True,
                update_profile=True,
                publish=False,
                archive=True,
            ),
        ),
        DatasetDetail(
            dataset_id="fluxonium-2025-031",
            name="Fluxonium sweep 031",
            family="Fluxonium",
            owner="Device Lab",
            owner_user_id="researcher-01",
            workspace_id="ws-device-lab",
            visibility_scope="private",
            lifecycle_state="active",
            updated_at="2026-03-14T10:20:00Z",
            device_type="Fluxonium",
            capabilities=("characterization", "simulation_review"),
            source="inferred",
            status="Ready",
            allowed_actions=DatasetAllowedActions(
                select=True,
                update_profile=True,
                publish=True,
                archive=True,
            ),
        ),
        DatasetDetail(
            dataset_id="resonator-chip-002",
            name="Readout resonator validation 002",
            family="Resonator",
            owner="Device Lab",
            owner_user_id="researcher-02",
            workspace_id="ws-device-lab",
            visibility_scope="workspace",
            lifecycle_state="active",
            updated_at="2026-03-13T16:45:00Z",
            device_type="Resonator",
            capabilities=("measurement_review",),
            source="manual",
            status="Queued",
            allowed_actions=DatasetAllowedActions(
                select=True,
                update_profile=True,
                publish=False,
                archive=True,
            ),
        ),
        DatasetDetail(
            dataset_id="transmon-coupler-014",
            name="Coupler detuning 014",
            family="Transmon",
            owner="Modeling",
            owner_user_id="modeler-07",
            workspace_id="ws-modeling",
            visibility_scope="workspace",
            lifecycle_state="active",
            updated_at="2026-03-14T09:10:00Z",
            device_type="Transmon",
            capabilities=("cross-resonance",),
            source="imported",
            status="Review",
            allowed_actions=DatasetAllowedActions(
                select=True,
                update_profile=True,
                publish=False,
                archive=False,
            ),
        ),
    )


def build_seed_designs() -> dict[str, tuple[DesignBrowseRow, ...]]:
    return {
        "local-dataset-001": (
            DesignBrowseRow(
                design_id="design_local_flux_playground",
                dataset_id="local-dataset-001",
                name="Local Flux Playground",
                source_coverage={"measurement": 1, "circuit_simulation": 1},
                compare_readiness="ready",
                trace_count=2,
                updated_at="2026-03-17T08:35:00Z",
            ),
        ),
        "fluxonium-2025-031": (
            DesignBrowseRow(
                design_id="design_flux_scan_a",
                dataset_id="fluxonium-2025-031",
                name="Flux Scan A",
                source_coverage={"measurement": 2, "layout_simulation": 1},
                compare_readiness="ready",
                trace_count=3,
                updated_at="2026-03-14T10:24:00Z",
            ),
            DesignBrowseRow(
                design_id="design_flux_scan_b",
                dataset_id="fluxonium-2025-031",
                name="Flux Scan B",
                source_coverage={"measurement": 1},
                compare_readiness="inspect_only",
                trace_count=1,
                updated_at="2026-03-14T09:50:00Z",
            ),
        ),
        "resonator-chip-002": (
            DesignBrowseRow(
                design_id="design_resonator_temp",
                dataset_id="resonator-chip-002",
                name="Temperature Sweep",
                source_coverage={"measurement": 1},
                compare_readiness="blocked",
                trace_count=1,
                updated_at="2026-03-13T16:00:00Z",
            ),
        ),
        "transmon-coupler-014": (
            DesignBrowseRow(
                design_id="design_coupler_detuning",
                dataset_id="transmon-coupler-014",
                name="Coupler Detuning",
                source_coverage={"circuit_simulation": 1, "measurement": 1},
                compare_readiness="ready",
                trace_count=2,
                updated_at="2026-03-14T09:20:00Z",
            ),
        ),
    }


def build_seed_trace_summaries() -> dict[tuple[str, str], tuple[TraceMetadataSummary, ...]]:
    return {
        (
            "local-dataset-001",
            "design_local_flux_playground",
        ): (
            TraceMetadataSummary(
                trace_id="trace_local_flux_measurement",
                dataset_id="local-dataset-001",
                design_id="design_local_flux_playground",
                family="y_matrix",
                parameter="Y11",
                representation="imaginary",
                trace_mode_group="base",
                source_kind="measurement",
                stage_kind="postprocess",
                provenance_summary="Local Measurement · Post-Processed · batch #1",
            ),
            TraceMetadataSummary(
                trace_id="trace_local_flux_preview",
                dataset_id="local-dataset-001",
                design_id="design_local_flux_playground",
                family="y_matrix",
                parameter="Y11",
                representation="imaginary",
                trace_mode_group="base",
                source_kind="circuit_simulation",
                stage_kind="raw",
                provenance_summary="Local Runtime · Raw · preview batch",
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
        ): (
            TraceMetadataSummary(
                trace_id="trace_flux_a_measurement",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                family="y_matrix",
                parameter="Y11",
                representation="imaginary",
                trace_mode_group="base",
                source_kind="measurement",
                stage_kind="postprocess",
                provenance_summary="Measurement · Post-Processed · batch #4",
            ),
            TraceMetadataSummary(
                trace_id="trace_flux_a_layout",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                family="y_matrix",
                parameter="Y11",
                representation="imaginary",
                trace_mode_group="base",
                source_kind="layout_simulation",
                stage_kind="raw",
                provenance_summary="Layout Simulation · Raw · batch #2",
            ),
            TraceMetadataSummary(
                trace_id="trace_flux_a_phase",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                family="y_matrix",
                parameter="Y11",
                representation="phase",
                trace_mode_group="sideband",
                source_kind="measurement",
                stage_kind="postprocess",
                provenance_summary="Measurement · Phase Projection · batch #4",
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_b",
        ): (
            TraceMetadataSummary(
                trace_id="trace_flux_b_measurement",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_b",
                family="s_matrix",
                parameter="S21",
                representation="magnitude",
                trace_mode_group="base",
                source_kind="measurement",
                stage_kind="raw",
                provenance_summary="Measurement · Raw · batch #7",
            ),
        ),
        (
            "resonator-chip-002",
            "design_resonator_temp",
        ): (
            TraceMetadataSummary(
                trace_id="trace_res_temp_measurement",
                dataset_id="resonator-chip-002",
                design_id="design_resonator_temp",
                family="s_matrix",
                parameter="S21",
                representation="magnitude",
                trace_mode_group="base",
                source_kind="measurement",
                stage_kind="raw",
                provenance_summary="Measurement · Raw · batch #12",
            ),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
        ): (
            TraceMetadataSummary(
                trace_id="trace_coupler_measurement",
                dataset_id="transmon-coupler-014",
                design_id="design_coupler_detuning",
                family="z_matrix",
                parameter="Z21",
                representation="real",
                trace_mode_group="base",
                source_kind="measurement",
                stage_kind="postprocess",
                provenance_summary="Measurement · Fit Input · batch #12",
            ),
            TraceMetadataSummary(
                trace_id="trace_coupler_simulation",
                dataset_id="transmon-coupler-014",
                design_id="design_coupler_detuning",
                family="z_matrix",
                parameter="Z21",
                representation="real",
                trace_mode_group="base",
                source_kind="circuit_simulation",
                stage_kind="raw",
                provenance_summary="Circuit Simulation · Raw · batch #5",
            ),
        ),
    }


def build_seed_trace_details() -> dict[tuple[str, str, str], TraceDetail]:
    return {
        (
            "local-dataset-001",
            "design_local_flux_playground",
            "trace_local_flux_measurement",
        ): TraceDetail(
            trace_id="trace_local_flux_measurement",
            dataset_id="local-dataset-001",
            design_id="design_local_flux_playground",
            axes=(TraceAxis(name="frequency", unit="GHz", length=51),),
            preview_payload={
                "kind": "series",
                "parameter": "Y11",
                "default_parameter": "Y11",
                "history_steps": [
                    "Measurement",
                    "PTC",
                    "Coordinate Transformation",
                    "Kron Reduction",
                ],
                "history_summary": (
                    "Measurement -> PTC -> Coordinate Transformation -> Kron Reduction"
                ),
                "points": _build_interpolated_series_points(
                    anchors=((4.82, 0.13), (5.01, 0.16), (5.19, 0.12)),
                    length=51,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/local-dataset-001/designs/design_local_flux_playground/measurement.zarr",
                store_uri="trace_store/local/local-dataset-001/design_local_flux_playground/measurement.zarr",
                group_path="/traces/trace_local_flux_measurement",
                array_path="values",
                dtype="float64",
                shape=(51,),
                chunk_shape=(51,),
            ),
            result_handles=(),
        ),
        (
            "local-dataset-001",
            "design_local_flux_playground",
            "trace_local_flux_preview",
        ): TraceDetail(
            trace_id="trace_local_flux_preview",
            dataset_id="local-dataset-001",
            design_id="design_local_flux_playground",
            axes=(TraceAxis(name="frequency", unit="GHz", length=51),),
            preview_payload={
                "kind": "series",
                "parameter": "Y11",
                "default_parameter": "Y11",
                "history_steps": ["Raw"],
                "history_summary": "Raw",
                "points": _build_interpolated_series_points(
                    anchors=((4.8, 0.11), (5.0, 0.13), (5.2, 0.1)),
                    length=51,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/local-dataset-001/designs/design_local_flux_playground/preview.zarr",
                store_uri="trace_store/local/local-dataset-001/design_local_flux_playground/preview.zarr",
                group_path="/traces/trace_local_flux_preview",
                array_path="values",
                dtype="float64",
                shape=(51,),
                chunk_shape=(51,),
            ),
            result_handles=(),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "trace_flux_a_measurement",
        ): TraceDetail(
            trace_id="trace_flux_a_measurement",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_a",
            axes=(TraceAxis(name="frequency", unit="GHz", length=401),),
            preview_payload={
                "kind": "series",
                "parameter": "Y11",
                "default_parameter": "Y11",
                "history_steps": ["Measurement", "Post-Processed"],
                "history_summary": "Measurement -> Post-Processed",
                "points": _build_interpolated_series_points(
                    anchors=((5.71, 0.013), (5.78, 0.018), (5.84, 0.015)),
                    length=401,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/fluxonium-2025-031/designs/design_flux_scan_a/batches/batch_4.zarr",
                store_uri="trace_store/datasets/fluxonium-2025-031/designs/design_flux_scan_a/batches/batch_4.zarr",
                group_path="/traces/trace_flux_a_measurement",
                array_path="values",
                dtype="float64",
                shape=(401,),
                chunk_shape=(401,),
            ),
            result_handles=(
                build_result_handle_ref(
                    handle_id="result:fluxonium-2025-031:fit-summary",
                    kind="fit_summary",
                    status="materialized",
                    label="Fluxonium fit summary",
                    metadata_record=build_metadata_record_ref(
                        "result_handle",
                        "result_handle:501",
                        version=2,
                    ),
                    payload_backend="json_artifact",
                    payload_format="json",
                    payload_role="report_artifact",
                    payload_locator="artifacts/fit-summary.json",
                    provenance_task_id=303,
                    provenance=build_result_provenance_ref(
                        source_dataset_id="fluxonium-2025-031",
                        source_task_id=303,
                        trace_batch_record=build_metadata_record_ref(
                            "trace_batch",
                            "trace_batch:88",
                            version=1,
                        ),
                    ),
                ),
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "trace_flux_a_layout",
        ): TraceDetail(
            trace_id="trace_flux_a_layout",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_a",
            axes=(TraceAxis(name="frequency", unit="GHz", length=401),),
            preview_payload={
                "kind": "series",
                "parameter": "Y11",
                "default_parameter": "Y11",
                "history_steps": ["Layout Simulation", "Raw"],
                "history_summary": "Layout Simulation -> Raw",
                "points": _build_interpolated_series_points(
                    anchors=((5.71, 0.011), (5.78, 0.017), (5.84, 0.014)),
                    length=401,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/fluxonium-2025-031/designs/design_flux_scan_a/batches/batch_2.zarr",
                store_uri="trace_store/datasets/fluxonium-2025-031/designs/design_flux_scan_a/batches/batch_2.zarr",
                group_path="/traces/trace_flux_a_layout",
                array_path="values",
                dtype="float64",
                shape=(401,),
                chunk_shape=(401,),
            ),
            result_handles=(),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "trace_flux_a_phase",
        ): TraceDetail(
            trace_id="trace_flux_a_phase",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_a",
            axes=(TraceAxis(name="frequency", unit="GHz", length=401),),
            preview_payload={
                "kind": "series",
                "parameter": "Y11",
                "default_parameter": "Y11",
                "history_steps": ["Measurement", "Phase Projection"],
                "history_summary": "Measurement -> Phase Projection",
                "points": _build_interpolated_series_points(
                    anchors=((5.71, -0.16), (5.78, -0.02), (5.84, 0.14)),
                    length=401,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/fluxonium-2025-031/designs/design_flux_scan_a/batches/batch_4_phase.zarr",
                store_uri="trace_store/datasets/fluxonium-2025-031/designs/design_flux_scan_a/batches/batch_4_phase.zarr",
                group_path="/traces/trace_flux_a_phase",
                array_path="values",
                dtype="float64",
                shape=(401,),
                chunk_shape=(401,),
            ),
            result_handles=(),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_b",
            "trace_flux_b_measurement",
        ): TraceDetail(
            trace_id="trace_flux_b_measurement",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_b",
            axes=(TraceAxis(name="frequency", unit="GHz", length=201),),
            preview_payload={
                "kind": "series",
                "parameter": "S21",
                "default_parameter": "S21",
                "history_steps": ["Measurement", "Raw"],
                "history_summary": "Measurement -> Raw",
                "points": _build_interpolated_series_points(
                    anchors=((6.1, 0.42), (6.18, 0.51), (6.24, 0.47)),
                    length=201,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/fluxonium-2025-031/designs/design_flux_scan_b/batches/batch_7.zarr",
                store_uri="trace_store/datasets/fluxonium-2025-031/designs/design_flux_scan_b/batches/batch_7.zarr",
                group_path="/traces/trace_flux_b_measurement",
                array_path="values",
                dtype="float64",
                shape=(201,),
                chunk_shape=(201,),
            ),
            result_handles=(),
        ),
        (
            "resonator-chip-002",
            "design_resonator_temp",
            "trace_res_temp_measurement",
        ): TraceDetail(
            trace_id="trace_res_temp_measurement",
            dataset_id="resonator-chip-002",
            design_id="design_resonator_temp",
            axes=(TraceAxis(name="temperature", unit="mK", length=31),),
            preview_payload={
                "kind": "series",
                "points": _build_interpolated_series_points(
                    anchors=((10, 0.91), (20, 0.88), (30, 0.81)),
                    length=31,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/resonator-chip-002/designs/design_resonator_temp/batches/batch_12.zarr",
                store_uri="trace_store/datasets/resonator-chip-002/designs/design_resonator_temp/batches/batch_12.zarr",
                group_path="/traces/trace_res_temp_measurement",
                array_path="values",
                dtype="float64",
                shape=(31,),
                chunk_shape=(31,),
            ),
            result_handles=(),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
            "trace_coupler_measurement",
        ): TraceDetail(
            trace_id="trace_coupler_measurement",
            dataset_id="transmon-coupler-014",
            design_id="design_coupler_detuning",
            axes=(TraceAxis(name="bias", unit="V", length=76),),
            preview_payload={
                "kind": "series",
                "points": _build_interpolated_series_points(
                    anchors=((-0.28, 11.2), (-0.265, 10.8), (-0.25, 10.4)),
                    length=76,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/transmon-coupler-014/designs/design_coupler_detuning/batches/batch_12.zarr",
                store_uri="trace_store/datasets/transmon-coupler-014/designs/design_coupler_detuning/batches/batch_12.zarr",
                group_path="/traces/trace_coupler_measurement",
                array_path="values",
                dtype="float64",
                shape=(76,),
                chunk_shape=(76,),
            ),
            result_handles=(
                build_result_handle_ref(
                    handle_id="result:transmon-coupler-014:characterization-report",
                    kind="characterization_report",
                    status="materialized",
                    label="Coupler characterization report",
                    metadata_record=build_metadata_record_ref(
                        "result_handle",
                        "result_handle:612",
                        version=3,
                    ),
                    payload_backend="markdown_artifact",
                    payload_format="markdown",
                    payload_role="report_artifact",
                    payload_locator="artifacts/fit-report.md",
                    provenance_task_id=305,
                    provenance=build_result_provenance_ref(
                        source_dataset_id="transmon-coupler-014",
                        source_task_id=305,
                        analysis_run_record=build_metadata_record_ref(
                            "analysis_run",
                            "analysis_run:12",
                            version=4,
                        ),
                    ),
                ),
            ),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
            "trace_coupler_simulation",
        ): TraceDetail(
            trace_id="trace_coupler_simulation",
            dataset_id="transmon-coupler-014",
            design_id="design_coupler_detuning",
            axes=(TraceAxis(name="bias", unit="V", length=76),),
            preview_payload={
                "kind": "series",
                "points": _build_interpolated_series_points(
                    anchors=((-0.28, 11.0), (-0.265, 10.7), (-0.25, 10.3)),
                    length=76,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/transmon-coupler-014/designs/design_coupler_detuning/batches/batch_5.zarr",
                store_uri="trace_store/datasets/transmon-coupler-014/designs/design_coupler_detuning/batches/batch_5.zarr",
                group_path="/traces/trace_coupler_simulation",
                array_path="values",
                dtype="float64",
                shape=(76,),
                chunk_shape=(76,),
            ),
            result_handles=(),
        ),
    }


def _build_interpolated_series_points(
    *,
    anchors: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
    length: int,
) -> list[list[float]]:
    if length <= 1:
        return [[round(anchors[0][0], 6), round(anchors[0][1], 6)]]

    start, middle, end = anchors
    middle_index = length // 2
    last_index = length - 1

    def _interpolate(
        left: tuple[float, float],
        right: tuple[float, float],
        ratio: float,
    ) -> list[float]:
        x = left[0] + ((right[0] - left[0]) * ratio)
        y = left[1] + ((right[1] - left[1]) * ratio)
        return [round(x, 6), round(y, 6)]

    points: list[list[float]] = []
    for index in range(length):
        if index <= middle_index:
            ratio = 0.0 if middle_index == 0 else index / middle_index
            points.append(_interpolate(start, middle, ratio))
            continue
        ratio = (index - middle_index) / max(last_index - middle_index, 1)
        points.append(_interpolate(middle, end, ratio))
    return points


def build_seed_characterization_analysis_registry() -> dict[
    tuple[str, str],
    tuple[CharacterizationAnalysisRegistryRow, ...],
]:
    return {
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
        ): (
            CharacterizationAnalysisRegistryRow(
                analysis_id="admittance_extraction",
                label="Admittance Resonance Extraction",
                availability_state="unavailable",
                required_config_fields=("fit_window", "residual_tolerance"),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=2,
                    selected_trace_count=0,
                    recommended_trace_modes=("base",),
                    summary="2 design traces are eligible for admittance resonance extraction.",
                ),
            ),
            CharacterizationAnalysisRegistryRow(
                analysis_id="sideband_comparison",
                label="Sideband Comparison",
                availability_state="available",
                required_config_fields=("comparison_window",),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=1,
                    selected_trace_count=0,
                    recommended_trace_modes=("sideband",),
                    summary="1 design trace is eligible for sideband comparison.",
                ),
            ),
            CharacterizationAnalysisRegistryRow(
                analysis_id="junction_parameter_identification",
                label="Junction Parameter Identification",
                availability_state="unavailable",
                required_config_fields=("fit_window", "prior_family"),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=0,
                    selected_trace_count=0,
                    recommended_trace_modes=("base", "sideband"),
                    summary=(
                        "No compatible trace bundle currently satisfies the "
                        "identification prerequisites."
                    ),
                ),
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_b",
        ): (
            CharacterizationAnalysisRegistryRow(
                analysis_id="screening_summary",
                label="Screening Summary",
                availability_state="available",
                required_config_fields=("screening_mode",),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=1,
                    selected_trace_count=0,
                    recommended_trace_modes=("base",),
                    summary="1 design trace is eligible for screening summary.",
                ),
            ),
            CharacterizationAnalysisRegistryRow(
                analysis_id="sideband_comparison",
                label="Sideband Comparison",
                availability_state="unavailable",
                required_config_fields=("comparison_window",),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=0,
                    selected_trace_count=0,
                    recommended_trace_modes=("sideband",),
                    summary="No sideband trace is available in this design scope yet.",
                ),
            ),
        ),
        (
            "resonator-chip-002",
            "design_resonator_temp",
        ): (
            CharacterizationAnalysisRegistryRow(
                analysis_id="quality_factor_fit",
                label="Quality Factor Fit",
                availability_state="recommended",
                required_config_fields=("temperature_window",),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=1,
                    selected_trace_count=0,
                    recommended_trace_modes=("base",),
                    summary="1 design trace is eligible for quality factor fit.",
                ),
            ),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
        ): (
            CharacterizationAnalysisRegistryRow(
                analysis_id="coupler_shift_fit",
                label="Coupler Shift Fit",
                availability_state="recommended",
                required_config_fields=("fit_window", "cross_check_mode"),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=2,
                    selected_trace_count=0,
                    recommended_trace_modes=("base",),
                    summary="2 design traces are eligible for coupler shift fit.",
                ),
            ),
        ),
    }


def build_seed_characterization_run_history() -> dict[
    tuple[str, str],
    tuple[CharacterizationRunHistoryRow, ...],
]:
    return {
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
        ): (
            CharacterizationRunHistoryRow(
                run_id="run-flux-a-004",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                analysis_id="sideband_comparison",
                label="Flux Scan A sideband comparison",
                status="failed",
                scope="design_traces",
                trace_count=1,
                sources_summary="Y phase 1",
                provenance_summary="Measurement sideband trace · batch #4",
                updated_at="2026-03-14T11:20:00Z",
                result_id="char-sideband-flux-a-02",
            ),
            CharacterizationRunHistoryRow(
                run_id="run-flux-a-003",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                analysis_id="admittance_extraction",
                label="Flux Scan A admittance resonance extraction",
                status="completed",
                scope="design_traces",
                trace_count=2,
                sources_summary="Y base 2",
                provenance_summary="Measurement batch #4 + layout batch #2",
                updated_at="2026-03-14T11:12:00Z",
                result_id="char-fit-flux-a-01",
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_b",
        ): (
            CharacterizationRunHistoryRow(
                run_id="run-flux-b-001",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_b",
                analysis_id="screening_summary",
                label="Flux Scan B screening summary",
                status="blocked",
                scope="design_traces",
                trace_count=1,
                sources_summary="S21 1",
                provenance_summary="Measurement raw trace · batch #7",
                updated_at="2026-03-14T09:54:00Z",
                result_id="char-flux-b-screening",
            ),
        ),
        (
            "resonator-chip-002",
            "design_resonator_temp",
        ): (
            CharacterizationRunHistoryRow(
                run_id="run-res-temp-002",
                dataset_id="resonator-chip-002",
                design_id="design_resonator_temp",
                analysis_id="quality_factor_fit",
                label="Temperature sweep quality factor fit",
                status="completed",
                scope="design_traces",
                trace_count=1,
                sources_summary="Temperature sweep 1",
                provenance_summary="Measurement batch #12",
                updated_at="2026-03-13T18:00:00Z",
                result_id="char-resonator-temp-qi",
            ),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
        ): (
            CharacterizationRunHistoryRow(
                run_id="run-coupler-011",
                dataset_id="transmon-coupler-014",
                design_id="design_coupler_detuning",
                analysis_id="coupler_shift_fit",
                label="Coupler detuning chi fit",
                status="completed",
                scope="design_traces",
                trace_count=2,
                sources_summary="Measurement 1 + simulation 1",
                provenance_summary="Measurement + simulation cross-check",
                updated_at="2026-03-14T09:35:00Z",
                result_id="char-coupler-detuning-chi",
            ),
        ),
    }


def build_seed_characterization_results() -> dict[
    tuple[str, str],
    tuple[CharacterizationResultSummary, ...],
]:
    return {
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
        ): (
            CharacterizationResultSummary(
                result_id="char-fit-flux-a-01",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                analysis_id="admittance_extraction",
                title="Flux Scan A admittance resonance extraction",
                status="completed",
                freshness_summary="Materialized 14 minutes ago",
                provenance_summary="Measurement batch #4 + layout batch #2",
                trace_count=2,
                artifact_count=3,
                updated_at="2026-03-14T11:12:00Z",
            ),
            CharacterizationResultSummary(
                result_id="char-sideband-flux-a-02",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                analysis_id="sideband_comparison",
                title="Flux Scan A sideband comparison",
                status="failed",
                freshness_summary="Failed 6 minutes ago",
                provenance_summary="Measurement phase trace only",
                trace_count=1,
                artifact_count=1,
                updated_at="2026-03-14T11:20:00Z",
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_b",
        ): (
            CharacterizationResultSummary(
                result_id="char-flux-b-screening",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_b",
                analysis_id="screening_summary",
                title="Flux Scan B screening summary",
                status="blocked",
                freshness_summary="Awaiting compatible trace bundle",
                provenance_summary="Single measurement trace only",
                trace_count=1,
                artifact_count=0,
                updated_at="2026-03-14T09:54:00Z",
            ),
        ),
        (
            "resonator-chip-002",
            "design_resonator_temp",
        ): (
            CharacterizationResultSummary(
                result_id="char-resonator-temp-qi",
                dataset_id="resonator-chip-002",
                design_id="design_resonator_temp",
                analysis_id="quality_factor_fit",
                title="Temperature sweep quality factor fit",
                status="completed",
                freshness_summary="Materialized 2 hours ago",
                provenance_summary="Measurement batch #12",
                trace_count=1,
                artifact_count=2,
                updated_at="2026-03-13T18:00:00Z",
            ),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
        ): (
            CharacterizationResultSummary(
                result_id="char-coupler-detuning-chi",
                dataset_id="transmon-coupler-014",
                design_id="design_coupler_detuning",
                analysis_id="coupler_shift_fit",
                title="Coupler detuning chi fit",
                status="completed",
                freshness_summary="Materialized 38 minutes ago",
                provenance_summary="Measurement + simulation cross-check",
                trace_count=2,
                artifact_count=3,
                updated_at="2026-03-14T09:35:00Z",
            ),
        ),
    }


def build_seed_characterization_result_details() -> dict[
    tuple[str, str, str],
    CharacterizationResultDetail,
]:
    return {
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "char-fit-flux-a-01",
        ): CharacterizationResultDetail(
            result_id="char-fit-flux-a-01",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_a",
            analysis_id="admittance_extraction",
            title="Flux Scan A admittance resonance extraction",
            status="completed",
            freshness_summary="Materialized 14 minutes ago",
            provenance_summary="Measurement batch #4 + layout batch #2",
            trace_count=2,
            updated_at="2026-03-14T11:12:00Z",
            input_trace_ids=("trace_flux_a_measurement", "trace_flux_a_layout"),
            payload=summarize_admittance_surface(
                analysis_run_id=101,
                analysis_config={
                    "fit_window": [5.4, 6.0],
                    "residual_tolerance": 0.02,
                },
                surface=_seed_admittance_flux_scan_a_surface(),
            ),
            diagnostics=_seed_admittance_flux_scan_a_surface().diagnostics,
            artifact_refs=annotate_admittance_artifact_refs(
                build_admittance_artifact_refs(result_id="char-fit-flux-a-01"),
                _seed_admittance_flux_scan_a_surface(),
            ),
            identify_surface=build_admittance_identify_surface(
                result_id="char-fit-flux-a-01",
                surface=_seed_admittance_flux_scan_a_surface(),
                applied_tags=(
                    CharacterizationAppliedTag(
                        artifact_id="char-fit-flux-a-01:identify-summary",
                        source_parameter="lowest_observed_frequency_ghz",
                        designated_metric="lowest_observed_frequency_ghz",
                        designated_metric_label="Lowest Observed Frequency",
                        tagged_at="2026-03-14T11:05:00Z",
                    ),
                    CharacterizationAppliedTag(
                        artifact_id="char-fit-flux-a-01:identify-summary",
                        source_parameter="residual_rms_max",
                        designated_metric="residual_rms_max",
                        designated_metric_label="Max Residual RMS",
                        tagged_at="2026-03-14T11:08:00Z",
                    ),
                ),
            ),
            downstream_unlock_analysis_ids=("admittance_member_fit",),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "char-sideband-flux-a-02",
        ): CharacterizationResultDetail(
            result_id="char-sideband-flux-a-02",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_a",
            analysis_id="sideband_comparison",
            title="Flux Scan A sideband comparison",
            status="failed",
            freshness_summary="Failed 6 minutes ago",
            provenance_summary="Measurement phase trace only",
            trace_count=1,
            updated_at="2026-03-14T11:20:00Z",
            input_trace_ids=("trace_flux_a_phase",),
            payload={
                "comparison_window": {"center": 5.81, "unit": "GHz"},
                "failure_summary": "Sideband peaks fell below the comparison threshold.",
            },
            diagnostics=(
                CharacterizationDiagnostic(
                    severity="error",
                    code="sideband_peak_missing",
                    message="No stable sideband peak was detected in the selected trace bundle.",
                    blocking=True,
                ),
            ),
            artifact_refs=(
                CharacterizationArtifactRef(
                    artifact_id="artifact-sideband-report-flux-a-02",
                    category="report",
                    view_kind="text",
                    title="Failure report",
                    payload_format="markdown",
                    payload_locator="artifacts/characterization/flux-a-sideband-report.md",
                ),
            ),
            identify_surface=_build_identify_surface(
                source_parameters=(),
                designated_metrics=(
                    CharacterizationDesignatedMetricOption(
                        metric_key="sideband_offset",
                        label="Sideband Offset",
                    ),
                ),
                applied_tags=(),
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_b",
            "char-flux-b-screening",
        ): CharacterizationResultDetail(
            result_id="char-flux-b-screening",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_b",
            analysis_id="screening_summary",
            title="Flux Scan B screening summary",
            status="blocked",
            freshness_summary="Awaiting compatible trace bundle",
            provenance_summary="Single measurement trace only",
            trace_count=1,
            updated_at="2026-03-14T09:54:00Z",
            input_trace_ids=("trace_flux_b_measurement",),
            payload={
                "blocking_reason": (
                    "At least one comparison trace is required before "
                    "screening can produce persisted artifacts."
                ),
            },
            diagnostics=(
                CharacterizationDiagnostic(
                    severity="warning",
                    code="trace_selection_incomplete",
                    message=(
                        "The selected design scope does not yet expose a "
                        "compatible comparison pair."
                    ),
                    blocking=True,
                ),
            ),
            artifact_refs=(),
            identify_surface=_build_identify_surface(
                source_parameters=(),
                designated_metrics=(),
                applied_tags=(),
            ),
        ),
        (
            "resonator-chip-002",
            "design_resonator_temp",
            "char-resonator-temp-qi",
        ): CharacterizationResultDetail(
            result_id="char-resonator-temp-qi",
            dataset_id="resonator-chip-002",
            design_id="design_resonator_temp",
            analysis_id="quality_factor_fit",
            title="Temperature sweep quality factor fit",
            status="completed",
            freshness_summary="Materialized 2 hours ago",
            provenance_summary="Measurement batch #12",
            trace_count=1,
            updated_at="2026-03-13T18:00:00Z",
            input_trace_ids=("trace_res_temp_measurement",),
            payload={
                "fit_table": [
                    {"parameter": "Qi_low_temp", "value": 18200, "unit": ""},
                    {"parameter": "Qi_high_temp", "value": 13100, "unit": ""},
                ],
            },
            diagnostics=(),
            artifact_refs=(
                CharacterizationArtifactRef(
                    artifact_id="artifact-resonator-temp-table",
                    category="fit_table",
                    view_kind="table",
                    title="Quality factor table",
                    payload_format="json",
                    payload_locator="artifacts/characterization/resonator-temp-fit-table.json",
                ),
                CharacterizationArtifactRef(
                    artifact_id="artifact-resonator-temp-plot",
                    category="plot",
                    view_kind="plot",
                    title="Temperature fit plot",
                    payload_format="svg",
                    payload_locator="artifacts/characterization/resonator-temp-fit-plot.svg",
                ),
            ),
            identify_surface=_build_identify_surface(
                source_parameters=(
                    CharacterizationSourceParameterOption(
                        artifact_id="artifact-resonator-temp-table",
                        source_parameter="Qi_low_temp",
                        label="Qi low temp",
                        artifact_title="Quality factor table",
                        current_designated_metric=None,
                    ),
                    CharacterizationSourceParameterOption(
                        artifact_id="artifact-resonator-temp-table",
                        source_parameter="Qi_high_temp",
                        label="Qi high temp",
                        artifact_title="Quality factor table",
                        current_designated_metric=None,
                    ),
                ),
                designated_metrics=(
                    CharacterizationDesignatedMetricOption(
                        metric_key="qi_low_temp",
                        label="Low Temperature Qi",
                    ),
                    CharacterizationDesignatedMetricOption(
                        metric_key="qi_high_temp",
                        label="High Temperature Qi",
                    ),
                    CharacterizationDesignatedMetricOption(
                        metric_key="thermal_rolloff",
                        label="Thermal Rolloff",
                    ),
                ),
                applied_tags=(),
            ),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
            "char-coupler-detuning-chi",
        ): CharacterizationResultDetail(
            result_id="char-coupler-detuning-chi",
            dataset_id="transmon-coupler-014",
            design_id="design_coupler_detuning",
            analysis_id="coupler_shift_fit",
            title="Coupler detuning chi fit",
            status="completed",
            freshness_summary="Materialized 38 minutes ago",
            provenance_summary="Measurement + simulation cross-check",
            trace_count=2,
            updated_at="2026-03-14T09:35:00Z",
            input_trace_ids=("trace_coupler_measurement", "trace_coupler_simulation"),
            payload={
                "fit_table": [
                    {"parameter": "chi", "value": 2.31, "unit": "MHz"},
                    {"parameter": "detuning_zero", "value": -0.247, "unit": "V"},
                ],
                "cross_check": {
                    "measurement_peak": 10.8,
                    "simulation_peak": 10.7,
                },
            },
            diagnostics=(
                CharacterizationDiagnostic(
                    severity="info",
                    code="simulation_cross_check_passed",
                    message="Simulation-backed cross-check stayed within tolerance.",
                    blocking=False,
                ),
            ),
            artifact_refs=(
                CharacterizationArtifactRef(
                    artifact_id="artifact-coupler-fit-table",
                    category="fit_table",
                    view_kind="table",
                    title="Chi fit table",
                    payload_format="json",
                    payload_locator="artifacts/characterization/coupler-fit-table.json",
                ),
                CharacterizationArtifactRef(
                    artifact_id="artifact-coupler-fit-plot",
                    category="plot",
                    view_kind="plot",
                    title="Detuning fit plot",
                    payload_format="svg",
                    payload_locator="artifacts/characterization/coupler-fit-plot.svg",
                ),
                CharacterizationArtifactRef(
                    artifact_id="artifact-coupler-report",
                    category="report",
                    view_kind="text",
                    title="Research summary",
                    payload_format="markdown",
                    payload_locator="artifacts/characterization/coupler-report.md",
                ),
            ),
            identify_surface=_build_identify_surface(
                source_parameters=(
                    CharacterizationSourceParameterOption(
                        artifact_id="artifact-coupler-fit-table",
                        source_parameter="chi",
                        label="chi",
                        artifact_title="Chi fit table",
                        current_designated_metric="chi",
                    ),
                    CharacterizationSourceParameterOption(
                        artifact_id="artifact-coupler-fit-table",
                        source_parameter="detuning_zero",
                        label="Detuning zero",
                        artifact_title="Chi fit table",
                        current_designated_metric=None,
                    ),
                ),
                designated_metrics=(
                    CharacterizationDesignatedMetricOption(
                        metric_key="chi",
                        label="Coupler Shift",
                    ),
                    CharacterizationDesignatedMetricOption(
                        metric_key="detuning_zero",
                        label="Zero Detuning Bias",
                    ),
                ),
                applied_tags=(
                    CharacterizationAppliedTag(
                        artifact_id="artifact-coupler-fit-table",
                        source_parameter="chi",
                        designated_metric="chi",
                        designated_metric_label="Coupler Shift",
                        tagged_at="2026-03-14T09:30:00Z",
                    ),
                ),
            ),
        ),
    }


def build_seed_characterization_artifact_surfaces() -> dict[
    tuple[str, str, str],
    AdmittanceResultSurface,
]:
    return {
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "char-fit-flux-a-01",
        ): _seed_admittance_flux_scan_a_surface(),
    }


def _seed_admittance_flux_scan_a_surface() -> AdmittanceResultSurface:
    return AdmittanceResultSurface(
        input_axis_key="flux_bias",
        input_axis_label="Flux bias",
        input_axis_unit="mA",
        input_axis_values=(7.4, 7.6, 7.8),
        members=(
            AdmittanceResultMember(
                member_key="measurement:trace_flux_a_measurement",
                label="measurement · admittance (complex)",
                trace_id="trace_flux_a_measurement",
                source_kind="measurement",
                trace_mode_group="base",
                parameter="admittance",
                representation="complex",
                provenance_summary="Measurement batch #4",
            ),
            AdmittanceResultMember(
                member_key="layout_simulation:trace_flux_a_layout",
                label="layout simulation · admittance (complex)",
                trace_id="trace_flux_a_layout",
                source_kind="layout_simulation",
                trace_mode_group="base",
                parameter="admittance",
                representation="complex",
                provenance_summary="Layout batch #2",
            ),
        ),
        frequency_grid_by_member=(
            (
                (5.612, 5.846),
                (5.587, 5.821),
                (None, None),
            ),
            (
                (5.604, 5.839),
                (5.58, 5.814),
                (None, None),
            ),
        ),
        residual_rms_by_member=(
            (0.0118, 0.0131, None),
            (0.0109, 0.0124, None),
        ),
        fit_window_ghz=(5.4, 6.0),
        masked_input_indices_by_member=((2,), (2,)),
        diagnostics=(
            CharacterizationDiagnostic(
                severity="info",
                code="fit_residual_rms_evaluated",
                message=(
                    "All persisted input positions stay within the configured residual tolerance."
                ),
                blocking=False,
            ),
            CharacterizationDiagnostic(
                severity="warning",
                code="masked_input_positions_preserved",
                message=(
                    "1 input positions remained fully masked and were preserved "
                    "in the persisted result surface."
                ),
                blocking=False,
            ),
        ),
    )


def _build_identify_surface(
    *,
    source_parameters: tuple[CharacterizationSourceParameterOption, ...],
    designated_metrics: tuple[CharacterizationDesignatedMetricOption, ...],
    applied_tags: tuple[CharacterizationAppliedTag, ...],
) -> CharacterizationIdentifySurface:
    return CharacterizationIdentifySurface(
        source_parameters=source_parameters,
        designated_metrics=designated_metrics,
        applied_tags=applied_tags,
    )


def build_seed_circuit_definitions() -> tuple[CircuitDefinitionRecord, ...]:
    floating_qubit_source = """{
    "name": "FloatingQubitWithXYLine",
    "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
        {"name": "C1", "default": 100.0, "unit": "fF"},
        {"name": "Lj1", "default": 1000.0, "unit": "pH"},
        {"name": "C2", "default": 1000.0, "unit": "fF"}
    ],
    "topology": [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("C1", "1", "2", "C1"),
        ("Lj1", "2", "0", "Lj1"),
        ("C2", "2", "0", "C2")
    ]
}"""
    readout_chain_source = """{
    "name": "FluxoniumReadoutChain",
    "parameters": [
        {"name": "Lj", "default": 1000.0, "unit": "pH"},
        {"name": "Cj", "default": 1000.0, "unit": "fF"}
    ],
    "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
        {"name": "C1", "default": 100.0, "unit": "fF"},
        {"name": "Lj1", "value_ref": "Lj", "unit": "pH"},
        {"name": "C2", "value_ref": "Cj", "unit": "fF"}
    ],
    "topology": [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("C1", "1", "2", "C1"),
        ("Lj1", "2", "0", "Lj1"),
        ("C2", "2", "0", "C2")
    ]
}"""
    coupler_demo_source = """{
    "name": "CouplerDetuningDemo",
    "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
        {"name": "C1", "default": 80.0, "unit": "fF"},
        {"name": "Lj1", "default": 850.0, "unit": "pH"},
        {"name": "C2", "default": 950.0, "unit": "fF"}
    ],
    "topology": [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("C1", "1", "2", "C1"),
        ("Lj1", "2", "0", "Lj1"),
        ("C2", "2", "0", "C2")
    ]
}"""
    local_resonator_source = """{
    "name": "LocalSpaceResonator",
    "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
        {"name": "C1", "default": 120.0, "unit": "fF"},
        {"name": "L1", "default": 900.0, "unit": "pH"}
    ],
    "topology": [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("C1", "1", "2", "C1"),
        ("L1", "2", "0", "L1")
    ]
}"""
    return (
        build_circuit_definition_record(
            definition_id=LOCAL_SPACE_RESONATOR_DEFINITION_ID,
            workspace_id="local-space",
            visibility_scope="local",
            owner_user_id="local-operator",
            owner_display_name="Local Operator",
            name="LocalSpaceResonator",
            created_at="2026-03-17T08:15:00Z",
            updated_at="2026-03-17T08:15:00Z",
            concurrency_token=f"etag_{LOCAL_SPACE_RESONATOR_DEFINITION_ID}_1",
            source_text=local_resonator_source,
        ),
        build_circuit_definition_record(
            definition_id=FLOATING_QUBIT_WITH_XY_LINE_DEFINITION_ID,
            workspace_id="ws-device-lab",
            visibility_scope="private",
            owner_user_id="researcher-01",
            owner_display_name="Ari",
            name="FloatingQubitWithXYLine",
            created_at="2026-03-08T18:19:42Z",
            updated_at="2026-03-14T08:30:00Z",
            concurrency_token=f"etag_{FLOATING_QUBIT_WITH_XY_LINE_DEFINITION_ID}_3",
            source_text=floating_qubit_source,
        ),
        build_circuit_definition_record(
            definition_id=FLUXONIUM_READOUT_CHAIN_DEFINITION_ID,
            workspace_id="ws-device-lab",
            visibility_scope="workspace",
            owner_user_id="researcher-01",
            owner_display_name="Ari",
            name="FluxoniumReadoutChain",
            created_at="2026-03-05T11:14:03Z",
            updated_at="2026-03-14T07:42:00Z",
            concurrency_token=f"etag_{FLUXONIUM_READOUT_CHAIN_DEFINITION_ID}_2",
            source_text=readout_chain_source,
        ),
        build_circuit_definition_record(
            definition_id=COUPLER_DETUNING_DEMO_DEFINITION_ID,
            workspace_id="ws-device-lab",
            visibility_scope="workspace",
            owner_user_id="collaborator-02",
            owner_display_name="Device Lab",
            name="CouplerDetuningDemo",
            created_at="2026-02-25T09:43:18Z",
            updated_at="2026-03-13T16:10:00Z",
            concurrency_token=f"etag_{COUPLER_DETUNING_DEMO_DEFINITION_ID}_4",
            source_text=coupler_demo_source,
        ),
    )
