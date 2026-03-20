"""Typed value objects for trace metadata normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class TraceKind(StrEnum):
    """Canonical trace data-kind tokens used by persistence and analysis."""

    S_PARAMETERS = "s_parameters"
    Y_PARAMETERS = "y_parameters"
    Z_PARAMETERS = "z_parameters"
    UNKNOWN = "unknown"

    @classmethod
    def from_token(cls, raw: object) -> TraceKind:
        """Normalize one raw token into canonical trace-kind enum."""
        token = str(raw or "").strip().lower()
        alias_map: dict[str, TraceKind] = {
            "s_parameters": cls.S_PARAMETERS,
            "s_params": cls.S_PARAMETERS,
            "s_matrix": cls.S_PARAMETERS,
            "scattering": cls.S_PARAMETERS,
            "scattering_matrix": cls.S_PARAMETERS,
            "y_parameters": cls.Y_PARAMETERS,
            "y_params": cls.Y_PARAMETERS,
            "y_matrix": cls.Y_PARAMETERS,
            "admittance": cls.Y_PARAMETERS,
            "admittance_matrix": cls.Y_PARAMETERS,
            "z_parameters": cls.Z_PARAMETERS,
            "z_params": cls.Z_PARAMETERS,
            "z_matrix": cls.Z_PARAMETERS,
            "impedance": cls.Z_PARAMETERS,
            "impedance_matrix": cls.Z_PARAMETERS,
        }
        return alias_map.get(token, cls.UNKNOWN)

    @property
    def accepted_tokens(self) -> tuple[str, ...]:
        """Return canonical + alias tokens accepted by repository filters."""
        aliases: dict[TraceKind, tuple[str, ...]] = {
            TraceKind.S_PARAMETERS: (
                "s_parameters",
                "s_params",
                "s_matrix",
                "scattering",
                "scattering_matrix",
            ),
            TraceKind.Y_PARAMETERS: (
                "y_parameters",
                "y_params",
                "y_matrix",
                "admittance",
                "admittance_matrix",
            ),
            TraceKind.Z_PARAMETERS: (
                "z_parameters",
                "z_params",
                "z_matrix",
                "impedance",
                "impedance_matrix",
            ),
            TraceKind.UNKNOWN: ("unknown",),
        }
        return aliases[self]


class ModeGroup(StrEnum):
    """Canonical trace mode-group tokens for filtering and provenance."""

    ALL = "all"
    BASE = "base"
    SIDEBAND = "sideband"
    UNKNOWN = "unknown"

    @classmethod
    def normalize(
        cls,
        raw: object,
        *,
        allow_all: bool = True,
        default: ModeGroup | None = None,
    ) -> ModeGroup:
        """Normalize one mode token with alias support."""
        token = str(raw or "").strip().lower()
        if token in ("base", "signal"):
            return cls.BASE
        if token == "sideband":
            return cls.SIDEBAND
        if allow_all and token == "all":
            return cls.ALL
        if default is not None:
            return default
        return cls.UNKNOWN

    @classmethod
    def from_trace_label(cls, raw: object, *, default: ModeGroup | None = None) -> ModeGroup:
        """Normalize one UI row-mode label (`Base`/`Sideband`) to canonical group."""
        token = str(raw or "").strip().lower()
        if token == "sideband":
            return cls.SIDEBAND
        if token in ("base", "signal"):
            return cls.BASE
        if default is not None:
            return default
        return cls.UNKNOWN


@dataclass(frozen=True)
class ParameterKey:
    """Normalized analysis parameter token with sideband metadata."""

    raw: str
    canonical: str
    has_sideband_suffix: bool

    @classmethod
    def from_raw(cls, raw: object) -> ParameterKey:
        """Build normalized parameter key from persistence/query token."""
        raw_text = str(raw or "").strip()
        canonical = raw_text.split(" [", 1)[0].strip()
        has_sideband_suffix = " [om=" in raw_text or " [im=" in raw_text
        return cls(raw=raw_text, canonical=canonical, has_sideband_suffix=has_sideband_suffix)

    @property
    def mode_group(self) -> ModeGroup:
        """Infer mode group from parameter suffix metadata."""
        if not self.has_sideband_suffix:
            return ModeGroup.BASE
        sideband_suffix = self.raw.split(" [", 1)[-1]
        integers = [int(token) for token in re.findall(r"-?\d+", sideband_suffix)]
        if not integers or all(value == 0 for value in integers):
            return ModeGroup.BASE
        return ModeGroup.SIDEBAND
