#!/usr/bin/env python3
"""Write the source-first Spring2025 initializer consumed by D3 forward runs.

This build helper serializes the existing pure-math initializer for the five
Human-selected slots. It does not fit circuit parameters, consume Q2D output,
or promote paper values to D3 design targets.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from superconducting_circuits_analysis.domain.math.spring2025_initial_spec import (
    INITIALIZER_ONLY_PROCESS_MISMATCH,
    PAPER_IDENTITY,
    SPRING2025_REFERENCE_GEOMETRY,
    solve_source_first_length_seed,
)

SCHEMA_VERSION = "purcell.spring2025-initial-spec.v1"
SLOT_FREQUENCIES_HZ = (5.52e9, 5.76e9, 6.00e9, 6.24e9, 6.48e9)
NOTCH_TARGET_HZ = 4.5e9
READOUT_OFFSET_HZ = -1.0e6
FILTER_OFFSET_HZ = 1.0e6
COUPLED_LENGTH_M = 318.0e-6
SHORT_DELAY_SPLIT = 0.5


def _scalar_record(value: Any) -> dict[str, Any]:
    return {
        "symbol": value.symbol,
        "reported_value": value.reported_value,
        "reported_unit": value.reported_unit,
        "si_value": value.si_value,
        "si_unit": value.si_unit,
        "source_identity": value.source_identity,
        "provenance": value.provenance,
    }


def _interval_record(value: Any) -> dict[str, Any]:
    return {
        "symbol": value.symbol,
        "reported_bounds": list(value.reported_bounds),
        "reported_unit": value.reported_unit,
        "si_bounds": list(value.si_bounds),
        "si_unit": value.si_unit,
        "source_identity": value.source_identity,
        "provenance": value.provenance,
    }


def build_initial_spec() -> dict[str, Any]:
    """Return the strict finite five-slot initializer payload."""

    geometry = SPRING2025_REFERENCE_GEOMETRY
    velocity = geometry.phase_velocity.si_value
    slots: list[dict[str, Any]] = []
    for slot_hz in SLOT_FREQUENCIES_HZ:
        fr_target_hz = slot_hz + READOUT_OFFSET_HZ
        fp_target_hz = slot_hz + FILTER_OFFSET_HZ
        seed = solve_source_first_length_seed(
            fr_hz=fr_target_hz,
            fp_hz=fp_target_hz,
            fn_hz=NOTCH_TARGET_HZ,
            coupled_length_m=COUPLED_LENGTH_M,
            short_delay_split=SHORT_DELAY_SPLIT,
            single_line_velocity_m_per_s=velocity,
            coupled_line_velocity_m_per_s=velocity,
        )
        lengths = seed.lengths
        slots.append(
            {
                "slot_hz": slot_hz,
                "target_frequencies_hz": {
                    "readout_loaded_bare_hz": fr_target_hz,
                    "filter_loaded_bare_hz": fp_target_hz,
                    "intrinsic_notch_hz": NOTCH_TARGET_HZ,
                },
                "lengths_um": {
                    "lr_open_um": lengths.lr_open_m * 1.0e6,
                    "lr_short_um": lengths.lr_short_m * 1.0e6,
                    "lc_um": lengths.lc_m * 1.0e6,
                    "lp_short_um": lengths.lp_short_m * 1.0e6,
                    "lp_open_um": lengths.lp_open_m * 1.0e6,
                    "lr_total_um": lengths.readout_total_m * 1.0e6,
                    "lp_total_um": lengths.filter_total_m * 1.0e6,
                    "notch_path_um": lengths.notch_path_m * 1.0e6,
                },
                "round_trip_check_hz": {
                    "fr_hz": seed.round_trip_frequencies.fr_hz,
                    "fp_hz": seed.round_trip_frequencies.fp_hz,
                    "fn_hz": seed.round_trip_frequencies.fn_hz,
                },
                "status": "initializer_only",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "initializer_only",
        "source": {
            "paper_identity": PAPER_IDENTITY,
            "provenance": INITIALIZER_ONLY_PROCESS_MISMATCH,
        },
        "assumptions": {
            "single_line_velocity_m_per_s": velocity,
            "coupled_line_velocity_m_per_s": velocity,
            "coupled_length_m": COUPLED_LENGTH_M,
            "short_delay_split": SHORT_DELAY_SPLIT,
            "readout_offset_hz": READOUT_OFFSET_HZ,
            "filter_offset_hz": FILTER_OFFSET_HZ,
            "notch_target_hz": NOTCH_TARGET_HZ,
            "readout_length_reference": (
                "initializer_for_shorted_end_to_open_side_local_cut_plane"
            ),
            "open_side_local_loading_included_in_formula": False,
        },
        "reference_geometry": {
            "center_trace_width": _scalar_record(geometry.center_trace_width),
            "cpw_gap": _scalar_record(geometry.cpw_gap),
            "separating_ground_strip": _interval_record(geometry.separating_ground_strip),
            "example_coupled_length": _scalar_record(geometry.example_coupled_length),
            "phase_velocity": _scalar_record(geometry.phase_velocity),
            "characteristic_impedance": _scalar_record(geometry.characteristic_impedance),
            "mutual_capacitance_per_length": _scalar_record(
                geometry.mutual_capacitance_per_length
            ),
        },
        "slots": slots,
    }


def write_initial_spec(output_path: Path) -> Path:
    """Atomically write one finite initializer JSON artifact."""

    output = output_path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(build_initial_spec(), indent=2, sort_keys=True, allow_nan=False) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent,
        prefix=f".{output.name}.",
        suffix=".tmp",
        text=True,
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
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    print(write_initial_spec(arguments.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
