"""Regression tests for the source-backed Spring2025 initializer boundary."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import pi

import pytest
from superconducting_circuits_analysis.domain.math.spring2025_initial_spec import (
    INITIALIZER_ONLY_PROCESS_MISMATCH,
    LUMPED_IDENTITY_SOURCE,
    SPRING2025_Q1_LENGTHS,
    SPRING2025_REFERENCE_GEOMETRY,
    FiveSectionLengths,
    five_section_round_trip_frequencies,
    intrinsic_notch_frequency_hz,
    quarter_wave_frequency_hz,
    quarter_wave_lumped_mode,
    solve_source_first_length_seed,
)


def test_reference_geometry_is_immutable_source_backed_initializer_evidence() -> None:
    """Every reported value retains units, source identity, and scope boundary."""

    geometry = SPRING2025_REFERENCE_GEOMETRY
    assert geometry.center_trace_width.reported_value == 5.0
    assert geometry.cpw_gap.reported_value == 7.5
    assert geometry.separating_ground_strip.reported_bounds == (3.8, 5.5)
    assert geometry.example_coupled_length.reported_value == 318.0
    assert geometry.phase_velocity.reported_value == 1.19e8
    assert geometry.characteristic_impedance.reported_value == 66.0
    assert geometry.mutual_capacitance_per_length.reported_value == 8.5
    assert geometry.mutual_capacitance_per_length.si_value == 8.5e-12

    values = (
        geometry.center_trace_width,
        geometry.cpw_gap,
        geometry.separating_ground_strip,
        geometry.example_coupled_length,
        geometry.phase_velocity,
        geometry.characteristic_impedance,
        geometry.mutual_capacitance_per_length,
    )
    assert all(value.provenance == INITIALIZER_ONLY_PROCESS_MISMATCH for value in values)
    assert all(
        "Fig." in value.source_identity or "Table AI" in value.source_identity for value in values
    )
    with pytest.raises(FrozenInstanceError):
        geometry.__setattr__("phase_velocity", geometry.characteristic_impedance)


def test_q1_table_ai_lengths_regress_through_frequency_identities() -> None:
    """The cited Q1 MTL row remains locked to the canonical delay formulas."""

    velocity = SPRING2025_REFERENCE_GEOMETRY.phase_velocity.si_value
    lengths = SPRING2025_Q1_LENGTHS
    assert tuple(length * 1.0e6 for length in lengths.all_m) == pytest.approx(
        (974.0, 1617.0, 318.0, 1659.0, 759.0)
    )

    frequencies = five_section_round_trip_frequencies(
        lengths,
        single_line_velocity_m_per_s=velocity,
        coupled_line_velocity_m_per_s=velocity,
    )
    assert frequencies.fr_hz == pytest.approx(10.226882090065315e9)
    assert frequencies.fp_hz == pytest.approx(10.873538011695908e9)
    assert frequencies.fn_hz == pytest.approx(8.277685030606566e9)
    assert frequencies.fr_hz == pytest.approx(
        quarter_wave_frequency_hz(
            velocity_m_per_s=velocity,
            length_m=lengths.readout_total_m,
        )
    )
    assert frequencies.fp_hz == pytest.approx(
        quarter_wave_frequency_hz(
            velocity_m_per_s=velocity,
            length_m=lengths.filter_total_m,
        )
    )
    assert frequencies.fn_hz == pytest.approx(
        intrinsic_notch_frequency_hz(
            velocity_m_per_s=velocity,
            lr_short_m=lengths.lr_short_m,
            lc_m=lengths.lc_m,
            lp_short_m=lengths.lp_short_m,
        )
    )


@pytest.mark.parametrize("slot_hz", [5.52e9, 5.76e9, 6.00e9, 6.24e9, 6.48e9])
def test_d3_frequency_seeds_are_positive_and_round_trip(slot_hz: float) -> None:
    """The declared source-first ``lc=318 um``, 50/50 split seeds stay physical."""

    velocity = SPRING2025_REFERENCE_GEOMETRY.phase_velocity.si_value
    seed = solve_source_first_length_seed(
        fr_hz=slot_hz,
        fp_hz=slot_hz,
        fn_hz=4.5e9,
        coupled_length_m=318.0e-6,
        short_delay_split=0.5,
        single_line_velocity_m_per_s=velocity,
        coupled_line_velocity_m_per_s=velocity,
    )
    assert min(seed.lengths.all_m) > 0.0
    assert seed.round_trip_frequencies.fr_hz == pytest.approx(slot_hz)
    assert seed.round_trip_frequencies.fp_hz == pytest.approx(slot_hz)
    assert seed.round_trip_frequencies.fn_hz == pytest.approx(4.5e9)
    assert seed.provenance == INITIALIZER_ONLY_PROCESS_MISMATCH


@pytest.mark.parametrize(
    "field",
    ["lr_open_m", "lr_short_m", "lc_m", "lp_short_m", "lp_open_m"],
)
def test_five_section_lengths_reject_every_nonpositive_section(field: str) -> None:
    """No section can cross the initializer boundary with a zero length."""

    values = {
        "lr_open_m": 1.0e-3,
        "lr_short_m": 1.0e-3,
        "lc_m": 0.3e-3,
        "lp_short_m": 1.0e-3,
        "lp_open_m": 1.0e-3,
    }
    values[field] = 0.0
    with pytest.raises(ValueError, match=rf"{field} must be positive and finite"):
        FiveSectionLengths(**values)


def test_seed_solver_rejects_a_nonpositive_solved_open_section() -> None:
    """An incompatible frequency/delay request fails instead of returning a seed."""

    velocity = SPRING2025_REFERENCE_GEOMETRY.phase_velocity.si_value
    with pytest.raises(ValueError, match="lr_open_m must be positive and finite"):
        solve_source_first_length_seed(
            fr_hz=20.0e9,
            fp_hz=6.0e9,
            fn_hz=4.5e9,
            coupled_length_m=318.0e-6,
            short_delay_split=0.5,
            single_line_velocity_m_per_s=velocity,
            coupled_line_velocity_m_per_s=velocity,
        )


def test_quarter_wave_lumped_identities_close_frequency_and_impedance() -> None:
    """The Appendix-C quarter-wave identities close frequency and impedance."""

    geometry = SPRING2025_REFERENCE_GEOMETRY
    velocity = geometry.phase_velocity.si_value
    impedance = geometry.characteristic_impedance.si_value
    capacitance_per_m = 1.0 / (impedance * velocity)
    inductance_per_m = impedance / velocity
    length = SPRING2025_Q1_LENGTHS.readout_total_m

    mode = quarter_wave_lumped_mode(
        capacitance_per_m_f=capacitance_per_m,
        inductance_per_m_h=inductance_per_m,
        length_m=length,
    )
    assert mode.capacitance_f == pytest.approx(capacitance_per_m * length / 2.0)
    assert mode.inductance_h == pytest.approx(8.0 * inductance_per_m * length / pi**2)
    assert mode.characteristic_impedance_ohm == pytest.approx(impedance)
    assert mode.mode_impedance_ohm == pytest.approx(4.0 * impedance / pi)
    assert mode.mode_impedance_from_lumped_ohm == pytest.approx(mode.mode_impedance_ohm)
    assert mode.lumped_frequency_hz == pytest.approx(mode.distributed_frequency_hz)
    assert mode.distributed_frequency_hz == pytest.approx(
        quarter_wave_frequency_hz(velocity_m_per_s=velocity, length_m=length)
    )
    assert mode.source_identity == LUMPED_IDENTITY_SOURCE
    assert mode.provenance == INITIALIZER_ONLY_PROCESS_MISMATCH
