#!/usr/bin/env python3
"""Render a captured D3 optimizer-time record as a static review surface.

This file owns JSON-artifact validation and plotting only. It never evaluates a
candidate or reruns simulation/optimization. Canonical semantics live in:

- D3 target: https://github.com/arfiligol/SCQ_Design/blob/main/docs/design-targets/d3-intrinsic-interferometric-purcell-filter.qmd
- Loaded-bare references: https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/loaded-bare-readout-filter-references.qmd
- Readout-filter J fit: https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd
- PTC observable: https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


EXPECTED_RUN_FILES = {
    "condition_manifest.json",
    "config_snapshot.json",
    "evaluations.jsonl",
    "final_diagnostics.json",
    "hash_inventory.json",
    "layout_specs.json",
    "optimization_result.json",
    "status.json",
}
NOMINAL_OUTPUT_FILES = {
    "hash_inventory.json",
    "layout_specs_snapshot.json",
    "nominal_evaluation.json",
    "status.json",
    "validation_manifest.json",
    "validation_summary.json",
}
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
LEGACY_MANIFEST_SCHEMA = "d3-condition-manifest.v1"
SLOT_EXECUTION_MANIFEST_SCHEMA = "d3-slot-execution-manifest.v1"
NOMINAL_MANIFEST_SCHEMA = "d3-nominal-validation-manifest.v1"
SEMANTIC_HASH_FRAMING = "d3-semantic-value-sha256-v1"
NOMINAL_OBJECTIVE_IDS = {
    "filter_loaded_bare_hz",
    "readout_loaded_bare_hz",
    "notch_hz",
    "filter_loaded_linewidth_hz",
    "j_hz",
    "g_hz",
}
NOMINAL_VARIABLE_IDS = [
    "lc_um",
    "lp_short_um",
    "lr_short_um",
    "lp_open_um",
    "lr_open_um",
    "filter_to_line_capacitance_fF",
]
NOMINAL_VARIABLE_UNITS = {
    "lc_um": "um",
    "lp_short_um": "um",
    "lr_short_um": "um",
    "lp_open_um": "um",
    "lr_open_um": "um",
    "filter_to_line_capacitance_fF": "fF",
}
INK = "#20242b"
BLUE = "#2764a5"
ORANGE = "#d67828"
GOLD = "#a77a13"
GREY = "#737b86"
LIGHT_GREY = "#c7ccd2"


class ArtifactContractError(ValueError):
    """Raised when persisted evidence is unsafe to present for Human review."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactContractError(message)


def json3_any_float(value: str) -> int | float:
    """Match JSON3's `Any` decoding of finite integral-valued JSON numbers."""
    result = float(value)
    if math.isfinite(result) and result.is_integer() and -(2**63) <= result < 2**63:
        return int(result)
    return result


def load_json(run_directory: Path, filename: str) -> dict[str, Any]:
    path = run_directory / filename

    def reject_constant(value: str) -> None:
        raise ArtifactContractError(f"{filename} contains non-finite JSON constant {value!r}.")

    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(
                handle,
                parse_constant=reject_constant,
                parse_float=json3_any_float,
            )
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactContractError(f"Could not read {filename}: {error}") from error
    require(isinstance(value, dict), f"{filename} must contain one JSON object.")
    return value


def mapping(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} must be a JSON object.")
    return value


def sequence(value: Any, label: str) -> list[Any]:
    require(isinstance(value, list), f"{label} must be a JSON array.")
    return value


def finite_number(value: Any, label: str) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{label} must be numeric.",
    )
    result = float(value)
    require(math.isfinite(result), f"{label} must be finite.")
    return result


def canonical_qubit_targets(target: dict[str, Any]) -> tuple[float, float]:
    """Read Workbench qubit values only from the canonical Design Target."""
    targets = mapping(target.get("targets"), "canonical target.targets")
    f01 = mapping(targets.get("qubit_transition_frequency"), "qubit transition target")
    lj = mapping(targets.get("qubit_junction_inductance"), "qubit junction target")
    require(f01.get("unit") == "GHz", "Canonical qubit transition target must use GHz.")
    require(
        lj.get("unit") == "nH_per_junction" and lj.get("parallel_junction_count") == 2,
        "Canonical qubit junction target must use nH_per_junction and declare two parallel junctions.",
    )
    f01_hz = finite_number(f01.get("value"), "canonical qubit transition target") * 1.0e9
    lj_nh = finite_number(lj.get("value"), "canonical per-junction L_J target")
    require(f01_hz > 0 and lj_nh > 0, "Canonical qubit targets must be positive.")
    return f01_hz, lj_nh


def numeric_array(container: dict[str, Any], key: str, label: str) -> np.ndarray:
    values = sequence(container.get(key), f"{label}.{key}")
    require(values, f"{label}.{key} must not be empty.")
    result = np.asarray(
        [finite_number(value, f"{label}.{key}[{index}]") for index, value in enumerate(values)],
        dtype=float,
    )
    return result


def complex_array(container: dict[str, Any], key: str, label: str) -> np.ndarray:
    values = sequence(container.get(key), f"{label}.{key}")
    require(values, f"{label}.{key} must not be empty.")
    result: list[complex] = []
    for index, value in enumerate(values):
        item = mapping(value, f"{label}.{key}[{index}]")
        require(
            set(item) == {"real", "imag"},
            f"{label}.{key}[{index}] must contain exactly real and imag.",
        )
        result.append(
            complex(
                finite_number(item["real"], f"{label}.{key}[{index}].real"),
                finite_number(item["imag"], f"{label}.{key}[{index}].imag"),
            )
        )
    return np.asarray(result, dtype=complex)


def require_same_length(label: str, *arrays: np.ndarray) -> None:
    lengths = {len(array) for array in arrays}
    require(len(lengths) == 1, f"{label} arrays must have matching lengths; observed {sorted(lengths)}.")


def require_increasing(values: np.ndarray, label: str) -> None:
    require(np.all(np.diff(values) > 0), f"{label} must be strictly increasing.")


def metric_by_name(breakdown: dict[str, Any], name: str) -> dict[str, Any]:
    metrics = sequence(breakdown.get("metrics"), "layout_specs.breakdown.metrics")
    matches = [mapping(metric, f"metric {name}") for metric in metrics if metric.get("name") == name]
    require(len(matches) == 1, f"Cost breakdown must contain exactly one {name!r} metric.")
    return matches[0]


def canonical_sha256(value: Any) -> str:
    """Legacy JSON-canonical identity; current contracts use semantic framing."""
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def semantic_value_bytes(value: Any) -> bytes:
    """Encode one value using the cross-language D3 semantic byte contract."""
    encoded = bytearray(f"{SEMANTIC_HASH_FRAMING}|".encode("ascii"))

    def append(item: Any) -> None:
        if item is None:
            encoded.extend(b"n;")
        elif isinstance(item, bool):
            encoded.extend(b"b1;" if item else b"b0;")
        elif isinstance(item, int):
            encoded.extend(f"i{item};".encode("ascii"))
        elif isinstance(item, float):
            require(math.isfinite(item), "D3 semantic hash rejects non-finite Float64 values.")
            if item.is_integer() and -(2**63) <= item <= 2**63 - 1:
                encoded.extend(f"i{int(item)};".encode("ascii"))
            else:
                bits = struct.unpack(">Q", struct.pack(">d", item))[0]
                encoded.extend(f"f{bits:016x};".encode("ascii"))
        elif isinstance(item, str):
            utf8 = item.encode("utf-8")
            encoded.extend(f"s{len(utf8)}:".encode("ascii"))
            encoded.extend(utf8)
        elif isinstance(item, (list, tuple)):
            encoded.extend(f"l{len(item)}[".encode("ascii"))
            for child in item:
                append(child)
            encoded.extend(b"]")
        elif isinstance(item, dict):
            keys = list(item)
            require(all(isinstance(key, str) for key in keys), "D3 semantic hash mapping keys must be strings.")
            require(all(key.isascii() for key in keys), "D3 semantic hash mapping keys must be ASCII.")
            require(len(set(keys)) == len(keys), "D3 semantic hash mapping keys must be unique.")
            keys.sort()
            encoded.extend(f"m{len(keys)}{{".encode("ascii"))
            for key in keys:
                append(key)
                append(item[key])
            encoded.extend(b"}")
        else:
            raise ArtifactContractError(
                f"Unsupported D3 semantic hash value type {type(item).__name__}."
            )

    append(value)
    return bytes(encoded)


