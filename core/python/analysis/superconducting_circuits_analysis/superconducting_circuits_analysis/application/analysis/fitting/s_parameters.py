from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

import numpy as np
from superconducting_circuits_analysis.domain.math.s_parameters import (
    MultiResonanceVectorFitter,
    fit_notch_s21,
    fit_transmission_s21,
    notch_s21,
    transmission_s21,
)

S21Model = Literal["notch", "transmission"]


def fit_complex_s21_notch(
    frequency_hz: Sequence[float],
    s21_real: Sequence[float],
    s21_imag: Sequence[float],
    *,
    initial_guess: Mapping[str, float] | None = None,
    fit_window_hz: tuple[float, float] | Sequence[float] | None = None,
) -> dict[str, Any]:
    """Fit a complex notch-type S21 response and return PythonCall-friendly values."""
    return _fit_complex_s21_model(
        frequency_hz,
        s21_real,
        s21_imag,
        model="notch",
        initial_guess=initial_guess,
        fit_window_hz=fit_window_hz,
    )


def fit_complex_s21_transmission(
    frequency_hz: Sequence[float],
    s21_real: Sequence[float],
    s21_imag: Sequence[float],
    *,
    initial_guess: Mapping[str, float] | None = None,
    fit_window_hz: tuple[float, float] | Sequence[float] | None = None,
) -> dict[str, Any]:
    """Fit a complex transmission/inline-resonator S21 response."""
    return _fit_complex_s21_model(
        frequency_hz,
        s21_real,
        s21_imag,
        model="transmission",
        initial_guess=initial_guess,
        fit_window_hz=fit_window_hz,
    )


def fit_complex_s21_vector(
    frequency_hz: Sequence[float],
    s21_real: Sequence[float],
    s21_imag: Sequence[float],
    *,
    n_resonators: int,
    bg_poles: int = 2,
    min_q: float = 2.0,
    restrict_to_input_span: bool = True,
) -> dict[str, Any]:
    """Fit a multi-resonance complex S21 response with scikit-rf VectorFitting."""
    try:
        f, s21 = _prepare_trace(frequency_hz, s21_real, s21_imag)
        if n_resonators < 1:
            return _failure("n_resonators must be at least 1.")
        if bg_poles < 0:
            return _failure("bg_poles must be non-negative.")
        if min_q < 0:
            return _failure("min_q must be non-negative.")

        result = MultiResonanceVectorFitter(f, s21).fit(
            n_resonators=int(n_resonators),
            bg_poles=int(bg_poles),
            min_q=float(min_q),
            restrict_to_input_span=bool(restrict_to_input_span),
        )
        model_s21 = np.asarray(result["model_s21"], dtype=complex)
        return {
            "status": "success",
            "model": "vector",
            "resonances": [_vector_resonance_record(item) for item in result.get("resonances", [])],
            "artifacts": [_vector_resonance_record(item) for item in result.get("artifacts", [])],
            "metrics": {"rms_error": _json_number(result.get("cost"))},
            "model_trace": _complex_trace_payload(f, model_s21),
        }
    except Exception as exc:
        return _failure(str(exc))


def _fit_complex_s21_model(
    frequency_hz: Sequence[float],
    s21_real: Sequence[float],
    s21_imag: Sequence[float],
    *,
    model: S21Model,
    initial_guess: Mapping[str, float] | None,
    fit_window_hz: tuple[float, float] | Sequence[float] | None,
) -> dict[str, Any]:
    try:
        f, s21 = _prepare_trace(frequency_hz, s21_real, s21_imag)
        f_fit, s21_fit, window = _apply_fit_window(f, s21, fit_window_hz)
        guess = _normalize_initial_guess(initial_guess)

        if model == "notch":
            params = fit_notch_s21(f_fit, s21_fit, guess)
            model_s21 = notch_s21(
                f_fit,
                params["fr"],
                params["Ql"],
                params["Qc_real"],
                params["Qc_imag"],
                params["a"],
                params["alpha"],
                params["tau"],
            )
        elif model == "transmission":
            params = fit_transmission_s21(f_fit, s21_fit, guess)
            model_s21 = transmission_s21(
                f_fit,
                params["fr"],
                params["Ql"],
                params["a"],
                params["alpha"],
                params["tau"],
            )
        else:
            return _failure(f"Unsupported S21 model: {model}")

        rmse = float(np.sqrt(np.mean(np.abs(model_s21 - s21_fit) ** 2)))
        return {
            "status": "success",
            "model": model,
            "params": _fit_params_payload(params),
            "metrics": {
                "rmse": _json_number(rmse),
                "cost": _json_number(params.get("cost")),
            },
            "fit_window_hz": list(window),
            "fit_curve": _complex_trace_payload(f_fit, model_s21),
        }
    except Exception as exc:
        return _failure(str(exc))


