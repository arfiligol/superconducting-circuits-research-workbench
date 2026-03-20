"""Application service for Characterization SQUID/Y11 fitting workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from core.analysis.application.analysis.extraction.admittance import extract_modes_from_dataframe
from core.analysis.application.analysis.extraction.cleaning import normalize_mode_columns
from core.analysis.application.analysis.fitting.modes import (
    fit_squid_model,
    fit_squid_model_with_Ls,
    fit_squid_model_with_Ls_fixed_C,
)
from core.analysis.application.analysis.fitting.y11 import fit_y11_response
from core.analysis.application.services.fit_result_persistence import (
    persist_lc_squid_fit_outputs,
    persist_y11_fit_outputs,
)
from core.analysis.application.services.squid_fitting import FitModel
from core.analysis.application.services.trace_record_materializer import materialize_trace_record
from core.analysis.domain import (
    normalize_trace_record,
    trace_record_data_type,
    trace_record_representation,
)
from core.analysis.domain.schemas.fitting import AnalysisEntry
from core.analysis.domain.services.data_conversion import convert_data_record_to_dataframe
from core.shared.persistence import DeviceType, get_unit_of_work


@dataclass(frozen=True)
class SquidFittingConfig:
    """Runtime config for SQUID fitting in Characterization."""

    fit_model: str
    ls_min_nh: float | None
    ls_max_nh: float | None
    c_min_pf: float | None
    c_max_pf: float | None
    fixed_c_pf: float | None
    fit_min_nh: float | None
    fit_max_nh: float | None


@dataclass(frozen=True)
class Y11FittingConfig:
    """Runtime config for Y11 fitting in Characterization."""

    ls1_init_nh: float
    ls2_init_nh: float
    c_init_pf: float
    c_max_pf: float


class CharacterizationFittingService:
    """Orchestrates fitting runs and persistence for Characterization page."""

    def run_squid_fitting(
        self,
        *,
        dataset_id: int,
        config: SquidFittingConfig,
        record_ids: list[int] | None,
        trace_mode_group: str | None,
    ) -> dict[str, Any]:
        """Run SQUID fitting and persist result artifacts."""
        dataset_name, data_record = self._resolve_dataset_and_y11_record(dataset_id, record_ids)
        df_raw = self._build_y11_dataframe(data_record)
        df_modes = extract_modes_from_dataframe(df_raw)
        if df_modes is None or df_modes.empty:
            raise ValueError("No resonance modes found from selected traces.")

        df_modes = normalize_mode_columns(df_modes)
        bounds = {
            "Ls_nH": (config.ls_min_nh, config.ls_max_nh),
            "C_pF": (config.c_min_pf, config.c_max_pf),
        }
        fit_window = (config.fit_min_nh, config.fit_max_nh)
        fit_model = self._resolve_fit_model(config.fit_model)

        if fit_model == FitModel.NO_LS:
            fit_results = fit_squid_model(df_modes, bounds, fit_window)
        elif fit_model == FitModel.WITH_LS:
            fit_results = fit_squid_model_with_Ls(df_modes, bounds, fit_window)
        else:
            if config.fixed_c_pf is None:
                raise ValueError("Fixed C (pF) is required when fit model is FIXED_C.")
            fit_results = fit_squid_model_with_Ls_fixed_C(
                df_modes, float(config.fixed_c_pf), bounds, fit_window
            )

        successful_modes = [
            mode_name
            for mode_name, result in fit_results.items()
            if getattr(result, "status", "failed") == "success"
        ]
        if not successful_modes:
            raise ValueError("SQUID fitting produced no successful mode fit.")

        entry = AnalysisEntry(filename=dataset_name, fits=fit_results)
        summary = persist_lc_squid_fit_outputs(
            dataset_id=dataset_id,
            entry=entry,
            device_type=DeviceType.OTHER,
            replace_existing=True,
            trace_mode_group=trace_mode_group,
        )
        return {
            "method": "lc_squid_fit",
            "successful_modes": successful_modes,
            "created_data_records": summary.data_records,
            "created_derived_parameters": summary.derived_parameters,
        }

    def run_y11_fitting(
        self,
        *,
        dataset_id: int,
        config: Y11FittingConfig,
        record_ids: list[int] | None,
        trace_mode_group: str | None,
    ) -> dict[str, Any]:
        """Run Y11 response fitting and persist result artifacts."""
        _, data_record = self._resolve_dataset_and_y11_record(dataset_id, record_ids)
        df_raw = self._build_y11_dataframe(data_record)
        fit_result = fit_y11_response(
            df_raw,
            ls1_init_nh=config.ls1_init_nh,
            ls2_init_nh=config.ls2_init_nh,
            c_init_pf=config.c_init_pf,
            c_max_pf=config.c_max_pf,
        )
        if fit_result.status != "success":
            raise ValueError(fit_result.reason)

        summary = persist_y11_fit_outputs(
            dataset_id=dataset_id,
            result=fit_result,
            device_type=DeviceType.OTHER,
            replace_existing=True,
            trace_mode_group=trace_mode_group,
        )
        return {
            "method": "y11_fit",
            "rmse": float(fit_result.metrics.RMSE),
            "created_data_records": summary.data_records,
            "created_derived_parameters": summary.derived_parameters,
        }

    def _resolve_dataset_and_y11_record(
        self,
        dataset_id: int,
        record_ids: list[int] | None,
    ) -> tuple[str, object]:
        with get_unit_of_work() as uow:
            dataset = uow.datasets.get(dataset_id)
            if dataset is None:
                raise ValueError(f"Dataset ID {dataset_id} not found.")

            selected_ids = {int(record_id) for record_id in record_ids or []}
            records = [
                normalize_trace_record(record)
                for record in uow.data_records.list_by_dataset(dataset_id)
            ]
            if selected_ids:
                records = [record for record in records if record.id in selected_ids]

            y11_records = [record for record in records if self._is_y11_imaginary_record(record)]
            if not y11_records:
                raise ValueError("No compatible Y11 imaginary trace found in selected scope.")

            y11_records.sort(key=lambda record: int(record.id or 0))
            selected_record = uow.data_records.get(int(y11_records[0].id or 0))
            if selected_record is None:
                raise ValueError("Selected Y11 trace could not be reloaded.")
            return str(dataset.name), materialize_trace_record(selected_record)

    @staticmethod
    def _is_y11_imaginary_record(record: object) -> bool:
        data_type = trace_record_data_type(record)
        if data_type != "y_parameters":
            return False

        normalized_record = normalize_trace_record(record)
        parameter = str(normalized_record.parameter).split(" [", maxsplit=1)[0].strip().upper()
        if parameter != "Y11":
            return False

        return trace_record_representation(record) == "imaginary"

    @staticmethod
    def _resolve_fit_model(raw_value: str) -> FitModel:
        normalized = str(raw_value).strip().upper()
        if normalized == "NO_LS":
            return FitModel.NO_LS
        if normalized == "FIXED_C":
            return FitModel.FIXED_C
        return FitModel.WITH_LS

    @staticmethod
    def _build_y11_dataframe(record: object) -> pd.DataFrame:
        normalized_record = normalize_trace_record(record)
        values_array = np.asarray(normalized_record.values, dtype=float)
        if values_array.ndim == 2:
            return convert_data_record_to_dataframe(normalized_record, value_label="im(Y) []")

        if not normalized_record.axes:
            raise ValueError("Selected record has no axes metadata.")
        freq_values = np.asarray(normalized_record.axes[0].get("values", []), dtype=float)
        if freq_values.size == 0:
            raise ValueError("Selected record has empty frequency axis.")
        freq_ghz = freq_values / 1e9 if np.max(freq_values) > 1e6 else freq_values

        if values_array.ndim == 1:
            if values_array.shape[0] != freq_ghz.shape[0]:
                raise ValueError("Y11 values/frequency axis length mismatch.")
            df = pd.DataFrame(
                {
                    "Freq [GHz]": freq_ghz.tolist(),
                    "im(Y) []": values_array.tolist(),
                }
            )
            if len(normalized_record.axes) > 1 and str(
                normalized_record.axes[1].get("name", "")
            ).lower() in {"l_jun", "l_ind"}:
                axis_values = normalized_record.axes[1].get("values", [])
                if axis_values:
                    df["L_jun [nH]"] = float(axis_values[0])
            return df

        raise ValueError("Selected Y11 record must be 1D or 2D.")
