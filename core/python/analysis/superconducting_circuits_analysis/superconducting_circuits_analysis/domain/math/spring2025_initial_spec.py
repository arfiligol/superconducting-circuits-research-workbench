"""Source-backed Spring2025 initial-spec mathematics.

This module owns an immutable, pure-Python initializer boundary for the
readout/filter geometry reported by Spring et al. and for the delay identities
used to seed five-section resonator lengths. The paper values are initializer
evidence from a different process, not promoted design targets. Parameter
fitting, full-QRP response evaluation, and any Q2D-matrix-to-``C14`` mapping
belong outside this module.

Primary source:
    P. A. Spring et al., PRX Quantum 6, 020345 (2025),
    https://doi.org/10.1103/PRXQuantum.6.020345,
    arXiv:2409.04967.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite, pi, sqrt

PAPER_IDENTITY = "Spring et al., PRX Quantum 6, 020345 (2025), arXiv:2409.04967"
INITIALIZER_ONLY_PROCESS_MISMATCH = (
    "initializer only / process mismatch: the reported device geometry seeds "
    "frequency and specification estimates but is not a promoted design target"
)
LUMPED_IDENTITY_SOURCE = (
    f"{PAPER_IDENTITY}, Appendix C quarter-wave transmission-line-to-parallel-LC identities"
)

_ALGEBRAIC_RELATIVE_TOLERANCE = 2.0e-14


def _positive_finite(value: float, name: str) -> float:
    numeric = float(value)
    if not isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f"{name} must be positive and finite.")
    return numeric


def _open_unit_interval(value: float, name: str) -> float:
    numeric = float(value)
    if not isfinite(numeric) or not 0.0 < numeric < 1.0:
        raise ValueError(f"{name} must be finite and strictly between zero and one.")
    return numeric


def _require_algebraic_match(actual: float, expected: float, identity: str) -> None:
    if not isclose(
        actual,
        expected,
        rel_tol=_ALGEBRAIC_RELATIVE_TOLERANCE,
        abs_tol=0.0,
    ):
        raise ArithmeticError(f"{identity} failed its algebraic round-trip check.")


@dataclass(frozen=True, slots=True)
class SourceBackedScalar:
    """Carry one immutable reported scalar and its SI conversion."""

    symbol: str
    reported_value: float
    reported_unit: str
    si_value: float
    si_unit: str
    source_identity: str
    provenance: str = INITIALIZER_ONLY_PROCESS_MISMATCH


@dataclass(frozen=True, slots=True)
class SourceBackedInterval:
    """Carry one immutable reported interval and its SI conversion."""

    symbol: str
    reported_bounds: tuple[float, float]
    reported_unit: str
    si_bounds: tuple[float, float]
    si_unit: str
    source_identity: str
    provenance: str = INITIALIZER_ONLY_PROCESS_MISMATCH


@dataclass(frozen=True, slots=True)
class Spring2025ReferenceGeometry:
    """Collect the paper geometry used only to initialize later design work."""

    center_trace_width: SourceBackedScalar
    cpw_gap: SourceBackedScalar
    separating_ground_strip: SourceBackedInterval
    example_coupled_length: SourceBackedScalar
    phase_velocity: SourceBackedScalar
    characteristic_impedance: SourceBackedScalar
    mutual_capacitance_per_length: SourceBackedScalar


SPRING2025_REFERENCE_GEOMETRY = Spring2025ReferenceGeometry(
    center_trace_width=SourceBackedScalar(
        symbol="w",
        reported_value=5.0,
        reported_unit="um",
        si_value=5.0e-6,
        si_unit="m",
        source_identity=f"{PAPER_IDENTITY}, Fig. A3(a), coupled-CPW geometry",
    ),
    cpw_gap=SourceBackedScalar(
        symbol="s",
        reported_value=7.5,
        reported_unit="um",
        si_value=7.5e-6,
        si_unit="m",
        source_identity=f"{PAPER_IDENTITY}, Fig. A3(a), coupled-CPW geometry",
    ),
    separating_ground_strip=SourceBackedInterval(
        symbol="d",
        reported_bounds=(3.8, 5.5),
        reported_unit="um",
        si_bounds=(3.8e-6, 5.5e-6),
        si_unit="m",
        source_identity=f"{PAPER_IDENTITY}, Fig. A3(c), blue designed-device range",
    ),
    example_coupled_length=SourceBackedScalar(
        symbol="l_c",
        reported_value=318.0,
        reported_unit="um",
        si_value=318.0e-6,
        si_unit="m",
        source_identity=f"{PAPER_IDENTITY}, Table AI, MTL row for the Q1 example",
    ),
    phase_velocity=SourceBackedScalar(
        symbol="v",
        reported_value=1.19e8,
        reported_unit="m/s",
        si_value=1.19e8,
        si_unit="m/s",
        source_identity=f"{PAPER_IDENTITY}, Table AI caption",
    ),
    characteristic_impedance=SourceBackedScalar(
        symbol="Z_0",
        reported_value=66.0,
        reported_unit="ohm",
        si_value=66.0,
        si_unit="ohm",
        source_identity=f"{PAPER_IDENTITY}, Table AI caption",
    ),
    mutual_capacitance_per_length=SourceBackedScalar(
        symbol="c_m",
        reported_value=8.5,
        reported_unit="fF/mm",
        si_value=8.5e-12,
        si_unit="F/m",
        source_identity=f"{PAPER_IDENTITY}, Table AI, MTL row for the Q1 example",
    ),
)


@dataclass(frozen=True, slots=True)
class FiveSectionLengths:
    """Store the positive ``r-open, r-short, coupled, p-short, p-open`` lengths."""

    lr_open_m: float
    lr_short_m: float
    lc_m: float
    lp_short_m: float
    lp_open_m: float

    def __post_init__(self) -> None:
        for name in (
            "lr_open_m",
            "lr_short_m",
            "lc_m",
            "lp_short_m",
            "lp_open_m",
        ):
            object.__setattr__(self, name, _positive_finite(getattr(self, name), name))

    @property
    def all_m(self) -> tuple[float, float, float, float, float]:
        """Return all five sections in physical order."""

        return (
            self.lr_open_m,
            self.lr_short_m,
            self.lc_m,
            self.lp_short_m,
            self.lp_open_m,
        )

    @property
    def readout_total_m(self) -> float:
        """Return the full readout-resonator length."""

        return self.lr_open_m + self.lc_m + self.lr_short_m

    @property
    def filter_total_m(self) -> float:
        """Return the full filter-resonator length."""

        return self.lp_open_m + self.lc_m + self.lp_short_m

    @property
    def notch_path_m(self) -> float:
        """Return the uniform-velocity short-to-short notch-path length."""

        return self.lr_short_m + self.lc_m + self.lp_short_m


@dataclass(frozen=True, slots=True)
class RoundTripFrequencies:
    """Carry readout, filter, and intrinsic-notch round-trip frequencies."""

    fr_hz: float
    fp_hz: float
    fn_hz: float


@dataclass(frozen=True, slots=True)
class Spring2025LengthSeed:
    """Return one initializer-only five-section seed and its round-trip check."""

    lengths: FiveSectionLengths
    round_trip_frequencies: RoundTripFrequencies
    single_line_velocity_m_per_s: float
    coupled_line_velocity_m_per_s: float
    short_delay_split: float
    provenance: str = INITIALIZER_ONLY_PROCESS_MISMATCH


SPRING2025_Q1_LENGTHS = FiveSectionLengths(
    lr_open_m=974.0e-6,
    lr_short_m=1617.0e-6,
    lc_m=318.0e-6,
    lp_short_m=1659.0e-6,
    lp_open_m=759.0e-6,
)
SPRING2025_Q1_LENGTHS_SOURCE = (
    f"{PAPER_IDENTITY}, Table AI, MTL row for the Q1 transfer-impedance example"
)


@dataclass(frozen=True, slots=True)
class QuarterWaveLumpedMode:
    """Carry the source-backed parallel-LC equivalent and round-trip evidence."""

    capacitance_f: float
    inductance_h: float
    characteristic_impedance_ohm: float
    mode_impedance_ohm: float
    mode_impedance_from_lumped_ohm: float
    distributed_frequency_hz: float
    lumped_frequency_hz: float
    source_identity: str = LUMPED_IDENTITY_SOURCE
    provenance: str = INITIALIZER_ONLY_PROCESS_MISMATCH


def quarter_wave_frequency_hz(*, velocity_m_per_s: float, length_m: float) -> float:
    """Return the canonical quarter-wave frequency ``f = v / (4*l)``."""

    velocity = _positive_finite(velocity_m_per_s, "velocity_m_per_s")
    length = _positive_finite(length_m, "length_m")
    return velocity / (4.0 * length)


def intrinsic_notch_frequency_hz(
    *,
    velocity_m_per_s: float,
    lr_short_m: float,
    lc_m: float,
    lp_short_m: float,
) -> float:
    """Return ``v / (4*(lr_short + lc + lp_short))`` for equal phase velocity."""

    velocity = _positive_finite(velocity_m_per_s, "velocity_m_per_s")
    notch_length = sum(
        (
            _positive_finite(lr_short_m, "lr_short_m"),
            _positive_finite(lc_m, "lc_m"),
            _positive_finite(lp_short_m, "lp_short_m"),
        )
    )
    return velocity / (4.0 * notch_length)


def five_section_round_trip_frequencies(
    lengths: FiveSectionLengths,
    *,
    single_line_velocity_m_per_s: float,
    coupled_line_velocity_m_per_s: float,
) -> RoundTripFrequencies:
    """Evaluate the three delay identities for explicit single/coupled velocities."""

    single_velocity = _positive_finite(
        single_line_velocity_m_per_s,
        "single_line_velocity_m_per_s",
    )
    coupled_velocity = _positive_finite(
        coupled_line_velocity_m_per_s,
        "coupled_line_velocity_m_per_s",
    )
    coupled_delay_s = lengths.lc_m / coupled_velocity
    readout_delay_s = (
        lengths.lr_short_m / single_velocity + coupled_delay_s + lengths.lr_open_m / single_velocity
    )
    filter_delay_s = (
        lengths.lp_short_m / single_velocity + coupled_delay_s + lengths.lp_open_m / single_velocity
    )
    notch_delay_s = (
        lengths.lr_short_m / single_velocity
        + coupled_delay_s
        + lengths.lp_short_m / single_velocity
    )
    return RoundTripFrequencies(
        fr_hz=1.0 / (4.0 * readout_delay_s),
        fp_hz=1.0 / (4.0 * filter_delay_s),
        fn_hz=1.0 / (4.0 * notch_delay_s),
    )


def solve_source_first_length_seed(
    *,
    fr_hz: float,
    fp_hz: float,
    fn_hz: float,
    coupled_length_m: float,
    short_delay_split: float,
    single_line_velocity_m_per_s: float,
    coupled_line_velocity_m_per_s: float,
) -> Spring2025LengthSeed:
    """Solve five positive section lengths from three target delay identities.

    ``short_delay_split`` assigns that fraction of the non-coupled notch delay
    to the readout short section and the remainder to the filter short section.
    All lengths and both velocities are explicit; no Q2D matrix entry or fitted
    parameter is inferred.

    Raises:
        ValueError: If any input is non-finite or nonpositive, the split is not
            strictly between zero and one, or any solved section is nonpositive.
    """

    target_fr_hz = _positive_finite(fr_hz, "fr_hz")
    target_fp_hz = _positive_finite(fp_hz, "fp_hz")
    target_fn_hz = _positive_finite(fn_hz, "fn_hz")
    coupled_length = _positive_finite(coupled_length_m, "coupled_length_m")
    single_velocity = _positive_finite(
        single_line_velocity_m_per_s,
        "single_line_velocity_m_per_s",
    )
    coupled_velocity = _positive_finite(
        coupled_line_velocity_m_per_s,
        "coupled_line_velocity_m_per_s",
    )
    split = _open_unit_interval(short_delay_split, "short_delay_split")

    coupled_delay_s = coupled_length / coupled_velocity
    short_delay_sum_s = 1.0 / (4.0 * target_fn_hz) - coupled_delay_s
    if short_delay_sum_s <= 0.0:
        raise ValueError(
            "fn_hz and coupled_length_m leave a nonpositive combined short-section delay."
        )

    lr_short_delay_s = split * short_delay_sum_s
    lp_short_delay_s = (1.0 - split) * short_delay_sum_s
    lr_open_delay_s = 1.0 / (4.0 * target_fr_hz) - coupled_delay_s - lr_short_delay_s
    lp_open_delay_s = 1.0 / (4.0 * target_fp_hz) - coupled_delay_s - lp_short_delay_s
    lengths = FiveSectionLengths(
        lr_open_m=lr_open_delay_s * single_velocity,
        lr_short_m=lr_short_delay_s * single_velocity,
        lc_m=coupled_length,
        lp_short_m=lp_short_delay_s * single_velocity,
        lp_open_m=lp_open_delay_s * single_velocity,
    )
    round_trip = five_section_round_trip_frequencies(
        lengths,
        single_line_velocity_m_per_s=single_velocity,
        coupled_line_velocity_m_per_s=coupled_velocity,
    )
    _require_algebraic_match(round_trip.fr_hz, target_fr_hz, "fr_hz")
    _require_algebraic_match(round_trip.fp_hz, target_fp_hz, "fp_hz")
    _require_algebraic_match(round_trip.fn_hz, target_fn_hz, "fn_hz")
    return Spring2025LengthSeed(
        lengths=lengths,
        round_trip_frequencies=round_trip,
        single_line_velocity_m_per_s=single_velocity,
        coupled_line_velocity_m_per_s=coupled_velocity,
        short_delay_split=split,
    )


def quarter_wave_lumped_mode(
    *,
    capacitance_per_m_f: float,
    inductance_per_m_h: float,
    length_m: float,
) -> QuarterWaveLumpedMode:
    """Map a lossless quarter-wave line to the Appendix-C parallel-LC mode.

    The source-backed identities are ``C_mode = c' * l / 2``,
    ``L_mode = 8 * l' * l / pi**2``, and ``Z_mode = 4 * Z0 / pi``. The
    function verifies that the lumped resonance returns ``v/(4*l)`` and that
    ``sqrt(L_mode/C_mode)`` returns the same mode impedance.
    """

    capacitance_per_m = _positive_finite(capacitance_per_m_f, "capacitance_per_m_f")
    inductance_per_m = _positive_finite(inductance_per_m_h, "inductance_per_m_h")
    length = _positive_finite(length_m, "length_m")

    velocity = 1.0 / sqrt(inductance_per_m * capacitance_per_m)
    characteristic_impedance = sqrt(inductance_per_m / capacitance_per_m)
    capacitance = capacitance_per_m * length / 2.0
    inductance = 8.0 * inductance_per_m * length / pi**2
    mode_impedance = 4.0 * characteristic_impedance / pi
    mode_impedance_from_lumped = sqrt(inductance / capacitance)
    distributed_frequency = quarter_wave_frequency_hz(
        velocity_m_per_s=velocity,
        length_m=length,
    )
    lumped_frequency = 1.0 / (2.0 * pi * sqrt(inductance * capacitance))

    _require_algebraic_match(
        lumped_frequency,
        distributed_frequency,
        "quarter-wave frequency",
    )
    _require_algebraic_match(
        mode_impedance_from_lumped,
        mode_impedance,
        "quarter-wave mode impedance",
    )
    return QuarterWaveLumpedMode(
        capacitance_f=capacitance,
        inductance_h=inductance,
        characteristic_impedance_ohm=characteristic_impedance,
        mode_impedance_ohm=mode_impedance,
        mode_impedance_from_lumped_ohm=mode_impedance_from_lumped,
        distributed_frequency_hz=distributed_frequency,
        lumped_frequency_hz=lumped_frequency,
    )
