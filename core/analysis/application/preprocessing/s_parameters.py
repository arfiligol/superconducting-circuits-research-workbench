from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from core.analysis.application.preprocessing.dataset_payload import (
    AxisPayload,
    DataPayload,
    DatasetPayload,
)


def derive_parameter_name(input_str: str) -> str:
    """Extracts S-parameter types like S11 or S21 from the string."""
    lower = input_str.lower()
    for p in ["s11", "s21", "s12", "s22"]:
        if p in lower:
            return p.upper()
    raise ValueError(f"Unable to derive phase parameter name (S11, S21, etc.) from '{input_str}'")


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


def detect_representation(filename: str, df: pd.DataFrame) -> tuple[str, str, str, str]:
    """Detect l_col, freq_col, data_col, and representation from the dataframe and filename."""
    l_cols = [c for c in df.columns if "l_jun" in c.lower() or "l_ind" in c.lower()]
    if not l_cols:
        raise ValueError("Unable to locate L_jun column.")

    freq_cols = [c for c in df.columns if "freq" in c.lower()]
    if not freq_cols:
        raise ValueError("Unable to locate frequency column.")

    data_cols = [c for c in df.columns if c not in l_cols and c not in freq_cols]
    if not data_cols:
        raise ValueError(f"Unable to locate S-parameter data column in {filename}.")
    data_col_name = data_cols[0]

    # Check representation from filename or columns
    combined = f"{filename} {data_col_name}".lower()

    representation = "magnitude"  # default fallback

    if "re_" in combined or "real" in combined or combined.startswith("re"):
        representation = "real"
    elif "im_" in combined or "imag" in combined or combined.startswith("im"):
        representation = "imaginary"
    elif any(kw in combined for kw in ["phase", "deg", "rad", "ang", "cang"]):
        representation = "unwrapped_phase" if "cang" in combined else "phase"
    elif "mag" in combined or "amp" in combined:
        representation = "magnitude"

    data_col = [data_col_name]

    if not data_col:
        raise ValueError(f"Unable to locate S-parameter data column in {filename}.")

    return l_cols[0], freq_cols[0], data_col[0], representation


def reshape_matrix(df: pd.DataFrame, l_col: str, freq_col: str, data_col: str) -> pd.DataFrame:
    pivot = df.pivot(index=freq_col, columns=l_col, values=data_col).sort_index()
    pivot = pivot[sorted(pivot.columns, key=float)]
    return pivot


def process_hfss_s_parameters(raw_path: Path, l_jun: float | None = None) -> DatasetPayload:
    """Orchestrate the processing of a generic HFSS S-Parameter CSV file."""
    df = pd.read_csv(raw_path)
    df = ensure_l_jun_column(df, l_jun)
    l_col, freq_col, data_col, representation = detect_representation(raw_path.name, df)

    parameter_name = derive_parameter_name(raw_path.name)
    pivot = reshape_matrix(df, l_col, freq_col, data_col)

    # Unit conversion for phase
    if representation in ["phase", "unwrapped_phase"]:
        combined = f"{raw_path.name} {data_col}".lower()
        is_degrees = bool("rad" not in combined or "deg" in combined)
        if is_degrees:
            pivot = pd.DataFrame(np.deg2rad(pivot), index=pivot.index, columns=pivot.columns)

    freq_axis = AxisPayload(name="Freq", unit="GHz", values=pivot.index.tolist())
    bias_axis = AxisPayload(name="L_jun", unit="nH", values=[float(x) for x in pivot.columns])

    data_record = DataPayload(
        data_type="s_parameters",
        parameter=parameter_name,
        representation=representation,
        axes=[freq_axis, bias_axis],
        values=pivot.values.tolist(),
    )

    return DatasetPayload(
        source_meta={"origin": "layout_simulation"},
        parameters={},
        data_records=[data_record],
        raw_files=[str(raw_path.resolve())],
    )
