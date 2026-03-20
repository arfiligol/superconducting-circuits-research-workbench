from __future__ import annotations

import re
import typing
from collections.abc import Mapping

import numpy as np
import pandas as pd

from core.analysis.application.analysis.extraction.admittance import extract_modes_from_dataframe
from core.analysis.application.services.data_record_management import (
    DataRecordManagementService,
)
from core.analysis.application.services.dataset_management import DatasetManagementService
from core.analysis.application.services.parameter_management import ParameterManagementService
from core.analysis.application.services.trace_record_materializer import materialize_trace_record
from core.analysis.domain import (
    normalize_trace_record,
    trace_record_data_type,
    trace_record_dataset_id,
    trace_record_representation,
)
from core.shared.persistence import get_unit_of_work


def _axis_display_name(axis: Mapping[str, typing.Any] | None, fallback: str = "Sweep Axis") -> str:
    name = str((axis or {}).get("name", "")).strip()
    return name or fallback


def _axis_unit(axis: Mapping[str, typing.Any] | None) -> str:
    return str((axis or {}).get("unit", "")).strip()


def _axis_column_label(axis: Mapping[str, typing.Any] | None) -> str:
    name = _axis_display_name(axis)
    unit = _axis_unit(axis)
    return f"{name} [{unit}]" if unit else name


