"""Application entry points for repository-owned S21 fitting workflows.

Knowledge:
    Notch resonator complex S21 fit:
    https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/notch-resonator-complex-s21-fit.qmd
    Network trace views:
    https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd
    Poles, zeros, and residues:
    https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/poles-zeros-residues.qmd
    Vector fitting and passivity:
    https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/vector-fitting-passivity.qmd

This module owns input normalization, fit-window application, orchestration,
and PythonCall-friendly result payloads. Numerical models live in the domain
module; reusable theory belongs to the linked SCQ_Design knowledge base.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any, Literal, cast

import numpy as np
from superconducting_circuits_analysis.domain.math.s_parameters import (
    MultiResonanceVectorFitter,
    fit_notch_s21,
    fit_transmission_s21,
    transmission_s21,
)

S21Model = Literal["notch", "transmission"]
_NOTCH_INITIAL_GUESS_KEYS = (
    "fr_hz",
    "ql",
    "qc_real",
    "qc_imag",
    "amplitude",
    "phase_rad",
    "delay_s",
)


def fit_complex_s21_notch(
    frequency_hz: Sequence[float],
    s21_real: Sequence[float],
    s21_imag: Sequence[float],
    *,
    initial_guess: Mapping[str, float] | None = None,
    fit_window_hz: tuple[float, float] | Sequence[float] | None = None,
) -> dict[str, Any]:
    """Fit one bracketed complex notch and publish auditable evidence.

    Numerical convergence is distinct from the reported exact ``qi_status``;
    this API does not apply a fit-quality or near-zero-Qi acceptance threshold.

    Args:
        frequency_hz: Strictly increasing positive frequencies in hertz.
        s21_real: Real parts of the complex S21 samples.
        s21_imag: Imaginary parts of the complex S21 samples.
        initial_guess: Optional mapping containing exactly the seven canonical
            physical fields documented by the SCQ_Design knowledge node.
        fit_window_hz: Optional inclusive lower and upper fit-window bounds.

    Returns:
        A PythonCall- and JSON-friendly success or failure payload. On success,
        ``fit_window_hz`` is the actual sampled interval and
        ``requested_fit_window_hz`` is the caller's exact requested pair or
        null when no pair was supplied.
    """
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
    bg_poles: int,
    min_q: float,
    restrict_to_input_span: bool = True,
) -> dict[str, Any]:
    """Fit one scalar complex S21 trace with scikit-rf VectorFitting.

    The internal one-response scikit-rf ``Network`` is only a carrier for the
    scalar samples; this result is not a physical network model and makes no
    passivity or reciprocity claim.
    """
    try:
        f, s21 = _prepare_trace(frequency_hz, s21_real, s21_imag)
        if isinstance(n_resonators, (bool, np.bool_)) or not isinstance(
            n_resonators, (int, np.integer)
        ):
            return _failure("n_resonators must be an integer.")
        if isinstance(bg_poles, (bool, np.bool_)) or not isinstance(bg_poles, (int, np.integer)):
            return _failure("bg_poles must be an integer.")
        n_resonators_value = int(n_resonators)
        bg_poles_value = int(bg_poles)
        if n_resonators_value < 1:
            return _failure("n_resonators must be at least 1.")
        if bg_poles_value < 0:
            return _failure("bg_poles must be non-negative.")
        if isinstance(min_q, (bool, np.bool_)) or not isinstance(min_q, Real):
            return _failure("min_q must be a real number.")
        min_q_value = float(min_q)
        if not np.isfinite(min_q_value) or min_q_value < 0:
            return _failure("min_q must be finite and non-negative.")
        if not isinstance(restrict_to_input_span, (bool, np.bool_)):
            return _failure("restrict_to_input_span must be a Boolean.")
        restrict_to_span = bool(restrict_to_input_span)

        result = MultiResonanceVectorFitter(f, s21).fit(
            n_resonators=n_resonators_value,
            bg_poles=bg_poles_value,
            min_q=min_q_value,
            restrict_to_input_span=restrict_to_span,
        )
        model_s21 = np.asarray(result["model_s21"], dtype=complex)
        payload = {
            "status": "success",
            "model": "scalar_s21_vector",
            "fit_settings": {
                "n_resonators": n_resonators_value,
                "bg_poles": bg_poles_value,
                "min_q": min_q_value,
                "restrict_to_input_span": restrict_to_span,
            },
            "resonances": [_vector_resonance_record(item) for item in result.get("resonances", [])],
            "artifacts": [_vector_resonance_record(item) for item in result.get("artifacts", [])],
            "metrics": {"rms_error": _json_number(result["rms_error"])},
            "model_trace": _complex_trace_payload(f, model_s21),
        }
        json.dumps(payload, allow_nan=False)
        return payload
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
        f_fit, s21_fit, window, requested_window = _apply_fit_window(f, s21, fit_window_hz)
        params: Mapping[str, Any]

        if model == "notch":
            guess = _normalize_notch_initial_guess(initial_guess, f_fit)
            params = fit_notch_s21(f_fit, s21_fit, guess)
            model_s21 = np.asarray(params["model_s21"], dtype=complex)
            if model_s21.shape != s21_fit.shape or not np.all(np.isfinite(model_s21)):
                raise ValueError("Notch fit returned a non-finite or incomplete fitted trace.")
        elif model == "transmission":
            guess = _normalize_initial_guess(initial_guess)
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
        payload: dict[str, Any] = {
            "status": "success",
            "model": model,
            "params": _fit_params_payload(params),
            "fit_window_hz": list(window),
            "requested_fit_window_hz": (
                list(requested_window) if requested_window is not None else None
            ),
            "fit_curve": _complex_trace_payload(f_fit, model_s21),
        }
        if model == "notch":
            payload.update(
                {
                    "initial_guess": _notch_initial_guess_payload(
                        cast(Mapping[str, Any], params["initial_guess"])
                    ),
                    "fit_settings": params["fit_settings"],
                    "optimizer": params["optimizer"],
                    "metrics": {
                        "complex_s21_rmse": _json_number(rmse),
                        "least_squares_cost": _json_number(params["least_squares_cost"]),
                    },
                }
            )
            _validate_notch_success_payload(payload)
        else:
            payload["metrics"] = {
                "rmse": _json_number(rmse),
                "cost": _json_number(params.get("cost")),
            }
        json.dumps(payload, allow_nan=False)
        return payload
    except Exception as exc:
        return _failure(str(exc))


def _prepare_trace(
    frequency_hz: Sequence[float],
    s21_real: Sequence[float],
    s21_imag: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    f = _strict_real_array(frequency_hz, "frequency_hz")
    real = _strict_real_array(s21_real, "s21_real")
    imag = _strict_real_array(s21_imag, "s21_imag")

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
) -> tuple[
    np.ndarray,
    np.ndarray,
    tuple[float, float],
    tuple[float, float] | None,
]:
    if fit_window_hz is None:
        return f, s21, (float(f[0]), float(f[-1])), None

    window_values = _strict_real_array(fit_window_hz, "fit_window_hz")
    if window_values.ndim != 1 or len(window_values) != 2:
        raise ValueError("fit_window_hz must contain exactly two values.")
    lower, upper = (float(value) for value in window_values)
    if not np.isfinite(lower) or not np.isfinite(upper):
        raise ValueError("fit_window_hz values must be finite.")
    if lower >= upper:
        raise ValueError("fit_window_hz lower bound must be less than upper bound.")

    mask = (f >= lower) & (f <= upper)
    if np.count_nonzero(mask) < 3:
        raise ValueError("fit_window_hz selects fewer than three samples.")
    selected_f = f[mask]
    return (
        selected_f,
        s21[mask],
        (float(selected_f[0]), float(selected_f[-1])),
        (lower, upper),
    )


def _strict_real_array(values: Sequence[float], name: str) -> np.ndarray:
    raw_values = list(values)
    if any(
        isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
        for value in raw_values
    ):
        raise ValueError(f"{name} must contain only real numbers, not implicit coercions.")
    return np.asarray(raw_values, dtype=float)


def _normalize_notch_initial_guess(
    initial_guess: Mapping[str, float] | None,
    frequency_hz: np.ndarray,
) -> dict[str, float] | None:
    if initial_guess is None:
        return None

    supplied_keys = set(initial_guess)
    required_keys: set[str] = set(_NOTCH_INITIAL_GUESS_KEYS)
    missing = sorted(required_keys - supplied_keys)
    unknown = sorted(str(key) for key in supplied_keys - required_keys)
    if missing or unknown:
        raise ValueError(
            "initial_guess must contain exactly "
            f"{list(_NOTCH_INITIAL_GUESS_KEYS)}; missing={missing}, unknown={unknown}."
        )

    values: dict[str, float] = {}
    for key in _NOTCH_INITIAL_GUESS_KEYS:
        value = initial_guess[key]
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise ValueError(f"initial_guess[{key!r}] must be a real number.")
        converted = float(value)
        if not np.isfinite(converted):
            raise ValueError(f"initial_guess[{key!r}] must be finite.")
        values[key] = converted

    if values["fr_hz"] <= 0.0 or values["ql"] <= 0.0 or values["amplitude"] <= 0.0:
        raise ValueError("initial_guess fr_hz, ql, and amplitude must be positive.")
    if complex(values["qc_real"], values["qc_imag"]) == 0.0:
        raise ValueError("initial_guess complex Qc must be nonzero.")
    if not frequency_hz[0] < values["fr_hz"] < frequency_hz[-1]:
        raise ValueError("initial_guess fr_hz must lie inside the selected fit window.")

    return {
        "fr": values["fr_hz"],
        "Ql": values["ql"],
        "Qc_real": values["qc_real"],
        "Qc_imag": values["qc_imag"],
        "a": values["amplitude"],
        "alpha": values["phase_rad"],
        "tau": values["delay_s"],
    }


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
    payload: dict[str, Any] = {
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
    if "inverse_Qi" in params:
        payload.update(
            {
                "inverse_qi": _json_number(params["inverse_Qi"]),
                "qi_status": str(params["Qi_status"]),
                "phase_reference_hz": _json_number(params["phase_reference_hz"]),
                "phase_at_reference_rad": _json_number(params["phase_at_reference_rad"]),
            }
        )
    return payload


def _notch_initial_guess_payload(initial_guess: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "fr_hz": _json_number(initial_guess["fr"]),
        "ql": _json_number(initial_guess["Ql"]),
        "qc_real": _json_number(initial_guess["Qc_real"]),
        "qc_imag": _json_number(initial_guess["Qc_imag"]),
        "amplitude": _json_number(initial_guess["a"]),
        "phase_rad": _json_number(initial_guess["alpha"]),
        "delay_s": _json_number(initial_guess["tau"]),
    }


def _validate_notch_success_payload(payload: Mapping[str, Any]) -> None:
    params = cast(Mapping[str, Any], payload["params"])
    _require_finite_fields(
        params,
        (
            "fr_hz",
            "ql",
            "qc_real",
            "qc_imag",
            "qc_mag",
            "inverse_qi",
            "amplitude",
            "phase_rad",
            "delay_s",
            "phase_reference_hz",
            "phase_at_reference_rad",
        ),
        "params",
    )
    qi_status = params.get("qi_status")
    if qi_status == "finite":
        _require_finite_fields(params, ("qi",), "params")
    elif qi_status in ("lossless_boundary", "nonphysical"):
        if params.get("qi") is not None:
            raise ValueError(f"params.qi must be null when qi_status={qi_status}.")
    else:
        raise ValueError("params.qi_status is missing or invalid.")

    _require_finite_fields(
        cast(Mapping[str, Any], payload["initial_guess"]),
        _NOTCH_INITIAL_GUESS_KEYS,
        "initial_guess",
    )
    fit_settings = cast(Mapping[str, Any], payload["fit_settings"])
    _require_finite_fields(
        fit_settings,
        ("frequency_center_hz", "frequency_scale_hz"),
        "fit_settings",
    )
    _require_finite_sequence(
        fit_settings.get("resonance_frequency_bounds_hz"),
        "fit_settings.resonance_frequency_bounds_hz",
    )
    optimizer = cast(Mapping[str, Any], payload["optimizer"])
    _require_finite_fields(
        optimizer,
        ("status", "nfev", "njev", "optimality"),
        "optimizer",
    )
    _require_finite_sequence(optimizer.get("active_mask"), "optimizer.active_mask")
    if not isinstance(optimizer.get("message"), str) or not optimizer["message"]:
        raise ValueError("optimizer.message must be a non-empty string.")

    _require_finite_fields(
        cast(Mapping[str, Any], payload["metrics"]),
        ("complex_s21_rmse", "least_squares_cost"),
        "metrics",
    )
    _require_finite_sequence(payload.get("fit_window_hz"), "fit_window_hz")
    requested_window = payload.get("requested_fit_window_hz")
    if requested_window is not None:
        _require_finite_sequence(requested_window, "requested_fit_window_hz")

    fit_curve = cast(Mapping[str, Any], payload["fit_curve"])
    curve_lengths = set()
    for key in ("frequency_hz", "s21_real", "s21_imag"):
        values = fit_curve.get(key)
        _require_finite_sequence(values, f"fit_curve.{key}")
        curve_lengths.add(len(cast(Sequence[Any], values)))
    if curve_lengths != {len(cast(Sequence[Any], fit_curve["frequency_hz"]))}:
        raise ValueError("fit_curve components must have the same length.")


def _require_finite_fields(
    values: Mapping[str, Any],
    keys: Sequence[str],
    name: str,
) -> None:
    for key in keys:
        value = values.get(key)
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise ValueError(f"{name}.{key} must be finite numeric evidence.")
        if not np.isfinite(float(value)):
            raise ValueError(f"{name}.{key} must be finite numeric evidence.")


def _require_finite_sequence(values: Any, name: str) -> None:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not values:
        raise ValueError(f"{name} must be a non-empty finite numeric sequence.")
    if any(
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, Real)
        or not np.isfinite(float(value))
        for value in values
    ):
        raise ValueError(f"{name} must be a non-empty finite numeric sequence.")


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
