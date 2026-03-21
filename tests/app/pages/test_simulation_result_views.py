"""Tests for simulation result view helpers."""

import inspect
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import legacy.legacy_nicegui_archived.features.simulation.page as simulation_feature_page
import legacy.legacy_nicegui_archived.pages.simulation as simulation_page
from legacy.legacy_nicegui_archived.pages.simulation import (
    _POST_PROCESS_INPUT_Y_SOURCE_OPTIONS,
    _RAW_RESULT_MATRIX_SOURCE_OPTIONS_BY_FAMILY,
    _Z0_CONTROL_CLASSES,
    _Z0_CONTROL_PROPS,
    _build_compensated_simulation_sweep_payload,
    _build_post_processed_bundle_artifacts,
    _build_post_processed_result_payload,
    _build_post_processed_runtime_data_records,
    _build_post_processed_sweep_explorer_payload,
    _build_post_processed_y_data_records,
    _build_result_bundle_data_records,
    _build_s_parameter_data_records,
    _build_simulation_result_figure,
    _build_simulation_workflow_context_lines,
    _build_sweep_metric_rows,
    _build_sweep_result_bundle_data_records,
    _build_termination_compensation_plan,
    _build_trace_batch_data_records,
    _cached_trace_store_bundle_from_post_processed_runtime,
    _can_save_post_processed_results,
    _coordinate_weight_fields_editable,
    _decode_simulation_result_payload,
    _hash_schema_source,
    _hash_stable_json,
    _load_cached_simulation_result,
    _load_saved_post_process_setups_for_schema,
    _load_saved_setups_for_schema,
    _load_selected_post_process_setup_id,
    _matrix_element_name,
    _normalize_sweep_result_view_state,
    _normalize_sweep_setup_payload,
    _normalize_termination_mode,
    _normalize_termination_selected_ports,
    _normalized_simulation_setup_snapshot,
    _resolve_latest_persisted_post_processing_snapshot,
    _resolve_persisted_post_processing_input_snapshot,
    _resolved_sweep_point_count,
    _result_from_trace_store_bundle,
    _result_metric_options_for_family,
    _result_mode_options,
    _result_port_options,
    _result_trace_options_for_family,
    _save_saved_post_process_setups_for_schema,
    _save_saved_setups_for_schema,
    _save_selected_post_process_setup_id,
    _should_log_sweep_point_progress,
    _source_simulation_bundle_id_from_snapshot,
    _sweep_payload_port_options,
    _sweep_progress_log_step,
    _trace_batch_payload_from_snapshot,
    _trace_store_bundle_from_simulation_result,
    _TraceRecordAuthority,
    _TraceStoreAxis,
    _TraceStoreResultBundle,
    _ViewTraceStore,
)
from legacy.legacy_nicegui_archived.features.simulation.setup.manager import (
    delete_setup,
    rename_setup,
    save_setup_as,
)
from core.shared.persistence.models import CircuitRecord
from core.shared.persistence.trace_store import (
    LocalZarrTraceStoreBackend,
    get_trace_store_path,
)
from core.simulation.application.post_processing import (
    PortMatrixSweep,
    PortMatrixSweepPoint,
    PortMatrixSweepRun,
)
from core.simulation.application.run_simulation import (
    SimulationSweepAxis,
    SimulationSweepPointResult,
    SimulationSweepRun,
    simulation_sweep_run_from_payload,
    simulation_sweep_run_to_payload,
)
from core.simulation.application.trace_architecture import (
    TRACE_BATCH_BUNDLE_SCHEMA_KIND,
    IncrementalPostProcessedSweepWriter,
    IncrementalRawSimulationSweepWriter,
    build_post_processed_trace_specs,
    build_raw_simulation_trace_specs,
    load_raw_simulation_bundle,
    persist_trace_batch_bundle,
)
from core.simulation.domain.circuit import (
    DriveSourceConfig,
    FrequencyRange,
    SimulationConfig,
    SimulationResult,
)


def _sample_result() -> SimulationResult:
    return SimulationResult(
        frequencies_ghz=[4.9, 5.0, 5.1],
        s11_real=[0.2, 0.0, -0.2],
        s11_imag=[0.0, 0.1, 0.0],
        port_indices=[1, 2],
        mode_indices=[(0,), (1,)],
        s_parameter_real={
            "S11": [0.2, 0.0, -0.2],
            "S21": [1.5, 1.6, 1.7],
            "S22": [0.1, 0.1, 0.1],
        },
        s_parameter_imag={
            "S11": [0.0, 0.1, 0.0],
            "S21": [0.0, 0.0, 0.0],
            "S22": [0.0, 0.0, 0.0],
        },
        s_parameter_mode_real={
            "om=0|op=1|im=0|ip=1": [0.2, 0.0, -0.2],
            "om=0|op=2|im=0|ip=1": [1.5, 1.6, 1.7],
            "om=1|op=2|im=0|ip=1": [0.9, 1.0, 1.1],
            "om=0|op=2|im=0|ip=2": [0.1, 0.1, 0.1],
        },
        s_parameter_mode_imag={
            "om=0|op=1|im=0|ip=1": [0.0, 0.1, 0.0],
            "om=0|op=2|im=0|ip=1": [0.0, 0.0, 0.0],
            "om=1|op=2|im=0|ip=1": [0.1, 0.0, -0.1],
            "om=0|op=2|im=0|ip=2": [0.0, 0.0, 0.0],
        },
        z_parameter_mode_real={"om=0|op=2|im=0|ip=2": [100.0, 110.0, 120.0]},
        z_parameter_mode_imag={"om=0|op=2|im=0|ip=2": [0.0, 1.0, 2.0]},
        y_parameter_mode_real={"om=0|op=2|im=0|ip=2": [0.01, 0.009, 0.008]},
        y_parameter_mode_imag={"om=0|op=2|im=0|ip=2": [0.0, -0.001, -0.002]},
        qe_parameter_mode={"om=1|op=2|im=0|ip=1": [0.8, 0.82, 0.84]},
        qe_ideal_parameter_mode={"om=1|op=2|im=0|ip=1": [0.9, 0.91, 0.92]},
        cm_parameter_mode={"om=1|op=2": [1.0, 1.0, 1.0]},
    )


def _sample_post_processed_sweep_run() -> PortMatrixSweepRun:
    first_matrix = np.asarray(((1.0 + 0.0j, 0.0 + 0.0j), (0.0 + 0.0j, 2.0 + 0.0j)))
    second_matrix = np.asarray(((3.0 + 0.0j, 0.0 + 0.0j), (0.0 + 0.0j, 4.0 + 0.0j)))
    return PortMatrixSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="Lj", values=(900.0, 1100.0), unit="pH"),),
        points=(
            PortMatrixSweepPoint(
                point_index=0,
                axis_indices=(0,),
                axis_values={"Lj": 900.0},
                sweep=PortMatrixSweep(
                    mode=(0,),
                    labels=("1", "2"),
                    frequencies_ghz=(5.0, 5.2),
                    y_matrices=(first_matrix, first_matrix.copy()),
                    source_kind="y",
                ),
            ),
            PortMatrixSweepPoint(
                point_index=1,
                axis_indices=(1,),
                axis_values={"Lj": 1100.0},
                sweep=PortMatrixSweep(
                    mode=(0,),
                    labels=("1", "2"),
                    frequencies_ghz=(5.0, 5.2),
                    y_matrices=(second_matrix, second_matrix.copy()),
                    source_kind="y",
                ),
            ),
        ),
        representative_point_index=0,
    )


def _sample_transformed_post_processed_sweep_run() -> PortMatrixSweepRun:
    first_matrix = np.asarray(((1.0 + 0.0j, 0.2 + 0.0j), (0.3 + 0.0j, 2.0 + 0.0j)))
    second_matrix = np.asarray(((3.0 + 0.0j, 0.4 + 0.0j), (0.5 + 0.0j, 4.0 + 0.0j)))
    return PortMatrixSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="L_q", values=(10.0, 15.0), unit="nH"),),
        points=(
            PortMatrixSweepPoint(
                point_index=0,
                axis_indices=(0,),
                axis_values={"L_q": 10.0},
                sweep=PortMatrixSweep(
                    mode=(0,),
                    labels=("cm(1,2)", "dm(1,2)"),
                    frequencies_ghz=(4.8, 4.9),
                    y_matrices=(first_matrix, first_matrix.copy()),
                    source_kind="y",
                ),
            ),
            PortMatrixSweepPoint(
                point_index=1,
                axis_indices=(1,),
                axis_values={"L_q": 15.0},
                sweep=PortMatrixSweep(
                    mode=(0,),
                    labels=("cm(1,2)", "dm(1,2)"),
                    frequencies_ghz=(4.8, 4.9),
                    y_matrices=(second_matrix, second_matrix.copy()),
                    source_kind="y",
                ),
            ),
        ),
        representative_point_index=0,
    )


class _NoFullReadArray:
    """Array wrapper that fails when callers request a full ND read before slicing."""

    def __init__(self, values: list[list[float]] | np.ndarray) -> None:
        self._values = np.asarray(values, dtype=np.float64)
        self.keys: list[object] = []

    def __getitem__(self, key: object) -> np.ndarray:
        self.keys.append(key)
        normalized = key if isinstance(key, tuple) else (key,)
        if normalized and all(item == slice(None) for item in normalized):
            raise AssertionError("unexpected full-read before slice")
        return self._values[key]


def test_result_metric_options_for_family_exposes_multiple_result_families() -> None:
    assert "magnitude_db" in _result_metric_options_for_family("s")
    assert "gain_db" in _result_metric_options_for_family("gain")
    assert "magnitude" in _result_metric_options_for_family("impedance")
    assert "magnitude" in _result_metric_options_for_family("admittance")
    assert "linear" in _result_metric_options_for_family("qe")
    assert "value" in _result_metric_options_for_family("cm")
    assert "trajectory" in _result_metric_options_for_family("complex")


def test_result_trace_options_for_complex_family_supports_s_z_y_traces() -> None:
    trace_options = _result_trace_options_for_family("complex")

    assert trace_options == {
        "s": "S",
        "z": "Z",
        "y": "Y",
    }


def test_raw_result_view_matrix_source_options_cover_only_y_and_z() -> None:
    assert set(_RAW_RESULT_MATRIX_SOURCE_OPTIONS_BY_FAMILY) == {"admittance", "impedance"}
    assert _RAW_RESULT_MATRIX_SOURCE_OPTIONS_BY_FAMILY["admittance"] == {
        "raw": "Raw Y",
        "ptc": "PTC Y",
    }
    assert _RAW_RESULT_MATRIX_SOURCE_OPTIONS_BY_FAMILY["impedance"] == {
        "raw": "Raw Z",
        "ptc": "PTC Z",
    }
    assert _POST_PROCESS_INPUT_Y_SOURCE_OPTIONS == {"raw_y": "Raw Y", "ptc_y": "PTC Y"}


def test_result_port_options_follow_result_bundle() -> None:
    assert _result_port_options(_sample_result()) == {1: "1", 2: "2"}


def test_result_mode_options_follow_result_bundle() -> None:
    assert _result_mode_options(_sample_result()) == {
        "0": "Signal (0)",
        "1": "Sideband (1)",
    }