def _sanitize_parameter_name(name: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", str(name).strip())
    normalized = normalized.strip("_")
    return normalized or "sweep_axis"


class ResonanceExtractService:
    """
    Application service orchestrating resonance extraction from existing dataset records.
    (Non-fitting methods like Im(Y)=0 Zero-Crossing)
    """

    def __init__(self) -> None:
        self.dataset_service = DatasetManagementService()
        self.data_record_service = DataRecordManagementService()
        self.param_service = ParameterManagementService()

    def extract_admittance(
        self,
        dataset_identifier: str,
        bias_index: int | None = None,
        record_ids: list[int] | None = None,
        trace_mode_group: str | None = None,
    ) -> dict[str, typing.Any]:
        """
        Extract resonance modes from a dataset's Admittance (Im(Y)) records.
        Returns the extracted modes and optionally saves them as derived parameters.
        """
        dataset = self.dataset_service.get_dataset(dataset_identifier)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_identifier}")

        # Find matching admittance records
        all_records = self.data_record_service.list_records(dataset.id)
        if record_ids is not None:
            selected_ids = set(record_ids)
            all_records = [
                record
                for record in all_records
                if normalize_trace_record(record).id in selected_ids
            ]
        y_records = [
            r
            for r in all_records
            if trace_record_dataset_id(r) == dataset.id
            and trace_record_data_type(r) == "y_parameters"
            and trace_record_representation(r) == "imaginary"
        ]

        if not y_records:
            raise ValueError(
                f"No Imaginary Admittance records found for dataset {dataset_identifier}"
            )

        # Fetch detailed records
        detailed_records = [
            self.data_record_service.get_record(int(trace_id))
            for record in y_records
            for trace_id in [normalize_trace_record(record).id]
            if trace_id is not None
        ]

        dfs = []
        sweep_axis_unit: str = ""
        for rec in detailed_records:
            if rec is None:
                continue
            record = materialize_trace_record(rec)

            y_vals = np.array(record.values, dtype=float)
            if not record.axes or not record.axes[0].get("values"):
                continue

            f_vals = np.array(record.axes[0]["values"], dtype=float)

            if y_vals.ndim == 1:
                if len(y_vals) != len(f_vals):
                    continue
                df_part = pd.DataFrame(
                    {
                        "Freq [GHz]": f_vals / 1e9
                        if np.max(f_vals) > 1e6
                        else f_vals,  # Handle Hz vs GHz
                        "im(Y) []": y_vals,
                    }
                )
                if len(record.axes) > 1 and record.axes[1].get("values"):
                    axis = record.axes[1]
                    axis_values = [float(value) for value in axis.get("values", [])]
                    if axis_values:
                        df_part[_axis_column_label(axis)] = float(axis_values[0])
                        sweep_axis_unit = sweep_axis_unit or _axis_unit(axis)
                dfs.append(df_part)

            elif y_vals.ndim == 2:
                axis = record.axes[1] if len(record.axes) > 1 else {}
                axis_values = [float(v) for v in axis.get("values", [])]
                if len(axis_values) != y_vals.shape[1]:
                    axis_values = [float(index) for index in range(y_vals.shape[1])]
                axis_column = _axis_column_label(axis)

                f_ghz = f_vals / 1e9 if np.max(f_vals) > 1e6 else f_vals

                for bi, axis_value in enumerate(axis_values):
                    if bi >= y_vals.shape[1]:
                        break
                    df_part = pd.DataFrame(
                        {
                            "Freq [GHz]": f_ghz,
                            "im(Y) []": y_vals[:, bi],
                            axis_column: float(axis_value),
                        }
                    )
                    dfs.append(df_part)
                sweep_axis_unit = sweep_axis_unit or _axis_unit(axis)

        if not dfs:
            raise ValueError("No valid frequency/admittance axes found in records.")

        full_df = pd.concat(dfs, ignore_index=True)

        # Run extraction
        result_df = extract_modes_from_dataframe(full_df)

        if result_df is None or result_df.empty:
            raise ValueError("No resonance modes found from extraction.")

        # Slice by bias index if requested
        if bias_index is not None:
            if bias_index >= len(result_df):
                raise ValueError(
                    f"Selected bias_index {bias_index} is out of bounds "
                    f"(max: {len(result_df) - 1})."
                )
            result_df = result_df.iloc[[bias_index]]

        # Persist extracted modes to the dataset as derived parameters
        method_name = "admittance_zero_crossing"
        normalized_trace_mode = str(trace_mode_group or "").strip().lower() or "unknown"

        # Replace previous outputs from the same extraction method to avoid stale mode inflation.
        with get_unit_of_work() as cleanup_uow:
            for existing_param in cleanup_uow.derived_params.list_by_dataset(dataset.id):
                if existing_param.method == method_name:
                    cleanup_uow.derived_params.delete(existing_param)
            cleanup_uow.commit()

        for idx, row in result_df.iterrows():
            mode_cols = [c for c in row.index if "Mode" in str(c)]
            sweep_cols = [str(column) for column in row.index if str(column) not in mode_cols]
            sweep_column = sweep_cols[0] if sweep_cols else None
            sweep_value = row.get(sweep_column, None) if sweep_column else None
            # Formatting the param name based on bias index
            suffix = f"_b{idx}" if len(result_df) > 1 else ""
            sweep_extra = {"trace_mode_group": normalized_trace_mode}
            if sweep_column is not None and sweep_value is not None and not pd.isna(sweep_value):
                sweep_extra.update(
                    {
                        "sweep_axis": str(sweep_column),
                        "sweep_value": float(sweep_value),
                        "sweep_index": idx,
                    }
                )

            if sweep_column is not None and sweep_value is not None and not pd.isna(sweep_value):
                sweep_param_name = (
                    "L_jun"
                    if str(sweep_column).strip().lower() in {"l_jun", "l_ind"}
                    else _sanitize_parameter_name(str(sweep_column))
                )
                self.param_service.create_or_update_param(
                    dataset.id,
                    name=f"{sweep_param_name}{suffix}",
                    value=float(sweep_value),
                    unit=sweep_axis_unit or "",
                    device_type="resonator",
                    method=method_name,
                    extra=dict(sweep_extra),
                )

            for m_idx, mode_col in enumerate(mode_cols, start=1):
                f_ghz = row[mode_col]
                if pd.isna(f_ghz):
                    continue

                match = re.search(r"(\d+)", str(mode_col))
                mode_index = int(match.group(1)) if match else m_idx

                self.param_service.create_or_update_param(
                    dataset.id,
                    name=f"mode_{mode_index}_ghz{suffix}",
                    value=float(f_ghz),
                    unit="GHz",
                    device_type="resonator",
                    method=method_name,
                    extra=dict(sweep_extra),
                )

        return {
            "dataset_id": dataset.id,
            "extraction_method": method_name,
            "results": result_df,
        }
