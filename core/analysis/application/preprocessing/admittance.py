from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.analysis.application.preprocessing.dataset_payload import (
    AxisPayload,
    DataPayload,
    DatasetPayload,
)


def detect_columns(df: pd.DataFrame) -> tuple[str, str, str]:
    l_cols = [c for c in df.columns if "l_jun" in c.lower() or "l_ind" in c.lower()]
    if not l_cols:
        raise ValueError("Unable to locate L_jun column.")
    freq_cols = [c for c in df.columns if "freq" in c.lower()]
    if not freq_cols:
        raise ValueError("Unable to locate frequency column.")
    y_cols = [c for c in df.columns if "y" in c.lower()]
    if not y_cols:
        raise ValueError("Unable to locate admittance column.")
    return l_cols[0], freq_cols[0], y_cols[0]


def ensure_l_jun_column(df: pd.DataFrame, l_jun: float | None) -> pd.DataFrame:
    """Ensure an L_jun column exists; inject one for single-bias files when provided."""
    l_cols = [c for c in df.columns if "l_jun" in c.lower() or "l_ind" in c.lower()]
    if l_cols:
        return df
    if l_jun is None:
        raise ValueError(
            "Unable to locate L_jun column. For single-bias CSV files, provide --l-jun <nH>."
        )
    df_with_bias = df.copy()
    df_with_bias["L_jun [nH]"] = float(l_jun)
    return df_with_bias


def reshape_matrix(df: pd.DataFrame, l_col: str, freq_col: str, y_col: str) -> pd.DataFrame:
    pivot = df.pivot(index=freq_col, columns=l_col, values=y_col).sort_index()
    # Sort columns (L_jun values) numerically
    pivot = pivot[sorted(pivot.columns, key=float)]
    return pivot


def derive_parameter_name(input_str: str) -> str:
    lower = input_str.lower()
    if "y11" in lower:
        return "Y11"
    if "yin" in lower:
        return "Yin"
    if "y22" in lower:
        return "Y22"
    if "y12" in lower:
        return "Y12"
    if "y21" in lower:
        return "Y21"
    raise ValueError(
        f"Unable to derive admittance parameter name (Y11, Yin, etc.) from '{input_str}'"
    )


def build_dataset_payload(
    pivot: pd.DataFrame,
    raw_path: str,
    parameter_name: str,
) -> DatasetPayload:
    frequency_axis = AxisPayload(name="Freq", unit="GHz", values=pivot.index.tolist())
    bias_axis = AxisPayload(name="L_jun", unit="nH", values=[float(x) for x in pivot.columns])
    values = pivot.values.tolist()

    data_record = DataPayload(
        data_type="y_parameters",
        parameter=parameter_name,
        representation="imaginary",
        axes=[frequency_axis, bias_axis],
        values=values,
    )

    return DatasetPayload(
        source_meta={"origin": "layout_simulation"},
        parameters={},
        data_records=[data_record],
        raw_files=[raw_path],
    )


def process_hfss_admittance_file(raw_path: Path, l_jun: float | None = None) -> DatasetPayload:
    """Orchestrate the processing of a single HFSS CSV file into a dataset payload."""
    df = pd.read_csv(raw_path)
    df = ensure_l_jun_column(df, l_jun)
    l_col, freq_col, y_col = detect_columns(df)
    pivot = reshape_matrix(df, l_col, freq_col, y_col)
    parameter_name = derive_parameter_name(raw_path.name)
    return build_dataset_payload(pivot, str(raw_path.resolve()), parameter_name)
