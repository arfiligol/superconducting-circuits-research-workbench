from __future__ import annotations

import numpy as np
import pandas as pd


def normalize_mode_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    If Mode 1 is entirely zero, shift remaining Mode columns forward and pad the tail with NaN.
    """
    mode_cols = [col for col in df.columns if col.startswith("Mode ")]
    if not mode_cols or "Mode 1" not in df.columns:
        return df

    first_mode = df["Mode 1"].fillna(0.0)
    # Check if all values are effectively zero
    if not np.allclose(first_mode, 0.0):
        return df

    df_clean = df.copy()
    for idx in range(1, len(mode_cols)):
        current_col = f"Mode {idx}"
        next_col = f"Mode {idx + 1}"
        if next_col in df_clean.columns:
            df_clean[current_col] = df_clean[next_col]
        else:
            df_clean[current_col] = np.nan

    df_clean[f"Mode {len(mode_cols)}"] = np.nan
    return df_clean