def test_build_simulation_result_figure_builds_impedance_view() -> None:
    figure = _build_simulation_result_figure(
        result=_sample_result(),
        view_family="impedance",
        metric="real",
        trace="z",
        output_mode=(0,),
        output_port=2,
        input_mode=(0,),
        input_port=2,
        reference_impedance_ohm=50.0,
        dark_mode=True,
    )

    assert figure.layout.title.text == "Z22 Real Part"
    assert figure.layout.yaxis.title.text == "Real (Ohm)"
    assert len(figure.data) == 1


def test_raw_result_figure_y_axis_title_updates_across_y_z_y_switches() -> None:
    result = _sample_result()
    fig_y_first = _build_simulation_result_figure(
        result=result,
        view_family="admittance",
        metric="real",
        trace="admittance",
        output_mode=(0,),
        output_port=2,
        input_mode=(0,),
        input_port=2,
        reference_impedance_ohm=50.0,
        dark_mode=True,
    )
    fig_z = _build_simulation_result_figure(
        result=result,
        view_family="impedance",
        metric="real",
        trace="impedance",
        output_mode=(0,),
        output_port=2,
        input_mode=(0,),
        input_port=2,
        reference_impedance_ohm=50.0,
        dark_mode=True,
    )
    fig_y_second = _build_simulation_result_figure(
        result=result,
        view_family="admittance",
        metric="real",
        trace="admittance",
        output_mode=(0,),
        output_port=2,
        input_mode=(0,),
        input_port=2,
        reference_impedance_ohm=50.0,
        dark_mode=True,
    )

    assert fig_y_first.layout.title.text == "Y22 Real Part"
    assert fig_y_first.layout.yaxis.title.text == "Real (S)"
    assert fig_z.layout.title.text == "Z22 Real Part"
    assert fig_z.layout.yaxis.title.text == "Real (Ohm)"
    assert fig_y_second.layout.title.text == "Y22 Real Part"
    assert fig_y_second.layout.yaxis.title.text == "Real (S)"


def test_build_simulation_result_figure_builds_complex_plane_view() -> None:
    figure = _build_simulation_result_figure(
        result=_sample_result(),
        view_family="complex",
        metric="trajectory",
        trace="y",
        output_mode=(0,),
        output_port=2,
        input_mode=(0,),
        input_port=2,
        reference_impedance_ohm=50.0,
        dark_mode=True,
    )

    assert figure.layout.title.text == "Y22 Complex Plane"
    assert figure.layout.xaxis.title.text == "Real"
    assert figure.layout.yaxis.title.text == "Imaginary"
    assert len(figure.data) == 1


def test_sweep_progress_log_step_scales_with_point_count() -> None:
    assert _sweep_progress_log_step(1) == 1
    assert _sweep_progress_log_step(40) == 1
    assert _sweep_progress_log_step(400) == 10


def test_should_log_sweep_point_progress_logs_first_last_and_interval() -> None:
    step = _sweep_progress_log_step(100)
    assert _should_log_sweep_point_progress(point_index=0, point_count=100, step=step) is True
    assert _should_log_sweep_point_progress(point_index=99, point_count=100, step=step) is True
    assert _should_log_sweep_point_progress(point_index=9, point_count=100, step=step) is True
    assert _should_log_sweep_point_progress(point_index=10, point_count=100, step=step) is False


def test_build_simulation_result_figure_builds_selected_s_parameter_view() -> None:
    figure = _build_simulation_result_figure(
        result=_sample_result(),
        view_family="s",
        metric="magnitude_linear",
        trace="s",
        output_mode=(0,),
        output_port=2,
        input_mode=(0,),
        input_port=1,
        reference_impedance_ohm=50.0,
        dark_mode=True,
    )

    assert figure.layout.title.text == "S21 Magnitude"
    assert figure.data[0].name == "S21"


def test_build_simulation_result_figure_overlays_multiple_s_parameter_traces() -> None:
    figure = _build_simulation_result_figure(
        result=_sample_result(),
        view_family="s",
        metric="magnitude_linear",
        trace="s",
        output_mode=(0,),
        output_port=1,
        input_mode=(0,),
        input_port=1,
        reference_impedance_ohm=50.0,
        dark_mode=True,
        trace_selections=[
            {
                "trace": "s",
                "output_mode": (0,),
                "output_port": 1,
                "input_mode": (0,),
                "input_port": 1,
            },
            {
                "trace": "s",
                "output_mode": (0,),
                "output_port": 2,
                "input_mode": (0,),
                "input_port": 1,
            },
        ],
    )

    assert str(figure.layout.title.text).startswith("S-Parameter Magnitude")
    assert "S11 Magnitude" in str(figure.layout.title.text)
    assert "S21 Magnitude" in str(figure.layout.title.text)
    assert [trace.name for trace in figure.data] == ["S11", "S21"]


def test_build_simulation_result_figure_builds_sideband_qe_view() -> None:
    figure = _build_simulation_result_figure(
        result=_sample_result(),
        view_family="qe",
        metric="linear",
        trace="qe",
        output_mode=(1,),
        output_port=2,
        input_mode=(0,),
        input_port=1,
        reference_impedance_ohm=50.0,
        dark_mode=True,
    )

    assert figure.layout.title.text == "QE 21 [om=(1,), im=(0,)]"
    assert list(figure.data[0].y) == [0.8, 0.82, 0.84]


def test_build_simulation_result_figure_builds_cm_view() -> None:
    figure = _build_simulation_result_figure(
        result=_sample_result(),
        view_family="cm",
        metric="value",
        trace="cm",
        output_mode=(1,),
        output_port=2,
        input_mode=(1,),
        input_port=2,
        reference_impedance_ohm=50.0,
        dark_mode=True,
    )

    assert figure.layout.title.text == "CM2 [om=(1,)]"
    assert list(figure.data[0].y) == [1.0, 1.0, 1.0]


def test_build_s_parameter_data_records_exports_all_cached_s_traces() -> None:
    records = _build_s_parameter_data_records(dataset_id=7, result=_sample_result())

    summary = {(record.parameter, record.representation): record.values for record in records}

    assert len(records) == 6
    assert summary[("S11", "real")] == [0.2, 0.0, -0.2]
    assert summary[("S21", "imaginary")] == [0.0, 0.0, 0.0]
    assert summary[("S22", "real")] == [0.1, 0.1, 0.1]


def test_build_result_bundle_data_records_exports_mode_bundles() -> None:
    records = _build_result_bundle_data_records(dataset_id=7, result=_sample_result())

    summary = {(record.data_type, record.parameter, record.representation) for record in records}

    assert ("s_params", "S21", "real") in summary
    assert ("s_params", "S21 [om=(1,), im=(0,)]", "imaginary") in summary
    assert ("z_params", "Z22", "real") in summary
    assert ("y_params", "Y22", "imaginary") in summary
    assert ("qe", "QE21 [om=(1,), im=(0,)]", "value") in summary
    assert ("qe_ideal", "QEideal21 [om=(1,), im=(0,)]", "value") in summary
    assert ("commutation", "CM2 [om=(1,)]", "value") in summary


def test_build_post_processed_y_data_records_for_base_mode_uses_yij_names() -> None:
    sweep = PortMatrixSweep(
        mode=(0,),
        labels=("1", "2"),
        frequencies_ghz=(5.0, 5.1),
        y_matrices=(
            np.asarray(((1.0 + 0.5j, 0.1 + 0.0j), (0.2 + 0.0j, 2.0 + 0.5j))),
            np.asarray(((1.1 + 0.6j, 0.1 + 0.1j), (0.2 + 0.1j, 2.1 + 0.6j))),
        ),
        source_kind="y",
    )
    records = _build_post_processed_y_data_records(dataset_id=11, sweep=sweep)
    summary = {(record.parameter, record.representation) for record in records}
    assert ("Y11", "real") in summary
    assert ("Y12", "imaginary") in summary
    assert ("Y21", "real") in summary
    assert ("Y22", "imaginary") in summary


def test_build_post_processed_y_data_records_for_transformed_sideband_labels() -> None:
    sweep = PortMatrixSweep(
        mode=(1,),
        labels=("cm(1,2)", "dm(1,2)"),
        frequencies_ghz=(5.0,),
        y_matrices=(np.asarray(((1.0 + 0.1j, 0.0 + 0.0j), (0.0 + 0.0j, 2.0 + 0.2j))),),
        source_kind="y",
    )
    records = _build_post_processed_y_data_records(dataset_id=12, sweep=sweep)
    parameter_names = {record.parameter for record in records}
    assert "Y_cm_1_2_cm_1_2 [om=(1,), im=(1,)]" in parameter_names
    assert "Y_dm_1_2_dm_1_2 [om=(1,), im=(1,)]" in parameter_names


def test_matrix_element_name_uses_transformed_port_label_tokens() -> None:
    labels = {1: "cm(1,2)", 2: "dm(1,2)", 3: "3"}
    assert (
        _matrix_element_name(
            matrix_symbol="Z",
            output_port=2,
            input_port=2,
            port_label_by_index=labels,
        )
        == "Z_dm_dm"
    )
    assert (
        _matrix_element_name(
            matrix_symbol="Z",
            output_port=2,
            input_port=1,
            port_label_by_index=labels,
        )
        == "Z_dm_cm"
    )
    assert (
        _matrix_element_name(
            matrix_symbol="Z",
            output_port=2,
            input_port=3,
            port_label_by_index=labels,
        )
        == "Z_dm_3"
    )


def test_coordinate_weight_fields_editable_depends_on_weight_mode() -> None:
    assert _coordinate_weight_fields_editable("manual") is True
    assert _coordinate_weight_fields_editable("auto") is False
    assert _coordinate_weight_fields_editable("AUTO") is False


def test_termination_mode_and_selected_ports_are_normalized() -> None:
    assert _normalize_termination_mode("MANUAL") == "manual"
    assert _normalize_termination_mode("unexpected") == "auto"
    assert _normalize_termination_selected_ports(
        ["2", "1", "not-a-port", "2"],
        available_ports=[1, 2, 3],
    ) == [1, 2]


def test_build_termination_compensation_plan_handles_auto_and_manual() -> None:
    auto_plan = _build_termination_compensation_plan(
        enabled=True,
        mode="auto",
        selected_ports=[1, 2],
        manual_resistance_ohm_by_port={1: 33.0, 2: 44.0},
        inferred_resistance_ohm_by_port={1: 50.0, 2: 100.0},
        inferred_source_by_port={1: "schema_infer", 2: "fallback_default_50"},
        inferred_warning_by_port={2: "Port 2 fallback warning"},
    )
    assert auto_plan["enabled"] is True
    assert auto_plan["mode"] == "auto"
    assert auto_plan["resistance_ohm_by_port"] == {1: 50.0, 2: 100.0}
    assert auto_plan["source_by_port"] == {1: "schema_infer", 2: "fallback_default_50"}
    assert auto_plan["warnings"] == ["Port 2 fallback warning"]

    manual_plan = _build_termination_compensation_plan(
        enabled=True,
        mode="manual",
        selected_ports=[2],
        manual_resistance_ohm_by_port={1: 55.0, 2: 75.0},
        inferred_resistance_ohm_by_port={1: 50.0, 2: 100.0},
        inferred_source_by_port={1: "schema_infer", 2: "schema_infer"},
        inferred_warning_by_port={},
    )
    assert manual_plan["enabled"] is True
    assert manual_plan["mode"] == "manual"
    assert manual_plan["resistance_ohm_by_port"] == {2: 75.0}
    assert manual_plan["source_by_port"] == {2: "manual"}
    assert manual_plan["warnings"] == []


