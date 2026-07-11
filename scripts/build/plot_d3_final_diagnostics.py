#!/usr/bin/env python3
"""Render the captured D3 final record as a static Human-review surface.

This file owns JSON-artifact validation and plotting only. It never evaluates a
candidate or reruns simulation/optimization. Canonical semantics live in:

- D3 target: https://github.com/arfiligol/SCQ_Design/blob/main/docs/design-targets/d3-intrinsic-interferometric-purcell-filter.qmd
- Loaded-bare references: https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/loaded-bare-readout-filter-references.qmd
- Readout-filter J fit: https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd
- PTC observable: https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
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
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
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


def load_json(run_directory: Path, filename: str) -> dict[str, Any]:
    path = run_directory / filename

    def reject_constant(value: str) -> None:
        raise ArtifactContractError(f"{filename} contains non-finite JSON constant {value!r}.")

    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle, parse_constant=reject_constant)
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


def validate_artifacts(run_directory: Path) -> dict[str, Any]:
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

    require(status.get("state") == "completed", "status.json state must be 'completed'.")
    require(final.get("state") == "captured", "final diagnostics state must be 'captured'.")
    final_record = mapping(final.get("record"), "final_diagnostics.record")
    require(final_record.get("status") == "valid", "Captured final diagnostics record must be valid.")
    require(layout.get("state") == "best_valid_candidate", "Layout state must be 'best_valid_candidate'.")
    require(
        status.get("artifact_approval") == layout.get("artifact_approval") == "unapproved_exploration",
        "Status and layout must both identify unapproved exploration evidence.",
    )

    hashes = {
        "status": status.get("contract_sha256"),
        "condition manifest": manifest.get("contract_sha256"),
        "hash inventory": inventory.get("contract_sha256"),
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
        require(item.get("expected_sha256") == item.get("observed_sha256"),
                f"Hash inventory mismatch for {item.get('id', index)!r}.")

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
    intrinsic = mapping(traces.get("intrinsic"), "traces.intrinsic")
    intrinsic_frequency = numeric_array(intrinsic, "frequencies_hz", "traces.intrinsic")
    intrinsic_z21 = complex_array(intrinsic, "z21_ptc", "traces.intrinsic")
    require_same_length("Intrinsic PTC", intrinsic_frequency, intrinsic_z21)
    require_increasing(intrinsic_frequency, "Intrinsic PTC frequency grid")

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
        "metrics": final_metrics,
        "diagnostics": diagnostics,
        "intrinsic_frequency": intrinsic_frequency,
        "intrinsic_z21": intrinsic_z21,
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
    axis.plot(data["intrinsic_frequency"] / 1e9, data["intrinsic_z21"].imag,
              color=BLUE, linewidth=1.5, label="Im(Z21 PTC)")
    axis.axhline(0.0, color=INK, linewidth=0.9, alpha=0.8)
    add_vertical_reference(axis, finite_number(notch_metric["target"], "notch target"),
                           "Target notch", color=GREY, linestyle="--")
    add_vertical_reference(axis, finite_number(notch_metric["observed"], "notch observed"),
                           "Found notch", color=ORANGE, linestyle=":")
    axis.set(title="Intrinsic compensated transfer response", xlabel="Frequency (GHz)", ylabel="Im(Z21 PTC) (Ω)")
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
              label="Measured normalized |S21|")
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
    axis.plot(fit_frequency_ghz, measured_phase, color=BLUE, linewidth=1.5, label="Measured normalized phase")
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
        f"D3 final diagnostic review — {run_id}\n"
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
        "Title": "D3 final diagnostic review — UNAPPROVED EXPLORATION",
        "Description": f"Run {run_id}; contract {data['contract_hash']}",
    })
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and plot one captured D3 optimizer run without rerunning scientific code."
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
