"""Tests for characterization analysis execution service."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest

from legacy.legacy_nicegui_archived.services.characterization_runner import (
    CharacterizationRunRequest,
    CharacterizationRunResult,
    SweepSupportDiagnostic,
    _diagnose_analysis_sweep_support_from_records,
    execute_analysis_run,
    execute_characterization_run,
    execute_characterization_run_async,
)
from legacy.legacy_nicegui_archived.services.execution_context import ActorContext, UseCaseContext
from core.analysis.application.services.resonance_extract_service import ResonanceExtractService
from core.analysis.application.services.resonance_fit_service import ResonanceFitService
from core.shared.persistence import DataRecord, database, get_unit_of_work
from core.shared.persistence.models import DesignRecord


def _record(
    *,
    data_type: str,
    parameter: str,
    representation: str,
    axes: list[dict[str, object]],
    values: object,
) -> DataRecord:
    return DataRecord(
        dataset_id=1,
        data_type=data_type,
        parameter=parameter,
        representation=representation,
        axes=axes,
        values=values,
    )


def _trace_record(
    *,
    family: str,
    parameter: str,
    representation: str,
    axes: list[dict[str, object]],
    values: object,
    dataset_id: int = 1,
    trace_id: int | None = None,
) -> dict[str, object]:
    axis_values = {str(axis["name"]): list(axis.get("values", [])) for axis in axes}
    stored_axes = [
        {
            "name": axis["name"],
            "unit": axis.get("unit", ""),
            "length": len(axis_values[str(axis["name"])]),
        }
        for axis in axes
    ]
    return {
        "id": trace_id,
        "design_id": dataset_id,
        "family": family,
        "parameter": parameter,
        "representation": representation,
        "axes": stored_axes,
        "axis_values": axis_values,
        "store_ref": {"values": values},
    }


def _configure_temp_database(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SC_DATABASE_PATH", str(tmp_path / "characterization.db"))
    database.get_engine.cache_clear()


def test_execute_analysis_run_dispatches_admittance_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_extract_admittance(
        self: object,
        dataset_id: str,
        *,
        record_ids: list[int] | None = None,
        trace_mode_group: str | None = None,
    ) -> None:
        captured["dataset_id"] = dataset_id
        captured["record_ids"] = record_ids
        captured["trace_mode_group"] = trace_mode_group

    monkeypatch.setattr(
        "core.analysis.application.services.resonance_extract_service.ResonanceExtractService.extract_admittance",
        _fake_extract_admittance,
    )

    execute_analysis_run(
        analysis_id="admittance_extraction",
        dataset_id=12,
        config_state={},
        trace_record_ids=[1, 2],
        trace_mode_group="base",
    )

    assert captured == {
        "dataset_id": "12",
        "record_ids": [1, 2],
        "trace_mode_group": "base",
    }


def test_execute_analysis_run_dispatches_squid_fitting_with_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_run_squid_fitting(
        self: object,
        *,
        dataset_id: int,
        config: object,
        record_ids: list[int] | None = None,
        trace_mode_group: str | None = None,
    ) -> None:
        captured["dataset_id"] = dataset_id
        captured["config"] = config
        captured["record_ids"] = record_ids
        captured["trace_mode_group"] = trace_mode_group

    monkeypatch.setattr(
        "core.analysis.application.services.characterization_fitting_service.CharacterizationFittingService.run_squid_fitting",
        _fake_run_squid_fitting,
    )

    execute_analysis_run(
        analysis_id="squid_fitting",
        dataset_id=7,
        config_state={"fit_model": "FIXED_C", "fixed_c_pf": 0.123},
        trace_record_ids=[9],
        trace_mode_group="sideband",
    )

    config = captured["config"]
    assert captured["dataset_id"] == 7
    assert captured["record_ids"] == [9]
    assert captured["trace_mode_group"] == "sideband"
    assert config.fit_model == "FIXED_C"
    assert config.fixed_c_pf == pytest.approx(0.123)


def test_execute_characterization_run_returns_context_and_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    progress_updates = []

    def _fake_extract_admittance(
        self: object,
        dataset_id: str,
        *,
        record_ids: list[int] | None = None,
        trace_mode_group: str | None = None,
    ) -> None:
        captured["dataset_id"] = dataset_id
        captured["record_ids"] = record_ids
        captured["trace_mode_group"] = trace_mode_group

    monkeypatch.setattr(
        "core.analysis.application.services.resonance_extract_service.ResonanceExtractService.extract_admittance",
        _fake_extract_admittance,
    )

    result = execute_characterization_run(
        CharacterizationRunRequest(
            analysis_id="admittance_extraction",
            dataset_id=12,
            config_state={},
            trace_record_ids=[1, 2],
            trace_mode_group="base",
            context=UseCaseContext(
                actor=ActorContext(actor_id=9, role="user", requested_by="api"),
                source="worker",
                task_id=22,
            ),
        ),
        progress_callback=progress_updates.append,
    )

    assert captured == {
        "dataset_id": "12",
        "record_ids": [1, 2],
        "trace_mode_group": "base",
    }
    assert result.context.actor.actor_id == 9
    assert result.selected_trace_ids == (1, 2)
    assert [update.phase for update in result.progress_updates] == [
        "running",
        "persisted",
        "completed",
    ]
    assert progress_updates[0].to_payload()["details"]["analysis_id"] == "admittance_extraction"


def test_execute_characterization_run_persists_analysis_run_contract(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_temp_database(tmp_path, monkeypatch)
    progress_updates: list[object] = []

    try:
        with get_unit_of_work() as uow:
            design = uow.datasets.add(
                DesignRecord(
                    name="Characterization Boundary Design",
                    source_meta={},
                    parameters={},
                )
            )
            uow.flush()
            assert design.id is not None
            design_id = int(design.id)
            uow.commit()

        monkeypatch.setattr(
            "core.analysis.application.services.resonance_extract_service.ResonanceExtractService.extract_admittance",
            lambda self, dataset_id, **kwargs: None,
        )

        result = execute_characterization_run(
            CharacterizationRunRequest(
                analysis_id="admittance_extraction",
                analysis_label="Admittance Extraction",
                dataset_id=design_id,
                config_state={},
                run_id="analysis-run-1",
                trace_record_ids=[11, 12],
                selected_batch_ids=[7],
                selected_scope_token="selected_trace_records",
                trace_mode_group="base",
                summary_payload={"selected_source_summary": [{"source_kind": "persisted_batch"}]},
                context=UseCaseContext(
                    actor=ActorContext(actor_id=4, role="admin", requested_by="ui"),
                    source="ui",
                    task_id=99,
                ),
            ),
            progress_callback=progress_updates.append,
        )

        assert result.analysis_run is not None
        assert result.analysis_run.id is not None
        assert result.selected_batch_ids == (7,)
        assert [update.phase for update in result.progress_updates] == [
            "running",
            "persisted",
            "completed",
        ]

        with get_unit_of_work() as uow:
            persisted_run = uow.result_bundles.analysis_runs.get(int(result.analysis_run.id))

        assert persisted_run is not None
        assert persisted_run.analysis_id == "admittance_extraction"
        assert persisted_run.analysis_label == "Admittance Extraction"
        assert persisted_run.run_id == "analysis-run-1"
        assert persisted_run.input_trace_ids == [11, 12]
        assert persisted_run.input_batch_ids == [7]
        assert persisted_run.input_scope == "selected_trace_records"
        assert persisted_run.summary_payload["selected_source_summary"] == [
            {"source_kind": "persisted_batch"}
        ]
        assert progress_updates[1].to_payload()["details"]["analysis_run_id"] == int(
            result.analysis_run.id
        )
    finally:
        database.get_engine.cache_clear()


def test_execute_characterization_run_async_owns_heartbeat_and_warning_progress(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_temp_database(tmp_path, monkeypatch)
    progress_updates: list[object] = []

    try:
        with get_unit_of_work() as uow:
            design = uow.datasets.add(
                DesignRecord(
                    name="Characterization Async Design",
                    source_meta={},
                    parameters={},
                )
            )
            uow.flush()
            assert design.id is not None
            design_id = int(design.id)
            uow.commit()

        monkeypatch.setattr(
            "core.analysis.application.services.resonance_extract_service.ResonanceExtractService.extract_admittance",
            lambda self, dataset_id, **kwargs: None,
        )

        async def _delayed_executor(
            operation,
        ) -> CharacterizationRunResult:
            await asyncio.sleep(0.02)
            return operation()

        result = asyncio.run(
            execute_characterization_run_async(
                CharacterizationRunRequest(
                    analysis_id="admittance_extraction",
                    analysis_label="Admittance Extraction",
                    dataset_id=design_id,
                    config_state={},
                    run_id="analysis-run-async",
                    trace_record_ids=[21],
                    selected_scope_token="selected_trace_records",
                    trace_mode_group="base",
                    context=UseCaseContext(
                        actor=ActorContext(actor_id=8, role="user", requested_by="api"),
                        source="worker",
                        task_id=44,
                    ),
                ),
                executor=_delayed_executor,
                heartbeat_interval_seconds=0.005,
                long_running_warning_after_seconds=0.01,
                progress_callback=progress_updates.append,
            )
        )

        phases = [update.phase for update in result.progress_updates]
        assert phases[0] == "heartbeat"
        assert "warning" in phases
        assert "persisted" in phases
        assert "completed" in phases
        assert result.analysis_run is not None
        assert any(
            update.to_payload()["details"].get("analysis_run_id")
            == int(result.analysis_run.id or 0)
            for update in progress_updates
        )
    finally:
        database.get_engine.cache_clear()


def test_diagnose_analysis_sweep_support_marks_y11_and_squid_ready_for_2d_ljun() -> None:
    y11_record = _record(
        data_type="y_parameters",
        parameter="Y11",
        representation="imaginary",
        axes=[
            {"name": "Freq", "values": [4.0, 5.0]},
            {"name": "L_jun", "values": [1.0, 2.0]},
        ],
        values=[[0.1, 0.2], [0.3, 0.4]],
    )

    y11_support = _diagnose_analysis_sweep_support_from_records(
        analysis_id="y11_fit",
        records=[y11_record],
    )
    squid_support = _diagnose_analysis_sweep_support_from_records(
        analysis_id="squid_fitting",
        records=[y11_record],
    )
    admittance_support = _diagnose_analysis_sweep_support_from_records(
        analysis_id="admittance_extraction",
        records=[y11_record],
    )

    assert y11_support == SweepSupportDiagnostic(
        status="sweep-ready",
        reason="2D Freq x L_jun sweeps are supported.",
    )
    assert squid_support == SweepSupportDiagnostic(
        status="sweep-ready",
        reason="2D Freq x L_jun sweeps are supported.",
    )
    assert admittance_support == SweepSupportDiagnostic(
        status="sweep-ready",
        reason="2D Freq x L_jun sweeps are supported for admittance extraction.",
    )


def test_diagnose_analysis_sweep_support_accepts_trace_record_contract_for_2d_ljun() -> None:
    y_trace = _trace_record(
        family="y_matrix",
        parameter="Y_dm_dm",
        representation="imag",
        axes=[
            {"name": "frequency", "unit": "GHz", "values": [4.0, 5.0]},
            {"name": "L_jun", "unit": "nH", "values": [1.0, 2.0]},
        ],
        values=[[0.1, 0.2], [0.3, 0.4]],
    )

    diagnostic = _diagnose_analysis_sweep_support_from_records(
        analysis_id="admittance_extraction",
        records=[y_trace],
    )

    assert diagnostic == SweepSupportDiagnostic(
        status="sweep-ready",
        reason="2D Freq x L_jun sweeps are supported for admittance extraction.",
    )


def test_diagnose_analysis_sweep_support_accepts_generic_single_axis_2d_admittance() -> None:
    y_trace = _trace_record(
        family="y_matrix",
        parameter="Y_dm_dm [om=(0,), im=(0,)]",
        representation="imag",
        axes=[
            {"name": "frequency", "unit": "GHz", "values": [4.0, 5.0]},
            {"name": "L_q", "unit": "nH", "values": [10.0, 12.0]},
        ],
        values=[[0.1, 0.2], [0.3, 0.4]],
    )

    diagnostic = _diagnose_analysis_sweep_support_from_records(
        analysis_id="admittance_extraction",
        records=[y_trace],
    )

    assert diagnostic == SweepSupportDiagnostic(
        status="sweep-ready",
        reason="2D Freq x L_q sweeps are supported for admittance extraction.",
    )


def test_diagnose_analysis_sweep_support_stays_source_agnostic_for_saved_traces() -> None:
    layout_trace = {
        **_trace_record(
            family="y_matrix",
            parameter="Y_dm_dm",
            representation="imag",
            axes=[
                {"name": "frequency", "unit": "GHz", "values": [4.0, 5.0]},
                {"name": "L_jun", "unit": "nH", "values": [1.0, 2.0]},
            ],
            values=[[0.1, 0.2], [0.3, 0.4]],
            trace_id=31,
        ),
        "source_kind": "layout_simulation",
        "stage_kind": "manual_export",
    }
    measurement_trace = {
        **_trace_record(
            family="y_matrix",
            parameter="Y_dm_dm",
            representation="imag",
            axes=[
                {"name": "frequency", "unit": "GHz", "values": [4.0, 5.0]},
                {"name": "L_jun", "unit": "nH", "values": [1.0, 2.0]},
            ],
            values=[[0.1, 0.2], [0.3, 0.4]],
            trace_id=32,
        ),
        "source_kind": "measurement",
        "stage_kind": "import",
    }
    circuit_trace = {
        **_trace_record(
            family="y_matrix",
            parameter="Y_dm_dm",
            representation="imag",
            axes=[
                {"name": "frequency", "unit": "GHz", "values": [4.0, 5.0]},
                {"name": "L_jun", "unit": "nH", "values": [1.0, 2.0]},
            ],
            values=[[0.1, 0.2], [0.3, 0.4]],
            trace_id=33,
        ),
        "source_kind": "circuit_simulation",
        "stage_kind": "manual_export",
    }

    diagnostic = _diagnose_analysis_sweep_support_from_records(
        analysis_id="admittance_extraction",
        records=[layout_trace, measurement_trace, circuit_trace],
    )

    assert diagnostic == SweepSupportDiagnostic(
        status="sweep-ready",
        reason="2D Freq x L_jun sweeps are supported for admittance extraction.",
    )


def test_diagnose_analysis_sweep_support_blocks_wrong_sweep_axis() -> None:
    wrong_axis_record = _record(
        data_type="y_parameters",
        parameter="Y11",
        representation="imaginary",
        axes=[
            {"name": "Freq", "values": [4.0, 5.0]},
            {"name": "Pump", "values": [0.0, 1.0]},
        ],
        values=[[0.1, 0.2], [0.3, 0.4]],
    )

    diagnostic = _diagnose_analysis_sweep_support_from_records(
        analysis_id="y11_fit",
        records=[wrong_axis_record],
    )

    assert diagnostic == SweepSupportDiagnostic(
        status="blocked",
        reason="This fitting path requires a 2D Freq x L_jun sweep.",
    )


def test_resonance_extract_service_persists_generic_sweep_axis_for_2d_sweeps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_calls: list[dict[str, object]] = []
    service = ResonanceExtractService()
    dataset = SimpleNamespace(id=1, name="generic-axis")
    generic_axis_record = _trace_record(
        trace_id=21,
        family="y_matrix",
        parameter="Y_dm_dm [om=(0,), im=(0,)]",
        representation="imag",
        axes=[
            {"name": "frequency", "unit": "GHz", "values": [4.0, 5.0, 6.0]},
            {"name": "L_q", "unit": "nH", "values": [10.0, 12.0]},
        ],
        values=[
            [-1.0, -2.0],
            [1.0, 2.0],
            [2.0, 3.0],
        ],
    )

    monkeypatch.setattr(service.dataset_service, "get_dataset", lambda _: dataset)
    monkeypatch.setattr(
        service.data_record_service,
        "list_records",
        lambda _: [generic_axis_record],
    )
    monkeypatch.setattr(
        service.data_record_service,
        "get_record",
        lambda record_id: {21: generic_axis_record}[record_id],
    )
    monkeypatch.setattr(
        service.param_service,
        "create_or_update_param",
        lambda dataset_id, **kwargs: captured_calls.append({"dataset_id": dataset_id, **kwargs}),
    )

    result = service.extract_admittance("1", record_ids=[21], trace_mode_group="base")

    assert result["dataset_id"] == 1
    sweep_params = [call for call in captured_calls if str(call["name"]).startswith("L_q")]
    mode_params = [call for call in captured_calls if str(call["name"]).startswith("mode_1_ghz")]
    assert {call["name"] for call in sweep_params} == {"L_q_b0", "L_q_b1"}
    assert {call["name"] for call in mode_params} == {"mode_1_ghz_b0", "mode_1_ghz_b1"}
    assert sweep_params[0]["extra"]["sweep_axis"] == "L_q"
    assert sweep_params[0]["extra"]["sweep_value"] == pytest.approx(10.0)
    assert mode_params[1]["extra"]["sweep_index"] == 1


def test_diagnose_analysis_sweep_support_marks_s21_ljun_2d_as_sweep_ready() -> None:
    s21_record = _record(
        data_type="s_parameters",
        parameter="S21",
        representation="real",
        axes=[
            {"name": "Freq", "values": [4.0, 5.0]},
            {"name": "L_jun", "values": [1.0, 2.0]},
        ],
        values=[[0.1, 0.2], [0.3, 0.4]],
    )

    diagnostic = _diagnose_analysis_sweep_support_from_records(
        analysis_id="s21_resonance_fit",
        records=[s21_record],
    )

    assert diagnostic == SweepSupportDiagnostic(
        status="sweep-ready",
        reason="2D Freq x L_jun sweeps persist per-slice bias and render Mode vs L_jun.",
    )


def test_diagnose_analysis_sweep_support_marks_s21_non_ljun_2d_as_partial() -> None:
    s21_record = _record(
        data_type="s_parameters",
        parameter="S21",
        representation="real",
        axes=[
            {"name": "Freq", "values": [4.0, 5.0]},
            {"name": "Pump", "values": [0.0, 1.0]},
        ],
        values=[[0.1, 0.2], [0.3, 0.4]],
    )

    diagnostic = _diagnose_analysis_sweep_support_from_records(
        analysis_id="s21_resonance_fit",
        records=[s21_record],
    )

    assert diagnostic == SweepSupportDiagnostic(
        status="partial",
        reason=(
            "Single-axis 2D sweeps run per slice, but only L_jun sweeps get the canonical "
            "Mode vs L_jun artifact."
        ),
    )


def test_diagnose_analysis_sweep_support_blocks_multi_axis_sweeps() -> None:
    multi_axis_record = _record(
        data_type="s_parameters",
        parameter="S21",
        representation="real",
        axes=[
            {"name": "Freq", "values": [4.0, 5.0]},
            {"name": "L_jun", "values": [1.0, 2.0]},
            {"name": "Pump", "values": [0.0, 1.0]},
        ],
        values=[[[0.1, 0.2], [0.3, 0.4]], [[0.5, 0.6], [0.7, 0.8]]],
    )

    diagnostic = _diagnose_analysis_sweep_support_from_records(
        analysis_id="s21_resonance_fit",
        records=[multi_axis_record],
    )

    assert diagnostic == SweepSupportDiagnostic(
        status="blocked",
        reason="S21 resonance fitting supports at most one sweep axis.",
    )


def test_execute_analysis_run_blocks_unsupported_sweep_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "legacy.legacy_nicegui_archived.services.characterization_runner.diagnose_analysis_sweep_support",
        lambda **_: SweepSupportDiagnostic(
            status="blocked",
            reason="S21 resonance fitting supports at most one sweep axis.",
        ),
    )

    with pytest.raises(
        ValueError,
        match=r"Sweep support: blocked - S21 resonance fitting supports at most one sweep axis\.",
    ):
        execute_analysis_run(
            analysis_id="s21_resonance_fit",
            dataset_id=5,
            config_state={},
            trace_record_ids=[1],
            trace_mode_group=None,
        )


def test_resonance_fit_service_persists_ljun_bias_params_for_2d_sweeps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_calls: list[dict[str, object]] = []
    service = ResonanceFitService()
    dataset = SimpleNamespace(id=1)
    real_record = _record(
        data_type="s_parameters",
        parameter="S21",
        representation="real",
        axes=[
            {"name": "Freq", "values": [4.0, 5.0, 6.0, 7.0, 8.0]},
            {"name": "L_jun", "values": [1.1, 1.6]},
        ],
        values=[
            [0.1, 0.2],
            [0.1, 0.2],
            [0.1, 0.2],
            [0.1, 0.2],
            [0.1, 0.2],
        ],
    )
    real_record.id = 10
    imag_record = _record(
        data_type="s_parameters",
        parameter="S21",
        representation="imaginary",
        axes=real_record.axes,
        values=[
            [0.01, 0.02],
            [0.01, 0.02],
            [0.01, 0.02],
            [0.01, 0.02],
            [0.01, 0.02],
        ],
    )
    imag_record.id = 11

    monkeypatch.setattr(service.dataset_service, "get_dataset", lambda _: dataset)
    monkeypatch.setattr(
        service.data_record_service,
        "list_records",
        lambda _: [real_record, imag_record],
    )
    monkeypatch.setattr(
        service.data_record_service,
        "get_record",
        lambda record_id: {10: real_record, 11: imag_record}[record_id],
    )
    monkeypatch.setattr(
        service.param_service,
        "create_or_update_param",
        lambda dataset_id, **kwargs: captured_calls.append({"dataset_id": dataset_id, **kwargs}),
    )
    monkeypatch.setattr(
        "core.analysis.application.services.resonance_fit_service.fit_notch_s21",
        lambda f_arr, s21_arr: {
            "fr": float(f_arr[2]),
            "Ql": 1000.0,
            "Qc_mag": 1200.0,
            "Qi": 6000.0,
            "tau": 1e-9,
            "Qc_real": 1200.0,
            "Qc_imag": 0.0,
            "a": 1.0,
            "alpha": 0.0,
        },
    )
    monkeypatch.setattr(
        "core.analysis.application.services.resonance_fit_service.notch_s21",
        lambda f_arr, **kwargs: np.ones_like(f_arr, dtype=complex),
    )

    service.perform_fit(
        dataset_identifier="1",
        parameter="S21",
        model="notch",
        record_ids=[10, 11],
    )

    mode_params = [call for call in captured_calls if str(call["name"]).startswith("mode_1_ghz")]
    l_jun_params = [call for call in captured_calls if str(call["name"]).startswith("L_jun")]

    assert {call["name"] for call in mode_params} == {"mode_1_ghz_b0", "mode_1_ghz_b1"}
    assert {call["name"] for call in l_jun_params} == {"L_jun_b0", "L_jun_b1"}
    assert l_jun_params[0]["extra"]["sweep_axis"] == "L_jun"
    assert l_jun_params[0]["extra"]["sweep_index"] == 0
    assert l_jun_params[1]["extra"]["sweep_index"] == 1


def test_resonance_fit_service_accepts_trace_record_contract_for_2d_sweeps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_calls: list[dict[str, object]] = []
    service = ResonanceFitService()
    dataset = SimpleNamespace(id=1)
    real_record = _trace_record(
        trace_id=10,
        family="s_matrix",
        parameter="S21",
        representation="real",
        axes=[
            {"name": "frequency", "unit": "GHz", "values": [4.0, 5.0, 6.0, 7.0, 8.0]},
            {"name": "L_jun", "unit": "nH", "values": [1.1, 1.6]},
        ],
        values=[
            [0.1, 0.2],
            [0.1, 0.2],
            [0.1, 0.2],
            [0.1, 0.2],
            [0.1, 0.2],
        ],
    )
    imag_record = _trace_record(
        trace_id=11,
        family="s_matrix",
        parameter="S21",
        representation="imaginary",
        axes=[
            {"name": "frequency", "unit": "GHz", "values": [4.0, 5.0, 6.0, 7.0, 8.0]},
            {"name": "L_jun", "unit": "nH", "values": [1.1, 1.6]},
        ],
        values=[
            [0.01, 0.02],
            [0.01, 0.02],
            [0.01, 0.02],
            [0.01, 0.02],
            [0.01, 0.02],
        ],
    )

    monkeypatch.setattr(service.dataset_service, "get_dataset", lambda _: dataset)
    monkeypatch.setattr(
        service.data_record_service,
        "list_records",
        lambda _: [real_record, imag_record],
    )
    monkeypatch.setattr(
        service.data_record_service,
        "get_record",
        lambda record_id: {10: real_record, 11: imag_record}[record_id],
    )
    monkeypatch.setattr(
        service.param_service,
        "create_or_update_param",
        lambda dataset_id, **kwargs: captured_calls.append({"dataset_id": dataset_id, **kwargs}),
    )
    monkeypatch.setattr(
        "core.analysis.application.services.resonance_fit_service.fit_notch_s21",
        lambda f_arr, s21_arr: {
            "fr": float(f_arr[2]),
            "Ql": 1000.0,
            "Qc_mag": 1200.0,
            "Qi": 6000.0,
            "tau": 1e-9,
            "Qc_real": 1200.0,
            "Qc_imag": 0.0,
            "a": 1.0,
            "alpha": 0.0,
        },
    )
    monkeypatch.setattr(
        "core.analysis.application.services.resonance_fit_service.notch_s21",
        lambda f_arr, **kwargs: np.ones_like(f_arr, dtype=complex),
    )

    service.perform_fit(
        dataset_identifier="1",
        parameter="S21",
        model="notch",
        record_ids=[10, 11],
    )

    l_jun_params = [call for call in captured_calls if str(call["name"]).startswith("L_jun")]

    assert {call["name"] for call in l_jun_params} == {"L_jun_b0", "L_jun_b1"}
    assert l_jun_params[0]["extra"]["sweep_axis"] == "L_jun"


def test_execute_analysis_run_rejects_unknown_analysis_id() -> None:
    with pytest.raises(ValueError, match="Unsupported analysis id"):
        execute_analysis_run(
            analysis_id="unknown_analysis",
            dataset_id=1,
            config_state={},
            trace_record_ids=None,
            trace_mode_group=None,
        )