def test_can_save_post_processed_results_requires_valid_output_state() -> None:
    sweep = PortMatrixSweep(
        mode=(0,),
        labels=("1", "2"),
        frequencies_ghz=(5.0,),
        y_matrices=(np.asarray(((1.0 + 0.0j, 0.0), (0.0, 2.0 + 0.0j))),),
        source_kind="y",
    )
    runtime_output = _sample_post_processed_sweep_run()
    assert _can_save_post_processed_results(sweep, {"steps": []}) is True
    assert _can_save_post_processed_results(runtime_output, {"run_kind": "parameter_sweep"}) is True
    assert _can_save_post_processed_results(None, {"steps": []}) is False
    assert _can_save_post_processed_results(sweep, None) is False


def test_build_post_processed_runtime_data_records_materializes_all_sweep_points() -> None:
    runtime_output = _sample_transformed_post_processed_sweep_run()

    records = _build_post_processed_runtime_data_records(
        dataset_id=7,
        runtime_output=runtime_output,
    )

    imag_records = [
        record
        for record in records
        if record.data_type == "y_params" and record.representation == "imaginary"
    ]
    assert len(records) == 16
    assert {record.dataset_id for record in records} == {7}
    assert {
        record.parameter
        for record in imag_records
        if record.parameter.startswith("Y_dm_1_2_dm_1_2")
    } == {
        "Y_dm_1_2_dm_1_2 [sweep L_q=10 nH]",
        "Y_dm_1_2_dm_1_2 [sweep L_q=15 nH]",
    }
    assert imag_records[0].axes[1]["name"] == "L_q"
    assert imag_records[0].axes[1]["values"] == [10.0]


def test_build_post_processed_bundle_artifacts_keep_single_run_payload_minimal() -> None:
    sweep = PortMatrixSweep(
        mode=(0,),
        labels=("1", "2"),
        frequencies_ghz=(5.0,),
        y_matrices=(np.asarray(((1.0 + 0.0j, 0.0), (0.0, 2.0 + 0.0j))),),
        source_kind="y",
    )

    source_meta, config_snapshot, result_payload = _build_post_processed_bundle_artifacts(
        sweep=sweep,
        flow_spec={"input_y_source": "raw_y", "steps": []},
        source_simulation_bundle_id=17,
    )

    assert source_meta["source_run_kind"] == "single_run"
    assert source_meta["input_source_type"] == "raw_y"
    assert config_snapshot["source_simulation_bundle_id"] == 17
    assert config_snapshot["source_run_kind"] == "single_run"
    assert result_payload["kind"] == "trace_batch_postprocess_lineage"
    assert result_payload["run_kind"] == "single_run"
    assert result_payload["canonical_authority"]["source_simulation_bundle_id"] == 17
    assert result_payload["projection"]["kind"] == "trace_store_projection"
    assert "sweep_axes" not in result_payload
    assert "points" not in result_payload


def test_build_post_processed_bundle_artifacts_preserve_source_sweep_authority() -> None:
    base = _sample_result()
    sweep = PortMatrixSweep(
        mode=(0,),
        labels=("1", "2"),
        frequencies_ghz=(5.0, 5.1),
        y_matrices=(
            np.asarray(((1.0 + 0.0j, 0.1 + 0.0j), (0.1 + 0.0j, 2.0 + 0.0j))),
            np.asarray(((1.1 + 0.0j, 0.2 + 0.0j), (0.2 + 0.0j, 2.1 + 0.0j))),
        ),
        source_kind="y",
    )
    source_run = SimulationSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="Lj", values=(900.0, 1100.0), unit="pH"),),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"Lj": 900.0},
                result=base,
            ),
            SimulationSweepPointResult(
                point_index=1,
                axis_indices=(1,),
                axis_values={"Lj": 1100.0},
                result=base,
            ),
        ),
        representative_point_index=1,
    )
    source_bundle_snapshot = {
        "id": 21,
        "dataset_id": 7,
        "bundle_type": "circuit_simulation",
        "role": "cache",
        "status": "completed",
        "schema_source_hash": "sha256:schema",
        "simulation_setup_hash": "sha256:setup",
        "source_meta": {"origin": "circuit_simulation", "sweep_setup_hash": "sha256:sweep"},
        "config_snapshot": {"sweep": {"setup_hash": "sha256:sweep"}},
        "result_payload": simulation_sweep_run_to_payload(source_run),
    }

    source_meta, config_snapshot, result_payload = _build_post_processed_bundle_artifacts(
        sweep=sweep,
        flow_spec={
            "input_y_source": "ptc_y",
            "steps": [{"type": "coordinate_transform", "enabled": True}],
            "hfss_comparable": True,
        },
        source_simulation_bundle_id=21,
        source_bundle_snapshot=source_bundle_snapshot,
    )

    assert source_meta["source_run_kind"] == "parameter_sweep"
    assert source_meta["source_bundle_type"] == "circuit_simulation"
    assert source_meta["input_source_type"] == "ptc_y"
    assert config_snapshot["sweep_setup_hash"] == "sha256:sweep"
    assert result_payload["run_kind"] == "parameter_sweep"
    assert result_payload["source_bundle"]["bundle_id"] == 21
    assert result_payload["point_count"] == 2
    assert result_payload["sweep_axes"][0]["target_value_ref"] == "Lj"
    assert result_payload["projection"]["representative_source_point_index"] == 1
    assert result_payload["points"][0]["source_point_index"] == 0
    assert result_payload["points"][0]["axis_values"]["Lj"] == pytest.approx(900.0)
    assert result_payload["points"][0]["postprocess_result_handle"] == {
        "kind": "replay_from_source_bundle_point",
        "source_simulation_bundle_id": 21,
        "source_point_index": 0,
        "input_source_type": "ptc_y",
        "flow_spec_ref": "config_snapshot",
    }


def test_trace_batch_bundle_roundtrip_rebuilds_parameter_sweep_from_trace_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    base = _sample_result()
    sweep_run = SimulationSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="Lj", values=(900.0, 1100.0), unit="pH"),),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"Lj": 900.0},
                result=base,
            ),
            SimulationSweepPointResult(
                point_index=1,
                axis_indices=(1,),
                axis_values={"Lj": 1100.0},
                result=SimulationResult.model_validate(
                    {
                        **base.model_dump(mode="json"),
                        "s_parameter_mode_real": {
                            **base.s_parameter_mode_real,
                            "om=0|op=2|im=0|ip=1": [2.5, 2.6, 2.7],
                        },
                    }
                ),
            ),
        ),
        representative_point_index=1,
    )
    payload = persist_trace_batch_bundle(
        bundle_id=105,
        design_id=42,
        design_name="Flux JPA",
        source_kind="circuit_simulation",
        stage_kind="raw",
        setup_kind="circuit_simulation.raw",
        setup_payload={"freq_range": {"start_ghz": 4.9, "stop_ghz": 5.1, "points": 3}},
        provenance_payload={"origin": "circuit_simulation"},
        trace_specs=build_raw_simulation_trace_specs(
            result=sweep_run.representative_result,
            sweep_payload=simulation_sweep_run_to_payload(sweep_run),
        ),
        summary_payload={
            "trace_count": 1,
            "run_kind": "parameter_sweep",
            "frequency_points": 3,
            "point_count": 2,
            "representative_point_index": 1,
        },
    )

    assert payload["schema_kind"] == TRACE_BATCH_BUNDLE_SCHEMA_KIND
    assert payload["trace_batch_record"]["stage_kind"] == "raw"
    assert payload["trace_batch_record"]["summary_payload"]["point_count"] == 2
    store_ref = payload["trace_records"][0]["store_ref"]
    assert store_ref["backend"] == "local_zarr"
    assert store_ref["store_key"] == "designs/42/batches/105.zarr"
    binding = LocalZarrTraceStoreBackend(root_path=get_trace_store_path())
    assert binding.resolve_store_path(store_key=store_ref["store_key"]).exists()

    rebuilt_result, rebuilt_sweep_payload = load_raw_simulation_bundle(payload)

    assert rebuilt_sweep_payload is not None
    rebuilt_run = simulation_sweep_run_from_payload(rebuilt_sweep_payload)
    assert rebuilt_result.frequencies_ghz == base.frequencies_ghz
    assert rebuilt_run.points[1].axis_values["Lj"] == pytest.approx(1100.0)
    assert rebuilt_run.representative_point_index == 1
    assert rebuilt_run.points[1].result.get_mode_s_parameter_real((0,), 2, (0,), 1) == [
        2.5,
        2.6,
        2.7,
    ]


def test_floating_qubit_with_xyline_simple_setup_cache_rebuild_stays_slice_first(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    sweep_values = tuple(15.0 + 2.5 * index for index in range(7))
    points = []
    for point_index, l_q in enumerate(sweep_values):
        base = _sample_result()
        point_result = SimulationResult.model_validate(
            {
                **base.model_dump(mode="json"),
                "y_parameter_mode_imag": {
                    **base.y_parameter_mode_imag,
                    "om=0|op=2|im=0|ip=2": [
                        value + (point_index * 0.0005)
                        for value in base.y_parameter_mode_imag["om=0|op=2|im=0|ip=2"]
                    ],
                },
            }
        )
        points.append(
            SimulationSweepPointResult(
                point_index=point_index,
                axis_indices=(point_index,),
                axis_values={"L_q": l_q},
                result=point_result,
            )
        )

    sweep_run = SimulationSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="L_q", values=sweep_values, unit="nH"),),
        points=tuple(points),
        representative_point_index=0,
    )
    payload = persist_trace_batch_bundle(
        bundle_id=205,
        design_id=10,
        design_name="FloatingQubitWithXYLine",
        source_kind="circuit_simulation",
        stage_kind="raw",
        setup_kind="circuit_simulation.raw",
        setup_payload={
            "preset_name": "Simple Setup",
            "freq_range": {"start_ghz": 1.0, "stop_ghz": 10.0001, "points": 1001},
            "sweep": {
                "point_count": len(sweep_values),
                "axes": [{"target_value_ref": "L_q", "unit": "nH"}],
            },
        },
        provenance_payload={"origin": "circuit_simulation"},
        trace_specs=build_raw_simulation_trace_specs(
            result=sweep_run.representative_result,
            sweep_payload=simulation_sweep_run_to_payload(sweep_run),
        ),
        summary_payload={
            "trace_count": 1,
            "run_kind": "parameter_sweep",
            "frequency_points": 3,
            "point_count": len(sweep_values),
            "representative_point_index": 0,
        },
    )

    def _forbid_full_read(path: Path) -> np.ndarray:
        raise AssertionError(f"unexpected full array read during cache reconstruction: {path}")

    monkeypatch.setattr(
        "core.simulation.application.trace_architecture._read_zarr_array",
        _forbid_full_read,
    )

    rebuilt_result, rebuilt_sweep_payload = load_raw_simulation_bundle(payload)

    assert rebuilt_sweep_payload is not None
    rebuilt_run = simulation_sweep_run_from_payload(rebuilt_sweep_payload)
    assert rebuilt_run.point_count == len(sweep_values)
    assert rebuilt_run.axes[0].target_value_ref == "L_q"
    assert rebuilt_run.points[6].axis_values["L_q"] == pytest.approx(30.0)
    assert rebuilt_result.y_parameter_mode_imag["om=0|op=2|im=0|ip=2"] == pytest.approx(
        points[0].result.y_parameter_mode_imag["om=0|op=2|im=0|ip=2"]
    )


