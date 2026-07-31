#!/usr/bin/env python3
"""Fit the D3 Q3D three-branch IDC gap/length sweep for Stage 2 and Stage 3."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

import numpy as np

from prepare_d3_retained_qubit_gap_sweep import (
    _CELL_PATTERN,
    _column_label,
    _column_number,
    _worksheet_cells,
)

SCHEMA_VERSION = "d3-three-branch-idc-gap-length-mapping.v1"
MAPPING_ID = "d3-same-die-filter-feedline-idc-q3d-tensor-fit-v1"
EXPECTED_GAPS_UM = (5.0, 6.0, 7.0, 8.0, 9.0, 10.0)
EXPECTED_LENGTHS_UM = (35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0)
NOMINAL_GAP_UM = 8.0
LENGTH_CENTER_UM = 55.0
LENGTH_HALF_RANGE_UM = 20.0
COEFFICIENT_NAMES = ("C_12_fF", "C_1G_fF", "C_2G_fF")
_GAP_PATTERN = re.compile(r"^h\s*=\s*(\d+(?:\.\d+)?)\(um\)$")
_EXPECTED_HEADERS = ("L(um)", "C_12(fF)", "C_1G(fF)", "C_2G(fF)")


def read_idc_xlsx(path: Path) -> list[dict[str, float]]:
    """Read every labeled gap/length/three-capacitance record."""

    with zipfile.ZipFile(path) as archive:
        cells = _worksheet_cells(archive)
    samples: list[dict[str, float]] = []
    for reference, raw_value in cells.items():
        if not isinstance(raw_value, str):
            continue
        gap_match = _GAP_PATTERN.fullmatch(raw_value.strip())
        if gap_match is None:
            continue
        cell_match = _CELL_PATTERN.fullmatch(reference)
        if cell_match is None:
            raise ValueError(f"Invalid XLSX cell reference: {reference}")
        base_column = _column_number(cell_match.group(1))
        base_row = int(cell_match.group(2))
        headers = tuple(
            cells.get(f"{_column_label(base_column + offset)}{base_row + 1}")
            for offset in range(4)
        )
        if headers != _EXPECTED_HEADERS:
            raise ValueError(
                f"IDC table at {reference} must use headers {_EXPECTED_HEADERS}."
            )
        gap_um = float(gap_match.group(1))
        for row_offset in range(2, 2 + len(EXPECTED_LENGTHS_UM)):
            values = [
                float(
                    cells[
                        f"{_column_label(base_column + column_offset)}"
                        f"{base_row + row_offset}"
                    ]
                )
                for column_offset in range(4)
            ]
            samples.append(
                {
                    "gap_um": gap_um,
                    "length_um": values[0],
                    "C_12_fF": values[1],
                    "C_1G_fF": values[2],
                    "C_2G_fF": values[3],
                }
            )
    observed_gaps = tuple(sorted({sample["gap_um"] for sample in samples}))
    if observed_gaps != EXPECTED_GAPS_UM:
        raise ValueError(f"IDC workbook must contain gaps {EXPECTED_GAPS_UM}.")
    for gap_um in EXPECTED_GAPS_UM:
        observed_lengths = tuple(
            sorted(
                sample["length_um"]
                for sample in samples
                if sample["gap_um"] == gap_um
            )
        )
        if observed_lengths != EXPECTED_LENGTHS_UM:
            raise ValueError(
                f"IDC gap {gap_um} um must contain lengths {EXPECTED_LENGTHS_UM}."
            )
    samples.sort(key=lambda sample: (sample["gap_um"], sample["length_um"]))
    return samples


def _basis(gap_um: np.ndarray, length_um: np.ndarray) -> np.ndarray:
    x = (length_um - LENGTH_CENTER_UM) / LENGTH_HALF_RANGE_UM
    inverse_gap = 1.0 / gap_um
    return np.column_stack(
        (
            np.ones_like(gap_um),
            inverse_gap,
            inverse_gap**2,
            x,
            x * inverse_gap,
            x * inverse_gap**2,
            x**2,
            x**2 * inverse_gap,
            x**2 * inverse_gap**2,
        )
    )


def _fit(samples: list[dict[str, float]]) -> dict[str, object]:
    gaps = np.asarray([sample["gap_um"] for sample in samples], dtype=float)
    lengths = np.asarray([sample["length_um"] for sample in samples], dtype=float)
    design = _basis(gaps, lengths)
    if np.linalg.matrix_rank(design) != 9:
        raise ValueError("IDC tensor-product fit is rank deficient.")
    coefficient_fits: dict[str, object] = {}
    fitted_coefficients: dict[str, np.ndarray] = {}
    for name in COEFFICIENT_NAMES:
        values = np.asarray([sample[name] for sample in samples], dtype=float)
        coefficients, _, rank, _ = np.linalg.lstsq(design, values, rcond=None)
        if rank != 9:
            raise ValueError(f"IDC tensor-product fit is rank deficient for {name}.")
        residual = design @ coefficients - values
        fitted_coefficients[name] = coefficients
        coefficient_fits[name] = {
            "coefficients_fF": coefficients.tolist(),
            "rms_residual_fF": float(np.sqrt(np.mean(residual**2))),
            "max_abs_residual_fF": float(np.max(np.abs(residual))),
            "max_abs_relative_residual": float(
                np.max(np.abs(residual) / values)
            ),
        }

    validation_gaps = np.linspace(5.0, 10.0, 51)
    validation_lengths = np.linspace(35.0, 75.0, 81)
    grid_gap, grid_length = np.meshgrid(
        validation_gaps, validation_lengths, indexing="ij"
    )
    validation_design = _basis(grid_gap.ravel(), grid_length.ravel())
    minimum_fF = min(
        float(np.min(validation_design @ coefficients))
        for coefficients in fitted_coefficients.values()
    )
    if minimum_fF <= 0.0:
        raise ValueError("IDC fit is not positive over the declared validation grid.")
    return {
        "model": (
            "tensor_product_quadratic_in_normalized_length_and_"
            "quadratic_in_inverse_gap"
        ),
        "basis": [
            "1",
            "1/h_um",
            "1/h_um^2",
            "x",
            "x/h_um",
            "x/h_um^2",
            "x^2",
            "x^2/h_um",
            "x^2/h_um^2",
        ],
        "normalized_length": {
            "definition": "x=(length_um-center_um)/half_range_um",
            "center_um": LENGTH_CENTER_UM,
            "half_range_um": LENGTH_HALF_RANGE_UM,
        },
        "least_squares_rank": 9,
        "design_matrix_condition_number": float(np.linalg.cond(design)),
        "coefficient_fits": coefficient_fits,
        "validation": {
            "gap_grid_start_um": 5.0,
            "gap_grid_stop_um": 10.0,
            "gap_grid_step_um": 0.1,
            "length_grid_start_um": 35.0,
            "length_grid_stop_um": 75.0,
            "length_grid_step_um": 0.5,
            "grid_point_count": int(validation_design.shape[0]),
            "all_coefficients_positive": True,
            "minimum_coefficient_fF": minimum_fF,
        },
    }


def build_artifact(input_path: Path) -> dict[str, object]:
    samples = read_idc_xlsx(input_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "mapping_id": MAPPING_ID,
        "capacitance_unit": "fF",
        "gap_unit": "um",
        "length_unit": "um",
        "nominal_gap_um": NOMINAL_GAP_UM,
        "valid_gap_range_um": [EXPECTED_GAPS_UM[0], EXPECTED_GAPS_UM[-1]],
        "valid_length_range_um": [
            EXPECTED_LENGTHS_UM[0],
            EXPECTED_LENGTHS_UM[-1],
        ],
        "terminal_mapping": {
            "authority": "human",
            "terminal_1": "f_c",
            "terminal_2": "p",
        },
        "coefficient_mapping": {
            "C_12_fF": "C_pf_c_IDC",
            "C_1G_fF": "C_f_cG_IDC",
            "C_2G_fF": "C_pG_IDC",
        },
        "evaluation_policy": (
            "exact_tabulated_point_uses_raw_q3d_sample__"
            "other_in_domain_points_use_persisted_tensor_fit"
        ),
        "source_artifact": {
            "kind": "q3d_three_branch_idc_gap_length_sweep_xlsx",
            "filename": input_path.name,
            "sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        },
        "samples": samples,
        "fit": _fit(samples),
    }


def write_artifact(input_path: Path, output_path: Path) -> Path:
    output = output_path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = (
        json.dumps(build_artifact(input_path.resolve()), indent=2, sort_keys=True)
        + "\n"
    )
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent, prefix=f".{output.name}.", suffix=".tmp", text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, output)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    print(write_artifact(arguments.input, arguments.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
