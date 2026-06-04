from __future__ import annotations

from dataclasses import dataclass

from app_backend.domain.result_traces import ResultTraceSelection
from app_backend.domain.tasks import TaskDetail

FAMILY_LABELS = {
    "s_matrix": "S Matrix",
    "y_matrix": "Y Matrix",
    "z_matrix": "Z Matrix",
}
SOURCE_LABELS = {
    "raw": "Raw",
    "ptc": "PTC",
}
FAMILY_METRICS = {
    "s_matrix": {
        "magnitude_db": {"label": "Magnitude (dB)", "unit": "dB"},
        "phase_deg": {"label": "Phase (deg)", "unit": "deg"},
        "real": {"label": "Real", "unit": "unitless"},
        "imag": {"label": "Imaginary", "unit": "unitless"},
    },
    "y_matrix": {
        "magnitude": {"label": "Magnitude", "unit": "S"},
        "real": {"label": "Real", "unit": "S"},
        "imag": {"label": "Imaginary", "unit": "S"},
    },
    "z_matrix": {
        "magnitude": {"label": "Magnitude", "unit": "ohm"},
        "real": {"label": "Real", "unit": "ohm"},
        "imag": {"label": "Imaginary", "unit": "ohm"},
    },
}


@dataclass(frozen=True)
class ExplorerSelectionRequest:
    family: str | None = None
    source: str | None = None
    metric: str | None = None
    sweep_index: int | None = None
    compare_axis_index: int | None = None
    z0_ohm: float | None = None
    output_port: int | None = None
    input_port: int | None = None


@dataclass(frozen=True)
class ExplorerContext:
    explorer_task: TaskDetail
    basis_task: TaskDetail
    port_options: dict[int, str]
    default_selection: dict[str, object]


@dataclass(frozen=True)
class ResolvedSelection:
    family: str
    source: str
    metric: str
    sweep_index: int | None
    compare_axis_index: int | None
    z0_ohm: float
    output_port: int
    input_port: int

    @property
    def trace_key(self) -> str:
        return self.to_trace_selection().to_trace_key()

    def to_mapping(self) -> dict[str, object]:
        return {
            "family": self.family,
            "source": self.source,
            "metric": self.metric,
            "sweep_index": self.sweep_index,
            "compare_axis_index": self.compare_axis_index,
            "z0_ohm": self.z0_ohm,
            "output_port": self.output_port,
            "input_port": self.input_port,
        }

    def to_trace_selection(self) -> ResultTraceSelection:
        return ResultTraceSelection(
            family=self.family,
            source=self.source,
            output_port=self.output_port,
            input_port=self.input_port,
            sweep_index=self.sweep_index,
            trace_mode_group="base",
            output_mode="mode_0",
            input_mode="mode_0",
            z0_ohm=self.z0_ohm if self.family in {"y_matrix", "z_matrix"} else None,
        )