def test_decode_trace_batch_sweep_payload_keeps_canonical_payload_without_full_rebuild(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    base = _sample_result()
    sweep_run = SimulationSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="L_q", values=(10.0, 12.0), unit="nH"),),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"L_q": 10.0},
                result=base,
            ),
            SimulationSweepPointResult(
                point_index=1,
                axis_indices=(1,),
                axis_values={"L_q": 12.0},
                result=SimulationResult.model_validate(
                    {
                        **base.model_dump(mode="json"),
                        "y_parameter_mode_imag": {
                            **base.y_parameter_mode_imag,
                            "om=0|op=2|im=0|ip=2": [0.1, 0.2, 0.3],
                        },
                    }
                ),
            ),
        ),
        representative_point_index=1,
    )
    payload = persist_trace_batch_bundle(
        bundle_id=206,
        design_id=10,
        design_name="FloatingQubitWithXYLine",
        source_kind="circuit_simulation",
        stage_kind="raw",
        setup_kind="circuit_simulation.raw",
        setup_payload={"preset_name": "Simple Setup"},
        provenance_payload={"origin": "circuit_simulation"},
        trace_specs=build_raw_simulation_trace_specs(
            result=sweep_run.representative_result,
            sweep_payload=simulation_sweep_run_to_payload(sweep_run),
        ),
        summary_payload={
            "trace_count": 1,
            "run_kind": "parameter_sweep",
            "frequency_points": 3,
            "point_count": 2,
            "representative_point_index": 1,
        },
    )

    result, sweep_payload = _decode_simulation_result_payload(payload)

    assert sweep_payload == payload
    assert _resolved_sweep_point_count(sweep_payload) == 2
    assert result.y_parameter_mode_imag["om=0|op=2|im=0|ip=2"] == pytest.approx([0.1, 0.2, 0.3])


def test_coerce_parameter_sweep_payload_accepts_trace_batch_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    base = _sample_result()
    sweep_run = SimulationSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="L_q", values=(10.0, 12.0), unit="nH"),),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"L_q": 10.0},
                result=base,
            ),
            SimulationSweepPointResult(
                point_index=1,
                axis_indices=(1,),
                axis_values={"L_q": 12.0},
                result=SimulationResult.model_validate(
                    {
                        **base.model_dump(mode="json"),
                        "y_parameter_mode_imag": {
                            **base.y_parameter_mode_imag,
                            "om=0|op=2|im=0|ip=2": [0.1, 0.2, 0.3],
                        },
                    }
                ),
            ),
        ),
        representative_point_index=1,
    )
    payload = persist_trace_batch_bundle(
        bundle_id=207,
        design_id=10,
        design_name="FloatingQubitWithXYLine",
        source_kind="circuit_simulation",
        stage_kind="raw",
        setup_kind="circuit_simulation.raw",
        setup_payload={"preset_name": "Simple Setup"},
        provenance_payload={"origin": "circuit_simulation"},
        trace_specs=build_raw_simulation_trace_specs(
            result=sweep_run.representative_result,
            sweep_payload=simulation_sweep_run_to_payload(sweep_run),
        ),
        summary_payload={
            "trace_count": 1,
            "run_kind": "parameter_sweep",
            "frequency_points": 3,
            "point_count": 2,
            "representative_point_index": 1,
        },
    )

    coerced = simulation_page._coerce_parameter_sweep_payload(payload)

    assert coerced is not None
    assert coerced["run_kind"] == "parameter_sweep"
    assert coerced["point_count"] == 2
    rebuilt_run = simulation_sweep_run_from_payload(coerced)
    assert rebuilt_run.representative_point_index == 1
    assert rebuilt_run.points[1].axis_values["L_q"] == pytest.approx(12.0)


def test_build_compensated_simulation_sweep_payload_accepts_trace_batch_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    base = _sample_result()
    sweep_run = SimulationSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="L_q", values=(10.0, 12.0), unit="nH"),),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"L_q": 10.0},
                result=base,
            ),
            SimulationSweepPointResult(
                point_index=1,
                axis_indices=(1,),
                axis_values={"L_q": 12.0},
                result=SimulationResult.model_validate(
                    {
                        **base.model_dump(mode="json"),
                        "y_parameter_mode_imag": {
                            **base.y_parameter_mode_imag,
                            "om=0|op=2|im=0|ip=2": [0.1, 0.2, 0.3],
                        },
                    }
                ),
            ),
        ),
        representative_point_index=1,
    )
    payload = persist_trace_batch_bundle(
        bundle_id=208,
        design_id=10,
        design_name="FloatingQubitWithXYLine",
        source_kind="circuit_simulation",
        stage_kind="raw",
        setup_kind="circuit_simulation.raw",
        setup_payload={"preset_name": "Simple Setup"},
        provenance_payload={"origin": "circuit_simulation"},
        trace_specs=build_raw_simulation_trace_specs(
            result=sweep_run.representative_result,
            sweep_payload=simulation_sweep_run_to_payload(sweep_run),
        ),
        summary_payload={
            "trace_count": 1,
            "run_kind": "parameter_sweep",
            "frequency_points": 3,
            "point_count": 2,
            "representative_point_index": 1,
        },
    )

    compensated = _build_compensated_simulation_sweep_payload(
        payload,
        resistance_ohm_by_port={1: 50.0, 2: 50.0},
        reference_impedance_ohm=50.0,
    )

    assert compensated["run_kind"] == "parameter_sweep"
    assert compensated["point_count"] == 2
    rebuilt_run = simulation_sweep_run_from_payload(compensated)
    assert rebuilt_run.points[1].axis_values["L_q"] == pytest.approx(12.0)
    assert len(rebuilt_run.points[1].result.frequencies_ghz) == len(base.frequencies_ghz)


def test_incremental_sweep_writer_persists_points_without_full_regroup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    sweep_values = (10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0)
    base = _sample_result()
    writer = IncrementalRawSimulationSweepWriter(
        design_id=10,
        design_name="FloatingQubitWithXYLine",
        run_id="floatingqubit-simple-setup",
        sweep_axes=(SimulationSweepAxis(target_value_ref="L_q", values=sweep_values, unit="nH"),),
    )

    for point_index, l_q in enumerate(sweep_values):
        point_result = SimulationResult.model_validate(
            {
                **base.model_dump(mode="json"),
                "y_parameter_mode_imag": {
                    **base.y_parameter_mode_imag,
                    "om=0|op=2|im=0|ip=2": [
                        value + (point_index * 0.001)
                        for value in base.y_parameter_mode_imag["om=0|op=2|im=0|ip=2"]
                    ],
                },
            }
        )
        writer.append_point(
            point_index=point_index,
            axis_indices=(point_index,),
            axis_values={"L_q": l_q},
            result=point_result,
        )

    payload = writer.build_payload(
        summary_payload={
            "trace_count": writer.trace_count,
            "run_kind": "parameter_sweep",
            "frequency_points": len(base.frequencies_ghz),
            "point_count": len(sweep_values),
            "representative_point_index": 0,
        }
    )

    def _forbid_full_read(path: Path) -> np.ndarray:
        raise AssertionError(f"unexpected full array read during incremental sweep reload: {path}")

    monkeypatch.setattr(
        "core.simulation.application.trace_architecture._read_zarr_array",
        _forbid_full_read,
    )

    rebuilt_result, rebuilt_sweep_payload = load_raw_simulation_bundle(payload)

    assert writer.trace_count > 0
    assert rebuilt_sweep_payload is not None
    rebuilt_run = simulation_sweep_run_from_payload(rebuilt_sweep_payload)
    assert rebuilt_run.point_count == len(sweep_values)
    assert rebuilt_run.axes[0].target_value_ref == "L_q"
    assert rebuilt_run.points[6].axis_values["L_q"] == pytest.approx(22.0)
    assert rebuilt_run.points[6].result.y_parameter_mode_imag[
        "om=0|op=2|im=0|ip=2"
    ] == pytest.approx(
        [value + 0.006 for value in base.y_parameter_mode_imag["om=0|op=2|im=0|ip=2"]]
    )
    assert rebuilt_result.y_parameter_mode_imag["om=0|op=2|im=0|ip=2"] == pytest.approx(
        base.y_parameter_mode_imag["om=0|op=2|im=0|ip=2"]
    )


def test_incremental_post_processed_writer_persists_points_without_full_regroup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    runtime_output = _sample_transformed_post_processed_sweep_run()
    writer = IncrementalPostProcessedSweepWriter(
        design_id=10,
        design_name="FloatingQubitWithXYLine",
        run_id="floatingqubit-postprocess",
        sweep_axes=runtime_output.axes,
    )

    for point in runtime_output.points:
        writer.append_point(
            point_index=point.point_index,
            axis_indices=point.axis_indices,
            sweep=point.sweep,
        )

    payload = writer.build_payload(
        summary_payload={
            "trace_count": writer.trace_count,
            "run_kind": "parameter_sweep",
            "frequency_points": len(runtime_output.points[0].sweep.frequencies_ghz),
            "point_count": runtime_output.point_count,
            "representative_point_index": runtime_output.representative_point_index,
        }
    )

    def _forbid_full_read(path: Path) -> np.ndarray:
        raise AssertionError(
            f"unexpected full array read during incremental postprocess reload: {path}"
        )

    monkeypatch.setattr(
        "core.simulation.application.trace_architecture._read_zarr_array",
        _forbid_full_read,
    )

    bundle = _cached_trace_store_bundle_from_post_processed_runtime(
        payload,
        reference_impedance_ohm=50.0,
    )

    assert writer.trace_count > 0
    assert bundle.representative_result.y_parameter_mode_real[
        "Y_dm_1_2_dm_1_2 [om=(0,), im=(0,)]"
    ] == pytest.approx([2.0, 2.0])
    assert bundle.sweep_axes[0].target_value_ref == "L_q"
    assert bundle.sweep_axes[0].values == pytest.approx((10.0, 15.0))


def test_load_cached_simulation_result_defers_preview_for_trace_batch_sweep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dataset = SimpleNamespace(id=42)
    bundle = SimpleNamespace(
        id=7,
        dataset_id=42,
        result_payload={
            "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
            "trace_batch_record": {
                "summary_payload": {
                    "run_kind": "parameter_sweep",
                }
            },
        },
        source_meta={},
        config_snapshot={},
    )

    class _ResultBundles:
        def find_simulation_cache(self, **_: object) -> object:
            return bundle

    class _FakeUow:
        result_bundles = _ResultBundles()

        def commit(self) -> None:
            raise AssertionError("cache hit should not upgrade or commit in this path")

    monkeypatch.setattr(
        simulation_feature_page,
        "_ensure_simulation_cache_dataset",
        lambda _uow: cache_dataset,
    )
    monkeypatch.setattr(
        simulation_feature_page,
        "_decode_simulation_result_payload",
        lambda _payload: (_sample_result(), {"run_kind": "parameter_sweep", "point_count": 2}),
    )

    resolved = _load_cached_simulation_result(
        _FakeUow(),
        schema_source_hash="schema-hash",
        simulation_setup_hash="setup-hash",
    )

    assert resolved == (7, 42, None, dict(bundle.result_payload))


