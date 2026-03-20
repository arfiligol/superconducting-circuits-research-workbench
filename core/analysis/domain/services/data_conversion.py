from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd

from core.analysis.domain import normalize_trace_record


def _canonical_column_name(axis: dict[str, Any], default: str | None = None) -> str:
    name = str(axis.get("name", ""))
    if default and default.lower() in name.lower():
        name = default
    unit = str(axis.get("unit", ""))
    return f"{name} [{unit}]"


def convert_data_record_to_dataframe(record: object, value_label: str) -> pd.DataFrame:
    """
    Convert a 2D DataRecord into a wide-format DataFrame (or long-format depending on usage).
    The implementation here builds a list of dicts.
    """
    normalized_record = normalize_trace_record(record)
    if len(normalized_record.axes) != 2:
        raise ValueError("Only 2D datasets can be converted to DataFrame.")
    axis_freq, axis_bias = normalized_record.axes
    freq_col = _canonical_column_name(axis_freq, default="Freq")
    bias_col = _canonical_column_name(axis_bias, default="L_jun")
    matrix = normalized_record.values
    rows = []

    # Validation for 2D structure
    if (
        not isinstance(matrix, Sequence)
        or isinstance(matrix, str | bytes)
        or len(matrix) == 0
        or not isinstance(matrix[0], Sequence)
        or isinstance(matrix[0], str | bytes)
    ):
        raise ValueError("Expected 2D matrix for values")

    freq_values = axis_freq.get("values", [])
    bias_values = axis_bias.get("values", [])
    for row_idx, freq in enumerate(freq_values):
        row_vals = matrix[row_idx]
        for col_idx, bias in enumerate(bias_values):
            rows.append(
                {
                    freq_col: float(freq),
                    bias_col: float(bias),
                    value_label: float(row_vals[col_idx]),  # type: ignore
                }
            )
    return pd.DataFrame(rows)
