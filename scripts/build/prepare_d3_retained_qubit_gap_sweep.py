#!/usr/bin/env python3
"""Convert the opposite-face-qubit Q3D XLSX sweep into the D3 retained input.

The raw workbook contains an explicitly named ``GND`` conductor plus an
unlisted outer/reference boundary.  D3 Same-Die v1 intentionally instantiates
only pairwise branches to the named ``GND`` conductor.  Signed full-row sums
are therefore evidence, not extra shunt capacitances.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import cast
from xml.etree import ElementTree

import numpy as np

SCHEMA_VERSION = "d3-retained-qubit-readout-named-ground-gap-sweep.v2"
NODE_ORDER = ("GND", "Q1_L", "Q1_R", "Q1_read")
BRANCH_NAMES = ("C01_fF", "C02_fF", "C12_fF", "Cr1_fF", "Cr2_fF", "C0r_fF")
EXPECTED_GAPS_UM = (5.0, 6.0, 7.0, 8.0, 9.0, 10.0)
NOMINAL_GAP_UM = 8.0
L_J_PER_JUNCTION_NH = 21.5
_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_GAP_PATTERN = re.compile(r"^h\s*=\s*(\d+(?:\.\d+)?)\s*um$")
_CELL_PATTERN = re.compile(r"^([A-Z]+)(\d+)$")


def _column_number(label: str) -> int:
    value = 0
    for character in label:
        value = 26 * value + ord(character) - ord("A") + 1
    return value


def _column_label(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in item.iter(f"{{{_MAIN_NS}}}t"))
        for item in root.findall(f"{{{_MAIN_NS}}}si")
    ]


def _worksheet_cells(archive: zipfile.ZipFile) -> dict[str, str | float]:
    shared = _shared_strings(archive)
    root = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    cells: dict[str, str | float] = {}
    for cell in root.iter(f"{{{_MAIN_NS}}}c"):
        reference = cell.attrib["r"]
        value_node = cell.find(f"{{{_MAIN_NS}}}v")
        if value_node is None or value_node.text is None:
            continue
        if cell.attrib.get("t") == "s":
            cells[reference] = shared[int(value_node.text)]
        else:
            cells[reference] = float(value_node.text)
    return cells


def read_q3d_xlsx(path: Path) -> dict[float, np.ndarray]:
    """Read the six labeled 4-by-4 Maxwell blocks without an XLSX dependency."""

    with zipfile.ZipFile(path) as archive:
        cells = _worksheet_cells(archive)
    matrices: dict[float, np.ndarray] = {}
    for reference, raw_value in cells.items():
        if not isinstance(raw_value, str):
            continue
        match = _GAP_PATTERN.fullmatch(raw_value.strip())
        if match is None:
            continue
        cell_match = _CELL_PATTERN.fullmatch(reference)
        if cell_match is None:
            raise ValueError(f"Invalid XLSX cell reference: {reference}")
        base_column = _column_number(cell_match.group(1))
        base_row = int(cell_match.group(2))
        column_labels = [
            cells.get(f"{_column_label(base_column + offset)}{base_row}")
            for offset in range(1, 5)
        ]
        row_labels = [
            cells.get(f"{cell_match.group(1)}{base_row + offset}")
            for offset in range(1, 5)
        ]
        if tuple(column_labels) != NODE_ORDER or tuple(row_labels) != NODE_ORDER:
            raise ValueError(f"Q3D matrix at {reference} must use node order {NODE_ORDER}.")
        matrix = np.asarray(
            [
                [
                    cells[f"{_column_label(base_column + column_offset)}{base_row + row_offset}"]
                    for column_offset in range(1, 5)
                ]
                for row_offset in range(1, 5)
            ],
            dtype=float,
        )
        gap_um = float(match.group(1))
        if gap_um in matrices:
            raise ValueError(f"Duplicate Q3D gap block: {gap_um} um.")
        matrices[gap_um] = matrix
    if tuple(sorted(matrices)) != EXPECTED_GAPS_UM:
        raise ValueError(f"Q3D workbook must contain gaps {EXPECTED_GAPS_UM}.")
    return matrices


def physical_branches_fF(matrix_fF: np.ndarray) -> dict[str, float]:
    """Map explicitly named conductor pairs to six positive branch values."""

    matrix = np.asarray(matrix_fF, dtype=float)
    if matrix.shape != (4, 4) or not np.all(np.isfinite(matrix)):
        raise ValueError("Q3D Maxwell matrix must be finite and 4-by-4.")
    if not np.allclose(matrix, matrix.T, rtol=1.0e-9, atol=1.0e-9):
        raise ValueError("Q3D Maxwell matrix must be symmetric within 1e-9 fF.")
    if np.min(np.linalg.eigvalsh(matrix)) <= 0.0:
        raise ValueError("Q3D Maxwell matrix must be positive definite.")
    branches = {
        "C01_fF": float(-matrix[0, 1]),
        "C02_fF": float(-matrix[0, 2]),
        "C12_fF": float(-matrix[1, 2]),
        "Cr1_fF": float(-matrix[1, 3]),
        "Cr2_fF": float(-matrix[2, 3]),
        "C0r_fF": float(-matrix[0, 3]),
    }
    if not all(np.isfinite(value) and value > 0.0 for value in branches.values()):
        raise ValueError("Retained Q3D physical branch capacitances must be positive.")
    reconstructed = np.asarray(
        [
            [
                branches["C01_fF"] + branches["C12_fF"] + branches["Cr1_fF"],
                -branches["C12_fF"],
                -branches["Cr1_fF"],
            ],
            [
                -branches["C12_fF"],
                branches["C02_fF"] + branches["C12_fF"] + branches["Cr2_fF"],
                -branches["Cr2_fF"],
            ],
            [
                -branches["Cr1_fF"],
                -branches["Cr2_fF"],
                branches["C0r_fF"] + branches["Cr1_fF"] + branches["Cr2_fF"],
            ],
        ]
    )
    outer_reference_residual = np.sum(matrix, axis=1)[1:]
    modeled_retained = matrix[1:, 1:] - np.diag(outer_reference_residual)
    if not np.allclose(
        reconstructed, modeled_retained, rtol=1.0e-12, atol=1.0e-10
    ):
        raise ValueError(
            "Named-GND branches do not reconstruct the retained principal block "
            "after excluding its signed outer-reference row sums."
        )
    return branches


def outer_reference_residual_fF(matrix_fF: np.ndarray) -> dict[str, float]:
    """Return signed full-row sums for report-only retained-node evidence."""

    matrix = np.asarray(matrix_fF, dtype=float)
    if matrix.shape != (4, 4) or not np.all(np.isfinite(matrix)):
        raise ValueError("Q3D Maxwell matrix must be finite and 4-by-4.")
    residual = np.sum(matrix, axis=1)
    return {
        "Q1_L_fF": float(residual[1]),
        "Q1_R_fF": float(residual[2]),
        "Q1_read_fF": float(residual[3]),
    }


def _fit_branches(samples: list[dict[str, object]]) -> dict[str, object]:
    gaps = np.asarray([sample["gap_um"] for sample in samples], dtype=float)
    basis = np.column_stack((np.ones_like(gaps), 1.0 / gaps, 1.0 / gaps**2))
    branch_fits: dict[str, object] = {}
    for branch_name in BRANCH_NAMES:
        values = np.asarray(
            [
                cast(dict[str, float], sample["physical_branches_fF"])[branch_name]
                for sample in samples
            ],
            dtype=float,
        )
        coefficients, _, rank, _ = np.linalg.lstsq(basis, values, rcond=None)
        if rank != 3:
            raise ValueError(f"Reciprocal-gap fit is rank-deficient for {branch_name}.")
        residual = basis @ coefficients - values
        relative_residual = np.abs(residual) / values
        leave_one_out_relative_residuals: list[float] = []
        for omitted_index in range(len(gaps)):
            keep = np.arange(len(gaps)) != omitted_index
            leave_one_out_coefficients, _, leave_one_out_rank, _ = np.linalg.lstsq(
                basis[keep], values[keep], rcond=None
            )
            if leave_one_out_rank != 3:
                raise ValueError(
                    f"Leave-one-out reciprocal-gap fit is rank-deficient for {branch_name}."
                )
            prediction = float(basis[omitted_index] @ leave_one_out_coefficients)
            leave_one_out_relative_residuals.append(
                abs(prediction - values[omitted_index]) / values[omitted_index]
            )
        branch_fits[branch_name] = {
            "coefficients_fF": coefficients.tolist(),
            "rms_residual_fF": float(np.sqrt(np.mean(residual**2))),
            "max_abs_residual_fF": float(np.max(np.abs(residual))),
            "max_abs_relative_residual": float(np.max(relative_residual)),
            "max_abs_leave_one_out_relative_residual": float(
                max(leave_one_out_relative_residuals)
            ),
        }
    validation_gaps = np.linspace(
        EXPECTED_GAPS_UM[0], EXPECTED_GAPS_UM[-1], 51, dtype=float
    )
    minimum_branch_fF = float("inf")
    minimum_retained_eigenvalue_fF = float("inf")
    for gap_um in validation_gaps:
        branches = {
            branch_name: float(
                np.asarray(
                    cast(dict[str, object], branch_fits[branch_name])[
                        "coefficients_fF"
                    ],
                    dtype=float,
                )
                @ np.asarray((1.0, 1.0 / gap_um, 1.0 / gap_um**2))
            )
            for branch_name in BRANCH_NAMES
        }
        minimum_branch_fF = min(minimum_branch_fF, *branches.values())
        retained = np.asarray(
            [
                [
                    branches["C01_fF"] + branches["C12_fF"] + branches["Cr1_fF"],
                    -branches["C12_fF"],
                    -branches["Cr1_fF"],
                ],
                [
                    -branches["C12_fF"],
                    branches["C02_fF"] + branches["C12_fF"] + branches["Cr2_fF"],
                    -branches["Cr2_fF"],
                ],
                [
                    -branches["Cr1_fF"],
                    -branches["Cr2_fF"],
                    branches["C0r_fF"] + branches["Cr1_fF"] + branches["Cr2_fF"],
                ],
            ]
        )
        minimum_retained_eigenvalue_fF = min(
            minimum_retained_eigenvalue_fF,
            float(np.min(np.linalg.eigvalsh(retained))),
        )
    if minimum_branch_fF <= 0.0 or minimum_retained_eigenvalue_fF <= 0.0:
        raise ValueError("Reciprocal-gap fit fails positivity on the 0.1 um validation grid.")
    return {
        "model": "a_plus_b_over_h_plus_c_over_h_squared",
        "basis": ["1", "1/h_um", "1/h_um^2"],
        "least_squares_rank": 3,
        "design_matrix_condition_number": float(np.linalg.cond(basis)),
        "branch_fits": branch_fits,
        "validation": {
            "gap_grid_start_um": float(validation_gaps[0]),
            "gap_grid_stop_um": float(validation_gaps[-1]),
            "gap_grid_step_um": 0.1,
            "gap_grid_count": len(validation_gaps),
            "all_branches_positive": True,
            "all_retained_matrices_positive_definite": True,
            "minimum_branch_fF": minimum_branch_fF,
            "minimum_retained_eigenvalue_fF": minimum_retained_eigenvalue_fF,
        },
    }


def build_artifact(input_path: Path) -> dict[str, object]:
    matrices = read_q3d_xlsx(input_path)
    samples = [
        {
            "gap_um": gap_um,
            "maxwell_capacitance_matrix_fF": matrix.tolist(),
            "physical_branches_fF": physical_branches_fF(matrix),
            "outer_reference_residual_fF": outer_reference_residual_fF(matrix),
        }
        for gap_um, matrix in sorted(matrices.items())
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "model_id": "same-face-resonators-opposite-face-qubit-q3d-gap-sweep",
        "capacitance_source_id": "q3d-c-qubit-gap-sweep-2026-07-28",
        "capacitance_unit": "fF",
        "gap_unit": "um",
        "nominal_gap_um": NOMINAL_GAP_UM,
        "valid_gap_range_um": [EXPECTED_GAPS_UM[0], EXPECTED_GAPS_UM[-1]],
        "conductor_labels": list(NODE_ORDER),
        "role_mapping": {
            "reference_conductor": "GND",
            "qubit_island_1": "Q1_L",
            "qubit_island_2": "Q1_R",
            "readout_attachment": "Q1_read",
        },
        "readout_self_capacitance_ownership": (
            "localized_open_side_interface_owns_named_ground_readout_shunt"
        ),
        "model_projection": {
            "policy": "named_GND_pairwise_branches_only",
            "named_ground_conductor": "GND",
            "retained_matrix_rule": (
                "raw_retained_principal_block_minus_diagonal_of_signed_"
                "retained_full_matrix_row_sums"
            ),
            "outer_reference_residual_circuit_use": "excluded",
            "outer_reference_residual_evidence_use": "report_only",
        },
        "region_ownership": {
            "modeling_mode": "electrostatic_local_interface_replacement",
            "local_region_id": "opposite-face-qubit-readout-q3d-retained-region",
            "readout_line_cut_plane_id": "Q1_read",
            "distributed_readout_length_reference": (
                "shorted_end_to_open_side_local_cut_plane"
            ),
            "distributed_line_excludes_local_capacitance": True,
            "electric_energy_owner": "named_ground_pairwise_projection",
            "magnetic_model": "not_supplied_by_q3d_capacitance_input",
        },
        "evaluation_policy": (
            "nominal_gap_uses_raw_q3d_sample__other_in_range_gaps_use_reciprocal_gap_fit"
        ),
        "source_artifact": {
            "kind": "q3d_capacitance_matrix_gap_sweep_xlsx",
            "filename": input_path.name,
            "sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        },
        "samples": samples,
        "fit": _fit_branches(samples),
        "L_J_per_junction_nH": L_J_PER_JUNCTION_NH,
    }


def write_artifact(input_path: Path, output_path: Path) -> Path:
    output = output_path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        build_artifact(input_path.resolve()), indent=2, sort_keys=True, allow_nan=False
    ) + "\n"
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