def test_source_simulation_bundle_id_prefers_parent_batch_from_trace_batch_snapshot() -> None:
    snapshot = {
        "id": 9,
        "dataset_id": 12,
        "bundle_type": "simulation_postprocess",
        "role": "derived_from_simulation",
        "status": "completed",
        "schema_source_hash": None,
        "simulation_setup_hash": None,
        "source_meta": {"source_simulation_bundle_id": 41},
        "config_snapshot": {"source_simulation_bundle_id": 42},
        "result_payload": {
            "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
            "trace_batch_record": {
                "parent_batch_id": 43,
                "provenance_payload": {"canonical_authority": {"source_simulation_bundle_id": 44}},
            },
        },
    }

    assert _trace_batch_payload_from_snapshot(snapshot) is snapshot["result_payload"]
    assert _source_simulation_bundle_id_from_snapshot(snapshot) == 43


def test_resolve_persisted_post_processing_input_snapshot_follows_postprocess_lineage() -> None:
    raw_snapshot = {
        "id": 3,
        "dataset_id": 1,
        "bundle_type": "circuit_simulation",
        "role": "cache",
        "status": "completed",
        "schema_source_hash": None,
        "simulation_setup_hash": None,
        "source_meta": {},
        "config_snapshot": {},
        "result_payload": {
            "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
            "trace_batch_record": {
                "source_kind": "circuit_simulation",
                "stage_kind": "raw",
            },
        },
    }
    post_snapshot = {
        "id": 4,
        "dataset_id": 2,
        "bundle_type": "simulation_postprocess",
        "role": "derived_from_simulation",
        "status": "completed",
        "schema_source_hash": None,
        "simulation_setup_hash": None,
        "source_meta": {"source_simulation_bundle_id": 3},
        "config_snapshot": {"source_simulation_bundle_id": 3},
        "result_payload": {
            "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
            "trace_batch_record": {
                "source_kind": "circuit_simulation",
                "stage_kind": "postprocess",
                "parent_batch_id": 3,
            },
        },
    }

    class _Batch:
        def __init__(self, batch_id: int) -> None:
            self.id = batch_id

    class _ResultBundles:
        def list_provenance_by_design(self, design_id: int) -> list[object]:
            if design_id == 2:
                return [_Batch(4)]
            return []

        def get_snapshot(self, batch_id: int) -> dict[str, object] | None:
            if batch_id == 3:
                return raw_snapshot
            if batch_id == 4:
                return post_snapshot
            return None

    class _FakeUow:
        result_bundles = _ResultBundles()

    resolved = _resolve_persisted_post_processing_input_snapshot(
        _FakeUow(),
        design_ids=(2,),
    )

    assert resolved == raw_snapshot


def test_resolve_latest_persisted_post_processing_snapshot_prefers_completed_batch() -> None:
    raw_snapshot = {
        "id": 3,
        "dataset_id": 1,
        "bundle_type": "circuit_simulation",
        "role": "cache",
        "status": "completed",
        "schema_source_hash": None,
        "simulation_setup_hash": None,
        "source_meta": {},
        "config_snapshot": {},
        "result_payload": {
            "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
            "trace_batch_record": {
                "source_kind": "circuit_simulation",
                "stage_kind": "raw",
            },
        },
    }
    post_snapshot = {
        "id": 4,
        "dataset_id": 2,
        "bundle_type": "simulation_postprocess",
        "role": "derived_from_simulation",
        "status": "completed",
        "schema_source_hash": None,
        "simulation_setup_hash": None,
        "source_meta": {"source_simulation_bundle_id": 3},
        "config_snapshot": {"source_simulation_bundle_id": 3},
        "result_payload": {
            "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
            "trace_batch_record": {
                "source_kind": "circuit_simulation",
                "stage_kind": "postprocess",
                "parent_batch_id": 3,
            },
        },
    }

    class _Batch:
        def __init__(self, batch_id: int) -> None:
            self.id = batch_id

    class _ResultBundles:
        def list_provenance_by_design(self, design_id: int) -> list[object]:
            if design_id == 2:
                return [_Batch(3), _Batch(4)]
            return []

        def get_snapshot(self, batch_id: int) -> dict[str, object] | None:
            if batch_id == 3:
                return raw_snapshot
            if batch_id == 4:
                return post_snapshot
            return None

    class _FakeUow:
        result_bundles = _ResultBundles()

    resolved = _resolve_latest_persisted_post_processing_snapshot(
        _FakeUow(),
        design_ids=(2,),
    )

    assert resolved == post_snapshot


def test_build_post_processed_trace_specs_preserve_nd_sweep_axes() -> None:
    trace_specs = build_post_processed_trace_specs(
        runtime_output=_sample_transformed_post_processed_sweep_run(),
    )

    assert trace_specs
    example = next(
        spec
        for spec in trace_specs
        if spec.parameter.startswith("Y_dm_1_2_dm_1_2") and spec.representation == "imaginary"
    )
    assert example.axes[0].name == "frequency"
    assert example.axes[1].name == "L_q"
    assert example.values.shape == (2, 2)
    assert example.values[:, 0].tolist() == pytest.approx([0.0, 0.0])


def test_z0_control_tokens_are_shared_across_views() -> None:
    assert _Z0_CONTROL_PROPS == "dense outlined"
    assert _Z0_CONTROL_CLASSES == "w-32"


def test_simulation_workflow_context_lines_mark_compare_as_inspect_only() -> None:
    context_lines = _build_simulation_workflow_context_lines(
        circuit_record=CircuitRecord(id=7, name="Flux JPA", definition_json="{}"),
        source_kind="circuit_simulation",
        stage_kind="raw",
        run_kind="single_run",
        provenance_tokens=("live_solver_runtime", "save-path=Save Raw Simulation Results"),
    )

    assert "Current Design Scope: live schema Flux JPA (Schema #7)" in context_lines
    assert (
        "TraceStore-first authority is active for result inspection on this page." in context_lines
    )
    assert "source=circuit_simulation" in context_lines[2]
    assert "stage=raw" in context_lines[2]
    assert "run=single_run" in context_lines[2]
    assert "Cross-source compare is inspect-only here and stays blocked" in context_lines[3]


def test_result_family_explorer_z0_commits_on_enter_or_blur_without_value_change_render() -> None:
    source = inspect.getsource(simulation_page._render_result_family_explorer)
    assert 'z0_input.on("keydown.enter"' in source
    assert 'z0_input.on("blur"' in source
    assert "z0_input.on_value_change" not in source


def test_post_processing_input_panel_does_not_define_save_button() -> None:
    source = inspect.getsource(simulation_page._render_post_processing_panel)
    assert "Save Post-Processed Results" not in source


def test_post_processing_panel_exposes_setup_save_load_controls() -> None:
    source = inspect.getsource(simulation_page._render_post_processing_panel)
    assert "Post-Processing Setup" in source
    assert "Save Post-Processing Setup" in source


def test_post_processing_panel_exposes_input_source_and_hfss_fields() -> None:
    panel_source = inspect.getsource(simulation_page._render_post_processing_panel)
    assert "Input Y Source" in panel_source
    assert '"input_y_source"' in panel_source
    result_source = inspect.getsource(simulation_page._render_simulation_environment)
    assert '"hfss_comparable"' in result_source
    assert '"hfss_not_comparable_reason"' in result_source


def test_post_processing_panel_submits_persisted_api_task_instead_of_cpu_bound_execution() -> None:
    panel_source = inspect.getsource(simulation_page._render_post_processing_panel)
    assert "submit_post_processing_task" not in panel_source
    assert "build_post_processing_submission" not in panel_source
    assert "on_submit" in panel_source
    result_source = inspect.getsource(simulation_page._render_simulation_environment)
    assert "_submit_post_processing_intent_impl" in result_source
    assert "prepare_simulation_run" in result_source
    assert "submit_simulation_run" in result_source
    assert "run.cpu_bound" not in panel_source


def test_simulation_environment_uses_persisted_post_processing_authority_not_runtime_fields() -> (
    None
):
    source = inspect.getsource(simulation_page._render_simulation_environment)
    assert "_persisted_post_processing_output_bundle()" in source
    assert "latest_post_processing_runtime" not in source
    assert "latest_flow_spec" not in source
    assert "latest_sweep" not in source


def test_raw_result_provider_scopes_ptc_to_yz_families_only() -> None:
    source = inspect.getsource(simulation_page._render_simulation_environment)
    assert "view_family in _RAW_RESULT_MATRIX_SOURCE_OPTIONS_BY_FAMILY" in source
    assert "_cached_trace_store_bundle_from_result(raw_result)" in source


def test_kron_keep_basis_uses_non_dropdown_multi_select_interaction() -> None:
    source = inspect.getsource(simulation_page._render_post_processing_panel)
    assert 'ui.label("Keep Basis Labels")' in source
    assert "Select All" in source
    assert "Clear" in source
    assert "multiple=True" not in source


def test_build_post_processed_result_payload_supports_family_metric_trace_rendering() -> None:
    sweep = PortMatrixSweep(
        mode=(1,),
        labels=("cm(1,2)", "dm(1,2)"),
        frequencies_ghz=(5.0, 5.2),
        y_matrices=(
            np.asarray(((0.02 + 0.01j, 0.001 + 0.0j), (0.002 + 0.0j, 0.03 + 0.02j))),
            np.asarray(((0.021 + 0.011j, 0.0015 + 0.0j), (0.0025 + 0.0j, 0.031 + 0.021j))),
        ),
        source_kind="y",
    )
    converted, port_options = _build_post_processed_result_payload(
        sweep,
        reference_impedance_ohm=50.0,
    )
    assert port_options == {1: "cm(1,2)", 2: "dm(1,2)"}

    figure = _build_simulation_result_figure(
        result=converted,
        view_family="admittance",
        metric="imag",
        trace="admittance",
        output_mode=(1,),
        output_port=1,
        input_mode=(1,),
        input_port=1,
        reference_impedance_ohm=50.0,
        dark_mode=True,
        trace_selections=[
            {
                "trace": "admittance",
                "output_mode": (1,),
                "output_port": 1,
                "input_mode": (1,),
                "input_port": 1,
            },
            {
                "trace": "admittance",
                "output_mode": (1,),
                "output_port": 2,
                "input_mode": (1,),
                "input_port": 2,
            },
        ],
    )
    assert len(figure.data) == 2
    assert figure.layout.title.text is not None