def _prepare_trace(
    frequency_hz: Sequence[float],
    s21_real: Sequence[float],
    s21_imag: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    f = np.asarray(list(frequency_hz), dtype=float)
    real = np.asarray(list(s21_real), dtype=float)
    imag = np.asarray(list(s21_imag), dtype=float)

    if f.ndim != 1 or real.ndim != 1 or imag.ndim != 1:
        raise ValueError("frequency_hz, s21_real, and s21_imag must be one-dimensional.")
    if not (len(f) == len(real) == len(imag)):
        raise ValueError("frequency_hz, s21_real, and s21_imag must have the same length.")
    if len(f) < 3:
        raise ValueError("At least three frequency samples are required.")
    if not np.all(np.isfinite(f)):
        raise ValueError("frequency_hz must contain only finite values.")
    if not np.all(f > 0):
        raise ValueError("frequency_hz must contain only positive values.")
    if not np.all(np.diff(f) > 0):
        raise ValueError("frequency_hz must be strictly increasing.")
    if not np.all(np.isfinite(real)) or not np.all(np.isfinite(imag)):
        raise ValueError("S21 samples must contain only finite real and imaginary values.")

    return f, real + 1j * imag


def _apply_fit_window(
    f: np.ndarray,
    s21: np.ndarray,
    fit_window_hz: tuple[float, float] | Sequence[float] | None,
) -> tuple[np.ndarray, np.ndarray, tuple[float, float]]:
    if fit_window_hz is None:
        return f, s21, (float(f[0]), float(f[-1]))

    window_values = tuple(float(value) for value in fit_window_hz)
    if len(window_values) != 2:
        raise ValueError("fit_window_hz must contain exactly two values.")
    lower, upper = window_values
    if not np.isfinite(lower) or not np.isfinite(upper):
        raise ValueError("fit_window_hz values must be finite.")
    if lower >= upper:
        raise ValueError("fit_window_hz lower bound must be less than upper bound.")

    mask = (f >= lower) & (f <= upper)
    if np.count_nonzero(mask) < 3:
        raise ValueError("fit_window_hz selects fewer than three samples.")
    return f[mask], s21[mask], (lower, upper)


def _normalize_initial_guess(
    initial_guess: Mapping[str, float] | None,
) -> dict[str, float] | None:
    if initial_guess is None:
        return None
    aliases = {
        "fr_hz": "fr",
        "ql": "Ql",
        "qc_real": "Qc_real",
        "qc_imag": "Qc_imag",
        "amplitude": "a",
        "phase_rad": "alpha",
        "delay_s": "tau",
    }
    normalized: dict[str, float] = {}
    for key, value in initial_guess.items():
        target = aliases.get(str(key), str(key))
        normalized[target] = float(value)
    return normalized


def _fit_params_payload(params: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "fr_hz": _json_number(params["fr"]),
        "ql": _json_number(params["Ql"]),
        "qc_real": _json_number(params["Qc_real"]),
        "qc_imag": _json_number(params["Qc_imag"]),
        "qc_mag": _json_number(params["Qc_mag"]),
        "qi": _json_number(params["Qi"]),
        "amplitude": _json_number(params["a"]),
        "phase_rad": _json_number(params["alpha"]),
        "delay_s": _json_number(params["tau"]),
    }


def _vector_resonance_record(item: Mapping[str, Any]) -> dict[str, Any]:
    fr_hz = float(item["fr"])
    ql = float(item["Ql"])
    return {
        "fr_hz": _json_number(fr_hz),
        "ql": _json_number(ql),
        "bandwidth_hz": _json_number(fr_hz / ql if ql > 0 else None),
        "pole_real": _json_number(item.get("pole_real")),
        "pole_imag": _json_number(item.get("pole_imag")),
    }


def _complex_trace_payload(frequency_hz: np.ndarray, trace: np.ndarray) -> dict[str, list[Any]]:
    return {
        "frequency_hz": [_json_number(value) for value in frequency_hz],
        "s21_real": [_json_number(value) for value in np.real(trace)],
        "s21_imag": [_json_number(value) for value in np.imag(trace)],
    }


def _json_number(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if np.isfinite(number) else None


def _failure(reason: str) -> dict[str, Any]:
    return {"status": "failed", "reason": reason}
