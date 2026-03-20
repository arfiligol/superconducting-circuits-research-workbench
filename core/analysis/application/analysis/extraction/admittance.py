from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.shared.logging import get_logger

CsvPath = str | Path
logger = get_logger(__name__)


def extract_mode_from_admittance(csv_file_path: CsvPath) -> pd.DataFrame | None:
    """
    Extracts resonant frequencies from HFSS CSV data based on Imaginary Admittance (Im(Y)=0).
    """
    try:
        csv_path = Path(csv_file_path)
        df = pd.read_csv(csv_path)
    except Exception as e:
        logger.error("Failed to read file %s: %s", csv_file_path, e)
        return None

    return extract_modes_from_dataframe(df)


def extract_modes_from_dataframe(df: pd.DataFrame) -> pd.DataFrame | None:
    """
    Extract resonant frequencies from a pre-loaded DataFrame.
    """
    # --- 1. Identify Columns ---
    freq_cols = [c for c in df.columns if "Freq" in c]
    if not freq_cols:
        logger.error("Frequency column (Freq) not found.")
        return None
    freq_col = freq_cols[0]

    y_cols = [c for c in df.columns if "im(" in c.lower() and ("Y" in c or "Z" in c)]
    if not y_cols:
        # Fallback for some pre-processed dataframes
        if "ImY" in df.columns:
            y_col = "ImY"
        elif "im(Y) []" in df.columns:
            y_col = "im(Y) []"
        else:
            logger.error("Admittance/Impedance Imaginary part column not found.")
            return None
    else:
        y_col = y_cols[0]

    sweep_cols = [c for c in df.columns if c not in {freq_col, y_col}]
    sweep_col = sweep_cols[0] if sweep_cols else None

    # --- 2. Process Data ---
    results: list[dict[str, float]] = []

    unique_Ls: list[float]
    unique_Ls = sorted(float(value) for value in df[sweep_col].unique()) if sweep_col else [0.0]

    for l_val in unique_Ls:
        # Filter data
        subset = (
            df[df[sweep_col] == l_val].sort_values(freq_col)
            if sweep_col
            else df.sort_values(freq_col)
        )

        freqs = subset[freq_col].to_numpy(dtype=float)
        ys = subset[y_col].to_numpy(dtype=float)

        crossings: list[float] = []

        # Find Zero Crossings
        for i in range(len(ys) - 1):
            y1, y2 = ys[i], ys[i + 1]
            if y1 == 0:
                crossings.append(freqs[i])
            elif y1 * y2 < 0:  # Sign change indicates crossing
                # Linear interpolation
                denom = y2 - y1
                # Avoid division by zero
                if denom == 0:
                    x_zero = freqs[i]
                else:
                    x_zero = freqs[i] - y1 * (freqs[i + 1] - freqs[i]) / denom
                crossings.append(x_zero)

        # Store results
        entry: dict[str, float] = {str(sweep_col or "L_jun").split(" [", 1)[0]: float(l_val)}
        for idx, f in enumerate(crossings):
            entry[f"Mode {idx + 1}"] = f
        results.append(entry)

    return pd.DataFrame(results)
