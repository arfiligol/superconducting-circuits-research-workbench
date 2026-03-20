"""Persist fitting outputs into SQLite."""

from __future__ import annotations

from dataclasses import dataclass

from core.analysis.domain.schemas.fitting import AnalysisEntry, Y11FitResult
from core.shared.persistence import DataRecord, DerivedParameter, DeviceType, get_unit_of_work

LC_SQUID_FIT_METHOD = "lc_squid_fit"
Y11_FIT_METHOD = "y11_fit"


@dataclass(frozen=True)
class PersistSummary:
    """Created-row counters after persisting fit outputs."""

    data_records: int
    derived_parameters: int


def persist_lc_squid_fit_outputs(
    dataset_id: int,
    entry: AnalysisEntry,
    device_type: DeviceType = DeviceType.OTHER,
    replace_existing: bool = True,
    trace_mode_group: str | None = None,
) -> PersistSummary:
    """
    Persist fitting outputs for one dataset.

    Stored outputs:
    - DataRecord(data_type=analysis_result, parameter=f_resonance)
    - DataRecord(data_type=analysis_result, parameter=f_resonance_fit)
    - DerivedParameter(name=Ls_nH, C_eff_pF, method=lc_squid_fit)
    """
    created_data_records = 0
    created_derived_params = 0

    with get_unit_of_work() as uow:
        dataset = uow.datasets.get(dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset ID {dataset_id} not found.")

        if replace_existing:
            _remove_previous_lc_squid_fit_outputs(uow, dataset_id)

        for mode_name, mode_result in entry.fits.items():
            if mode_result.status != "success":
                continue

            raw_axes = [
                {
                    "name": "L_jun",
                    "unit": "nH",
                    "values": [float(value) for value in mode_result.raw_data.L_jun],
                }
            ]
            raw_values = [float(value) for value in mode_result.raw_data.Freq]

            uow.data_records.add(
                DataRecord(
                    dataset_id=dataset_id,
                    data_type="analysis_result",
                    parameter="f_resonance",
                    representation=mode_name,
                    axes=raw_axes,
                    values=raw_values,
                )
            )
            created_data_records += 1

            fit_axes = [
                {
                    "name": "L_jun",
                    "unit": "nH",
                    "values": [float(value) for value in mode_result.fit_curve.L_jun],
                }
            ]
            fit_values = [float(value) for value in mode_result.fit_curve.Freq]

            uow.data_records.add(
                DataRecord(
                    dataset_id=dataset_id,
                    data_type="analysis_result",
                    parameter="f_resonance_fit",
                    representation=mode_name,
                    axes=fit_axes,
                    values=fit_values,
                )
            )
            created_data_records += 1

            shared_extra = {
                "mode": mode_name,
                "rmse": float(mode_result.metrics.RMSE),
                "source": LC_SQUID_FIT_METHOD,
                "trace_mode_group": _normalize_trace_mode_group(trace_mode_group),
            }

            uow.derived_params.add(
                DerivedParameter(
                    dataset_id=dataset_id,
                    device_type=device_type,
                    name="Ls_nH",
                    value=float(mode_result.params.Ls_nH),
                    unit="nH",
                    method=LC_SQUID_FIT_METHOD,
                    extra=shared_extra,
                )
            )
            created_derived_params += 1

            uow.derived_params.add(
                DerivedParameter(
                    dataset_id=dataset_id,
                    device_type=device_type,
                    name="C_eff_pF",
                    value=float(mode_result.params.C_eff_pF),
                    unit="pF",
                    method=LC_SQUID_FIT_METHOD,
                    extra=shared_extra,
                )
            )
            created_derived_params += 1

        uow.commit()

    return PersistSummary(
        data_records=created_data_records,
        derived_parameters=created_derived_params,
    )


def persist_y11_fit_outputs(
    dataset_id: int,
    result: Y11FitResult,
    device_type: DeviceType = DeviceType.OTHER,
    replace_existing: bool = True,
    trace_mode_group: str | None = None,
) -> PersistSummary:
    """Persist Y11 fitting outputs for one dataset."""
    if result.status != "success":
        raise ValueError(f"Y11 fit did not succeed: {result.reason}")

    created_data_records = 0
    created_derived_params = 0
    normalized_mode = _normalize_trace_mode_group(trace_mode_group)

    with get_unit_of_work() as uow:
        dataset = uow.datasets.get(dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset ID {dataset_id} not found.")

        if replace_existing:
            _remove_previous_y11_fit_outputs(uow, dataset_id)

        raw_axes = [
            {
                "name": "Freq",
                "unit": "GHz",
                "values": [float(value) for value in result.raw_data.freq_ghz],
            },
            {
                "name": "L_jun",
                "unit": "nH",
                "values": [float(value) for value in result.raw_data.L_jun],
            },
        ]
        fit_axes = [
            {
                "name": "Freq",
                "unit": "GHz",
                "values": [float(value) for value in result.fit_curve.freq_ghz],
            },
            {
                "name": "L_jun",
                "unit": "nH",
                "values": [float(value) for value in result.fit_curve.L_jun],
            },
        ]
        uow.data_records.add(
            DataRecord(
                dataset_id=dataset_id,
                data_type="analysis_result",
                parameter="y11_imag_raw",
                representation="Y11",
                axes=raw_axes,
                values=[float(value) for value in result.raw_data.imag_y],
            )
        )
        created_data_records += 1
        uow.data_records.add(
            DataRecord(
                dataset_id=dataset_id,
                data_type="analysis_result",
                parameter="y11_imag_fit",
                representation="Y11",
                axes=fit_axes,
                values=[float(value) for value in result.fit_curve.imag_y],
            )
        )
        created_data_records += 1

        shared_extra = {
            "source": Y11_FIT_METHOD,
            "rmse": float(result.metrics.RMSE),
            "trace_mode_group": normalized_mode,
        }
        y11_params = [
            ("Ls1_nH", float(result.params.Ls1_nH), "nH"),
            ("Ls2_nH", float(result.params.Ls2_nH), "nH"),
            ("C_pF", float(result.params.C_pF), "pF"),
            ("RMSE", float(result.metrics.RMSE), ""),
        ]
        for name, value, unit in y11_params:
            uow.derived_params.add(
                DerivedParameter(
                    dataset_id=dataset_id,
                    device_type=device_type,
                    name=name,
                    value=value,
                    unit=unit,
                    method=Y11_FIT_METHOD,
                    extra=shared_extra,
                )
            )
            created_derived_params += 1

        uow.commit()

    return PersistSummary(
        data_records=created_data_records,
        derived_parameters=created_derived_params,
    )


def _remove_previous_lc_squid_fit_outputs(uow, dataset_id: int) -> None:
    """Delete older SQUID fitting outputs for idempotent persistence."""
    for record in uow.data_records.list_by_dataset(dataset_id):
        if record.data_type != "analysis_result":
            continue
        if record.parameter in {"f_resonance", "f_resonance_fit"}:
            uow.data_records.delete(record)

    for param in uow.derived_params.list_by_dataset(dataset_id):
        if param.method != LC_SQUID_FIT_METHOD:
            continue
        if param.name in {"Ls_nH", "C_eff_pF"}:
            uow.derived_params.delete(param)


def _remove_previous_y11_fit_outputs(uow, dataset_id: int) -> None:
    """Delete older Y11 fit outputs for idempotent persistence."""
    for record in uow.data_records.list_by_dataset(dataset_id):
        if record.data_type != "analysis_result":
            continue
        if record.parameter in {"y11_imag_raw", "y11_imag_fit"}:
            uow.data_records.delete(record)

    for param in uow.derived_params.list_by_dataset(dataset_id):
        if param.method != Y11_FIT_METHOD:
            continue
        if param.name in {"Ls1_nH", "Ls2_nH", "C_pF", "RMSE"}:
            uow.derived_params.delete(param)


def _normalize_trace_mode_group(raw_value: str | None) -> str:
    """Normalize trace-mode token persisted on derived parameter metadata."""
    normalized = str(raw_value or "").strip().lower()
    if normalized in {"base", "signal"}:
        return "base"
    if normalized == "sideband":
        return "sideband"
    return "all"
