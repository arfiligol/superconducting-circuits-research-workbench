from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import skrf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run scikit-rf Vector Fitting on complex readout S21 data."
    )
    parser.add_argument(
        "--input-csv", required=True, help="CSV with frequency_hz, S21_real, S21_imag"
    )
    parser.add_argument("--model-csv", required=True, help="Output CSV for fitted model trace")
    parser.add_argument(
        "--resonance-csv", required=True, help="Output CSV for fitted resonance summary"
    )
    parser.add_argument(
        "--resonators", type=int, default=2, help="Number of physical resonators to fit"
    )
    parser.add_argument("--bg-poles", type=int, default=2, help="Number of real background poles")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input_csv)
    model_path = Path(args.model_csv)
    resonance_path = Path(args.resonance_csv)

    df = pd.read_csv(input_path)
    freq_hz = df["frequency_hz"].to_numpy()
    s21 = df["S21_real"].to_numpy() + 1j * df["S21_imag"].to_numpy()

    freq = skrf.Frequency.from_f(freq_hz, unit="Hz")
    s_matrix = np.zeros((len(freq_hz), 2, 2), dtype=complex)
    s_matrix[:, 1, 0] = s21
    s_matrix[:, 0, 0] = s21
    ntwk = skrf.Network(frequency=freq, s=s_matrix)

    vf = skrf.VectorFitting(ntwk)
    vf.vector_fit(n_poles_real=args.bg_poles, n_poles_cmplx=args.resonators)

    model_s21 = vf.get_model_response(1, 0, freq_hz)

    resonances: list[dict[str, float]] = []
    fmin_hz = float(np.min(freq_hz))
    fmax_hz = float(np.max(freq_hz))
    for pole in np.asarray(vf.poles):
        omega = float(np.imag(pole))
        sigma = float(-np.real(pole))
        if omega <= 0 or sigma <= 0:
            continue
        fr_hz = omega / (2 * np.pi)
        ql = omega / (2 * sigma)
        if ql <= 2.0:
            continue
        if fr_hz < fmin_hz or fr_hz > fmax_hz:
            continue
        resonances.append({"fr": fr_hz, "Ql": ql})
    resonances.sort(key=lambda item: item["fr"])

    model_df = pd.DataFrame(
        {
            "frequency_hz": freq_hz,
            "frequency_ghz": freq_hz / 1e9,
            "S21_model_real": model_s21.real,
            "S21_model_imag": model_s21.imag,
            "S21_model_mag": abs(model_s21),
        }
    )
    model_df.to_csv(model_path, index=False)

    resonance_rows: list[dict[str, float | str]] = []
    for item in resonances:
        fr_hz = float(item["fr"])
        ql = float(item["Ql"])
        bw_hz = fr_hz / ql if ql > 0 else float("inf")
        resonance_rows.append(
            {
                "fr_hz": fr_hz,
                "fr_ghz": fr_hz / 1e9,
                "Ql": ql,
                "bw_hz": bw_hz,
                "bw_mhz": bw_hz / 1e6,
            }
        )

    resonance_df = pd.DataFrame(resonance_rows).sort_values("bw_hz", ascending=False)
    if len(resonance_df) >= 1:
        resonance_df.loc[resonance_df.index[0], "role"] = "Purcell filter"
    if len(resonance_df) >= 2:
        resonance_df.loc[resonance_df.index[1], "role"] = "Readout resonator"
    if len(resonance_df) > 2:
        resonance_df.loc[resonance_df.index[2:], "role"] = "Additional mode"
    resonance_df.to_csv(resonance_path, index=False)


if __name__ == "__main__":
    main()
