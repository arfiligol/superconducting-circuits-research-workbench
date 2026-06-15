"""
Unit conversion utilities.

Provides constants and functions for working with physical units
commonly used in superconducting circuit simulations.
"""

# Frequency
GHz = 1e9
MHz = 1e6
kHz = 1e3

# Inductance
H = 1.0
mH = 1e-3
uH = 1e-6
nH = 1e-9
pH = 1e-12

# Capacitance
F = 1.0
mF = 1e-3
uF = 1e-6
nF = 1e-9
pF = 1e-12
fF = 1e-15

# Resistance
Ohm = 1.0
kOhm = 1e3
MOhm = 1e6

# Flux quantum
PHI_0 = 2.067833848e-15  # Wb (magnetic flux quantum)


def freq_to_angular(freq_hz: float) -> float:
    """Convert frequency (Hz) to angular frequency (rad/s)."""
    import math

    return 2 * math.pi * freq_hz


def angular_to_freq(omega: float) -> float:
    """Convert angular frequency (rad/s) to frequency (Hz)."""
    import math

    return omega / (2 * math.pi)


def lc_resonance_hz(inductance_h: float, capacitance_f: float) -> float:
    """
    Calculate LC resonance frequency.

    f0 = 1 / (2π√LC)

    Args:
        inductance_h: Inductance in Henries.
        capacitance_f: Capacitance in Farads.

    Returns:
        Resonance frequency in Hz.
    """
    import math

    return 1 / (2 * math.pi * math.sqrt(inductance_h * capacitance_f))
