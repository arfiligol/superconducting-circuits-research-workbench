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
    max_iterations: int,
    min_q: float,
    restrict_to_input_span: bool = True,
    fit_window_hz: tuple[float, float] | Sequence[float] | None = None,
) -> dict[str, Any]:
    """Fit one scalar complex S21 trace with scikit-rf VectorFitting.

    The internal one-response scikit-rf ``Network`` is only a carrier for the
    scalar samples; this result is not a physical network model and makes no
    passivity or reciprocity claim. The result retains every fitted storage
    pole and its aligned scalar residue so a caller can assess continuation.
    The v2 ``resonances`` bucket contains candidates that passed the fitter's
    stability/span/Q classification only; callers must still apply convergence,
    residue-response, continuation, and ambiguity gates before promotion. Local
    storage indices do not establish physical mode identity.
    """
    try:
        f, s21 = _prepare_trace(frequency_hz, s21_real, s21_imag)
        f_fit, s21_fit, window, requested_window = _apply_fit_window(f, s21, fit_window_hz)
        if isinstance(n_resonators, (bool, np.bool_)) or not isinstance(
            n_resonators, (int, np.integer)
        ):
            return _vector_failure("n_resonators must be an integer.")
        if isinstance(bg_poles, (bool, np.bool_)) or not isinstance(bg_poles, (int, np.integer)):
            return _vector_failure("bg_poles must be an integer.")
        n_resonators_value = int(n_resonators)
        bg_poles_value = int(bg_poles)
        if n_resonators_value < 1:
            return _vector_failure("n_resonators must be at least 1.")
        if bg_poles_value < 0:
            return _vector_failure("bg_poles must be non-negative.")
        if isinstance(max_iterations, (bool, np.bool_)) or not isinstance(
            max_iterations, (int, np.integer)
        ):
            return _vector_failure("max_iterations must be an integer.")
        max_iterations_value = int(max_iterations)
        if max_iterations_value < 1:
            return _vector_failure("max_iterations must be at least 1.")
        if isinstance(min_q, (bool, np.bool_)) or not isinstance(min_q, Real):
            return _vector_failure("min_q must be a real number.")
        min_q_value = float(min_q)
        if not np.isfinite(min_q_value) or min_q_value < 0:
            return _vector_failure("min_q must be finite and non-negative.")
        if not isinstance(restrict_to_input_span, (bool, np.bool_)):
            return _vector_failure("restrict_to_input_span must be a Boolean.")
        restrict_to_span = bool(restrict_to_input_span)

        result = MultiResonanceVectorFitter(f_fit, s21_fit).fit(
            n_resonators=n_resonators_value,
            bg_poles=bg_poles_value,
            max_iterations=max_iterations_value,
            min_q=min_q_value,
            restrict_to_input_span=restrict_to_span,
        )
        model_s21 = np.asarray(result["model_s21"], dtype=complex)
        payload = {
            "schema_version": "scalar-s21-vector-fit.v2",
            "status": "success",
            "model": "scalar_s21_vector",
            "fit_settings": {
                "n_resonators": n_resonators_value,
                "bg_poles": bg_poles_value,
                "max_iterations": max_iterations_value,
                "min_q": min_q_value,
                "restrict_to_input_span": restrict_to_span,
                "fit_constant": True,
                "fit_proportional": False,
            },
            "resonances": [_vector_resonance_record(item) for item in result.get("resonances", [])],
            "artifacts": [_vector_resonance_record(item) for item in result.get("artifacts", [])],
            "fit_window_hz": list(window),
            "requested_fit_window_hz": (
                list(requested_window) if requested_window is not None else None
            ),
            "sampling": {
                "sample_count": len(f_fit),
                "minimum_frequency_step_hz": _json_number(np.min(np.diff(f_fit))),
                "maximum_frequency_step_hz": _json_number(np.max(np.diff(f_fit))),
            },
            "rational_model": {
                "response_domain": "scalar_s21",
                "laplace_variable_convention": "s = j*2*pi*f",
                "pole_units": "rad_per_s",
                "residue_units": "rad_per_s",
                "constant_term_units": "dimensionless",
                "proportional_term_units": "seconds",
                "proportional_term_status": "fixed_zero_not_fitted",
                "complex_pair_storage": (
                    "one_stored_pole_and_residue_plus_inferred_conjugate_term"
                ),
                "stored_pole_count": result["stored_pole_count"],
                "final_model_order": result["final_model_order"],
                "constant_term": _complex_number_payload(result["constant_term"]),
                "proportional_term": _complex_number_payload(result["proportional_term"]),
                "poles": [_vector_pole_record(item) for item in result["poles"]],
            },
            "metrics": {
                "rms_error": _json_number(result["rms_error"]),
                "max_abs_error": _json_number(result["max_abs_error"]),
            },
            "fit_diagnostics": result["fit_diagnostics"],
            "model_trace": _complex_trace_payload(f_fit, model_s21),
            "complex_residual_trace": _complex_residual_payload(
                f_fit, np.asarray(result["residual_s21"], dtype=complex)
            ),
        }
        _validate_vector_success_payload(payload)
        json.dumps(payload, allow_nan=False)
        return payload
    except Exception as exc:
        return _vector_failure(str(exc))


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