def test_post_processed_result_figure_y_axis_title_updates_across_y_z_y_switches() -> None:
    sweep = PortMatrixSweep(
        mode=(1,),
        labels=("cm(1,2)", "dm(1,2)"),
        frequencies_ghz=(5.0, 5.2),
        y_matrices=(
            np.asarray(((0.02 + 0.01j, 0.001 + 0.0j), (0.002 + 0.0j, 0.03 + 0.02j))),
            np.asarray(((0.021 + 0.011j, 0.0015 + 0.0j), (0.0025 + 0.0j, 0.031 + 0.021j))),
        ),
        source_kind="y",
    )
    converted, _ = _build_post_processed_result_payload(
        sweep,
        reference_impedance_ohm=50.0,
    )
    fig_y_first = _build_simulation_result_figure(
        result=converted,
        view_family="admittance",
        metric="imag",
        trace="admittance",
        output_mode=(1,),
        output_port=1,
        input_mode=(1,),
        input_port=1,
        reference_impedance_ohm=50.0,
        dark_mode=True,
    )
    fig_z = _build_simulation_result_figure(
        result=converted,
        view_family="impedance",
        metric="imag",
        trace="impedance",
        output_mode=(1,),
        output_port=1,
        input_mode=(1,),
        input_port=1,
        reference_impedance_ohm=50.0,
        dark_mode=True,
    )
    fig_y_second = _build_simulation_result_figure(
        result=converted,
        view_family="admittance",
        metric="imag",
        trace="admittance",
        output_mode=(1,),
        output_port=1,
        input_mode=(1,),
        input_port=1,
        reference_impedance_ohm=50.0,
        dark_mode=True,
    )

    assert fig_y_first.layout.title.text == "Y11 [om=(1,), im=(1,)] Imaginary Part"
    assert fig_y_first.layout.yaxis.title.text == "Imaginary (S)"
    assert fig_z.layout.title.text == "Z11 [om=(1,), im=(1,)] Imaginary Part"
    assert fig_z.layout.yaxis.title.text == "Imaginary (Ohm)"
    assert fig_y_second.layout.title.text == "Y11 [om=(1,), im=(1,)] Imaginary Part"
    assert fig_y_second.layout.yaxis.title.text == "Imaginary (S)"


def test_build_post_processed_sweep_explorer_payload_preserves_canonical_points() -> None:
    payload = _build_post_processed_sweep_explorer_payload(
        _sample_post_processed_sweep_run(),
        reference_impedance_ohm=50.0,
    )
    sweep_run = simulation_sweep_run_from_payload(payload)

    assert payload["run_kind"] == "parameter_sweep"
    assert payload["point_count"] == 2
    assert payload["representative_point_index"] == 0
    assert sweep_run.points[1].axis_values == {"Lj": 1100.0}
    second_trace = sweep_run.points[1].result.get_mode_y_parameter_complex((0,), 1, (0,), 1)
    assert second_trace[0].real == pytest.approx(3.0)


def test_post_processed_sweep_explorer_payload_preserves_transformed_port_labels() -> None:
    payload = _build_post_processed_sweep_explorer_payload(
        _sample_transformed_post_processed_sweep_run(),
        reference_impedance_ohm=50.0,
    )
    sweep_run = simulation_sweep_run_from_payload(payload)

    port_options = _sweep_payload_port_options(
        payload,
        fallback_result=sweep_run.representative_result,
    )
    rendered = _build_sweep_metric_rows(
        sweep_payload=payload,
        family="admittance",
        metric="real",
        trace_selection={
            "trace": "admittance",
            "output_mode": (0,),
            "output_port": 2,
            "input_mode": (0,),
            "input_port": 2,
            "sweep_axis_index": 1,
        },
        z0=50.0,
        frequency_index=0,
        dark_mode=True,
        port_label_by_index=port_options,
    )

    assert payload["port_labels"] == {"1": "cm(1,2)", "2": "dm(1,2)"}
    assert port_options == {1: "cm(1,2)", 2: "dm(1,2)"}
    assert rendered["figure"].data[0].name.startswith("Y_dm_dm")
    assert "Y22" not in rendered["figure"].data[0].name


def test_post_processed_sweep_metric_rows_can_render_non_representative_point() -> None:
    payload = _build_post_processed_sweep_explorer_payload(
        _sample_post_processed_sweep_run(),
        reference_impedance_ohm=50.0,
    )

    rendered = _build_sweep_metric_rows(
        sweep_payload=payload,
        family="admittance",
        metric="real",
        trace_selection={
            "trace": "admittance",
            "output_mode": (0,),
            "output_port": 1,
            "input_mode": (0,),
            "input_port": 1,
            "sweep_axis_index": 1,
        },
        z0=50.0,
        frequency_index=0,
        dark_mode=True,
    )

    assert rendered["point_count"] == 2
    assert rendered["slice_point_count"] == 1
    assert rendered["trace_details"][0]["point_index"] == 1
    assert rendered["trace_details"][0]["axis_value"] == pytest.approx(1100.0)
    assert rendered["figure"].data[0].y[0] == pytest.approx(3.0)


def test_trace_store_result_bundle_roundtrips_single_result_view() -> None:
    bundle = _trace_store_bundle_from_simulation_result(_sample_result())

    reconstructed = _result_from_trace_store_bundle(bundle)

    assert reconstructed.frequencies_ghz == pytest.approx([4.9, 5.0, 5.1])
    assert reconstructed.get_mode_s_parameter_real((0,), 1, (0,), 1) == pytest.approx(
        [0.2, 0.0, -0.2]
    )
    assert reconstructed.get_mode_y_parameter_complex((0,), 2, (0,), 2)[2].imag == pytest.approx(
        -0.002
    )