def semantic_value_sha256(value: Any) -> str:
    """Hash one value with `d3-semantic-value-sha256-v1` framing."""
    return hashlib.sha256(semantic_value_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    """Return the byte identity used by persisted artifact contracts."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frequency_grid_sha256(frequencies_hz: np.ndarray | list[float]) -> str:
    """Match Julia's versioned ordered Float64-bit frequency-grid identity."""
    frequencies = [finite_number(value, "frequency grid value") for value in frequencies_hz]
    require(frequencies, "Frequency grid must not be empty.")
    bitstrings = [format(struct.unpack(">Q", struct.pack(">d", value))[0], "064b") for value in frequencies]
    payload = (
        f"d3-frequency-grid-float64-bits-v1|count={len(frequencies)}|"
        + "|".join(bitstrings)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_declared_frequency_grid(
    trace: dict[str, Any],
    label: str,
    *,
    expected_step_hz: float | None,
    require_declared_hash: bool,
) -> tuple[np.ndarray, str | None]:
    frequencies = numeric_array(trace, "frequencies_hz", label)
    require_increasing(frequencies, f"{label} frequency grid")
    declared_hash = trace.get("frequency_grid_sha256")
    if require_declared_hash or declared_hash is not None:
        require(
            isinstance(declared_hash, str)
            and HEX_SHA256.fullmatch(declared_hash) is not None
            and declared_hash == frequency_grid_sha256(frequencies.tolist()),
            f"{label} frequency_grid_sha256 does not match its complete Float64 grid.",
        )
    if expected_step_hz is not None:
        require(expected_step_hz > 0.0, "Bound evaluator frequency step must be positive.")
        require(
            len(frequencies) >= 2
            and np.allclose(
                np.diff(frequencies),
                expected_step_hz,
                rtol=0.0,
                atol=max(1e-6, abs(expected_step_hz) * 1e-12),
            ),
            f"{label} must use the hash-bound evaluator frequency step.",
        )
    return frequencies, declared_hash


def _require_trace_id_grid_link(value: Any, grid_hash: str, label: str) -> None:
    require(
        isinstance(value, str) and f"grid_sha256={grid_hash}" in value,
        f"{label} must directly bind grid_sha256={grid_hash}.",
    )


def optimizer_candidate_identity(
    optimizer_run_directory: Path,
    optimizer_artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconstruct the immutable optimizer and frozen-candidate identities."""
    artifacts = optimizer_artifacts or {
        name: load_json(optimizer_run_directory, name)
        for name in EXPECTED_RUN_FILES
        if name.endswith(".json")
    }
    manifest = artifacts["condition_manifest.json"]
    optimization = artifacts["optimization_result.json"]
    layout = artifacts["layout_specs.json"]
    schema = manifest.get("schema_version", LEGACY_MANIFEST_SCHEMA)
    current_semantic = schema == SLOT_EXECUTION_MANIFEST_SCHEMA
    identity_field = "execution_sha256" if schema == SLOT_EXECUTION_MANIFEST_SCHEMA else "contract_sha256"
    optimizer_contract_sha256 = manifest.get(identity_field)
    require(
        isinstance(optimizer_contract_sha256, str)
        and HEX_SHA256.fullmatch(optimizer_contract_sha256) is not None,
        "Optimizer manifest identity must be lowercase SHA-256.",
    )
    contract = mapping(manifest.get("contract"), "condition_manifest.contract")
    optimizer_id = contract.get("manifest_id", optimization.get("condition_manifest_id"))
    require(isinstance(optimizer_id, str) and optimizer_id, "Optimizer identity is missing.")
    require(
        optimization.get("condition_manifest_id") == optimizer_id,
        "Optimizer result id disagrees with its manifest.",
    )
    variables = sequence(layout.get("variables"), "layout_specs.variables")
    require(
        [item.get("id") for item in variables if isinstance(item, dict)] == NOMINAL_VARIABLE_IDS,
        "Layout variable ids/order do not match the D3 nominal candidate contract.",
    )
    candidate_records: list[dict[str, Any]] = []
    for index, value in enumerate(variables):
        item = mapping(value, f"layout_specs.variables[{index}]")
        variable_value = finite_number(item.get("value"), f"layout variable {item.get('id')}")
        unit = item.get("unit")
        require(
            unit == NOMINAL_VARIABLE_UNITS[item["id"]],
            f"Layout variable {item.get('id')} must use {NOMINAL_VARIABLE_UNITS[item['id']]!r}.",
        )
        candidate_records.append({"id": item["id"], "value": variable_value, "unit": unit})
    optimizer_identity = {
        "optimizer_id": optimizer_id,
        "condition_manifest_sha256": optimizer_contract_sha256,
        "optimization_result_sha256": file_sha256(optimizer_run_directory / "optimization_result.json"),
    }
    return {
        "run_id": optimizer_run_directory.name,
        "optimizer_id": optimizer_id,
        "optimizer_contract_sha256": optimizer_contract_sha256,
        "optimizer_identity_sha256": (
            semantic_value_sha256(optimizer_identity)
            if current_semantic
            else canonical_sha256(optimizer_identity)
        ),
        "layout_specs_raw_sha256": file_sha256(optimizer_run_directory / "layout_specs.json"),
        "candidate_id": layout.get("candidate_record_id"),
        "candidate_sha256": (
            semantic_value_sha256(candidate_records)
            if current_semantic
            else canonical_sha256(candidate_records)
        ),
        "layout_specs": layout,
    }


def _validate_nominal_wide_trace(
    record: dict[str, Any], expected_step_hz: float
) -> tuple[np.ndarray, np.ndarray]:
    traces = mapping(record.get("traces"), "nominal_evaluation.record.traces")
    intrinsic = mapping(traces.get("intrinsic_wide"), "nominal record traces.intrinsic_wide")
    provenance = mapping(
        intrinsic.get("range_provenance"),
        "nominal record traces.intrinsic_wide.range_provenance",
    )
    require(
        provenance.get("contract_id") == "d3-intrinsic-wide-final-capture-v1"
        and provenance.get("scope") == "final_capture_only",
        "Independent nominal validation requires the declared wide final-capture contract.",
    )
    frequencies = numeric_array(intrinsic, "frequencies_hz", "nominal intrinsic_wide")
    values = complex_array(intrinsic, "z21_ptc", "nominal intrinsic_wide")
    require_same_length("Nominal wide intrinsic PTC", frequencies, values)
    require_increasing(frequencies, "Nominal wide intrinsic PTC frequency grid")
    require(
        frequencies[0] == finite_number(provenance.get("start_hz"), "nominal wide start")
        and frequencies[-1] == finite_number(provenance.get("stop_hz"), "nominal wide stop"),
        "Nominal wide intrinsic grid endpoints must match range provenance.",
    )
    margin = finite_number(
        provenance.get("start_margin_below_notch_hz"), "nominal wide start margin"
    )
    notch_target = finite_number(
        provenance.get("notch_target_hz"), "nominal wide notch target"
    )
    filter_loaded_bare = finite_number(
        provenance.get("filter_loaded_bare_hz"), "nominal wide filter loaded-bare"
    )
    required_stop = finite_number(
        provenance.get("required_minimum_stop_hz"), "nominal wide required stop"
    )
    declared_stop_ghz = finite_number(
        provenance.get("declared_design_scan_stop_ghz"), "nominal wide declared stop"
    )
    frequency_step = finite_number(
        provenance.get("frequency_step_hz"), "nominal wide frequency step"
    )
    require(frequency_step > 0.0, "Nominal wide frequency step must be positive.")
    require(
        frequency_step == expected_step_hz,
        "Nominal wide frequency step must equal the hash-bound evaluator setting.",
    )
    span = frequencies[-1] - frequencies[0]
    interval_count = round(span / frequency_step)
    require(
        interval_count >= 1
        and math.isclose(span, interval_count * frequency_step, rel_tol=0.0, abs_tol=1e-6)
        and len(frequencies) == interval_count + 1
        and np.allclose(
            np.diff(frequencies),
            frequency_step,
            rtol=0.0,
            atol=max(1e-6, abs(frequency_step) * 1e-12),
        ),
        "Nominal wide frequency grid must contain every equally spaced point from start to stop.",
    )
    grid_hash = intrinsic.get("frequency_grid_sha256")
    require(
        isinstance(grid_hash, str)
        and HEX_SHA256.fullmatch(grid_hash) is not None
        and grid_hash == frequency_grid_sha256(frequencies.tolist()),
        "Nominal wide frequency_grid_sha256 does not match the complete Float64 grid.",
    )
    require(
        margin == 500.0e6
        and frequencies[0] == notch_target - margin
        and required_stop == filter_loaded_bare + margin
        and frequencies[-1] == declared_stop_ghz * 1.0e9
        and frequencies[-1] >= required_stop,
        "Nominal wide intrinsic provenance does not satisfy the full 500 MHz coverage contract.",
    )
    return frequencies, values


def _relative_workspace_path(path_value: Any, workspace_root: Path, label: str) -> tuple[str, Path]:
    require(isinstance(path_value, str) and path_value, f"{label} must be a non-empty path.")
    pure_path = PurePosixPath(path_value)
    require(
        not Path(path_value).is_absolute() and ".." not in pure_path.parts,
        f"{label} must be workspace-relative.",
    )
    resolved = (workspace_root / path_value).resolve()
    try:
        normalized = resolved.relative_to(workspace_root.resolve()).as_posix()
    except ValueError as error:
        raise ArtifactContractError(f"{label} escapes the workspace.") from error
    return normalized, resolved


def _optimizer_inventory_by_id(inventory: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Normalize current optimizer inventory rows without accepting nominal aliases."""
    result: dict[str, dict[str, str]] = {}
    for index, value in enumerate(sequence(inventory.get("files"), "optimizer hash_inventory.files")):
        item = mapping(value, f"optimizer hash_inventory.files[{index}]")
        source_id = item.get("id")
        require(
            isinstance(source_id, str) and source_id and source_id not in result,
            "Optimizer inventory ids must be unique non-empty strings.",
        )
        path = item.get("path")
        require(isinstance(path, str) and path, f"Optimizer inventory {source_id!r} needs a path.")
        observed = item.get("sha256", item.get("observed_sha256"))
        require(
            isinstance(observed, str) and HEX_SHA256.fullmatch(observed) is not None,
            f"Optimizer inventory {source_id!r} has no valid observed hash.",
        )
        expected = item.get("expected_sha256")
        require(
            expected is None or expected == observed,
            f"Optimizer inventory {source_id!r} expected and observed hashes disagree.",
        )
        result[source_id] = {"path": path, "sha256": observed}
    return result


def _validate_notebook_record_shape(
    record: dict[str, Any], expected_step_hz: float | None
) -> None:
    """Validate the diagnostics and traces consumed by Notebook 08."""
    record_metrics = mapping(record.get("metrics"), "record.metrics")
    diagnostics = mapping(record.get("diagnostics"), "record.diagnostics")
    design = mapping(diagnostics.get("design"), "record.diagnostics.design")
    for key in ("lp_total_um", "lr_total_um", "notch_length_um"):
        finite_number(design.get(key), f"record.diagnostics.design.{key}")

    j_fit = mapping(diagnostics.get("j_fit"), "record.diagnostics.j_fit")
    mapping(j_fit.get("metrics"), "record.diagnostics.j_fit.metrics")
    mapping(j_fit.get("gates"), "record.diagnostics.j_fit.gates")
    j_diagnostics = mapping(j_fit.get("diagnostics"), "record.diagnostics.j_fit.diagnostics")
    finite_number(j_diagnostics.get("successful_seed_count"), "J successful seed count")
    finite_number(j_diagnostics.get("j_seed_spread_hz"), "J seed spread")
    poles = sequence(j_fit.get("derived_poles"), "record.diagnostics.j_fit.derived_poles")
    require(len(poles) == 2, "J fit must contain exactly two derived poles.")
    for index, pole_value in enumerate(poles):
        pole = mapping(pole_value, f"J derived pole {index}")
        finite_number(pole.get("frequency_hz"), f"J derived pole {index} frequency")
        finite_number(pole.get("linewidth_hz"), f"J derived pole {index} linewidth")
    vector_poles = sequence(
        diagnostics.get("vector_crosscheck_poles_hz"), "record.diagnostics.vector_crosscheck_poles_hz"
    )
    require(len(vector_poles) == 2, "Vector cross-check must contain two poles.")
    for index, value in enumerate(vector_poles):
        finite_number(value, f"vector cross-check pole {index}")
    filter_diagnostics = mapping(
        diagnostics.get("filter_loaded_bare"), "record.diagnostics.filter_loaded_bare"
    )
    finite_number(filter_diagnostics.get("vector_rms_error"), "filter vector RMS")

    channel = mapping(diagnostics.get("channel_calibration"), "record.diagnostics.channel_calibration")
    mapping(channel.get("metrics"), "channel calibration metrics")
    mapping(channel.get("gates"), "channel calibration gates")
    frequency_fit = mapping(
        diagnostics.get("readout_zero_probe_frequency_fit"), "readout frequency fit"
    )
    linewidth_fit = mapping(
        diagnostics.get("readout_zero_probe_linewidth_fit"), "readout linewidth fit"
    )
    g_fit = (
        mapping(diagnostics.get("g_zero_probe_fit"), "g fit")
        if expected_step_hz is not None
        else None
    )
    fit_x_by_label: dict[str, np.ndarray] = {}
    fits = [("readout frequency fit", frequency_fit), ("readout linewidth fit", linewidth_fit)]
    if g_fit is not None:
        fits.append(("g fit", g_fit))
    for label, fit in fits:
        x_values = numeric_array(fit, "x_values", label)
        fit_x_by_label[label] = x_values
        y_values = numeric_array(fit, "y_values", label)
        fitted_values = numeric_array(fit, "fitted_y_values", label)
        require_same_length(label, x_values, y_values, fitted_values)
        finite_number(fit.get("intercept"), f"{label} intercept")
        mapping(fit.get("coefficients"), f"{label} coefficients")
    require(
        all(np.array_equal(fit_x_by_label["readout frequency fit"], values)
            for values in fit_x_by_label.values()),
        "Readout frequency, linewidth, and g fits must share the probe grid.",
    )
    frequency_coefficients = mapping(
        frequency_fit.get("coefficients"), "readout frequency fit coefficients"
    )
    for key in ("linear_per_fF", "quadratic_per_fF2"):
        finite_number(frequency_coefficients.get(key), f"readout frequency coefficient {key}")
    linewidth_coefficients = mapping(
        linewidth_fit.get("coefficients"), "readout linewidth fit coefficients"
    )
    for key in ("quadratic_per_fF2", "quartic_per_fF4"):
        finite_number(linewidth_coefficients.get(key), f"readout linewidth coefficient {key}")
    if g_fit is not None:
        require(finite_number(record_metrics.get("g_hz"), "record.metrics.g_hz") > 0, "g_hz must be positive.")
        require(
            finite_number(g_fit.get("intercept"), "g fit intercept") == record_metrics["g_hz"] > 0,
            "g fit intercept must equal the positive g_hz metric.",
        )
        floating_qubit = mapping(diagnostics.get("floating_qubit"), "record.diagnostics.floating_qubit")
        require(
            isinstance(floating_qubit.get("input_sha256"), str)
            and HEX_SHA256.fullmatch(floating_qubit["input_sha256"]) is not None,
            "Floating-qubit diagnostics must bind the private input SHA-256.",
        )
        reduction = mapping(
            floating_qubit.get("electrostatic_reduction"),
            "record.diagnostics.floating_qubit.electrostatic_reduction",
        )
        require(
            reduction.get("readout_self_capacitance_ownership")
            == "distributed_resonator_owns_self_capacitance"
            and reduction.get("readout_diagonal_instantiated") is False,
            "Reduced readout self-capacitance must remain owned by the distributed resonator.",
        )
        partition = mapping(reduction.get("partition"), "floating-qubit reduction partition")
        require(
            len(sequence(partition.get("floating_labels"), "floating Coupler-pad labels")) == 4
            and len(sequence(partition.get("retained_labels"), "retained qubit labels")) == 3,
            "Floating-qubit reduction must eliminate four pads and retain three ordered nodes.",
        )
        reduced_matrix = sequence(reduction.get("reduced_maxwell_matrix_fF"), "reduced Maxwell matrix")
        require(len(reduced_matrix) == 3, "Reduced Maxwell matrix must have three rows.")
        for row_index, row_value in enumerate(reduced_matrix):
            row = sequence(row_value, f"reduced Maxwell row {row_index}")
            require(len(row) == 3, "Reduced Maxwell matrix must be 3x3.")
            for column_index, value in enumerate(row):
                finite_number(value, f"reduced Maxwell[{row_index},{column_index}]")
        physics = mapping(reduction.get("physics_diagnostics"), "floating-qubit physics diagnostics")
        f01 = finite_number(physics.get("first_order_transmon_f01_hz"), "qubit f01")
        f01_target = finite_number(physics.get("human_target_f01_hz"), "qubit f01 target")
        f01_residual = finite_number(physics.get("first_order_transmon_f01_residual_hz"), "qubit f01 residual")
        require(
            math.isclose(f01 - f01_target, f01_residual, rel_tol=1e-12, abs_tol=1e-6),
            "Qubit f01 residual is inconsistent.",
        )

        reference_notch = mapping(diagnostics.get("reference_notch"), "no-qubit reference notch")
        loaded_notch = mapping(diagnostics.get("notch"), "qubit-loaded notch")
        reference_roots = sequence(reference_notch.get("all_roots"), "reference notch roots")
        loaded_roots = sequence(loaded_notch.get("all_roots"), "loaded notch roots")
        require(
            reference_notch.get("ownership") == "unique_no_qubit_intrinsic_reference"
            and len(reference_roots) == 1,
            "No-qubit intrinsic reference notch must retain unique-root ownership.",
        )
        require(
            loaded_notch.get("ownership") == "nearest_unique_no_qubit_intrinsic_reference"
            and len(loaded_roots) >= 1
            and loaded_notch.get("reference_notch_hz") == reference_notch.get("frequency_hz")
            and finite_number(loaded_notch.get("assignment_margin_hz"), "loaded-notch assignment margin") > 0,
            "Loaded-notch ownership must bind the unique no-qubit reference with a positive margin.",
        )

    traces = mapping(record.get("traces"), "record.traces")
    intrinsic = mapping(traces.get("intrinsic"), "record.traces.intrinsic")
    intrinsic_frequency = numeric_array(intrinsic, "frequencies_hz", "record.traces.intrinsic")
    intrinsic_z21 = complex_array(intrinsic, "z21_ptc", "record.traces.intrinsic")
    require_same_length("record intrinsic trace", intrinsic_frequency, intrinsic_z21)
    require_increasing(intrinsic_frequency, "record intrinsic frequency grid")
    if expected_step_hz is not None:
        intrinsic_grid_hash = frequency_grid_sha256(intrinsic_frequency)
        require(
            intrinsic.get("frequency_grid_sha256") == intrinsic_grid_hash,
            "Loaded intrinsic-notch grid hash is inconsistent.",
        )
        _require_trace_id_grid_link(
            intrinsic.get("trace_id"), intrinsic_grid_hash, "loaded intrinsic-notch trace_id"
        )
        intrinsic_reference = mapping(
            traces.get("intrinsic_reference"), "record.traces.intrinsic_reference"
        )
        intrinsic_reference_frequency = numeric_array(
            intrinsic_reference, "frequencies_hz", "record.traces.intrinsic_reference"
        )
        intrinsic_reference_z21 = complex_array(
            intrinsic_reference, "z21_ptc", "record.traces.intrinsic_reference"
        )
        require_same_length(
            "record intrinsic reference trace", intrinsic_reference_frequency, intrinsic_reference_z21
        )
        require(
            np.array_equal(intrinsic_reference_frequency, intrinsic_frequency),
            "Loaded and no-qubit reference notch traces must share the exact grid.",
        )
        require(
            intrinsic_reference.get("frequency_grid_sha256") == intrinsic_grid_hash,
            "No-qubit reference-notch grid hash is inconsistent.",
        )
        _require_trace_id_grid_link(
            intrinsic_reference.get("trace_id"),
            intrinsic_grid_hash,
            "no-qubit intrinsic reference trace_id",
        )
        require(
            diagnostics["notch"].get("trace_id") == intrinsic.get("trace_id")
            and diagnostics["notch"].get("reference_trace_id")
            == diagnostics["reference_notch"].get("trace_id")
            == intrinsic_reference.get("trace_id"),
            "Notch diagnostic and captured trace identities disagree.",
        )

    filter_trace = mapping(traces.get("filter"), "record.traces.filter")
    filter_frequency, filter_grid_hash = _validate_declared_frequency_grid(
        filter_trace,
        "record.traces.filter",
        expected_step_hz=expected_step_hz,
        require_declared_hash=expected_step_hz is not None,
    )
    filter_s21 = complex_array(filter_trace, "s21", "record.traces.filter")
    filter_reference = complex_array(filter_trace, "reference_s21", "record.traces.filter")
    require_same_length("record filter trace", filter_frequency, filter_s21, filter_reference)
    require(np.all(np.abs(filter_reference) > 0), "Record filter reference S21 must be nonzero.")

    pair_trace = mapping(traces.get("pair"), "record.traces.pair")
    pair_frequency, pair_grid_hash = _validate_declared_frequency_grid(
        pair_trace,
        "record.traces.pair",
        expected_step_hz=expected_step_hz,
        require_declared_hash=expected_step_hz is not None,
    )
    pair_s21 = complex_array(pair_trace, "s21", "record.traces.pair")
    pair_reference = complex_array(pair_trace, "reference_s21", "record.traces.pair")
    require_same_length("record pair trace", pair_frequency, pair_s21, pair_reference)
    require(np.all(np.abs(pair_reference) > 0), "Record pair reference S21 must be nonzero.")
    pair_fit_frequency = numeric_array(pair_trace, "fit_frequencies_hz", "record.traces.pair")
    pair_fit_observed = complex_array(pair_trace, "fit_normalized_s21", "record.traces.pair")
    pair_fit_model = complex_array(pair_trace, "fitted_s21", "record.traces.pair")
    require_same_length(
        "record pair fit", pair_fit_frequency, pair_fit_observed, pair_fit_model
    )
    require_increasing(pair_fit_frequency, "record pair fit frequency grid")

    probes = sequence(traces.get("readout_probes"), "record.traces.readout_probes")
    require(len(probes) == len(frequency_fit["x_values"]), "Readout probes must match fit points.")
    probe_capacitances: list[float] = []
    probe_grid_hashes: list[str | None] = []
    qubit_probe_grid_hashes: list[str | None] = []
    for index, probe_value in enumerate(probes):
        probe = mapping(probe_value, f"record readout probe {index}")
        probe_capacitances.append(
            finite_number(probe.get("capacitance_fF"), f"record readout probe {index} capacitance")
        )
        probe_frequency, probe_grid_hash = _validate_declared_frequency_grid(
            probe,
            f"record readout probe {index}",
            expected_step_hz=expected_step_hz,
            require_declared_hash=expected_step_hz is not None,
        )
        probe_grid_hashes.append(probe_grid_hash)
        probe_s21 = complex_array(probe, "s21", f"record readout probe {index}")
        probe_reference = complex_array(probe, "reference_s21", f"record readout probe {index}")
        require_same_length(
            f"record readout probe {index}", probe_frequency, probe_s21, probe_reference
        )
        require(np.all(np.abs(probe_reference) > 0), f"Record readout probe {index} reference must be nonzero.")
        if expected_step_hz is not None:
            qubit_frequency = numeric_array(probe, "qubit_frequencies_hz", f"record qubit probe {index}")
            qubit_grid_hash = probe.get("qubit_frequency_grid_sha256")
            require(
                isinstance(qubit_grid_hash, str)
                and qubit_grid_hash == frequency_grid_sha256(qubit_frequency),
                f"Record qubit probe {index} grid hash is inconsistent.",
            )
            qubit_probe_grid_hashes.append(qubit_grid_hash)
            qubit_s21 = complex_array(probe, "qubit_s21", f"record qubit probe {index}")
            qubit_reference = complex_array(probe, "qubit_reference_s21", f"record qubit probe {index}")
            require_same_length(
                f"record qubit probe {index}", qubit_frequency, qubit_s21, qubit_reference
            )
            require(np.all(np.abs(qubit_reference) > 0), f"Record qubit probe {index} reference must be nonzero.")
    require(
        np.array_equal(
            np.asarray(probe_capacitances), fit_x_by_label["readout frequency fit"]
        ),
        "Readout probe capacitances must exactly match the fit grid.",
    )
    if filter_grid_hash is not None and pair_grid_hash is not None:
        require(
            diagnostics.get("loaded_frequency_grid_sha256") == filter_grid_hash
            and all(grid_hash == filter_grid_hash for grid_hash in probe_grid_hashes),
            "Filter/readout trace grids must match diagnostics.loaded_frequency_grid_sha256.",
        )
        require(
            diagnostics.get("pair_frequency_grid_sha256") == pair_grid_hash,
            "Pair trace grid must match diagnostics.pair_frequency_grid_sha256.",
        )
        if expected_step_hz is not None:
            qubit_grid_hash = diagnostics.get("qubit_frequency_grid_sha256")
            require(
                isinstance(qubit_grid_hash, str)
                and all(value == qubit_grid_hash for value in qubit_probe_grid_hashes),
                "Qubit probe grids must match diagnostics.qubit_frequency_grid_sha256.",
            )
        for trace_label, trace, grid_hash in (
            ("filter", filter_trace, filter_grid_hash),
            ("pair", pair_trace, pair_grid_hash),
        ):
            _require_trace_id_grid_link(
                trace.get("measured_trace_id"), grid_hash, f"{trace_label} measured_trace_id"
            )
            _require_trace_id_grid_link(
                trace.get("reference_trace_id"), grid_hash, f"{trace_label} reference_trace_id"
            )
        readout_modes = sequence(
            diagnostics.get("readout_probe_modes"), "record.diagnostics.readout_probe_modes"
        )
        require(len(readout_modes) == len(probes), "Readout modes must match captured probes.")
        for index, (probe_value, mode_value) in enumerate(zip(probes, readout_modes)):
            probe = mapping(probe_value, f"record readout probe {index}")
            mode = mapping(mode_value, f"record readout mode {index}")
            require(
                mode.get("frequency_grid_sha256") == filter_grid_hash,
                f"Readout mode {index} must bind the loaded grid hash.",
            )
            for identity_key in ("measured_trace_id", "reference_trace_id"):
                require(
                    mode.get(identity_key) == probe.get(identity_key),
                    f"Readout mode {index} and trace must share {identity_key}.",
                )
                _require_trace_id_grid_link(
                    probe.get(identity_key), filter_grid_hash, f"readout probe {index} {identity_key}"
                )
            if expected_step_hz is not None:
                qubit_mode = mapping(mode.get("qubit_mode"), f"record qubit mode {index}")
                require(
                    qubit_mode.get("frequency_grid_sha256") == probe.get("qubit_frequency_grid_sha256")
                    and qubit_mode.get("measured_trace_id") == probe.get("qubit_measured_trace_id"),
                    f"Qubit mode {index} and trace identities disagree.",
                )
                require(finite_number(mode.get("g_hz"), f"finite-probe g {index}") > 0, f"Finite-probe g {index} must be positive.")
        for diagnostic_id in (
            "filter_loaded_bare_reference_id",
            "readout_loaded_bare_reference_id",
        ):
            _require_trace_id_grid_link(
                diagnostics.get(diagnostic_id), filter_grid_hash, f"diagnostics.{diagnostic_id}"
            )
        j_provenance = mapping(j_fit.get("provenance"), "record.diagnostics.j_fit.provenance")
        for identity_key in ("measured_trace_id", "empty_feedline_trace_id"):
            _require_trace_id_grid_link(
                j_provenance.get(identity_key), pair_grid_hash, f"J-fit provenance {identity_key}"
            )


def validate_nominal_artifacts(
    nominal_directory: Path,
    optimizer_run_directory: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    """Validate one exact-six independent nominal result against one frozen optimizer candidate.

    This is intentionally a separate schema from optimizer evidence. It never
    adapts, falls back to, or relabels optimizer-time final diagnostics.
    """
    actual_files = {path.name for path in nominal_directory.iterdir() if path.is_file()}
    require(
        actual_files == NOMINAL_OUTPUT_FILES,
        "Nominal directory must contain exactly the six declared files; "
        f"missing={sorted(NOMINAL_OUTPUT_FILES - actual_files)}, "
        f"unexpected={sorted(actual_files - NOMINAL_OUTPUT_FILES)}.",
    )
    artifacts = {name: load_json(nominal_directory, name) for name in NOMINAL_OUTPUT_FILES}
    manifest = artifacts["validation_manifest.json"]
    status = artifacts["status.json"]
    snapshot = artifacts["layout_specs_snapshot.json"]
    inventory = artifacts["hash_inventory.json"]
    evaluation = artifacts["nominal_evaluation.json"]
    summary = artifacts["validation_summary.json"]

    require(
        manifest.get("schema_version") == NOMINAL_MANIFEST_SCHEMA,
        f"Nominal manifest must use exactly {NOMINAL_MANIFEST_SCHEMA!r}.",
    )
    require(
        manifest.get("semantic_hash_framing") == SEMANTIC_HASH_FRAMING,
        "Nominal manifest uses the wrong semantic hash framing.",
    )
    contract = mapping(manifest.get("contract"), "validation_manifest.contract")
    validation_hash = manifest.get("validation_contract_sha256")
    require(
        isinstance(validation_hash, str) and HEX_SHA256.fullmatch(validation_hash) is not None,
        "Nominal validation identity must be lowercase SHA-256.",
    )
    require(
        semantic_value_sha256(
            {
                "schema_version": NOMINAL_MANIFEST_SCHEMA,
                "semantic_hash_framing": SEMANTIC_HASH_FRAMING,
                "contract": contract,
            }
        )
        == validation_hash,
        "Nominal validation manifest hash does not match its contract.",
    )
    hashes = {
        name: artifact.get("validation_contract_sha256")
        for name, artifact in artifacts.items()
    }
    require(
        set(hashes.values()) == {validation_hash},
        f"Nominal exact-six validation identities disagree: {hashes}.",
    )
    require(contract.get("analysis_kind") == "nominal", "Nominal contract analysis_kind must be 'nominal'.")
    require(
        status.get("analysis_kind") == "nominal"
        and status.get("state") == "completed"
        and status.get("artifact_role") == "view_only_validation",
        "Nominal status must be completed view-only nominal validation.",
    )
    require(summary.get("analysis_kind") == "nominal", "Nominal summary analysis_kind must be 'nominal'.")
    require(summary.get("human_acceptance_claim") is None, "Nominal validation cannot claim Human acceptance.")

    validate_artifacts(optimizer_run_directory, workspace_root)
    optimizer_artifacts = {
        name: load_json(optimizer_run_directory, name)
        for name in EXPECTED_RUN_FILES
        if name.endswith(".json")
    }
    optimizer_manifest = optimizer_artifacts["condition_manifest.json"]
    require(
        optimizer_manifest.get("schema_version") == SLOT_EXECUTION_MANIFEST_SCHEMA,
        "Independent nominal validation is permitted only for a current per-Slot optimizer run.",
    )
    optimizer_contract = mapping(
        optimizer_manifest.get("contract"), "current optimizer manifest.contract"
    )
    optimizer_selection = mapping(
        optimizer_contract.get("selection"), "current optimizer contract.selection"
    )
    expected_selection = {
        "case_id": optimizer_selection.get("case_id"),
        "target_set_id": optimizer_selection.get("target_set_id"),
        "slot_target_ghz": optimizer_selection.get("slot_target_ghz"),
    }
    require(
        contract.get("selection") == expected_selection,
        "Nominal selection does not exactly match the optimizer case, target set, and Slot.",
    )
    optimizer_config = optimizer_artifacts["config_snapshot.json"]
    optimizer_inventory = _optimizer_inventory_by_id(optimizer_artifacts["hash_inventory.json"])
    optimizer_identity = optimizer_candidate_identity(optimizer_run_directory, optimizer_artifacts)
    source_optimizer = mapping(contract.get("source_optimizer"), "nominal contract.source_optimizer")
    expected_source = {
        key: optimizer_identity[key]
        for key in (
            "run_id",
            "optimizer_id",
            "optimizer_contract_sha256",
            "optimizer_identity_sha256",
            "layout_specs_raw_sha256",
            "candidate_id",
            "candidate_sha256",
        )
    }
    require(
        all(source_optimizer.get(key) == value for key, value in expected_source.items()),
        "Nominal validation does not match the selected optimizer run and frozen candidate.",
    )
    source_run_path, resolved_source_run = _relative_workspace_path(
        source_optimizer.get("run_directory"), workspace_root, "Nominal source optimizer path"
    )
    require(
        resolved_source_run == optimizer_run_directory.resolve(),
        "Nominal source optimizer path resolves to a different run.",
    )
    require(
        snapshot.get("layout_specs_raw_sha256") == optimizer_identity["layout_specs_raw_sha256"]
        and snapshot.get("layout_specs") == optimizer_identity["layout_specs"],
        "Nominal layout snapshot is not the selected optimizer layout_specs.json.",
    )

    source_hashes = sequence(contract.get("source_hashes"), "nominal contract.source_hashes")
    require(source_hashes == inventory.get("files"), "Nominal manifest and hash inventory must match exactly.")
    require(source_hashes, "Nominal source hash inventory must not be empty.")
    source_ids: set[str] = set()
    source_hash_by_id: dict[str, str] = {}
    source_path_by_id: dict[str, Path] = {}
    source_relative_by_id: dict[str, str] = {}
    for index, value in enumerate(source_hashes):
        item = mapping(value, f"nominal source_hashes[{index}]")
        require(set(item) == {"id", "path", "sha256"}, "Nominal source hash rows have an exact id/path/sha256 schema.")
        source_id, source_path, source_hash = item["id"], item["path"], item["sha256"]
        require(isinstance(source_id, str) and source_id and source_id not in source_ids, "Nominal source ids must be unique.")
        source_ids.add(source_id)
        normalized_source_path, current_path = _relative_workspace_path(
            source_path, workspace_root, f"Nominal source {source_id!r} path"
        )
        require(isinstance(source_hash, str) and HEX_SHA256.fullmatch(source_hash) is not None, f"Nominal source {source_id!r} hash is invalid.")
        require(current_path.is_file(), f"Nominal source {source_id!r} no longer exists.")
        require(file_sha256(current_path) == source_hash, f"Nominal source {source_id!r} is stale.")
        source_hash_by_id[source_id] = source_hash
        source_path_by_id[source_id] = current_path
        source_relative_by_id[source_id] = normalized_source_path
    require(
        source_ids == {"target", "conditions", "config_snapshot", "q2d", "seed", "common", "evaluator", "semantic_hash", "qubit_input", "qubit_input_loader", "runner", "nominal_runtime"},
        "Nominal source inventory must bind the exact production source set.",
    )

    required_optimizer_sources = {
        "target_contract",
        "optimizer_conditions",
        "seed_csv",
        "orpen_case_json",
        "d3_purcell_common",
        "d3_coupled_evaluator",
        "d3_semantic_hash",
        "floating_qubit_nominal",
        "d3_floating_qubit_input_loader",
    }
    require(
        required_optimizer_sources <= set(optimizer_inventory),
        "Current optimizer inventory is missing a nominal-validation source binding.",
    )
    declared_consumed = _optimizer_inventory_by_id(
        {"files": sequence(optimizer_contract.get("consumed_files"), "current optimizer consumed_files")}
    )
    require(
        all(declared_consumed.get(source_id) == optimizer_inventory[source_id]
            for source_id in required_optimizer_sources),
        "Current optimizer manifest and hash inventory source bindings disagree.",
    )

    config_target = mapping(optimizer_config.get("target_contract"), "optimizer config target_contract")
    expected_paths = {
        "target": config_target.get("workspace_relative_path"),
        "conditions": optimizer_inventory["optimizer_conditions"]["path"],
        "q2d": optimizer_config.get("orpen_case_json_workspace_path"),
        "seed": str(
            PurePosixPath(str(optimizer_config.get("design_csv_workspace_root", "")))
            / str(optimizer_config.get("design_csv_filename", ""))
        ),
        "common": optimizer_inventory["d3_purcell_common"]["path"],
        "evaluator": optimizer_inventory["d3_coupled_evaluator"]["path"],
        "semantic_hash": optimizer_inventory["d3_semantic_hash"]["path"],
        "qubit_input": optimizer_config.get("floating_qubit_nominal_workspace_path"),
        "qubit_input_loader": optimizer_inventory["d3_floating_qubit_input_loader"]["path"],
    }
    try:
        config_snapshot_relative = (
            optimizer_run_directory.resolve() / "config_snapshot.json"
        ).relative_to(workspace_root.resolve()).as_posix()
    except ValueError as error:
        raise ArtifactContractError("Selected optimizer run must reside inside the workspace.") from error
    expected_paths["config_snapshot"] = config_snapshot_relative
    for source_id, expected_path in expected_paths.items():
        normalized_expected, resolved_expected = _relative_workspace_path(
            expected_path, workspace_root, f"Expected optimizer source {source_id!r}"
        )
        require(
            source_relative_by_id[source_id] == normalized_expected
            and source_path_by_id[source_id] == resolved_expected,
            f"Nominal source {source_id!r} does not match the selected optimizer source path.",
        )

    conditions_payload = load_json(source_path_by_id["conditions"].parent, source_path_by_id["conditions"].name)
    conditions_contract = {
        key: value for key, value in conditions_payload.items() if key != "sol_review"
    }
    target_payload = load_json(source_path_by_id["target"].parent, source_path_by_id["target"].name)
    optimizer_target = mapping(
        optimizer_contract.get("target_contract"), "current optimizer target_contract"
    )
    optimizer_conditions = mapping(
        optimizer_contract.get("optimizer_conditions"), "current optimizer optimizer_conditions"
    )
    require(
        target_payload.get("target_id") == config_target.get("expected_target_id") == optimizer_target.get("target_id")
        and target_payload.get("revision") == config_target.get("expected_revision") == optimizer_target.get("revision"),
        "Current target identity/revision is inconsistent across source, config, and optimizer manifest.",
    )
    require(
        source_hash_by_id["target"]
        == config_target.get("expected_sha256")
        == optimizer_target.get("sha256")
        == optimizer_inventory["target_contract"]["sha256"],
        "Current target raw hash is inconsistent across nominal and optimizer bindings.",
    )
    require(
        optimizer_conditions.get("hash_framing") == SEMANTIC_HASH_FRAMING
        and mapping(conditions_payload.get("sol_review"), "conditions.sol_review").get("hash_framing")
        == SEMANTIC_HASH_FRAMING
        and conditions_payload.get("conditions_id") == optimizer_conditions.get("conditions_id")
        and semantic_value_sha256(conditions_contract) == optimizer_conditions.get("sha256"),
        "Current optimizer conditions identity/canonical hash is inconsistent.",
    )
    require(
        source_hash_by_id["conditions"] == optimizer_inventory["optimizer_conditions"]["sha256"],
        "Current optimizer conditions raw hash is inconsistent.",
    )
    optimizer_config_hash = file_sha256(optimizer_run_directory / "config_snapshot.json")
    require(
        source_hash_by_id["config_snapshot"] == optimizer_config_hash
        and optimizer_artifacts["hash_inventory.json"].get("config_snapshot_sha256")
        == optimizer_config_hash,
        "Nominal config snapshot is not the exact selected optimizer snapshot.",
    )
    for nominal_id, optimizer_id in {
        "q2d": "orpen_case_json",
        "seed": "seed_csv",
        "common": "d3_purcell_common",
        "evaluator": "d3_coupled_evaluator",
        "semantic_hash": "d3_semantic_hash",
        "qubit_input": "floating_qubit_nominal",
        "qubit_input_loader": "d3_floating_qubit_input_loader",
    }.items():
        require(
            source_hash_by_id[nominal_id] == optimizer_inventory[optimizer_id]["sha256"],
            f"Nominal source {nominal_id!r} hash disagrees with the selected optimizer binding.",
        )
    bound_identities = mapping(contract.get("bound_identities"), "nominal contract.bound_identities")
    qubit_payload = load_json(source_path_by_id["qubit_input"].parent, source_path_by_id["qubit_input"].name)
    qubit_contract = mapping(
        optimizer_contract.get("floating_qubit_nominal"),
        "current optimizer floating_qubit_nominal",
    )
    expected_f01_hz, expected_lj_nh = canonical_qubit_targets(target_payload)
    require(
        source_hash_by_id["qubit_input"] == qubit_contract.get("input_sha256")
        and qubit_payload.get("model_id") == qubit_contract.get("model_id"),
        "Floating-qubit private input bytes/model identity disagree with the optimizer contract.",
    )
    require(
        qubit_payload.get("schema_version") == qubit_contract.get("schema_version")
        == "d3-floating-qubit-maxwell.v1"
        and qubit_payload.get("readout_self_capacitance_ownership")
        == qubit_contract.get("readout_self_capacitance_ownership")
        == "distributed_resonator_owns_self_capacitance"
        and qubit_contract.get("readout_diagonal_instantiated") is False
        and qubit_payload.get("L_J_per_junction_nH")
        == qubit_contract.get("L_J_per_junction_nH") == expected_lj_nh,
        "Floating-qubit full-Maxwell schema, readout ownership, or canonical junction contract is inconsistent.",
    )
    qubit_targets = mapping(qubit_contract.get("canonical_targets"), "floating-qubit canonical targets")
    require(
        qubit_targets.get("target_contract_id") == target_payload.get("target_id")
        and qubit_targets.get("target_contract_sha256") == source_hash_by_id["target"]
        and mapping(qubit_targets.get("qubit_transition_frequency"), "manifest qubit f01 target").get("value") == expected_f01_hz
        and mapping(qubit_targets.get("qubit_junction_inductance"), "manifest qubit L_J target").get("value") == expected_lj_nh,
        "Floating-qubit manifest target identities/values disagree with the canonical Design Target.",
    )
    expected_bound_identities = {
        "target_sha256": source_hash_by_id["target"],
        "conditions_contract_sha256": semantic_value_sha256(conditions_contract),
        "conditions_file_sha256": source_hash_by_id["conditions"],
        "config_snapshot_sha256": source_hash_by_id["config_snapshot"],
        "q2d_sha256": source_hash_by_id["q2d"],
        "seed_sha256": source_hash_by_id["seed"],
        "floating_qubit_input_sha256": source_hash_by_id["qubit_input"],
        "floating_qubit_loader_sha256": source_hash_by_id["qubit_input_loader"],
        "floating_qubit_model_id": qubit_payload["model_id"],
        "layout_specs_raw_sha256": optimizer_identity["layout_specs_raw_sha256"],
        "candidate_sha256": optimizer_identity["candidate_sha256"],
        "optimizer_identity_sha256": optimizer_identity["optimizer_identity_sha256"],
    }
    require(
        bound_identities == expected_bound_identities,
        "Nominal bound identities do not match the source, optimizer, and candidate hashes.",
    )

    execution = mapping(contract.get("execution"), "nominal contract.execution")
    require(
        execution == {
            "fresh_process": True,
            "fresh_evaluator": True,
            "capture_traces": True,
            "optimizer_cache_allowed": False,
            "evaluation_budget": 1,
        },
        "Nominal execution contract must require one fresh uncached trace-capturing evaluation.",
    )
    no_variation = {"kind": "none", "parameters": []}
    require(contract.get("variation") == no_variation, "Nominal contract variation must be none.")
    require(
        evaluation.get("analysis_kind") == "nominal"
        and evaluation.get("independent_validation") is True
        and evaluation.get("evaluation_count") == 1
        and evaluation.get("variation") == no_variation,
        "Nominal evaluation must be one independent evaluation with no variation.",
    )
    record = mapping(evaluation.get("record"), "nominal_evaluation.record")
    require(record.get("status") == "valid", "Nominal evaluation record must be valid.")
    bound_frequency_step_hz = finite_number(
        mapping(
            conditions_payload.get("evaluator_settings"), "conditions.evaluator_settings"
        ).get("frequency_step_hz"),
        "conditions evaluator frequency step",
    )
    _validate_notebook_record_shape(record, bound_frequency_step_hz)
    record_qubit_physics = mapping(
        mapping(
            mapping(record["diagnostics"]["floating_qubit"], "nominal floating-qubit diagnostics").get("electrostatic_reduction"),
            "nominal floating-qubit reduction",
        ).get("physics_diagnostics"),
        "nominal floating-qubit physics",
    )
    require(
        record_qubit_physics.get("human_target_f01_hz") == expected_f01_hz,
        "Nominal candidate diagnostics do not use the canonical qubit f01 target.",
    )
    metrics = mapping(record.get("metrics"), "nominal_evaluation.record.metrics")
    layout_breakdown = mapping(
        optimizer_identity["layout_specs"].get("breakdown"), "optimizer layout breakdown"
    )
    layout_metrics = {
        mapping(value, "optimizer layout metric").get("name"): mapping(
            value, "optimizer layout metric"
        )
        for value in sequence(layout_breakdown.get("metrics"), "optimizer layout breakdown.metrics")
    }
    require(len(layout_metrics) == len(sequence(layout_breakdown.get("metrics"), "optimizer layout breakdown.metrics")),
            "Optimizer layout metric names must be unique.")
    condition_metric_specs = mapping(
        conditions_payload.get("metric_specs"), "current optimizer conditions.metric_specs"
    )
    positive_condition_ids = {
        metric_id
        for metric_id, spec_value in condition_metric_specs.items()
        if finite_number(mapping(spec_value, f"metric spec {metric_id}").get("weight"), f"{metric_id} weight") > 0.0
    }
    require(
        positive_condition_ids == NOMINAL_OBJECTIVE_IDS,
        "Current positive-weight Cost Function operands do not match the nominal objective contract.",
    )
    target_values = mapping(target_payload.get("targets"), "current target.targets")
    slot_ghz = finite_number(expected_selection["slot_target_ghz"], "current optimizer Slot")
    canonical_targets = {
        "filter_loaded_bare_hz": (
            slot_ghz * 1.0e3
            + finite_number(mapping(target_values.get("filter_loaded_bare_offset"), "filter target").get("value"), "filter offset")
        ) * 1.0e6,
        "readout_loaded_bare_hz": (
            slot_ghz * 1.0e3
            + finite_number(mapping(target_values.get("readout_loaded_bare_offset"), "readout target").get("value"), "readout offset")
        ) * 1.0e6,
        "notch_hz": finite_number(
            mapping(target_values.get("interference_notch_frequency"), "notch target").get("value"),
            "notch target",
        ) * 1.0e9,
        "filter_loaded_linewidth_hz": finite_number(
            mapping(target_values.get("filter_loaded_bare_linewidth"), "linewidth target").get("value"),
            "linewidth target",
        ) * 1.0e6,
        "j_hz": finite_number(
            mapping(target_values.get("readout_filter_exchange_coupling"), "J target").get("value"),
            "J target",
        ) * 1.0e6,
        "g_hz": finite_number(
            mapping(target_values.get("qubit_readout_coupling"), "g target").get("value"),
            "g target",
        ) * 1.0e6,
    }
    operands = sequence(summary.get("objective_operands"), "validation_summary.objective_operands")
    require(len(operands) == len(NOMINAL_OBJECTIVE_IDS), "Nominal summary must contain the six objective operands.")
    operand_ids: set[str] = set()
    for index, value in enumerate(operands):
        operand = mapping(value, f"objective_operands[{index}]")
        require(set(operand) == {"id", "unit", "target", "observed", "scale", "normalized_residual"}, "Objective operand schema is not exact.")
        operand_id = operand.get("id")
        require(isinstance(operand_id, str) and operand_id not in operand_ids, "Objective operand ids must be unique.")
        operand_ids.add(operand_id)
        require(operand.get("unit") == "Hz", f"{operand_id} objective operand unit must be 'Hz'.")
        target = finite_number(operand.get("target"), f"{operand_id} target")
        observed = finite_number(operand.get("observed"), f"{operand_id} observed")
        scale = finite_number(operand.get("scale"), f"{operand_id} scale")
        residual = finite_number(operand.get("normalized_residual"), f"{operand_id} residual")
        require(scale > 0.0, f"{operand_id} scale must be positive.")
        layout_metric = mapping(layout_metrics.get(operand_id), f"optimizer layout metric {operand_id}")
        condition_spec = mapping(condition_metric_specs.get(operand_id), f"condition metric {operand_id}")
        require(
            target == canonical_targets[operand_id] == layout_metric.get("target")
            and scale == finite_number(condition_spec.get("scale"), f"{operand_id} condition scale")
            == layout_metric.get("scale"),
            f"{operand_id} target/scale disagrees with canonical and optimizer Cost Function bindings.",
        )
        require(metrics.get(operand_id) == observed, f"{operand_id} summary observation disagrees with the nominal record.")
        require(math.isclose(residual, (observed - target) / scale, rel_tol=1e-12, abs_tol=1e-12), f"{operand_id} normalized residual is inconsistent.")
    require(operand_ids == NOMINAL_OBJECTIVE_IDS, "Nominal objective operand ids do not match the Cost Function operands.")
    intrinsic_frequency, intrinsic_z21 = _validate_nominal_wide_trace(
        record, bound_frequency_step_hz
    )
    wide_provenance = mapping(
        mapping(mapping(record.get("traces"), "nominal traces").get("intrinsic_wide"), "nominal intrinsic_wide").get("range_provenance"),
        "nominal intrinsic_wide.range_provenance",
    )
    require(
        wide_provenance.get("notch_target_hz") == canonical_targets["notch_hz"]
        and wide_provenance.get("filter_loaded_bare_hz") == metrics.get("filter_loaded_bare_hz"),
        "Nominal wide range provenance is not bound to the canonical notch and observed filter frequency.",
    )
    return {
        "artifacts": artifacts,
        "status": status,
        "contract": contract,
        "validation_hash": validation_hash,
        "record": record,
        "metrics": metrics,
        "objective_operands": operands,
        "intrinsic_frequency": intrinsic_frequency,
        "intrinsic_z21": intrinsic_z21,
        "optimizer_identity": optimizer_identity,
    }


def discover_nominal_validations(
    output_root: Path,
    optimizer_run_directory: Path,
    workspace_root: Path,
) -> dict[str, list[Any]]:
    """Find matching evidence without misclassifying other Slots as rejected."""
    report: dict[str, list[Any]] = {"valid": [], "rejected": [], "unrelated": []}
    if not output_root.is_dir():
        return report
    for directory in sorted(path for path in output_root.iterdir() if path.is_dir()):
        try:
            manifest = load_json(directory, "validation_manifest.json")
            contract = mapping(manifest.get("contract"), "validation_manifest.contract")
            source_optimizer = mapping(
                contract.get("source_optimizer"), "validation_manifest.contract.source_optimizer"
            )
            source_run_id = source_optimizer.get("run_id")
            if isinstance(source_run_id, str) and source_run_id != optimizer_run_directory.name:
                report["unrelated"].append((directory, source_run_id))
                continue
            report["valid"].append(
                (directory, validate_nominal_artifacts(directory, optimizer_run_directory, workspace_root))
            )
        except (ArtifactContractError, OSError) as error:
            report["rejected"].append((directory, str(error)))
    return report


def normalize_review_contract(
    manifest: dict[str, Any],
    config_snapshot: dict[str, Any],
    target_contract: dict[str, Any],
    target_sha256: str,
    optimizer_conditions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize legacy and per-slot manifests without mixing their source keys."""
    schema = manifest.get("schema_version")
    contract = mapping(manifest.get("contract"), "condition_manifest.contract")
    if schema == LEGACY_MANIFEST_SCHEMA:
        scope = mapping(contract.get("scope"), "legacy contract.scope")
        design_selection = mapping(
            contract.get("design_selection"), "legacy contract.design_selection"
        )
        source_row = mapping(
            mapping(design_selection.get("source_row"), "legacy source_row").get("value"),
            "legacy source_row.value",
        )
        feedline = mapping(
            mapping(contract.get("feedline"), "legacy contract.feedline").get("value"),
            "legacy contract.feedline.value",
        )
        metric_contract = mapping(
            contract.get("metric_contract"), "legacy contract.metric_contract"
        )
        return {
            "schema_version": schema,
            "selected_case_id": scope["selected_case_id"],
            "selected_target_set_id": source_row["target_set_id"],
            "selected_slot_ghz": finite_number(scope["slot_target_hz"], "legacy slot") / 1e9,
            "source_row": source_row,
            "metric_specs": sequence(metric_contract.get("metric_specs"), "legacy metric specs"),
            "optimizer_metric_fields": sequence(
                metric_contract.get("optimizer_metric_fields"), "legacy optimizer metric fields"
            ),
            "variable_specs": sequence(contract.get("variables"), "legacy variables"),
            "feedline": feedline,
            "execution_scope": scope.get("value", "legacy_single_slot_execution"),
            "sol_review": mapping(manifest.get("sol_review"), "legacy sol_review"),
            "human_review": mapping(manifest.get("human_review"), "legacy human_review"),
        }

    require(
        schema == SLOT_EXECUTION_MANIFEST_SCHEMA,
        f"Unsupported D3 manifest schema {schema!r}.",
    )
    require(optimizer_conditions is not None, "Per-slot review requires optimizer conditions.")
    conditions = mapping(optimizer_conditions, "optimizer conditions")
    require(
        conditions.get("schema_version") == "d3-optimizer-conditions.v1",
        "Unsupported optimizer conditions schema.",
    )
    conditions_contract = {key: value for key, value in conditions.items() if key != "sol_review"}
    conditions_hash = semantic_value_sha256(conditions_contract)
    manifest_conditions = mapping(
        contract.get("optimizer_conditions"), "per-slot contract.optimizer_conditions"
    )
    require(
        manifest.get("semantic_hash_framing") == SEMANTIC_HASH_FRAMING
        and manifest_conditions.get("hash_framing") == SEMANTIC_HASH_FRAMING
        and mapping(conditions.get("sol_review"), "optimizer conditions.sol_review").get("hash_framing")
        == SEMANTIC_HASH_FRAMING
        and
        manifest_conditions.get("conditions_id") == conditions.get("conditions_id")
        and manifest_conditions.get("sha256") == conditions_hash,
        "Current optimizer conditions id/hash do not match the per-slot manifest.",
    )
    manifest_target = mapping(contract.get("target_contract"), "per-slot target_contract")
    require(
        manifest_target.get("target_id") == target_contract.get("target_id")
        and manifest_target.get("revision") == target_contract.get("revision")
        and manifest_target.get("sha256") == target_sha256,
        "Current Design Target identity/hash do not match the per-slot manifest.",
    )
    selection = mapping(contract.get("selection"), "per-slot contract.selection")
    source_row = mapping(selection.get("source_row"), "per-slot selection.source_row")
    feedline_snapshot = mapping(config_snapshot.get("feedline_rlgc"), "config_snapshot.feedline_rlgc")
    target_impedance = finite_number(
        feedline_snapshot.get("target_impedance_ohm"), "feedline target impedance"
    )
    extracted_impedance = math.sqrt(
        finite_number(feedline_snapshot.get("l_per_m_h"), "feedline L")
        / finite_number(feedline_snapshot.get("c_per_m_f"), "feedline C")
    )
    reflection = abs((extracted_impedance - target_impedance) / (extracted_impedance + target_impedance))
    feedline = dict(feedline_snapshot)
    feedline.update(
        {
            "extracted_lc_impedance_ohm": extracted_impedance,
            "actual_return_loss_db": -20.0 * math.log10(reflection),
            "r_per_m_ohm": {
                "meaning": f"{feedline_snapshot.get('r_status')}; {feedline_snapshot.get('loss_assumption')}"
            },
            "g_per_m_s": {
                "meaning": f"{feedline_snapshot.get('g_status')}; {feedline_snapshot.get('loss_assumption')}"
            },
        }
    )
    metric_specs = sequence(contract.get("derived_metrics"), "per-slot derived_metrics")
    return {
        "schema_version": schema,
        "selected_case_id": selection["case_id"],
        "selected_target_set_id": selection["target_set_id"],
        "selected_slot_ghz": finite_number(selection["slot_target_ghz"], "per-slot slot"),
        "source_row": source_row,
        "metric_specs": metric_specs,
        "optimizer_metric_fields": [mapping(item, "derived metric")["id"] for item in metric_specs],
        "variable_specs": sequence(contract.get("derived_variables"), "per-slot derived_variables"),
        "feedline": feedline,
        "execution_scope": contract.get("purpose", "single_slot_layout_search_exploration"),
        "sol_review": mapping(manifest_conditions.get("sol_review"), "per-slot sol_review"),
        "human_review": {
            "reviewer_identity": None,
            "reviewer_role": "Human design decision owner",
            "status": "required",
        },
    }


def validate_artifacts(
    run_directory: Path, workspace_root: Path | None = None
) -> dict[str, Any]:
    actual_files = {path.name for path in run_directory.iterdir() if path.is_file()}
    require(
        actual_files == EXPECTED_RUN_FILES,
        "Run directory must retain exactly the eight declared files; "
        f"missing={sorted(EXPECTED_RUN_FILES - actual_files)}, "
        f"unexpected={sorted(actual_files - EXPECTED_RUN_FILES)}.",
    )

    artifacts = {
        filename: load_json(run_directory, filename)
        for filename in sorted(EXPECTED_RUN_FILES)
        if filename.endswith(".json")
    }
    status = artifacts["status.json"]
    final = artifacts["final_diagnostics.json"]
    layout = artifacts["layout_specs.json"]
    optimization = artifacts["optimization_result.json"]
    manifest = artifacts["condition_manifest.json"]
    inventory = artifacts["hash_inventory.json"]
    config_snapshot = artifacts["config_snapshot.json"]

    require(status.get("state") == "completed", "status.json state must be 'completed'.")
    require(final.get("state") == "captured", "final diagnostics state must be 'captured'.")
    final_record = mapping(final.get("record"), "final_diagnostics.record")
    require(final_record.get("status") == "valid", "Captured final diagnostics record must be valid.")
    require(layout.get("state") == "best_valid_candidate", "Layout state must be 'best_valid_candidate'.")
    require(
        status.get("artifact_approval") == layout.get("artifact_approval") == "unapproved_exploration",
        "Status and layout must both identify unapproved exploration evidence.",
    )

    manifest_schema = manifest.get("schema_version")
    expected_trace_step_hz: float | None = None
    if manifest_schema == LEGACY_MANIFEST_SCHEMA:
        identity_field = "contract_sha256"
        identity_label = "contract"
    elif manifest_schema == SLOT_EXECUTION_MANIFEST_SCHEMA:
        identity_field = "execution_sha256"
        identity_label = "execution"
        require(
            manifest.get("semantic_hash_framing") == SEMANTIC_HASH_FRAMING,
            "Current optimizer manifest uses the wrong semantic hash framing.",
        )
        manifest_contract = mapping(
            manifest.get("contract"), "current condition_manifest.contract"
        )
        recomputed_execution_sha256 = semantic_value_sha256(
            {
                "schema_version": SLOT_EXECUTION_MANIFEST_SCHEMA,
                "semantic_hash_framing": SEMANTIC_HASH_FRAMING,
                "contract": manifest_contract,
            }
        )
        require(
            manifest.get("execution_sha256") == recomputed_execution_sha256,
            "Current optimizer execution_sha256 does not match canonical {schema_version, contract}.",
        )
        require(
            final.get("analysis_kind") == "optimizer_internal_final_reproduction"
            and final.get("independent_validation") is False,
            "Current final_diagnostics must be optimizer-internal reproduction, not independent validation.",
        )
        config_snapshot_sha256 = file_sha256(run_directory / "config_snapshot.json")
        require(
            isinstance(inventory.get("config_snapshot_sha256"), str)
            and HEX_SHA256.fullmatch(inventory["config_snapshot_sha256"]) is not None
            and inventory["config_snapshot_sha256"] == config_snapshot_sha256,
            "Current hash inventory config_snapshot_sha256 does not match raw config_snapshot.json.",
        )
        require(
            manifest_contract.get("consumed_files") == inventory.get("files"),
            "Current manifest consumed_files must exactly equal hash_inventory.files.",
        )
        optimizer_inventory = _optimizer_inventory_by_id(inventory)
        require(
            {"target_contract", "optimizer_conditions", "floating_qubit_nominal", "d3_floating_qubit_input_loader"}
            <= set(optimizer_inventory),
            "Current optimizer inventory must bind conditions, floating-qubit input, and its loader.",
        )
        conditions_relative = optimizer_inventory["optimizer_conditions"]["path"]
        candidate_roots = (
            [workspace_root.resolve()]
            if workspace_root is not None
            else [run_directory.resolve(), *run_directory.resolve().parents]
        )
        target_relative = optimizer_inventory["target_contract"]["path"]
        matching_targets = [
            root / target_relative
            for root in candidate_roots
            if (root / target_relative).is_file()
        ]
        require(len(matching_targets) == 1, "Current canonical target must resolve exactly once.")
        target_path = matching_targets[0]
        require(
            file_sha256(target_path) == optimizer_inventory["target_contract"]["sha256"],
            "Current canonical target bytes disagree with the inventory binding.",
        )
        target_payload = load_json(target_path.parent, target_path.name)
        expected_f01_hz, expected_lj_nh = canonical_qubit_targets(target_payload)
        matching_conditions = [
            root / conditions_relative
            for root in candidate_roots
            if (root / conditions_relative).is_file()
        ]
        require(
            len(matching_conditions) == 1,
            "Current optimizer conditions path must resolve exactly once from the workspace.",
        )
        conditions_path = matching_conditions[0]
        require(
            file_sha256(conditions_path)
            == optimizer_inventory["optimizer_conditions"]["sha256"],
            "Current optimizer conditions raw hash disagrees with its inventory binding.",
        )
        current_conditions = load_json(conditions_path.parent, conditions_path.name)
        current_conditions_contract = {
            key: value for key, value in current_conditions.items() if key != "sol_review"
        }
        manifest_conditions = mapping(
            manifest_contract.get("optimizer_conditions"),
            "current contract.optimizer_conditions",
        )
        require(
            manifest_conditions.get("hash_framing") == SEMANTIC_HASH_FRAMING
            and semantic_value_sha256(current_conditions_contract)
            == manifest_conditions.get("sha256"),
            "Current optimizer conditions semantic identity is inconsistent.",
        )
        expected_trace_step_hz = finite_number(
            mapping(
                current_conditions.get("evaluator_settings"),
                "current conditions.evaluator_settings",
            ).get("frequency_step_hz"),
            "current evaluator frequency step",
        )
        qubit_relative = optimizer_inventory["floating_qubit_nominal"]["path"]
        require(
            qubit_relative == config_snapshot.get("floating_qubit_nominal_workspace_path"),
            "Current config and inventory floating-qubit paths disagree.",
        )
        matching_qubit_inputs = [
            root / qubit_relative
            for root in candidate_roots
            if (root / qubit_relative).is_file()
        ]
        require(len(matching_qubit_inputs) == 1, "Current floating-qubit input must resolve exactly once.")
        qubit_path = matching_qubit_inputs[0]
        require(
            file_sha256(qubit_path) == optimizer_inventory["floating_qubit_nominal"]["sha256"],
            "Current floating-qubit input bytes disagree with the inventory binding.",
        )
        qubit_payload = load_json(qubit_path.parent, qubit_path.name)
        loader_relative = optimizer_inventory["d3_floating_qubit_input_loader"]["path"]
        matching_loaders = [
            root / loader_relative
            for root in candidate_roots
            if (root / loader_relative).is_file()
        ]
        require(len(matching_loaders) == 1, "Current floating-qubit loader must resolve exactly once.")
        require(
            file_sha256(matching_loaders[0])
            == optimizer_inventory["d3_floating_qubit_input_loader"]["sha256"],
            "Current floating-qubit loader bytes disagree with the inventory binding.",
        )
        qubit_contract = mapping(
            manifest_contract.get("floating_qubit_nominal"),
            "current contract.floating_qubit_nominal",
        )
        require(
            qubit_contract.get("input_sha256") == optimizer_inventory["floating_qubit_nominal"]["sha256"]
            and qubit_contract.get("model_id") == qubit_payload.get("model_id"),
            "Current floating-qubit bytes/model identity disagree with the manifest.",
        )
        require(
            qubit_payload.get("schema_version") == qubit_contract.get("schema_version")
            == "d3-floating-qubit-maxwell.v1"
            and qubit_payload.get("readout_self_capacitance_ownership")
            == qubit_contract.get("readout_self_capacitance_ownership")
            == "distributed_resonator_owns_self_capacitance"
            and qubit_contract.get("readout_diagonal_instantiated") is False
            and qubit_payload.get("L_J_per_junction_nH")
            == qubit_contract.get("L_J_per_junction_nH") == expected_lj_nh,
            "Current floating-qubit full-Maxwell schema, readout ownership, or canonical junction value is inconsistent.",
        )
        qubit_targets = mapping(qubit_contract.get("canonical_targets"), "current floating-qubit canonical targets")
        require(
            qubit_targets.get("target_contract_id") == target_payload.get("target_id")
            and qubit_targets.get("target_contract_sha256") == optimizer_inventory["target_contract"]["sha256"]
            and mapping(qubit_targets.get("qubit_transition_frequency"), "current manifest qubit f01 target").get("value") == expected_f01_hz
            and mapping(qubit_targets.get("qubit_junction_inductance"), "current manifest qubit L_J target").get("value") == expected_lj_nh,
            "Current floating-qubit manifest target identities/values disagree with the canonical Design Target.",
        )
        selection = mapping(manifest_contract.get("selection"), "current contract.selection")
        source_row = mapping(selection.get("source_row"), "current contract.selection.source_row")
        require(
            selection.get("source_row_sha256") == semantic_value_sha256(source_row),
            "Current optimizer source_row_sha256 does not match semantic source-row framing.",
        )
        for optional_identity in ("execution_sha256", "condition_manifest_sha256"):
            require(
                optional_identity not in final
                or final.get(optional_identity) == manifest.get("execution_sha256"),
                f"Current final_diagnostics {optional_identity} disagrees with execution identity.",
            )
    else:
        raise ArtifactContractError(f"Unsupported D3 manifest schema {manifest_schema!r}.")
    hashes = {
        "status": status.get(identity_field),
        "condition manifest": manifest.get(identity_field),
        "hash inventory": inventory.get(identity_field),
        "optimization result": optimization.get("condition_manifest_sha256"),
        "layout specs": layout.get("condition_manifest_sha256"),
    }
    require(all(isinstance(value, str) and HEX_SHA256.fullmatch(value) for value in hashes.values()),
            f"Every contract hash must be lowercase SHA-256; observed {hashes}.")
    require(len(set(hashes.values())) == 1, f"Persisted contract hashes disagree: {hashes}.")
    contract_hash = next(iter(hashes.values()))
    require(run_directory.name.endswith(f"__{contract_hash[:12]}"),
            "Run-directory hash suffix does not match the persisted contract hash.")

    inventory_files = sequence(inventory.get("files"), "hash_inventory.files")
    require(inventory_files, "hash_inventory.files must not be empty.")
    for index, item_value in enumerate(inventory_files):
        item = mapping(item_value, f"hash_inventory.files[{index}]")
        expected = item.get("expected_sha256")
        observed = item.get("observed_sha256")
        require(
            isinstance(expected, str)
            and HEX_SHA256.fullmatch(expected) is not None
            and isinstance(observed, str)
            and HEX_SHA256.fullmatch(observed) is not None
            and expected == observed,
            f"Hash inventory mismatch for {item.get('id', index)!r}.",
        )
        if manifest_schema == SLOT_EXECUTION_MANIFEST_SCHEMA:
            inventory_path = item.get("path")
            require(
                isinstance(inventory_path, str)
                and inventory_path
                and not Path(inventory_path).is_absolute()
                and ".." not in PurePosixPath(inventory_path).parts,
                f"Per-slot inventory path must be workspace-relative for {item.get('id', index)!r}.",
            )

    _validate_notebook_record_shape(final_record, expected_trace_step_hz)
    if manifest_schema == SLOT_EXECUTION_MANIFEST_SCHEMA:
        current_qubit_physics = mapping(
            mapping(
                mapping(final_record["diagnostics"]["floating_qubit"], "current floating-qubit diagnostics").get("electrostatic_reduction"),
                "current floating-qubit reduction",
            ).get("physics_diagnostics"),
            "current floating-qubit physics",
        )
        require(
            current_qubit_physics.get("human_target_f01_hz") == expected_f01_hz,
            "Current candidate diagnostics do not use the canonical qubit f01 target.",
        )

    history = sequence(optimization.get("history"), "optimization_result.history")
    selected_id = layout.get("candidate_record_id")
    require(isinstance(selected_id, str) and selected_id, "Layout candidate_record_id must be non-empty.")
    selected_matches = [mapping(record, "optimization history record") for record in history
                        if isinstance(record, dict) and record.get("record_id") == selected_id]
    require(len(selected_matches) == 1, "Layout candidate must identify exactly one optimization record.")
    selected = selected_matches[0]
    selected_candidate = mapping(selected.get("candidate"), "selected_record.candidate")
    selected_breakdown = mapping(selected.get("breakdown"), "selected_record.breakdown")
    selected_evaluation = mapping(selected.get("evaluation"), "selected_record.evaluation")
    selected_metrics = mapping(selected_evaluation.get("metrics"), "selected_record.evaluation.metrics")
    final_metrics = mapping(final_record.get("metrics"), "final_diagnostics.record.metrics")
    diagnostics = mapping(final_record.get("diagnostics"), "final_diagnostics.record.diagnostics")
    design = mapping(diagnostics.get("design"), "final_diagnostics.record.diagnostics.design")

    layout_variables = sequence(layout.get("variables"), "layout_specs.variables")
    layout_candidate: dict[str, Any] = {}
    for index, variable_value in enumerate(layout_variables):
        variable = mapping(variable_value, f"layout_specs.variables[{index}]")
        variable_id = variable.get("id")
        require(isinstance(variable_id, str) and variable_id not in layout_candidate,
                "Layout variable ids must be unique non-empty strings.")
        layout_candidate[variable_id] = variable.get("value")
    require(layout_candidate == selected_candidate,
            "Layout variables must exactly match the selected optimization candidate.")
    require(all(design.get(name) == value for name, value in selected_candidate.items()),
            "Captured final design must exactly match the selected optimization candidate.")
    require(layout.get("breakdown") == selected_breakdown,
            "Layout breakdown must exactly match the selected optimization record.")
    require(layout.get("cost") == selected.get("cost") == selected_breakdown.get("total"),
            "Layout, selected record, and breakdown total costs must match exactly.")
    require(all(final_metrics.get(name) == value for name, value in selected_metrics.items()),
            "Captured final metrics must exactly reproduce the selected optimization metrics.")
    for metric_value in sequence(selected_breakdown.get("metrics"), "selected_record.breakdown.metrics"):
        metric = mapping(metric_value, "selected_record breakdown metric")
        name = metric.get("name")
        require(isinstance(name, str) and final_metrics.get(name) == metric.get("observed"),
                f"Captured metric {name!r} does not match its selected-record observation.")

    traces = mapping(final_record.get("traces"), "final_diagnostics.record.traces")
    intrinsic_narrow = mapping(traces.get("intrinsic"), "traces.intrinsic")
    narrow_frequency = numeric_array(intrinsic_narrow, "frequencies_hz", "traces.intrinsic")
    narrow_z21 = complex_array(intrinsic_narrow, "z21_ptc", "traces.intrinsic")
    require_same_length("Narrow intrinsic PTC", narrow_frequency, narrow_z21)
    require_increasing(narrow_frequency, "Narrow intrinsic PTC frequency grid")
    if "intrinsic_wide" in traces:
        intrinsic = mapping(traces.get("intrinsic_wide"), "traces.intrinsic_wide")
        range_provenance = mapping(
            intrinsic.get("range_provenance"),
            "traces.intrinsic_wide.range_provenance",
        )
        require(
            range_provenance.get("contract_id") == "d3-intrinsic-wide-final-capture-v1"
            and range_provenance.get("scope") == "final_capture_only",
            "Wide intrinsic trace must declare its final-capture range contract.",
        )
        intrinsic_frequency = numeric_array(
            intrinsic, "frequencies_hz", "traces.intrinsic_wide"
        )
        intrinsic_z21 = complex_array(intrinsic, "z21_ptc", "traces.intrinsic_wide")
        require_same_length("Wide intrinsic PTC", intrinsic_frequency, intrinsic_z21)
        require_increasing(intrinsic_frequency, "Wide intrinsic PTC frequency grid")
        wide_margin = finite_number(
            range_provenance.get("start_margin_below_notch_hz"), "wide start margin"
        )
        wide_notch_target = finite_number(
            range_provenance.get("notch_target_hz"), "wide notch target"
        )
        wide_filter_loaded_bare = finite_number(
            range_provenance.get("filter_loaded_bare_hz"), "wide filter loaded-bare"
        )
        wide_required_stop = finite_number(
            range_provenance.get("required_minimum_stop_hz"), "wide required stop"
        )
        wide_declared_stop_ghz = finite_number(
            range_provenance.get("declared_design_scan_stop_ghz"), "wide declared stop"
        )
        require(
            intrinsic_frequency[0] == finite_number(range_provenance.get("start_hz"), "wide start")
            and intrinsic_frequency[-1] == finite_number(range_provenance.get("stop_hz"), "wide stop"),
            "Wide intrinsic grid endpoints must exactly match their range provenance.",
        )
        require(
            wide_margin == 500.0e6
            and intrinsic_frequency[0] == wide_notch_target - wide_margin
            and wide_required_stop == wide_filter_loaded_bare + wide_margin
            and intrinsic_frequency[-1] == wide_declared_stop_ghz * 1.0e9
            and intrinsic_frequency[-1] >= wide_required_stop,
            "Wide intrinsic range provenance does not satisfy the 500 MHz coverage contract.",
        )
        intrinsic_range_label = "Wide final-capture scan"
        intrinsic_limited_range = False
    else:
        intrinsic_frequency = narrow_frequency
        intrinsic_z21 = narrow_z21
        intrinsic_range_label = "Legacy narrow notch-window scan"
        intrinsic_limited_range = True

    filter_trace = mapping(traces.get("filter"), "traces.filter")
    filter_frequency = numeric_array(filter_trace, "frequencies_hz", "traces.filter")
    filter_s21 = complex_array(filter_trace, "s21", "traces.filter")
    filter_reference = complex_array(filter_trace, "reference_s21", "traces.filter")
    require_same_length("Filter S21", filter_frequency, filter_s21, filter_reference)
    require_increasing(filter_frequency, "Filter frequency grid")
    require(np.all(np.abs(filter_reference) > 0), "Filter reference S21 must be nonzero.")

    pair_trace = mapping(traces.get("pair"), "traces.pair")
    pair_frequency = numeric_array(pair_trace, "frequencies_hz", "traces.pair")
    pair_s21 = complex_array(pair_trace, "s21", "traces.pair")
    pair_reference = complex_array(pair_trace, "reference_s21", "traces.pair")
    require_same_length("Paired raw S21", pair_frequency, pair_s21, pair_reference)
    require_increasing(pair_frequency, "Paired frequency grid")
    require(np.all(np.abs(pair_reference) > 0), "Paired reference S21 must be nonzero.")
    pair_fit_frequency = numeric_array(pair_trace, "fit_frequencies_hz", "traces.pair")
    pair_measured_fit = complex_array(pair_trace, "fit_normalized_s21", "traces.pair")
    pair_fitted = complex_array(pair_trace, "fitted_s21", "traces.pair")
    require_same_length("Paired fitted S21", pair_fit_frequency, pair_measured_fit, pair_fitted)
    require_increasing(pair_fit_frequency, "Paired fit frequency grid")

    frequency_fit = mapping(diagnostics.get("readout_zero_probe_frequency_fit"),
                            "diagnostics.readout_zero_probe_frequency_fit")
    linewidth_fit = mapping(diagnostics.get("readout_zero_probe_linewidth_fit"),
                            "diagnostics.readout_zero_probe_linewidth_fit")
    frequency_x = numeric_array(frequency_fit, "x_values", "frequency fit")
    frequency_y = numeric_array(frequency_fit, "y_values", "frequency fit")
    frequency_fitted = numeric_array(frequency_fit, "fitted_y_values", "frequency fit")
    linewidth_x = numeric_array(linewidth_fit, "x_values", "linewidth fit")
    linewidth_y = numeric_array(linewidth_fit, "y_values", "linewidth fit")
    linewidth_fitted = numeric_array(linewidth_fit, "fitted_y_values", "linewidth fit")
    require_same_length("Readout frequency fit", frequency_x, frequency_y, frequency_fitted)
    require_same_length("Readout linewidth fit", linewidth_x, linewidth_y, linewidth_fitted)
    require(np.array_equal(frequency_x, linewidth_x), "Frequency and linewidth fits must use identical probes.")

    readout_probes = sequence(traces.get("readout_probes"), "traces.readout_probes")
    require(len(readout_probes) == len(frequency_x), "Readout trace count must match finite-probe fit points.")
    probe_capacitances: list[float] = []
    for index, probe_value in enumerate(readout_probes):
        probe = mapping(probe_value, f"traces.readout_probes[{index}]")
        probe_capacitances.append(finite_number(probe.get("capacitance_fF"), f"probe {index} capacitance"))
        probe_frequency = numeric_array(probe, "frequencies_hz", f"readout probe {index}")
        probe_s21 = complex_array(probe, "s21", f"readout probe {index}")
        probe_reference = complex_array(probe, "reference_s21", f"readout probe {index}")
        require_same_length(f"Readout probe {index}", probe_frequency, probe_s21, probe_reference)
        require(np.all(np.abs(probe_reference) > 0), f"Readout probe {index} reference S21 must be nonzero.")
    require(np.array_equal(np.asarray(probe_capacitances), frequency_x),
            "Captured readout trace capacitances must match fit x-values exactly.")

    frequency_coefficients = mapping(frequency_fit.get("coefficients"), "frequency fit coefficients")
    frequency_intercept = finite_number(frequency_fit.get("intercept"), "frequency fit intercept")
    require(frequency_coefficients.get("intercept") == frequency_fit.get("intercept"),
            "Stored frequency intercept fields must agree exactly.")
    frequency_linear = finite_number(frequency_coefficients.get("linear_per_fF"), "frequency linear coefficient")
    frequency_quadratic = finite_number(frequency_coefficients.get("quadratic_per_fF2"), "frequency quadratic coefficient")
    require(np.allclose(
        frequency_intercept + frequency_linear * frequency_x + frequency_quadratic * frequency_x**2,
        frequency_fitted,
        rtol=1e-14,
        atol=1e-6,
    ), "Stored frequency fitted values disagree with the stored polynomial coefficients.")

    linewidth_coefficients = mapping(linewidth_fit.get("coefficients"), "linewidth fit coefficients")
    linewidth_intercept = finite_number(linewidth_fit.get("intercept"), "linewidth fit intercept")
    require(linewidth_intercept == 0.0, "Readout linewidth fit must have an exact zero intercept.")
    linewidth_quadratic = finite_number(linewidth_coefficients.get("quadratic_per_fF2"), "linewidth C^2 coefficient")
    linewidth_quartic = finite_number(linewidth_coefficients.get("quartic_per_fF4"), "linewidth C^4 coefficient")
    require(np.allclose(
        linewidth_quadratic * linewidth_x**2 + linewidth_quartic * linewidth_x**4,
        linewidth_fitted,
        rtol=1e-14,
        atol=1e-6,
    ), "Stored linewidth fitted values disagree with the stored C²+C⁴ coefficients.")

    return {
        "status": status,
        "layout": layout,
        "contract_hash": contract_hash,
        "artifact_hash": contract_hash,
        "artifact_hash_label": identity_label,
        "manifest_schema": manifest_schema,
        "metrics": final_metrics,
        "diagnostics": diagnostics,
        "intrinsic_frequency": intrinsic_frequency,
        "intrinsic_z21": intrinsic_z21,
        "intrinsic_range_label": intrinsic_range_label,
        "intrinsic_limited_range": intrinsic_limited_range,
        "filter_frequency": filter_frequency,
        "filter_normalized": filter_s21 / filter_reference,
        "pair_fit_frequency": pair_fit_frequency,
        "pair_measured_fit": pair_measured_fit,
        "pair_fitted": pair_fitted,
        "frequency_x": frequency_x,
        "frequency_y": frequency_y,
        "frequency_intercept": frequency_intercept,
        "frequency_linear": frequency_linear,
        "frequency_quadratic": frequency_quadratic,
        "linewidth_x": linewidth_x,
        "linewidth_y": linewidth_y,
        "linewidth_quadratic": linewidth_quadratic,
        "linewidth_quartic": linewidth_quartic,
    }


def db20(values: np.ndarray) -> np.ndarray:
    return 20.0 * np.log10(np.maximum(np.abs(values), np.finfo(float).tiny))


def add_vertical_reference(
    axis: plt.Axes,
    frequency_hz: float,
    label: str,
    *,
    color: str,
    linestyle: str,
) -> None:
    axis.axvline(frequency_hz / 1e9, color=color, linestyle=linestyle, linewidth=1.25, label=label)


def style_axis(axis: plt.Axes) -> None:
    axis.set_facecolor("#fbfcfd")
    axis.grid(True, color="#e3e6e9", linewidth=0.7, alpha=0.85)
    axis.spines[["top", "right"]].set_visible(False)
    axis.tick_params(colors=INK, labelsize=8)
    axis.title.set_color(INK)
    axis.xaxis.label.set_color(INK)
    axis.yaxis.label.set_color(INK)


def render_figure(data: dict[str, Any], run_directory: Path, output_png: Path) -> None:
    layout = data["layout"]
    metrics = data["metrics"]
    diagnostics = data["diagnostics"]

    notch_metric = metric_by_name(layout["breakdown"], "notch_hz")
    filter_metric = metric_by_name(layout["breakdown"], "filter_loaded_bare_hz")
    readout_metric = metric_by_name(layout["breakdown"], "readout_loaded_bare_hz")

    figure, axes = plt.subplots(3, 2, figsize=(16, 15), constrained_layout=False)
    figure.patch.set_facecolor("white")
    for axis in axes.flat:
        style_axis(axis)

    axis = axes[0, 0]
    intrinsic_abs_imag = np.abs(data["intrinsic_z21"].imag)
    require(np.any(intrinsic_abs_imag > 0), "Intrinsic PTC trace must contain a nonzero imaginary value.")
    axis.plot(
        data["intrinsic_frequency"] / 1e9,
        np.where(intrinsic_abs_imag > 0, intrinsic_abs_imag, np.nan),
        color=BLUE,
        linewidth=1.5,
        label=data["intrinsic_range_label"],
    )
    axis.set_yscale("log")
    add_vertical_reference(axis, finite_number(notch_metric["target"], "notch target"),
                           "Target notch", color=GREY, linestyle="--")
    add_vertical_reference(axis, finite_number(notch_metric["observed"], "notch observed"),
                           "Found notch", color=ORANGE, linestyle=":")
    axis.set(title="Intrinsic compensated transfer magnitude", xlabel="Frequency (GHz)", ylabel="|Im(Z21 PTC)| (Ω)")
    if data["intrinsic_limited_range"]:
        axis.text(
            0.02,
            0.04,
            "LEGACY LIMITED RANGE — narrow notch window only",
            transform=axis.transAxes,
            color="#8a3f22",
            fontsize=8,
            weight="bold",
            bbox={"facecolor": "white", "edgecolor": "#c9a48f", "alpha": 0.9},
        )
    axis.legend(loc="best", fontsize=8, frameon=False)

    axis = axes[0, 1]
    axis.plot(data["filter_frequency"] / 1e9, db20(data["filter_normalized"]),
              color=BLUE, linewidth=1.5, label="Filter / empty-feedline reference")
    add_vertical_reference(axis, finite_number(filter_metric["target"], "filter target"),
                           "Target loaded-bare filter", color=GREY, linestyle="--")
    add_vertical_reference(axis, finite_number(filter_metric["observed"], "filter observed"),
                           "Found loaded-bare filter", color=ORANGE, linestyle=":")
    axis.set(title="Normalized filter-only transmission", xlabel="Frequency (GHz)", ylabel="20 log10 |S21 / reference| (dB)")
    axis.legend(loc="best", fontsize=8, frameon=False)

    axis = axes[1, 0]
    fit_frequency_ghz = data["pair_fit_frequency"] / 1e9
    axis.plot(fit_frequency_ghz, db20(data["pair_measured_fit"]), color=BLUE, linewidth=1.5,
              label="Simulated normalized |S21|")
    axis.plot(fit_frequency_ghz, db20(data["pair_fitted"]), color=ORANGE, linewidth=1.3,
              linestyle="--", label="Complex-S21 fit")
    add_vertical_reference(axis, finite_number(metrics["readout_loaded_bare_hz"], "readout loaded-bare"),
                           "Readout loaded-bare", color=GREY, linestyle="--")
    add_vertical_reference(axis, finite_number(metrics["filter_loaded_bare_hz"], "filter loaded-bare"),
                           "Filter loaded-bare", color=GREY, linestyle=":")
    model_poles = sequence(mapping(diagnostics["j_fit"], "diagnostics.j_fit").get("derived_poles"), "J-fit poles")
    for index, pole_value in enumerate(model_poles):
        pole = mapping(pole_value, f"J-fit pole {index}")
        add_vertical_reference(axis, finite_number(pole.get("frequency_hz"), f"model pole {index}"),
                               "Model poles" if index == 0 else "_nolegend_", color=GOLD, linestyle="-.")
    vector_poles = sequence(diagnostics.get("vector_crosscheck_poles_hz"), "vector cross-check poles")
    for index, pole in enumerate(vector_poles):
        add_vertical_reference(axis, finite_number(pole, f"vector pole {index}"),
                               "Vector poles" if index == 0 else "_nolegend_", color=INK, linestyle=(0, (2, 2)))
    axis.set(title="Paired normalized transmission magnitude", xlabel="Frequency (GHz)", ylabel="|S21| (dB)")
    axis.legend(loc="best", fontsize=7.5, frameon=False, ncols=2)

    axis = axes[1, 1]
    measured_phase = np.unwrap(np.angle(data["pair_measured_fit"])) * 180.0 / np.pi
    relative_phase = np.unwrap(
        np.angle(data["pair_fitted"] * np.conjugate(data["pair_measured_fit"]))
    ) * 180.0 / np.pi
    relative_phase -= 360.0 * round(float(np.median(relative_phase)) / 360.0)
    fitted_phase = measured_phase + relative_phase
    axis.plot(fit_frequency_ghz, measured_phase, color=BLUE, linewidth=1.5, label="Simulated normalized phase")
    axis.plot(fit_frequency_ghz, fitted_phase, color=ORANGE, linewidth=1.3, linestyle="--", label="Fitted phase")
    axis.set(title="Paired normalized transmission phase", xlabel="Frequency (GHz)", ylabel="Unwrapped phase (deg)")
    axis.legend(loc="best", fontsize=8, frameon=False)

    fit_x = np.linspace(0.0, float(np.max(data["frequency_x"])) * 1.05, 400)
    frequency_curve = (
        data["frequency_intercept"]
        + data["frequency_linear"] * fit_x
        + data["frequency_quadratic"] * fit_x**2
    )
    axis = axes[2, 0]
    axis.scatter(data["frequency_x"], data["frequency_y"] / 1e9, color=BLUE, s=36,
                 zorder=3, label="Finite-probe poles")
    axis.plot(fit_x, frequency_curve / 1e9, color=ORANGE, linewidth=1.5, label="Stored quadratic fit")
    axis.scatter([0.0], [data["frequency_intercept"] / 1e9], facecolors="white", edgecolors=ORANGE,
                 linewidths=1.5, s=55, zorder=4, label="C → 0 intercept")
    axis.axhline(finite_number(readout_metric["target"], "readout target") / 1e9,
                 color=GREY, linestyle="--", linewidth=1.25, label="Target loaded-bare readout")
    axis.set(title="Readout loaded-bare frequency extrapolation", xlabel="Probe capacitance (fF)", ylabel="Frequency (GHz)")
    axis.legend(loc="best", fontsize=8, frameon=False)

    linewidth_curve = data["linewidth_quadratic"] * fit_x**2 + data["linewidth_quartic"] * fit_x**4
    axis = axes[2, 1]
    axis.scatter(data["linewidth_x"], data["linewidth_y"] / 1e6, color=BLUE, s=36,
                 zorder=3, label="Finite-probe linewidths")
    axis.plot(fit_x, linewidth_curve / 1e6, color=ORANGE, linewidth=1.5, label="Stored C²+C⁴ fit")
    axis.scatter([0.0], [0.0], facecolors="white", edgecolors=ORANGE, linewidths=1.5, s=55,
                 zorder=4, label="Constrained zero intercept")
    axis.axhline(0.0, color=INK, linewidth=0.9, alpha=0.8)
    axis.set(title="Readout linewidth extrapolation", xlabel="Probe capacitance (fF)", ylabel="Linewidth (MHz)")
    axis.legend(loc="best", fontsize=8, frameon=False)

    run_id = run_directory.name
    cost = finite_number(layout["cost"], "layout cost")
    kappa_mhz = finite_number(metrics["filter_loaded_linewidth_hz"], "filter linewidth") / 1e6
    j_mhz = finite_number(metrics["j_hz"], "J") / 1e6
    figure.suptitle(
        f"D3 historical optimizer-time reproduction — {run_id}\n"
        f"contract {data['contract_hash'][:12]}  |  cost {cost:.6g}  |  κfilter {kappa_mhz:.6f} MHz  |  J {j_mhz:.6f} MHz",
        fontsize=13,
        color=INK,
        y=0.985,
    )
    status = data["status"]
    figure.text(
        0.5,
        0.012,
        "UNAPPROVED EXPLORATION  •  JSON-only static review  •  "
        f"CMA {status.get('cma_state')}  •  Nelder–Mead {status.get('nelder_mead_state')}  •  "
        f"promotion {status.get('promotion_state')}",
        ha="center",
        va="bottom",
        fontsize=9,
        color="#8a3f22",
        weight="bold",
    )
    figure.subplots_adjust(left=0.075, right=0.975, bottom=0.06, top=0.925, hspace=0.34, wspace=0.23)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_png, dpi=300, facecolor="white", metadata={
        "Title": "D3 historical optimizer-time reproduction — UNAPPROVED EXPLORATION",
        "Description": f"Run {run_id}; contract {data['contract_hash']}",
    })
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and plot one historical D3 optimizer-time reproduction without rerunning scientific code."
    )
    parser.add_argument("run_directory", type=Path, help="Exact-eight-file D3 run directory.")
    parser.add_argument("output_png", type=Path, help="PNG path outside the run directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_directory = args.run_directory.expanduser().resolve(strict=True)
        require(run_directory.is_dir(), "run_directory must be a directory.")
        output_png = args.output_png.expanduser().resolve(strict=False)
        require(output_png.suffix.lower() == ".png", "output_png must have a .png suffix.")
        require(output_png != run_directory and run_directory not in output_png.parents,
                "output_png must resolve outside run_directory to preserve its exact-eight-file contract.")
        data = validate_artifacts(run_directory)
        render_figure(data, run_directory, output_png)
    except (ArtifactContractError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(output_png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