def _validate_vector_success_payload(payload: Mapping[str, Any]) -> None:
    """Fail closed unless a vector-fit success payload carries complete finite evidence."""
    if payload.get("schema_version") != "scalar-s21-vector-fit.v2":
        raise ValueError("Vector-fit schema_version must be scalar-s21-vector-fit.v2.")
    if payload.get("status") != "success" or payload.get("model") != "scalar_s21_vector":
        raise ValueError("Vector-fit success payload has an invalid status or model.")

    settings = cast(Mapping[str, Any], payload["fit_settings"])
    if set(settings) != {
        "n_resonators",
        "bg_poles",
        "max_iterations",
        "min_q",
        "restrict_to_input_span",
        "fit_constant",
        "fit_proportional",
    }:
        raise ValueError("Vector-fit settings do not match the v2 contract.")
    for name, minimum in (("n_resonators", 1), ("bg_poles", 0), ("max_iterations", 1)):
        value = settings[name]
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
            raise ValueError(f"fit_settings.{name} must be an integer.")
        if int(value) < minimum:
            raise ValueError(f"fit_settings.{name} must be at least {minimum}.")
    _require_finite_fields(settings, ("min_q",), "fit_settings")
    if float(settings["min_q"]) < 0:
        raise ValueError("fit_settings.min_q must be non-negative.")
    if not isinstance(settings["restrict_to_input_span"], bool):
        raise ValueError("fit_settings.restrict_to_input_span must be Boolean.")
    if settings["fit_constant"] is not True or settings["fit_proportional"] is not False:
        raise ValueError("Vector fit must fit D and keep E fixed at zero.")

    for name in ("fit_window_hz", "requested_fit_window_hz"):
        values = payload.get(name)
        if values is None and name == "requested_fit_window_hz":
            continue
        _require_finite_sequence(values, name)
        window_values = cast(Sequence[Any], values)
        if len(window_values) != 2 or window_values[0] >= window_values[1]:
            raise ValueError(f"{name} must be an increasing finite pair.")

    sampling = cast(Mapping[str, Any], payload["sampling"])
    sample_count = sampling.get("sample_count")
    if (
        isinstance(sample_count, (bool, np.bool_))
        or not isinstance(sample_count, (int, np.integer))
        or int(sample_count) < 3
    ):
        raise ValueError("sampling.sample_count must be an integer of at least three.")
    _require_finite_fields(
        sampling,
        ("minimum_frequency_step_hz", "maximum_frequency_step_hz"),
        "sampling",
    )
    minimum_step = float(sampling["minimum_frequency_step_hz"])
    maximum_step = float(sampling["maximum_frequency_step_hz"])
    if minimum_step <= 0 or maximum_step < minimum_step:
        raise ValueError("sampling frequency steps must be positive and ordered.")

    rational = cast(Mapping[str, Any], payload["rational_model"])
    expected_conventions = {
        "response_domain": "scalar_s21",
        "laplace_variable_convention": "s = j*2*pi*f",
        "pole_units": "rad_per_s",
        "residue_units": "rad_per_s",
        "constant_term_units": "dimensionless",
        "proportional_term_units": "seconds",
        "proportional_term_status": "fixed_zero_not_fitted",
        "complex_pair_storage": "one_stored_pole_and_residue_plus_inferred_conjugate_term",
    }
    if any(rational.get(key) != value for key, value in expected_conventions.items()):
        raise ValueError("Rational-model conventions do not match the v2 contract.")
    for name in ("constant_term", "proportional_term"):
        term = cast(Mapping[str, Any], rational[name])
        if set(term) != {"real", "imag"}:
            raise ValueError(f"rational_model.{name} must contain real and imag only.")
        _require_finite_fields(term, ("real", "imag"), f"rational_model.{name}")
    proportional = cast(Mapping[str, Any], rational["proportional_term"])
    if float(proportional["real"]) != 0 or float(proportional["imag"]) != 0:
        raise ValueError("The unfitted proportional term E must be exactly zero.")

    poles = rational.get("poles")
    if isinstance(poles, (str, bytes)) or not isinstance(poles, Sequence) or not poles:
        raise ValueError("rational_model.poles must be a non-empty sequence.")
    expected_pole_keys = {
        "storage_index",
        "pole_real_rad_per_s",
        "pole_imag_rad_per_s",
        "residue_real_rad_per_s",
        "residue_imag_rad_per_s",
        "residue_abs_rad_per_s",
        "pole_kind",
        "conjugate_term_inferred",
        "stable",
        "fr_hz",
        "ql",
        "bandwidth_hz",
        "inside_selected_frequency_span",
        "classification",
        "exclusion_reason",
    }
    final_order = 0
    for index, raw_pole in enumerate(poles):
        if not isinstance(raw_pole, Mapping) or set(raw_pole) != expected_pole_keys:
            raise ValueError("Every rational pole must match the exact v2 pole schema.")
        pole = cast(Mapping[str, Any], raw_pole)
        if pole["storage_index"] != index:
            raise ValueError("Pole storage indices must be consecutive and aligned with residues.")
        _require_finite_fields(
            pole,
            (
                "pole_real_rad_per_s",
                "pole_imag_rad_per_s",
                "residue_real_rad_per_s",
                "residue_imag_rad_per_s",
                "residue_abs_rad_per_s",
            ),
            f"rational_model.poles[{index}]",
        )
        residue = complex(
            float(pole["residue_real_rad_per_s"]),
            float(pole["residue_imag_rad_per_s"]),
        )
        if not np.isclose(abs(residue), pole["residue_abs_rad_per_s"], rtol=1e-13, atol=0):
            raise ValueError("Pole residue magnitude does not match its aligned complex residue.")
        if pole["stable"] is not (float(pole["pole_real_rad_per_s"]) < 0):
            raise ValueError("Pole stability classification does not match its real part.")
        if pole["classification"] == "resonance":
            if pole["exclusion_reason"] is not None:
                raise ValueError("A retained resonance cannot carry an exclusion reason.")
        elif pole["classification"] == "excluded":
            if not isinstance(pole["exclusion_reason"], str) or not pole["exclusion_reason"]:
                raise ValueError("Every excluded pole must carry an exclusion reason.")
        else:
            raise ValueError("Pole classification must be resonance or excluded.")

        if pole["pole_kind"] == "real":
            final_order += 1
            if float(pole["pole_imag_rad_per_s"]) != 0:
                raise ValueError("A real storage pole must have zero imaginary part.")
            if pole["conjugate_term_inferred"] is not False:
                raise ValueError("A real storage pole cannot infer a conjugate term.")
            if any(pole[name] is not None for name in ("fr_hz", "ql", "bandwidth_hz")):
                raise ValueError("Real background-pole frequency fields must be null.")
            if pole["classification"] != "excluded":
                raise ValueError("A real background pole cannot be a reported resonance.")
        elif pole["pole_kind"] == "complex_conjugate_pair":
            final_order += 2
            if float(pole["pole_imag_rad_per_s"]) == 0:
                raise ValueError("A complex storage pole must have nonzero imaginary part.")
            if pole["conjugate_term_inferred"] is not True:
                raise ValueError("A complex storage pole must infer its conjugate term.")
            _require_finite_fields(
                pole,
                ("fr_hz", "ql", "bandwidth_hz"),
                f"rational_model.poles[{index}]",
            )
        else:
            raise ValueError("Pole kind must be real or complex_conjugate_pair.")
        inside_span = pole["inside_selected_frequency_span"]
        if inside_span is not None and not isinstance(inside_span, bool):
            raise ValueError("inside_selected_frequency_span must be Boolean or null.")
        if settings["restrict_to_input_span"] is True and pole["pole_kind"] != "real":
            if not isinstance(inside_span, bool):
                raise ValueError("A span-restricted complex pole must report span membership.")
        elif settings["restrict_to_input_span"] is False and inside_span is not None:
            raise ValueError("An unrestricted fit must leave span membership null.")

        expected_reason = None
        if pole["stable"] is False:
            expected_reason = "unstable_pole"
        elif pole["pole_kind"] == "real":
            expected_reason = "real_background_pole"
        elif float(pole["pole_imag_rad_per_s"]) < 0:
            expected_reason = "negative_frequency_storage_pole"
        elif inside_span is False:
            expected_reason = "outside_selected_frequency_span"
        elif float(pole["ql"]) <= float(settings["min_q"]):
            expected_reason = "quality_factor_not_above_min_q"
        expected_classification = "resonance" if expected_reason is None else "excluded"
        if (
            pole["classification"] != expected_classification
            or pole["exclusion_reason"] != expected_reason
        ):
            raise ValueError("Pole classification does not match the declared v2 decision rules.")

    stored_pole_count = rational.get("stored_pole_count")
    model_order = rational.get("final_model_order")
    if stored_pole_count != len(poles) or model_order != final_order:
        raise ValueError("Rational-model pole counts do not match the published pole records.")

    for bucket_name in ("resonances", "artifacts"):
        bucket = payload.get(bucket_name)
        if isinstance(bucket, (str, bytes)) or not isinstance(bucket, Sequence):
            raise ValueError(f"{bucket_name} must be a sequence.")
        for index, item in enumerate(bucket):
            if not isinstance(item, Mapping) or set(item) != {
                "fr_hz",
                "ql",
                "bandwidth_hz",
                "pole_real_rad_per_s",
                "pole_imag_rad_per_s",
            }:
                raise ValueError(f"{bucket_name}[{index}] does not match the v2 schema.")
            _require_finite_fields(
                item,
                (
                    "fr_hz",
                    "ql",
                    "bandwidth_hz",
                    "pole_real_rad_per_s",
                    "pole_imag_rad_per_s",
                ),
                f"{bucket_name}[{index}]",
            )

    model_trace = cast(Mapping[str, Any], payload["model_trace"])
    residual_trace = cast(Mapping[str, Any], payload["complex_residual_trace"])
    for trace, keys, name in (
        (model_trace, ("frequency_hz", "s21_real", "s21_imag"), "model_trace"),
        (
            residual_trace,
            ("frequency_hz", "residual_real", "residual_imag", "residual_abs"),
            "complex_residual_trace",
        ),
    ):
        if set(trace) != set(keys):
            raise ValueError(f"{name} does not match the v2 trace schema.")
        for key in keys:
            _require_finite_sequence(trace[key], f"{name}.{key}")
            if len(trace[key]) != sample_count:
                raise ValueError(f"{name}.{key} length does not match sampling.sample_count.")
    model_frequency = np.asarray(model_trace["frequency_hz"], dtype=float)
    residual_frequency = np.asarray(residual_trace["frequency_hz"], dtype=float)
    if not np.array_equal(model_frequency, residual_frequency):
        raise ValueError("Model and residual traces must use the same frequency samples.")
    frequency_steps = np.diff(model_frequency)
    if not np.all(model_frequency > 0) or not np.all(frequency_steps > 0):
        raise ValueError("Vector-fit model frequencies must be positive and strictly increasing.")
    if not np.isclose(np.min(frequency_steps), minimum_step, rtol=1e-13, atol=0) or not np.isclose(
        np.max(frequency_steps), maximum_step, rtol=1e-13, atol=0
    ):
        raise ValueError("Published sampling steps do not match the model trace.")
    fit_window = cast(Sequence[float], payload["fit_window_hz"])
    if model_frequency[0] != fit_window[0] or model_frequency[-1] != fit_window[1]:
        raise ValueError("Actual fit window does not match the model trace endpoints.")

    residual_real = np.asarray(residual_trace["residual_real"], dtype=float)
    residual_imag = np.asarray(residual_trace["residual_imag"], dtype=float)
    residual_abs = np.asarray(residual_trace["residual_abs"], dtype=float)
    calculated_abs = np.hypot(residual_real, residual_imag)
    if not np.allclose(residual_abs, calculated_abs, rtol=1e-13, atol=0):
        raise ValueError("Residual magnitude does not match the complex residual.")
    metrics = cast(Mapping[str, Any], payload["metrics"])
    if set(metrics) != {"rms_error", "max_abs_error"}:
        raise ValueError("Vector-fit metrics do not match the v2 schema.")
    _require_finite_fields(metrics, ("rms_error", "max_abs_error"), "metrics")
    calculated_rmse = float(np.sqrt(np.mean(residual_abs**2)))
    if not np.isclose(metrics["rms_error"], calculated_rmse, rtol=1e-13, atol=0) or not np.isclose(
        metrics["max_abs_error"], np.max(residual_abs), rtol=1e-13, atol=0
    ):
        raise ValueError("Vector-fit metrics do not match the complex residual trace.")

    diagnostics = cast(Mapping[str, Any], payload["fit_diagnostics"])
    diagnostic_max_iterations = diagnostics.get("max_iterations")
    if (
        isinstance(diagnostic_max_iterations, (bool, np.bool_))
        or not isinstance(diagnostic_max_iterations, (int, np.integer))
        or int(diagnostic_max_iterations) < 1
    ):
        raise ValueError("fit_diagnostics.max_iterations must be a positive integer.")
    if int(diagnostic_max_iterations) != int(settings["max_iterations"]):
        raise ValueError("Vector-fit iteration budgets disagree between settings and diagnostics.")
    iteration_count = diagnostics.get("iteration_count")
    delta_history = diagnostics.get("delta_max_history")
    if (
        isinstance(iteration_count, (bool, np.bool_))
        or not isinstance(iteration_count, (int, np.integer))
        or int(iteration_count) < 1
    ):
        raise ValueError("fit_diagnostics.iteration_count must be a positive integer.")
    _require_finite_sequence(delta_history, "fit_diagnostics.delta_max_history")
    delta_values = cast(Sequence[Any], delta_history)
    if len(delta_values) != iteration_count:
        raise ValueError("Vector-fit convergence history length is inconsistent.")
    if int(iteration_count) > int(diagnostic_max_iterations):
        raise ValueError("Vector-fit iteration count exceeds its declared budget.")
    _require_finite_fields(diagnostics, ("convergence_tolerance",), "fit_diagnostics")
    tolerance = float(diagnostics["convergence_tolerance"])
    converged = diagnostics.get("converged")
    if tolerance <= 0 or not isinstance(converged, bool):
        raise ValueError("Vector-fit convergence evidence is invalid.")
    if converged is not (float(delta_values[-1]) < tolerance):
        raise ValueError("Vector-fit converged flag does not match its history and tolerance.")
    warning_messages = diagnostics.get("warnings")
    if not isinstance(warning_messages, list) or any(
        not isinstance(message, str) for message in warning_messages
    ):
        raise ValueError("fit_diagnostics.warnings must be a list of strings.")


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
    pole = complex(item["pole"])
    return {
        "fr_hz": _json_number(fr_hz),
        "ql": _json_number(ql),
        "bandwidth_hz": _json_number(fr_hz / ql if ql > 0 else None),
        "pole_real_rad_per_s": _json_number(pole.real),
        "pole_imag_rad_per_s": _json_number(pole.imag),
    }