def test_trace_store_backed_sweep_metric_rows_read_only_selected_slice() -> None:
    sweep_axis = SimulationSweepAxis(target_value_ref="Lj", values=(900.0, 1100.0), unit="pH")
    frequency_axis = _TraceStoreAxis(name="frequency", unit="GHz", values=(4.9, 5.0, 5.1))
    compare_real = _NoFullReadArray(((0.2, 0.0, -0.2), (0.4, 0.0, -0.4)))
    compare_imag = _NoFullReadArray(((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
    bundle = _TraceStoreResultBundle(
        trace_records=(
            _TraceRecordAuthority(
                family="s_params",
                parameter="om=0|op=1|im=0|ip=1",
                representation="real",
                axes=(
                    _TraceStoreAxis(name="Lj", unit="pH", values=(900.0, 1100.0)),
                    frequency_axis,
                ),
                store_key="s11:real",
                trace_meta={
                    "family": "s_params",
                    "parameter": "om=0|op=1|im=0|ip=1",
                    "representation": "real",
                },
            ),
            _TraceRecordAuthority(
                family="s_params",
                parameter="om=0|op=1|im=0|ip=1",
                representation="imaginary",
                axes=(
                    _TraceStoreAxis(name="Lj", unit="pH", values=(900.0, 1100.0)),
                    frequency_axis,
                ),
                store_key="s11:imaginary",
                trace_meta={
                    "family": "s_params",
                    "parameter": "om=0|op=1|im=0|ip=1",
                    "representation": "imaginary",
                },
            ),
        ),
        trace_store=_ViewTraceStore(
            arrays={
                "s11:real": compare_real,
                "s11:imaginary": compare_imag,
            }
        ),
        sweep_axes=(sweep_axis,),
        representative_axis_indices=(0,),
        representative_result=_sample_result(),
        port_indices=(1, 2),
        mode_indices=((0,), (1,)),
        port_label_by_index={1: "1", 2: "2"},
    )

    rendered = _build_sweep_metric_rows(
        sweep_payload={},
        trace_store_bundle=bundle,
        family="s",
        metric="magnitude_linear",
        trace_selection={
            "trace": "s_param",
            "output_mode": (0,),
            "output_port": 1,
            "input_mode": (0,),
            "input_port": 1,
            "sweep_axis_index": 1,
        },
        z0=50.0,
        frequency_index=0,
        dark_mode=True,
    )

    assert compare_real.keys == [(1, slice(None, None, None))]
    assert compare_imag.keys == [(1, slice(None, None, None))]
    assert rendered["slice_point_count"] == 1
    assert rendered["trace_details"][0]["point_index"] == 1
    assert rendered["figure"].data[0].y[0] == pytest.approx(0.4)


def test_post_processed_trace_store_bundle_preserves_compare_labels() -> None:
    trace_store_bundle = simulation_page._trace_store_bundle_from_post_processed_sweep_run(
        _sample_transformed_post_processed_sweep_run(),
        reference_impedance_ohm=50.0,
    )

    rendered = _build_sweep_metric_rows(
        sweep_payload={},
        trace_store_bundle=trace_store_bundle,
        family="admittance",
        metric="real",
        trace_selection={
            "trace": "admittance",
            "output_mode": (0,),
            "output_port": 2,
            "input_mode": (0,),
            "input_port": 2,
            "sweep_axis_index": 1,
        },
        z0=50.0,
        frequency_index=0,
        dark_mode=True,
        port_label_by_index=trace_store_bundle.port_label_by_index,
    )

    assert trace_store_bundle.port_label_by_index == {1: "cm(1,2)", 2: "dm(1,2)"}
    assert rendered["trace_details"][0]["axis_value"] == pytest.approx(15.0)
    assert rendered["figure"].data[0].name.startswith("Y_dm_dm")
    assert "Y22" not in rendered["figure"].data[0].name


def test_hash_stable_json_is_order_independent() -> None:
    assert _hash_stable_json({"b": 2, "a": 1}) == _hash_stable_json({"a": 1, "b": 2})


def test_hash_schema_source_changes_with_source_text() -> None:
    assert _hash_schema_source('{"name":"A"}') != _hash_schema_source('{"name":"B"}')


def test_simulation_setup_storage_roundtrip_preserves_termination_compensation(monkeypatch) -> None:
    storage: dict[str, object] = {}

    def fake_get(key: str, default: object = None) -> object:
        return storage.get(key, default)

    def fake_set(key: str, value: object) -> None:
        storage[key] = value

    monkeypatch.setattr(simulation_feature_page, "_user_storage_get", fake_get)
    monkeypatch.setattr(simulation_feature_page, "_user_storage_set", fake_set)

    schema_id = 183
    setup_payload = {
        "freq_range": {"start_ghz": 4.0, "stop_ghz": 5.0, "points": 101},
        "harmonics": {"n_modulation_harmonics": 4, "n_pump_harmonics": 8},
        "sources": [{"pump_freq_ghz": 4.75, "port": 1, "current_amp": 0.0, "mode": [1]}],
        "advanced": {
            "include_dc": False,
            "enable_three_wave_mixing": False,
            "enable_four_wave_mixing": True,
            "max_intermod_order": -1,
            "max_iterations": 1000,
            "f_tol": 1e-8,
            "line_search_switch_tol": 1e-5,
            "alpha_min": 1e-4,
        },
        "termination_compensation": {
            "enabled": True,
            "mode": "manual",
            "selected_ports": [1, 2],
            "manual_resistance_ohm_by_port": {"1": 50.0, "2": 75.0},
        },
    }
    _save_saved_setups_for_schema(
        schema_id,
        [{"id": "sim-a", "name": "Simulation Setup A", "payload": setup_payload}],
    )

    loaded = _load_saved_setups_for_schema(schema_id)
    assert [entry["id"] for entry in loaded] == ["sim-a"]
    assert (
        loaded[0]["payload"]["termination_compensation"]
        == setup_payload["termination_compensation"]
    )


def test_simulation_setup_manager_save_as_requires_unique_name_case_insensitive() -> None:
    setups = [
        {
            "id": "user:a",
            "name": "Two Pump",
            "saved_at": "2026-03-05T10:00:00",
            "payload": {"freq_range": {"start_ghz": 1.0}},
        }
    ]
    with pytest.raises(ValueError, match="already exists"):
        save_setup_as(
            setups,
            name="two pump",
            payload={"freq_range": {"start_ghz": 2.0}},
        )


def test_simulation_setup_manager_rename_and_delete_block_builtin_setups() -> None:
    builtin = {
        "id": "builtin:official",
        "name": "Official Example",
        "saved_at": "builtin",
        "payload": {"freq_range": {"start_ghz": 4.5}},
    }
    with pytest.raises(ValueError, match="cannot be renamed"):
        rename_setup([builtin], setup_id="builtin:official", new_name="Renamed")
    with pytest.raises(ValueError, match="cannot be deleted"):
        delete_setup([builtin], setup_id="builtin:official")


def test_simulation_setup_manager_rename_updates_only_target_entry() -> None:
    setups = [
        {
            "id": "user:a",
            "name": "Setup A",
            "saved_at": "2026-03-05T10:00:00",
            "payload": {"freq_range": {"start_ghz": 1.0}},
        },
        {
            "id": "user:b",
            "name": "Setup B",
            "saved_at": "2026-03-05T10:01:00",
            "payload": {"freq_range": {"start_ghz": 2.0}},
        },
    ]
    updated_setups, updated_record = rename_setup(
        setups,
        setup_id="user:b",
        new_name="Setup B Prime",
    )
    assert updated_record["id"] == "user:b"
    assert updated_record["name"] == "Setup B Prime"
    assert [entry["name"] for entry in updated_setups] == ["Setup A", "Setup B Prime"]


def test_post_process_setup_storage_roundtrip_per_schema(monkeypatch) -> None:
    storage: dict[str, object] = {}

    def fake_get(key: str, default: object = None) -> object:
        return storage.get(key, default)

    def fake_set(key: str, value: object) -> None:
        storage[key] = value

    monkeypatch.setattr(simulation_feature_page, "_user_storage_get", fake_get)
    monkeypatch.setattr(simulation_feature_page, "_user_storage_set", fake_set)

    schema_a = 183
    schema_b = 999
    setup_payload = {
        "mode_filter": "base",
        "mode_token": "0",
        "reference_impedance_ohm": 50.0,
        "steps": [{"type": "kron_reduction", "enabled": True, "keep_labels": ["1", "2"]}],
    }
    _save_saved_post_process_setups_for_schema(
        schema_a,
        [{"id": "post-a", "name": "Post-Processing Setup A", "payload": setup_payload}],
    )
    _save_saved_post_process_setups_for_schema(
        schema_b,
        [{"id": "post-b", "name": "Post-Processing Setup B", "payload": {"steps": []}}],
    )

    loaded_a = _load_saved_post_process_setups_for_schema(schema_a)
    loaded_b = _load_saved_post_process_setups_for_schema(schema_b)
    assert [entry["id"] for entry in loaded_a] == ["post-a"]
    assert [entry["id"] for entry in loaded_b] == ["post-b"]
    assert loaded_a[0]["payload"]["steps"][0]["type"] == "kron_reduction"


def test_post_process_selected_setup_id_roundtrip(monkeypatch) -> None:
    storage: dict[str, object] = {}

    def fake_get(key: str, default: object = None) -> object:
        return storage.get(key, default)

    def fake_set(key: str, value: object) -> None:
        storage[key] = value

    monkeypatch.setattr(simulation_feature_page, "_user_storage_get", fake_get)
    monkeypatch.setattr(simulation_feature_page, "_user_storage_set", fake_set)

    assert _load_selected_post_process_setup_id(183) == ""
    _save_selected_post_process_setup_id(183, "post-a")
    _save_selected_post_process_setup_id(999, "post-b")
    assert _load_selected_post_process_setup_id(183) == "post-a"
    assert _load_selected_post_process_setup_id(999) == "post-b"


def test_normalized_simulation_setup_snapshot_captures_sources_and_advanced_options() -> None:
    snapshot = _normalized_simulation_setup_snapshot(
        FrequencyRange(start_ghz=4.0, stop_ghz=5.0, points=201),
        SimulationConfig(
            sources=[
                DriveSourceConfig(
                    pump_freq_ghz=4.65,
                    port=1,
                    current_amp=2e-6,
                    mode_components=(1, 0),
                ),
                DriveSourceConfig(
                    pump_freq_ghz=4.85,
                    port=2,
                    current_amp=3e-6,
                    mode_components=(0, 1),
                ),
            ],
            n_modulation_harmonics=4,
            n_pump_harmonics=6,
            include_dc=True,
            enable_three_wave_mixing=False,
            enable_four_wave_mixing=True,
            max_intermod_order=None,
            max_iterations=321,
            f_tol=1e-7,
            line_search_switch_tol=1e-6,
            alpha_min=1e-5,
        ),
    )

    assert snapshot["freq_range"] == {"start_ghz": 4.0, "stop_ghz": 5.0, "points": 201}
    assert snapshot["sources"] == [
        {"pump_freq_ghz": 4.65, "port": 1, "current_amp": 2e-06, "mode": [1, 0]},
        {"pump_freq_ghz": 4.85, "port": 2, "current_amp": 3e-06, "mode": [0, 1]},
    ]
    assert snapshot["advanced"]["include_dc"] is True
    assert snapshot["advanced"]["max_intermod_order"] == -1


def test_normalize_sweep_setup_payload_resolves_unknown_target_to_available_option() -> None:
    normalized = _normalize_sweep_setup_payload(
        {
            "enabled": True,
            "axes": [
                {
                    "target_value_ref": "UnknownRef",
                    "start": 1.0,
                    "stop": 3.0,
                    "points": 5,
                    "unit": "X",
                }
            ],
        },
        available_target_units={"Lj": "pH", "Cc": "fF"},
    )

    assert normalized["enabled"] is True
    assert normalized["mode"] == "cartesian"
    assert normalized["axes"][0]["target_value_ref"] == "Lj"
    assert normalized["axes"][0]["unit"] == "pH"


def test_normalize_sweep_setup_payload_supports_legacy_axis_1_shape() -> None:
    normalized = _normalize_sweep_setup_payload(
        {
            "enabled": True,
            "mode": "paired",
            "axis_1": {
                "target_value_ref": "sources[1].current_amp",
                "start": 100e-6,
                "stop": 200e-6,
                "points": 3,
            },
        },
        available_target_units={"Lj": "pH", "sources[1].current_amp": "A"},
    )

    assert normalized["enabled"] is True
    assert normalized["mode"] == "paired"
    assert len(normalized["axes"]) == 1
    assert normalized["axes"][0]["target_value_ref"] == "sources[1].current_amp"
    assert normalized["axes"][0]["unit"] == "A"


def test_normalize_sweep_setup_payload_keeps_multi_axes() -> None:
    normalized = _normalize_sweep_setup_payload(
        {
            "enabled": True,
            "mode": "cartesian",
            "axes": [
                {
                    "target_value_ref": "Lj",
                    "start": 900.0,
                    "stop": 1100.0,
                    "points": 3,
                },
                {
                    "target_value_ref": "sources[1].current_amp",
                    "start": 120e-6,
                    "stop": 160e-6,
                    "points": 5,
                },
            ],
        },
        available_target_units={"Lj": "pH", "sources[1].current_amp": "A"},
    )

    assert normalized["enabled"] is True
    assert normalized["mode"] == "cartesian"
    assert len(normalized["axes"]) == 2
    assert normalized["axes"][0]["target_value_ref"] == "Lj"
    assert normalized["axes"][1]["target_value_ref"] == "sources[1].current_amp"


def test_normalize_sweep_setup_payload_keeps_source_target_axis() -> None:
    normalized = _normalize_sweep_setup_payload(
        {
            "enabled": True,
            "axes": [
                {
                    "target_value_ref": "sources[1].current_amp",
                    "start": 130e-6,
                    "stop": 150e-6,
                    "points": 5,
                    "unit": "A",
                }
            ],
        },
        available_target_units={"Lj": "pH", "sources[1].current_amp": "A"},
    )

    axis = normalized["axes"][0]
    assert normalized["enabled"] is True
    assert axis["target_value_ref"] == "sources[1].current_amp"
    assert axis["start"] == pytest.approx(130e-6)
    assert axis["stop"] == pytest.approx(150e-6)
    assert axis["points"] == 5
    assert axis["unit"] == "A"


def test_decode_simulation_result_payload_supports_parameter_sweep_payload() -> None:
    base = _sample_result()
    sweep_run = SimulationSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="Lj", values=(900.0, 1100.0), unit="pH"),),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"Lj": 900.0},
                result=base,
            ),
            SimulationSweepPointResult(
                point_index=1,
                axis_indices=(1,),
                axis_values={"Lj": 1100.0},
                result=base,
            ),
        ),
        representative_point_index=0,
    )
    payload = simulation_sweep_run_to_payload(sweep_run)

    result, sweep_payload = _decode_simulation_result_payload(payload)

    assert sweep_payload is not None
    assert sweep_payload["run_kind"] == "parameter_sweep"
    assert sweep_payload["point_count"] == 2
    assert result.frequencies_ghz == base.frequencies_ghz


def test_decode_simulation_result_payload_supports_source_sweep_target_axis() -> None:
    base = _sample_result()
    sweep_run = SimulationSweepRun(
        axes=(
            SimulationSweepAxis(
                target_value_ref="sources[1].current_amp",
                values=(130e-6, 150e-6),
                unit="A",
            ),
        ),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"sources[1].current_amp": 130e-6},
                result=base,
            ),
            SimulationSweepPointResult(
                point_index=1,
                axis_indices=(1,),
                axis_values={"sources[1].current_amp": 150e-6},
                result=base,
            ),
        ),
        representative_point_index=0,
    )
    payload = simulation_sweep_run_to_payload(sweep_run)

    result, sweep_payload = _decode_simulation_result_payload(payload)

    assert sweep_payload is not None
    assert sweep_payload["sweep_axes"][0]["target_value_ref"] == "sources[1].current_amp"
    assert sweep_payload["points"][1]["axis_values"]["sources[1].current_amp"] == pytest.approx(
        150e-6
    )
    assert result.frequencies_ghz == base.frequencies_ghz


def test_build_sweep_result_bundle_data_records_embeds_sweep_axis_metadata() -> None:
    base = _sample_result()
    sweep_run = SimulationSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="Lj", values=(900.0, 1100.0), unit="pH"),),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"Lj": 900.0},
                result=base,
            ),
            SimulationSweepPointResult(
                point_index=1,
                axis_indices=(1,),
                axis_values={"Lj": 1100.0},
                result=base,
            ),
        ),
        representative_point_index=0,
    )
    records = _build_sweep_result_bundle_data_records(
        dataset_id=42,
        sweep_payload=simulation_sweep_run_to_payload(sweep_run),
    )

    assert records
    first_axes = records[0].axes
    assert first_axes[0]["name"] == "frequency"
    assert first_axes[1]["name"] == "sweep:Lj"
    assert first_axes[1]["unit"] == "pH"
    assert first_axes[1]["axis_points"] == 2
    assert any("[sweep Lj=" in record.parameter for record in records)