def _vector_pole_record(item: Mapping[str, Any]) -> dict[str, Any]:
    pole = complex(item["pole"])
    residue = complex(item["residue"])
    fr_hz = item.get("fr")
    ql = item.get("Ql")
    return {
        "storage_index": int(item["storage_index"]),
        "pole_real_rad_per_s": _json_number(pole.real),
        "pole_imag_rad_per_s": _json_number(pole.imag),
        "residue_real_rad_per_s": _json_number(residue.real),
        "residue_imag_rad_per_s": _json_number(residue.imag),
        "residue_abs_rad_per_s": _json_number(abs(residue)),
        "pole_kind": str(item["pole_kind"]),
        "conjugate_term_inferred": bool(item["conjugate_term_inferred"]),
        "stable": bool(item["stable"]),
        "fr_hz": _json_number(fr_hz),
        "ql": _json_number(ql),
        "bandwidth_hz": _json_number(
            float(fr_hz) / float(ql) if fr_hz is not None and ql is not None and ql > 0 else None
        ),
        "inside_selected_frequency_span": item["inside_selected_frequency_span"],
        "classification": str(item["classification"]),
        "exclusion_reason": item["exclusion_reason"],
    }


def _complex_number_payload(value: complex) -> dict[str, float | None]:
    number = complex(value)
    return {"real": _json_number(number.real), "imag": _json_number(number.imag)}


def _complex_trace_payload(frequency_hz: np.ndarray, trace: np.ndarray) -> dict[str, list[Any]]:
    return {
        "frequency_hz": [_json_number(value) for value in frequency_hz],
        "s21_real": [_json_number(value) for value in np.real(trace)],
        "s21_imag": [_json_number(value) for value in np.imag(trace)],
    }


def _complex_residual_payload(
    frequency_hz: np.ndarray, residual: np.ndarray
) -> dict[str, list[Any]]:
    return {
        "frequency_hz": [_json_number(value) for value in frequency_hz],
        "residual_real": [_json_number(value) for value in np.real(residual)],
        "residual_imag": [_json_number(value) for value in np.imag(residual)],
        "residual_abs": [_json_number(value) for value in np.abs(residual)],
    }


def _json_number(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if np.isfinite(number) else None


def _failure(reason: str) -> dict[str, Any]:
    return {"status": "failed", "reason": reason}


def _vector_failure(reason: str) -> dict[str, Any]:
    return {
        "schema_version": "scalar-s21-vector-fit.v2",
        "status": "failed",
        "model": "scalar_s21_vector",
        "reason": reason,
    }