def test_normalize_sweep_result_view_state_clamps_invalid_selector_state() -> None:
    base = _sample_result()
    sweep_run = SimulationSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="Lj", values=(900.0,), unit="pH"),),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"Lj": 900.0},
                result=base,
            ),
        ),
        representative_point_index=0,
    )
    view_state = {
        "family": "unknown",
        "metric": "bad_metric",
        "z0": -1,
        "frequency_index": 99,
        "trace_selection": {
            "trace": "missing_trace",
            "output_mode": (999,),
            "output_port": 999,
            "input_mode": (999,),
            "input_port": 999,
        },
        "view_axis_target_value_ref": "unknown",
        "fixed_axis_indices": {"Lj": 123},
    }
    normalized = _normalize_sweep_result_view_state(
        view_state=view_state,
        sweep_run=sweep_run,
    )
    assert normalized["family"] == "s"
    assert normalized["metric"] in _result_metric_options_for_family("s")
    assert normalized["z0"] == 50.0
    assert normalized["frequency_index"] == 2
    assert normalized["trace_selection"]["trace"] == "s_param"
    assert normalized["trace_selection"]["output_port"] == 1
    assert normalized["trace_selection"]["input_port"] == 1
    assert normalized["trace_selection"]["sweep_axis_index"] == 0
    assert normalized["view_axis_target_value_ref"] == "Lj"
    assert normalized["fixed_axis_indices"] == {}
    assert len(normalized["traces"]) == 1


def test_normalize_sweep_result_view_state_accepts_sweep_value_label_text() -> None:
    base = _sample_result()
    sweep_run = SimulationSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="L_q", values=(10.0, 15.0, 20.0), unit="nH"),),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"L_q": 10.0},
                result=base,
            ),
            SimulationSweepPointResult(
                point_index=1,
                axis_indices=(1,),
                axis_values={"L_q": 15.0},
                result=base,
            ),
            SimulationSweepPointResult(
                point_index=2,
                axis_indices=(2,),
                axis_values={"L_q": 20.0},
                result=base,
            ),
        ),
        representative_point_index=0,
    )
    view_state = {
        "family": "admittance",
        "metric": "real",
        "view_axis_target_value_ref": "L_q",
        "traces": [
            {
                "trace": "admittance",
                "output_mode": (0,),
                "output_port": 1,
                "input_mode": (0,),
                "input_port": 1,
                "sweep_axis_index": "2: 15 nH",
            }
        ],
    }

    normalized = _normalize_sweep_result_view_state(
        view_state=view_state,
        sweep_run=sweep_run,
    )

    assert normalized["traces"][0]["sweep_axis_index"] == 1
    assert normalized["trace_selection"]["sweep_axis_index"] == 1


def test_build_sweep_metric_rows_maps_selected_sweep_value_to_frequency_trace() -> None:
    result_a = _sample_result()
    result_b = _sample_result().model_copy(deep=True)
    result_b.s11_real = [0.4, 0.0, -0.4]
    result_b.s_parameter_real["S11"] = [0.4, 0.0, -0.4]
    result_b.s_parameter_mode_real["om=0|op=1|im=0|ip=1"] = [0.4, 0.0, -0.4]

    sweep_run = SimulationSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="Lj", values=(900.0, 1100.0), unit="pH"),),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"Lj": 900.0},
                result=result_a,
            ),
            SimulationSweepPointResult(
                point_index=1,
                axis_indices=(1,),
                axis_values={"Lj": 1100.0},
                result=result_b,
            ),
        ),
        representative_point_index=0,
    )
    payload = _build_sweep_metric_rows(
        sweep_payload=simulation_sweep_run_to_payload(sweep_run),
        family="s",
        metric="magnitude_linear",
        trace_selection={
            "trace": "s_param",
            "output_mode": (0,),
            "output_port": 1,
            "input_mode": (0,),
            "input_port": 1,
            "sweep_axis_index": 1,
        },
        z0=50.0,
        frequency_index=0,
        dark_mode=True,
    )

    assert payload["axis_label"] == "Lj (pH)"
    assert payload["metric_label"] == "Magnitude (linear)"
    assert payload["slice_point_count"] == 1
    assert payload["trace_details"][0]["axis_index"] == 1
    assert payload["trace_details"][0]["axis_value"] == pytest.approx(1100.0)
    assert payload["figure"].data[0].x[0] == pytest.approx(4.9)
    assert payload["figure"].data[0].y[0] == pytest.approx(0.4)
    assert len(payload["figure"].data) == 1


def test_build_sweep_metric_rows_updates_when_sweep_value_changes() -> None:
    base = _sample_result()
    second = _sample_result().model_copy(deep=True)
    second.s_parameter_real["S11"] = [0.5, 0.25, -0.25]
    second.s_parameter_mode_real["om=0|op=1|im=0|ip=1"] = [0.5, 0.25, -0.25]
    sweep_run = SimulationSweepRun(
        axes=(SimulationSweepAxis(target_value_ref="Lj", values=(900.0, 1100.0), unit="pH"),),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"Lj": 900.0},
                result=base,
            ),
            SimulationSweepPointResult(
                point_index=1,
                axis_indices=(1,),
                axis_values={"Lj": 1100.0},
                result=second,
            ),
        ),
        representative_point_index=0,
    )
    payload = simulation_sweep_run_to_payload(sweep_run)
    first = _build_sweep_metric_rows(
        sweep_payload=payload,
        family="s",
        metric="magnitude_linear",
        trace_selection={
            "trace": "s_param",
            "output_mode": (0,),
            "output_port": 1,
            "input_mode": (0,),
            "input_port": 1,
            "sweep_axis_index": 0,
        },
        z0=50.0,
        frequency_index=0,
        dark_mode=True,
    )
    second = _build_sweep_metric_rows(
        sweep_payload=payload,
        family="s",
        metric="magnitude_linear",
        trace_selection={
            "trace": "s_param",
            "output_mode": (0,),
            "output_port": 1,
            "input_mode": (0,),
            "input_port": 1,
            "sweep_axis_index": 1,
        },
        z0=50.0,
        frequency_index=0,
        dark_mode=True,
    )
    assert first["figure"].data[0].y[0] != second["figure"].data[0].y[0]


def test_build_sweep_metric_rows_recomputes_without_process_global_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = simulation_sweep_run_to_payload(
        SimulationSweepRun(
            axes=(SimulationSweepAxis(target_value_ref="Lj", values=(900.0, 1100.0), unit="pH"),),
            points=(
                SimulationSweepPointResult(
                    point_index=0,
                    axis_indices=(0,),
                    axis_values={"Lj": 900.0},
                    result=_sample_result(),
                ),
                SimulationSweepPointResult(
                    point_index=1,
                    axis_indices=(1,),
                    axis_values={"Lj": 1100.0},
                    result=_sample_result(),
                ),
            ),
            representative_point_index=0,
        )
    )
    original_builder = simulation_feature_page._build_simulation_result_figure
    call_count = 0

    def counting_builder(*args: object, **kwargs: object):
        nonlocal call_count
        call_count += 1
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        simulation_feature_page,
        "_build_simulation_result_figure",
        counting_builder,
    )

    kwargs = {
        "sweep_payload": payload,
        "family": "s",
        "metric": "magnitude_linear",
        "trace_selection": {
            "trace": "s_param",
            "output_mode": (0,),
            "output_port": 1,
            "input_mode": (0,),
            "input_port": 1,
            "sweep_axis_index": 0,
        },
        "z0": 50.0,
        "frequency_index": 0,
        "dark_mode": True,
    }
    first_payload = _build_sweep_metric_rows(**kwargs)
    second_payload = _build_sweep_metric_rows(**kwargs)

    assert call_count == 2
    assert first_payload["slice_point_count"] == second_payload["slice_point_count"]
    assert first_payload["trace_labels"] == second_payload["trace_labels"]


def test_build_sweep_metric_rows_multi_axis_slice_and_multi_trace() -> None:
    result_a = _sample_result()
    result_b = _sample_result().model_copy(deep=True)
    result_b.s11_real = [0.45, 0.2, -0.35]
    result_b.s_parameter_real["S11"] = [0.45, 0.2, -0.35]
    result_b.s_parameter_mode_real["om=0|op=1|im=0|ip=1"] = [0.45, 0.2, -0.35]

    sweep_run = SimulationSweepRun(
        axes=(
            SimulationSweepAxis(target_value_ref="Lj", values=(900.0, 1100.0), unit="pH"),
            SimulationSweepAxis(
                target_value_ref="sources[1].current_amp",
                values=(120e-6, 160e-6),
                unit="A",
            ),
        ),
        points=(
            SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0, 0),
                axis_values={"Lj": 900.0, "sources[1].current_amp": 120e-6},
                result=result_a,
            ),
            SimulationSweepPointResult(
                point_index=1,
                axis_indices=(0, 1),
                axis_values={"Lj": 900.0, "sources[1].current_amp": 160e-6},
                result=result_b,
            ),
            SimulationSweepPointResult(
                point_index=2,
                axis_indices=(1, 0),
                axis_values={"Lj": 1100.0, "sources[1].current_amp": 120e-6},
                result=result_b,
            ),
            SimulationSweepPointResult(
                point_index=3,
                axis_indices=(1, 1),
                axis_values={"Lj": 1100.0, "sources[1].current_amp": 160e-6},
                result=result_a,
            ),
        ),
        representative_point_index=0,
    )
    payload = _build_sweep_metric_rows(
        sweep_payload=simulation_sweep_run_to_payload(sweep_run),
        family="s",
        metric="magnitude_linear",
        trace_selections=[
            {
                "trace": "s_param",
                "output_mode": (0,),
                "output_port": 1,
                "input_mode": (0,),
                "input_port": 1,
                "sweep_axis_index": 0,
            },
            {
                "trace": "s_param",
                "output_mode": (0,),
                "output_port": 2,
                "input_mode": (0,),
                "input_port": 1,
                "sweep_axis_index": 1,
            },
        ],
        view_axis_target_value_ref="Lj",
        fixed_axis_indices={"sources[1].current_amp": 1},
        z0=50.0,
        frequency_index=0,
        dark_mode=True,
    )

    assert payload["dimension"] == 2
    assert payload["point_count"] == 4
    assert payload["slice_point_count"] == 2
    assert payload["view_axis_target_value_ref"] == "Lj"
    assert payload["fixed_axis_indices"]["sources[1].current_amp"] == 1
    assert payload["trace_details"][0]["axis_value"] == pytest.approx(900.0)
    assert payload["trace_details"][1]["axis_value"] == pytest.approx(1100.0)
    assert len(payload["figure"].data) == 2


def test_build_trace_batch_data_records_materializes_metadata_only_trace_rows() -> None:
    trace_specs = build_post_processed_trace_specs(
        runtime_output=_sample_transformed_post_processed_sweep_run(),
    )
    payload = persist_trace_batch_bundle(
        bundle_id=404,
        design_id=12,
        design_name="FloatingQubitWithXYLine",
        source_kind="circuit_simulation",
        stage_kind="postprocess",
        setup_kind="circuit_simulation.postprocess",
        setup_payload={"steps": [{"type": "kron_reduction"}]},
        provenance_payload={"input_source_type": "ptc_y"},
        trace_specs=trace_specs,
        summary_payload={"trace_count": len(trace_specs), "run_kind": "parameter_sweep"},
    )

    records = _build_trace_batch_data_records(
        dataset_id=33,
        trace_batch_payload=payload,
    )

    assert len(records) == len(payload["trace_records"])
    assert all(record.dataset_id == 33 for record in records)
    assert all(record.values == [] for record in records)
    assert all(record.store_ref for record in records)
    assert all(record.axes and "length" in record.axes[0] for record in records)
    assert any(record.representation == "imaginary" for record in records)
    assert any(record.parameter.startswith("Y_dm_1_2_dm_1_2") for record in records)
