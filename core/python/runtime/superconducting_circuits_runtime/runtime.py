# ruff: noqa: E501
"""Sealed Python authoring and Julia-action transport for Circuit Workbench.

This module deliberately has no Julia embedding.  Each execute action may start
one Julia subprocess; resolve paths only verify sealed stage receipts.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal, cast

PLAN_SCHEMA = "circuit-workbench-plan.v1"
REQUEST_SCHEMA = "circuit-workbench-run-request.v1"
RECEIPT_SCHEMA = "circuit-workbench-run-receipt.v1"
STAGE_ORDER = (
    "optimize",
    "refine_winner",
    "evaluate_responses",
    "fit_c11",
    "evaluate_t1",
    "build_report",
)
STAGE_DEPENDENCIES = {
    "optimize": (),
    "refine_winner": ("optimize",),
    "evaluate_responses": ("optimize", "refine_winner"),
    "fit_c11": ("evaluate_responses",),
    "evaluate_t1": ("optimize", "fit_c11"),
    "build_report": STAGE_ORDER[:-1],
}
_STAGE_ACTIONS = {"execute", "resolve"}
_LIFECYCLE_STATES = {"CONVERGING", "ACCEPTED", "STABILIZED"}
_DATA_CLASSIFICATIONS = {"public", "project-internal", "NCUAS-private", "report-safe-derived"}
_PACKAGE_ROOT = Path(__file__).resolve().parent
_SOURCE_CORE_ROOT = _PACKAGE_ROOT.parents[2]
_JULIA_ROOT = (
    _SOURCE_CORE_ROOT / "julia"
    if (_SOURCE_CORE_ROOT / "julia" / "SuperconductingCircuitsRunner").is_dir()
    else _PACKAGE_ROOT / "_julia"
)
_RUNNER_PROJECT = _JULIA_ROOT / "SuperconductingCircuitsRunner"
_RUNNER_CLI = _RUNNER_PROJECT / "bin" / "circuit_workbench_runtime.jl"


class RuntimeContractError(ValueError):
    """Raised before Julia for a malformed or incomplete consumer declaration."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "circuit_workbench_contract_invalid",
        category: str = "validation_error",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.category = category
        self.retryable = retryable


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


@dataclass(frozen=True)
class EndpointRef:
    component_id: str
    pin_name: str


@dataclass(frozen=True)
class CoordinateRef:
    component_id: str
    coordinate_name: str


@dataclass(frozen=True)
class ParameterRef:
    component_id: str
    parameter_name: str


@dataclass(frozen=True)
class ParameterDeclaration:
    """One declared numeric component parameter with consumer-visible metadata."""

    name: str
    units: str
    role: str
    variable_capable: bool = True


@dataclass(frozen=True)
class CoordinateDeclaration:
    name: str
    units: str = "node_flux"
    role: str = "signal"


def _parameter_declaration(
    value: ParameterDeclaration | Mapping[str, Any],
) -> ParameterDeclaration:
    if isinstance(value, ParameterDeclaration):
        return value
    if isinstance(value, Mapping):
        try:
            if set(value) - {"name", "units", "role", "variable_capable"}:
                raise RuntimeContractError("Parameter declaration contains an unknown field.")
            variable_capable = value.get("variable_capable", True)
            if (
                not _nonempty_string(value["name"])
                or not _nonempty_string(value["units"])
                or not _nonempty_string(value["role"])
                or not isinstance(variable_capable, bool)
            ):
                raise RuntimeContractError(
                    "Parameter declarations require string name/units/role and boolean variable_capable."
                )
            return ParameterDeclaration(
                value["name"], value["units"], value["role"], variable_capable
            )
        except KeyError as error:
            raise RuntimeContractError(
                "Parameter declaration mappings require name, units, and role."
            ) from error
    raise RuntimeContractError("Parameter declarations require ParameterDeclaration or mapping.")


def _coordinate_declaration(
    value: CoordinateDeclaration | Mapping[str, Any] | str,
) -> CoordinateDeclaration:
    if isinstance(value, CoordinateDeclaration):
        return value
    if isinstance(value, Mapping):
        try:
            if set(value) != {"name", "units", "role"} or any(
                not _nonempty_string(value[key]) for key in ("name", "units", "role")
            ):
                raise RuntimeContractError(
                    "Coordinate declarations require only string name, units, and role."
                )
            return CoordinateDeclaration(value["name"], value["units"], value["role"])
        except KeyError as error:
            raise RuntimeContractError(
                "Coordinate declaration mappings require name, units, and role."
            ) from error
    return CoordinateDeclaration(str(value))


@dataclass(frozen=True)
class ComponentType:
    type_id: str
    pins: tuple[str, ...]
    parameters: tuple[ParameterDeclaration | Mapping[str, Any], ...]
    coordinates: tuple[CoordinateDeclaration | Mapping[str, Any] | str, ...] = ()
    lowerer: str = ""

    def __post_init__(self) -> None:
        if not _nonempty_string(self.type_id) or not _nonempty_string(self.lowerer):
            raise RuntimeContractError(
                "Component types require type_id and Julia lowerer identity."
            )
        if (
            not self.pins
            or len(set(self.pins)) != len(self.pins)
            or any(not _nonempty_string(pin) for pin in self.pins)
        ):
            raise RuntimeContractError("Component type pins must be nonempty and unique.")
        parameters = tuple(_parameter_declaration(item) for item in self.parameters)
        coordinates = tuple(_coordinate_declaration(item) for item in self.coordinates)
        if any(
            not _nonempty_string(item.name)
            or not _nonempty_string(item.units)
            or not _nonempty_string(item.role)
            for item in parameters
        ):
            raise RuntimeContractError("Component parameters require name, units, and role.")
        if len({item.name for item in parameters}) != len(parameters):
            raise RuntimeContractError("Component parameter names must be unique.")
        if any(
            not _nonempty_string(item.name)
            or not _nonempty_string(item.units)
            or not _nonempty_string(item.role)
            for item in coordinates
        ) or len({item.name for item in coordinates}) != len(coordinates):
            raise RuntimeContractError("Component coordinate names must be unique.")
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "coordinates", coordinates)


@dataclass(frozen=True)
class ComponentInstance:
    id: str
    type_id: str
    parameters: Mapping[str, float]
    children: tuple[ComponentInstance, ...] = ()
    pin_bindings: Mapping[str, EndpointRef] = field(default_factory=dict)
    coordinate_bindings: Mapping[str, CoordinateRef] = field(default_factory=dict)
    parameter_bindings: Mapping[str, ParameterRef] = field(default_factory=dict)
    internal_connections: tuple[tuple[EndpointRef, EndpointRef], ...] = ()

    def pin(self, name: str) -> EndpointRef:
        return EndpointRef(self.id, name)

    def coord(self, name: str) -> CoordinateRef:
        return CoordinateRef(self.id, name)

    def parameter(self, name: str) -> ParameterRef:
        return ParameterRef(self.id, name)


@dataclass
class CircuitLibrary:
    id: str
    version: str
    source_sha256: str
    types: dict[str, ComponentType] = field(default_factory=dict)

    def register(self, component: ComponentType | Callable[..., ComponentInstance]) -> None:
        declared = getattr(component, "__circuit_component_type__", component)
        if not isinstance(declared, ComponentType):
            raise RuntimeContractError(
                "CircuitLibrary.register requires ComponentType or @circuit_component factory."
            )
        if declared.type_id in self.types:
            raise RuntimeContractError(f"Duplicate component type '{declared.type_id}'.")
        self.types[declared.type_id] = declared

    def component(
        self,
        type_id: str,
        *,
        id: str,
        parameters: Mapping[str, float],
        children: Sequence[ComponentInstance] = (),
        pin_bindings: Mapping[str, EndpointRef] | None = None,
        coordinate_bindings: Mapping[str, CoordinateRef] | None = None,
        parameter_bindings: Mapping[str, ParameterRef] | None = None,
        internal_connections: Sequence[tuple[EndpointRef, EndpointRef]] = (),
    ) -> ComponentInstance:
        """Construct one registered explicit instance without exposing runtime internals."""

        if type_id not in self.types:
            raise RuntimeContractError(f"Library '{self.id}' does not register type '{type_id}'.")
        instance = ComponentInstance(
            id=id,
            type_id=type_id,
            parameters=dict(parameters),
            children=tuple(children),
            pin_bindings=dict(pin_bindings or {}),
            coordinate_bindings=dict(coordinate_bindings or {}),
            parameter_bindings=dict(parameter_bindings or {}),
            internal_connections=tuple(internal_connections),
        )
        _validate_component(instance, self.types[type_id])
        return instance

    def identity(self) -> dict[str, Any]:
        if (
            not _nonempty_string(self.id)
            or not _nonempty_string(self.version)
            or not isinstance(self.source_sha256, str)
            or len(self.source_sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.source_sha256)
        ):
            raise RuntimeContractError(
                "CircuitLibrary source_sha256 must be an exact lowercase SHA-256 identity."
            )
        return {"id": self.id, "version": self.version, "source_sha256": self.source_sha256}


def circuit_component(
    *,
    type_id: str,
    pins: Sequence[str],
    parameters: Sequence[ParameterDeclaration | Mapping[str, Any]],
    coordinates: Sequence[CoordinateDeclaration | Mapping[str, Any] | str] = (),
    lowerer: str,
) -> Callable[[Callable[..., ComponentInstance]], Callable[..., ComponentInstance]]:
    """Attach a sealed runtime type declaration to a Python composition factory.

    The factory is run during Plan assembly only; it is never called by Julia.
    """

    declaration = ComponentType(
        type_id, tuple(pins), tuple(parameters), tuple(coordinates), lowerer
    )

    def decorate(factory: Callable[..., ComponentInstance]) -> Callable[..., ComponentInstance]:
        def checked(*args: Any, **kwargs: Any) -> ComponentInstance:
            instance = factory(*args, **kwargs)
            if (
                not isinstance(instance, ComponentInstance)
                or instance.type_id != declaration.type_id
            ):
                raise RuntimeContractError(
                    f"@circuit_component factory '{factory.__name__}' must return ComponentInstance type '{declaration.type_id}'."
                )
            return instance

        checked.__name__ = factory.__name__
        checked.__doc__ = factory.__doc__
        checked.__circuit_component_type__ = declaration
        return checked

    return decorate


_BUILTIN_PARALLEL_LC = ComponentType(
    "workbench.parallel_lc_resonator.v1",
    ("signal",),
    (
        ParameterDeclaration("capacitance_f", "F", "capacitance"),
        ParameterDeclaration("inductance_h", "H", "inductance"),
        ParameterDeclaration("conductance_s", "S", "conductance"),
    ),
    (CoordinateDeclaration("signal", "node_flux", "signal"),),
    lowerer="parallel_lc_resonator",
)
_BUILTIN_TRANSMISSION_LINE = ComponentType(
    "workbench.transmission_line.v1",
    ("head", "tail"),
    (
        ParameterDeclaration("length_m", "m", "length"),
        ParameterDeclaration("n_sections", "count", "discretization", variable_capable=False),
        ParameterDeclaration("l_per_m_h", "H/m", "inductance_density"),
        ParameterDeclaration("c_per_m_f", "F/m", "capacitance_density"),
        ParameterDeclaration("r_per_m_ohm", "Ohm/m", "resistance_density"),
        ParameterDeclaration("g_per_m_s", "S/m", "conductance_density"),
    ),
    (
        CoordinateDeclaration("head", "node_flux", "signal"),
        CoordinateDeclaration("tail", "node_flux", "signal"),
    ),
    lowerer="transmission_line",
)
_BUILTIN_LINEARIZED_FLOATING_QUBIT = ComponentType(
    "workbench.linearized_floating_qubit.v1",
    ("readout_attachment", "island_1", "island_2"),
    (
        ParameterDeclaration("c01_f", "F", "island_1_ground_capacitance"),
        ParameterDeclaration("c02_f", "F", "island_2_ground_capacitance"),
        ParameterDeclaration("c12_f", "F", "island_mutual_capacitance"),
        ParameterDeclaration("cr1_f", "F", "readout_island_1_capacitance"),
        ParameterDeclaration("cr2_f", "F", "readout_island_2_capacitance"),
        ParameterDeclaration("l_j_per_junction_h", "H", "josephson_inductance"),
        ParameterDeclaration(
            "josephson_branch_count", "count", "josephson_branch_count", variable_capable=False
        ),
    ),
    tuple(
        CoordinateDeclaration(name, "node_flux", "signal")
        for name in ("readout_attachment", "island_1", "island_2")
    ),
    lowerer="linearized_floating_qubit",
)
_IPF_PARAMETERS = (
    ("readout_open_length_m", "m", "readout_open_length"),
    ("shared_short_length_m", "m", "shared_short_length"),
    ("coupled_length_m", "m", "coupled_length"),
    ("filter_open_length_m", "m", "filter_open_length"),
    ("readout_short_sections", "count", "discretization"),
    ("readout_open_sections", "count", "discretization"),
    ("coupled_sections", "count", "discretization"),
    ("filter_short_sections", "count", "discretization"),
    ("filter_open_sections", "count", "discretization"),
    ("readout_l_per_m_h", "H/m", "readout_inductance_density"),
    ("readout_c_per_m_f", "F/m", "readout_capacitance_density"),
    ("filter_l_per_m_h", "H/m", "filter_inductance_density"),
    ("filter_c_per_m_f", "F/m", "filter_capacitance_density"),
    ("mtl_l11_per_m_h", "H/m", "mtl_inductance_matrix"),
    ("mtl_l12_per_m_h", "H/m", "mtl_inductance_matrix"),
    ("mtl_l21_per_m_h", "H/m", "mtl_inductance_matrix"),
    ("mtl_l22_per_m_h", "H/m", "mtl_inductance_matrix"),
    ("mtl_c11_per_m_f", "F/m", "mtl_capacitance_matrix"),
    ("mtl_c12_per_m_f", "F/m", "mtl_capacitance_matrix"),
    ("mtl_c21_per_m_f", "F/m", "mtl_capacitance_matrix"),
    ("mtl_c22_per_m_f", "F/m", "mtl_capacitance_matrix"),
    ("idc_finger_length_um", "um", "idc_finger_length"),
    ("idc_source_min_um", "um", "idc_fit_support"),
    ("idc_source_max_um", "um", "idc_fit_support"),
    ("idc_filter_ground_slope_f_per_um", "F/um", "idc_ols_coefficient"),
    ("idc_filter_ground_intercept_f", "F", "idc_ols_coefficient"),
    ("idc_feedline_ground_slope_f_per_um", "F/um", "idc_ols_coefficient"),
    ("idc_feedline_ground_intercept_f", "F", "idc_ols_coefficient"),
    ("idc_mutual_slope_f_per_um", "F/um", "idc_ols_coefficient"),
    ("idc_mutual_intercept_f", "F", "idc_ols_coefficient"),
    ("c0r_f", "F", "readout_attachment_ground_capacitance"),
)
_IPF_SECTION_PARAMETERS = {
    "readout_short_sections",
    "readout_open_sections",
    "coupled_sections",
    "filter_short_sections",
    "filter_open_sections",
}
_BUILTIN_INTRINSIC_INTERFEROMETRIC_PURCELL_FILTER = ComponentType(
    "workbench.intrinsic_interferometric_purcell_filter.v1",
    ("readout_attachment", "feedline_attachment"),
    tuple(
        ParameterDeclaration(*item, variable_capable=item[0] not in _IPF_SECTION_PARAMETERS)
        for item in _IPF_PARAMETERS
    ),
    (
        CoordinateDeclaration("readout_attachment", "node_flux", "signal"),
        CoordinateDeclaration("filter_open_tail", "node_flux", "signal"),
    ),
    lowerer="intrinsic_interferometric_purcell_filter",
)
_BUILTIN_TYPES = (
    _BUILTIN_PARALLEL_LC,
    _BUILTIN_TRANSMISSION_LINE,
    _BUILTIN_LINEARIZED_FLOATING_QUBIT,
    _BUILTIN_INTRINSIC_INTERFEROMETRIC_PURCELL_FILTER,
)
_BUILTIN_LIBRARY = CircuitLibrary(
    id="workbench.core.catalog",
    version="1",
    source_sha256=hashlib.sha256(
        json.dumps(
            [asdict(item) for item in _BUILTIN_TYPES], sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest(),
    types={item.type_id: item for item in _BUILTIN_TYPES},
)


@dataclass(frozen=True)
class ReductionSpec:
    retained: tuple[CoordinateRef, ...]
    transforms: tuple[Mapping[str, Any], ...] = ()
    eliminated: Literal["complete_complement"] = "complete_complement"


@dataclass(frozen=True)
class CircuitObjective:
    cared_outputs: Mapping[str, Mapping[str, Any]]
    residuals: Mapping[str, Mapping[str, Any]]
    cost: Mapping[str, Any]

    @classmethod
    def from_targets(cls, declaration: Mapping[str, Any]) -> CircuitObjective:
        """Compile visible targets and weights to the restricted Julia objective AST.

        ``declaration`` has exactly three mappings: ``outputs`` contains the
        existing cared-output declarations, ``values`` maps each output id to a
        nonzero target, and ``weights`` maps the same ids to positive weights.
        Target meaning and values remain consumer-owned; this helper only owns
        the mechanical relative-residual expression.
        """

        if not isinstance(declaration, Mapping) or set(declaration) != {
            "outputs",
            "values",
            "weights",
        }:
            raise RuntimeContractError(
                "CircuitObjective.from_targets requires only outputs, values, and weights."
            )
        outputs = declaration["outputs"]
        values = declaration["values"]
        weights = declaration["weights"]
        if not all(isinstance(item, Mapping) and item for item in (outputs, values, weights)):
            raise RuntimeContractError(
                "CircuitObjective targets require nonempty outputs, values, and weights mappings."
            )
        names = set(outputs)
        if set(values) != names or set(weights) != names:
            raise RuntimeContractError(
                "CircuitObjective target values and weights must exactly match output ids."
            )
        residuals: dict[str, Mapping[str, Any]] = {}
        weighted: list[Mapping[str, Any]] = []
        for name in sorted(names):
            target = values[name]
            weight = weights[name]
            if (
                isinstance(target, bool)
                or not isinstance(target, (int, float))
                or not math.isfinite(float(target))
                or float(target) == 0.0
            ):
                raise RuntimeContractError(
                    f"CircuitObjective target '{name}' must be finite and nonzero."
                )
            if (
                isinstance(weight, bool)
                or not isinstance(weight, (int, float))
                or not math.isfinite(float(weight))
                or float(weight) <= 0.0
            ):
                raise RuntimeContractError(
                    f"CircuitObjective weight '{name}' must be finite and positive."
                )
            residual_id = f"relative_{name}"
            residuals[residual_id] = {
                "op": "div",
                "args": [
                    {
                        "op": "sub",
                        "args": [{"output": name}, {"const": float(target)}],
                    },
                    {"const": float(target)},
                ],
            }
            weighted.append(
                {
                    "op": "mul",
                    "args": [
                        {"const": float(weight)},
                        {"output": residual_id},
                    ],
                }
            )
        return cls(
            cared_outputs={str(name): dict(outputs[name]) for name in sorted(names)},
            residuals=residuals,
            cost={"op": "sum_squares", "args": weighted},
        )


@dataclass(frozen=True)
class ResponseSpec:
    frequency_hz: tuple[float, ...]
    input_port: str
    output_port: str
    pump_frequency_hz: float

    def __post_init__(self) -> None:
        values = tuple(float(value) for value in self.frequency_hz)
        if (
            len(values) < 3
            or any(not math.isfinite(value) or value <= 0.0 for value in values)
            or any(right <= left for left, right in pairwise(values))
        ):
            raise RuntimeContractError(
                "ResponseSpec frequency_hz must be a strictly increasing positive grid."
            )
        if not _nonempty_string(self.input_port) or not _nonempty_string(self.output_port):
            raise RuntimeContractError("ResponseSpec requires named input and output ports.")
        if self.input_port == self.output_port:
            raise RuntimeContractError("ResponseSpec input and output ports must differ.")
        if not math.isfinite(self.pump_frequency_hz) or self.pump_frequency_hz <= 0.0:
            raise RuntimeContractError("ResponseSpec pump_frequency_hz must be positive.")
        object.__setattr__(self, "frequency_hz", values)


@dataclass(frozen=True)
class T1Spec:
    frequency_hz: tuple[float, ...]
    feedline_ports: tuple[str, str]
    qubit_probe_ports: tuple[str, str]
    common_mode_weights: tuple[float, float]
    pump_frequency_hz: float

    def __post_init__(self) -> None:
        values = tuple(float(value) for value in self.frequency_hz)
        ports = (*self.feedline_ports, *self.qubit_probe_ports)
        alpha, beta = (float(value) for value in self.common_mode_weights)
        if (
            len(values) < 3
            or any(not math.isfinite(value) or value <= 0.0 for value in values)
            or any(right <= left for left, right in pairwise(values))
        ):
            raise RuntimeContractError(
                "T1Spec frequency_hz must be a strictly increasing positive grid."
            )
        if any(not _nonempty_string(port) for port in ports) or len(set(ports)) != 4:
            raise RuntimeContractError("T1Spec requires four unique named ports.")
        if (
            not math.isfinite(alpha)
            or not math.isfinite(beta)
            or not math.isclose(alpha + beta, 1.0, rel_tol=0.0, abs_tol=1.0e-9)
        ):
            raise RuntimeContractError("T1Spec common-mode weights must be finite and sum to one.")
        if not math.isfinite(self.pump_frequency_hz) or self.pump_frequency_hz <= 0.0:
            raise RuntimeContractError("T1Spec pump_frequency_hz must be positive.")
        object.__setattr__(self, "frequency_hz", values)
        object.__setattr__(self, "common_mode_weights", (alpha, beta))


@dataclass(frozen=True)
class GateSpec:
    id: str
    expression: Mapping[str, Any]
    state: Literal["active", "proposed", "inactive"]
    human_authority: str | None = None


@dataclass(frozen=True)
class VariableSpec:
    ref: ParameterRef
    transform: Literal["identity", "log", "unit_interval"] = "identity"
    lower: float | None = None
    upper: float | None = None


@dataclass(frozen=True)
class OptimizerSpec:
    algorithm: str
    seed: int
    human_authority: str | None = None
    resource_controls: Mapping[str, int] = field(default_factory=dict)
    controls: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Connection:
    left: EndpointRef
    right: EndpointRef


@dataclass(frozen=True)
class _Port:
    id: str
    endpoint: EndpointRef
    resistance_ohm: float


@dataclass
class CircuitPlan:
    id: str
    _components: dict[str, ComponentInstance] = field(default_factory=dict, init=False)
    _connections: list[_Connection] = field(default_factory=list, init=False)
    _ports: list[_Port] = field(default_factory=list, init=False)

    def add(self, component: ComponentInstance) -> ComponentInstance:
        if not isinstance(component, ComponentInstance) or not component.id:
            raise RuntimeContractError("CircuitPlan.add requires a nonempty ComponentInstance.")
        if component.id in self._components:
            raise RuntimeContractError(f"Duplicate component instance id '{component.id}'.")
        self._components[component.id] = component
        return component

    def connect(self, left: EndpointRef, right: EndpointRef) -> None:
        self._connections.append(_Connection(_endpoint(left), _endpoint(right)))

    def add_port(self, id: str, endpoint: EndpointRef, *, resistance_ohm: float = 50.0) -> None:
        if not id or any(port.id == id for port in self._ports):
            raise RuntimeContractError("Port ids must be nonempty and unique.")
        if not math.isfinite(resistance_ohm) or resistance_ohm <= 0:
            raise RuntimeContractError("Port resistance_ohm must be finite and positive.")
        self._ports.append(_Port(id, _endpoint(endpoint), float(resistance_ohm)))

    def seal(self, libraries: Sequence[CircuitLibrary]) -> dict[str, Any]:
        resolved = _resolve_types(libraries)
        if not self.id or not self._components:
            raise RuntimeContractError(
                "A sealed CircuitPlan requires an id and at least one component."
            )
        (
            components,
            endpoint_bindings,
            coordinate_bindings,
            parameter_bindings,
            internal_connections,
        ) = _elaborate_components(self._components, resolved)
        for connection in self._connections:
            _resolve_endpoint(connection.left, endpoint_bindings)
            _resolve_endpoint(connection.right, endpoint_bindings)
        for port in self._ports:
            _resolve_endpoint(port.endpoint, endpoint_bindings)
        payload: dict[str, Any] = {
            "schema": PLAN_SCHEMA,
            "id": self.id,
            "libraries": [library.identity() for library in libraries],
            "component_types": [
                _plain(item) for item in sorted(resolved.values(), key=lambda value: value.type_id)
            ],
            "engineering_graph": {
                "root_components": [_plain(item) for item in self._components.values()]
            },
            "components": components,
            "connections": [
                {
                    "left": _plain(_resolve_endpoint(item.left, endpoint_bindings)),
                    "right": _plain(_resolve_endpoint(item.right, endpoint_bindings)),
                }
                for item in (*self._connections, *internal_connections)
            ],
            "ports": [
                {
                    "id": item.id,
                    "endpoint": _plain(_resolve_endpoint(item.endpoint, endpoint_bindings)),
                    "resistance_ohm": item.resistance_ohm,
                }
                for item in self._ports
            ],
            "exposed_coordinates": [
                _plain(value) for _, value in sorted(coordinate_bindings.items())
            ],
            "coordinate_bindings": {
                key: _plain(value) for key, value in sorted(coordinate_bindings.items())
            },
            "exposed_parameters": [
                _plain(value) for _, value in sorted(parameter_bindings.items())
            ],
            "parameter_bindings": {
                key: _plain(value) for key, value in sorted(parameter_bindings.items())
            },
            "schematic_intent": _schematic_intent(
                components,
                (*self._connections, *internal_connections),
                self._ports,
                endpoint_bindings,
            ),
        }
        payload["canonical_sha256"] = _fingerprint(payload)
        return payload

    def show(self, libraries: Sequence[CircuitLibrary] = ()) -> Any:
        """Validate and render the sealed topology through Schemdraw without Julia."""

        from ._runtime_plan import render_runtime_plan

        sealed = self.seal((_BUILTIN_LIBRARY, *libraries))
        drawing = render_runtime_plan(sealed)
        cast(Any, drawing).circuit_workbench_plan = sealed
        return drawing


@dataclass
class CircuitSim:
    run_root: Path | str
    run_id: str
    lifecycle_state: Literal["CONVERGING", "ACCEPTED", "STABILIZED"] = "CONVERGING"
    data_classification: Literal[
        "public", "project-internal", "NCUAS-private", "report-safe-derived"
    ] = "project-internal"
    _libraries: list[CircuitLibrary] = field(default_factory=lambda: [_BUILTIN_LIBRARY], init=False)
    _plan: CircuitPlan | None = field(default=None, init=False)
    _artifacts: dict[str, Mapping[str, Any]] = field(default_factory=dict, init=False)
    _reduction: ReductionSpec | None = field(default=None, init=False)
    _objective: CircuitObjective | None = field(default=None, init=False)
    _gates: list[GateSpec] = field(default_factory=list, init=False)
    _variables: list[VariableSpec] = field(default_factory=list, init=False)
    _optimizer: OptimizerSpec | None = field(default=None, init=False)
    _refinement_plan: CircuitPlan | None = field(default=None, init=False)
    _refinement_tolerance: float | None = field(default=None, init=False)
    _response: ResponseSpec | None = field(default=None, init=False)
    _t1: T1Spec | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if (
            not _nonempty_string(self.run_id)
            or Path(self.run_id).name != self.run_id
            or self.run_id in {".", ".."}
        ):
            raise RuntimeContractError("run_id must be one path-safe directory name.")
        if self.lifecycle_state not in _LIFECYCLE_STATES:
            raise RuntimeContractError(
                "lifecycle_state must be CONVERGING, ACCEPTED, or STABILIZED."
            )
        if self.data_classification not in _DATA_CLASSIFICATIONS:
            raise RuntimeContractError(
                "data_classification must be public, project-internal, NCUAS-private, or report-safe-derived."
            )

    def register_library(self, library: CircuitLibrary) -> None:
        if not isinstance(library, CircuitLibrary):
            raise RuntimeContractError("register_library requires CircuitLibrary.")
        library.identity()
        if any(existing.id == library.id for existing in self._libraries):
            raise RuntimeContractError(f"Duplicate registered library id '{library.id}'.")
        self._libraries.append(library)

    def set_plan(self, plan: CircuitPlan) -> None:
        if not isinstance(plan, CircuitPlan):
            raise RuntimeContractError("set_plan requires CircuitPlan.")
        sealed = plan.seal(self._libraries)
        builtin_leaves = set(_BUILTIN_LIBRARY.types)
        if any(component["type_id"] not in builtin_leaves for component in sealed["components"]):
            raise RuntimeContractError(
                "Circuit Workbench V1 accepts only registered composite types and built-in leaf lowerers."
            )
        self._plan = plan

    def bind_artifact(
        self,
        name: str,
        path: Path | str,
        *,
        schema: str,
        units: str | Mapping[str, Any],
        provenance: Mapping[str, Any],
    ) -> None:
        if not _nonempty_string(name):
            raise RuntimeContractError("Artifact bindings require a nonempty name.")
        if (
            not _nonempty_string(schema)
            or not (_nonempty_string(units) or (isinstance(units, Mapping) and bool(units)))
            or not isinstance(provenance, Mapping)
            or not provenance
        ):
            raise RuntimeContractError(
                "Artifact binding requires declared schema, units, and provenance."
            )
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise RuntimeContractError("Artifact binding requires a readable bound file path.")
        sealed = {
            "schema": schema,
            "units": units,
            "provenance": dict(provenance),
            "path": str(resolved),
            "source_sha256": _sha256(resolved.read_bytes()),
        }
        try:
            _canonical_bytes(sealed)
        except (TypeError, ValueError) as error:
            raise RuntimeContractError(
                "Artifact binding must be canonical-JSON serializable."
            ) from error
        self._artifacts[name] = sealed

    def set_reduction(self, spec: ReductionSpec) -> None:
        if not isinstance(spec, ReductionSpec):
            raise RuntimeContractError("set_reduction requires ReductionSpec.")
        self._reduction = spec

    def set_objective(self, spec: CircuitObjective) -> None:
        if not isinstance(spec, CircuitObjective):
            raise RuntimeContractError("set_objective requires CircuitObjective.")
        if not spec.cared_outputs or not spec.residuals or not spec.cost:
            raise RuntimeContractError(
                "CircuitObjective requires cared outputs, residuals, and cost expression."
            )
        targeted_anchors: tuple[Any, Any, Any] | None = None
        for name, cared in spec.cared_outputs.items():
            if not name or not isinstance(cared, Mapping):
                raise RuntimeContractError(
                    "Objective cared outputs require nonempty ids and mappings."
                )
            kind = cared.get("kind")
            if not isinstance(kind, str):
                raise RuntimeContractError(f"Cared output '{name}' requires a string kind.")
            allowed = {
                "closed_mode_frequency_hz": {"kind", "mode_index"},
                "schur_dynamic_stiffness_abs": {"kind", "frequency_hz", "row", "column"},
                "s_parameter": {"kind", "frequency_hz", "output_port", "input_port", "part"},
                "targeted_schur": {
                    "kind",
                    "quantity",
                    "readout_root_anchor_hz",
                    "filter_root_anchor_hz",
                    "transfer_zero_anchor_hz",
                },
            }.get(kind)
            if allowed is None or set(cared) != allowed:
                raise RuntimeContractError(
                    f"Unsupported or malformed cared-output declaration '{name}'."
                )
            _validate_cared_output(name, cared)
            if kind == "targeted_schur":
                anchors = tuple(
                    cared[field_name]
                    for field_name in (
                        "readout_root_anchor_hz",
                        "filter_root_anchor_hz",
                        "transfer_zero_anchor_hz",
                    )
                )
                if targeted_anchors is not None and anchors != targeted_anchors:
                    raise RuntimeContractError(
                        "All targeted-Schur cared outputs must use identical anchors."
                    )
                targeted_anchors = anchors
        for expression in spec.residuals.values():
            _validate_expression(expression, set(spec.cared_outputs))
        _validate_expression(spec.cost, set(spec.residuals))
        self._objective = spec

    def set_refinement(
        self,
        *,
        plan: CircuitPlan,
        relative_tolerance: float,
    ) -> None:
        if not isinstance(plan, CircuitPlan):
            raise RuntimeContractError("set_refinement requires a CircuitPlan.")
        plan.seal(self._libraries)
        if (
            isinstance(relative_tolerance, bool)
            or not isinstance(relative_tolerance, (int, float))
            or not math.isfinite(float(relative_tolerance))
            or float(relative_tolerance) < 0.0
        ):
            raise RuntimeContractError(
                "set_refinement relative_tolerance must be finite and nonnegative."
            )
        self._refinement_plan = plan
        self._refinement_tolerance = float(relative_tolerance)

    def set_responses(self, spec: ResponseSpec) -> None:
        if not isinstance(spec, ResponseSpec):
            raise RuntimeContractError("set_responses requires ResponseSpec.")
        self._response = spec

    def set_t1(self, spec: T1Spec) -> None:
        if not isinstance(spec, T1Spec):
            raise RuntimeContractError("set_t1 requires T1Spec.")
        self._t1 = spec

    def set_gates(self, specs: Sequence[GateSpec]) -> None:
        if self._objective is None:
            raise RuntimeContractError(
                "set_gates requires set_objective first for cared-output validation."
            )
        ids: set[str] = set()
        for spec in specs:
            if (
                not isinstance(spec, GateSpec)
                or not _nonempty_string(spec.id)
                or spec.id in ids
                or spec.state not in {"active", "proposed", "inactive"}
            ):
                raise RuntimeContractError(
                    "Gate ids must be unique and states must be active, proposed, or inactive."
                )
            ids.add(spec.id)
            if spec.state == "active" and not spec.human_authority:
                raise RuntimeContractError(f"Active Gate '{spec.id}' lacks exact Human authority.")
            _validate_expression(spec.expression, set(self._objective.cared_outputs))
        self._gates = list(specs)

    def set_variables(self, specs: Sequence[VariableSpec]) -> None:
        if any(
            not isinstance(spec, VariableSpec) or not isinstance(spec.ref, ParameterRef)
            for spec in specs
        ):
            raise RuntimeContractError(
                "set_variables requires VariableSpec values with ParameterRef bindings."
            )
        self._variables = list(specs)

    def set_optimizer(self, spec: OptimizerSpec) -> None:
        if (
            not isinstance(spec, OptimizerSpec)
            or spec.algorithm != "cma_es"
            or isinstance(spec.seed, bool)
            or not isinstance(spec.seed, int)
            or spec.seed < 0
            or not spec.human_authority
            or set(spec.resource_controls) - {"worker_count"}
        ):
            raise RuntimeContractError(
                "Optimizer requires algorithm='cma_es', exact Human authority, integer seed, and only worker_count resource control."
            )
        if spec.resource_controls.get("worker_count", 1) < 1:
            raise RuntimeContractError("worker_count must be positive.")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in spec.resource_controls.values()
        ):
            raise RuntimeContractError("Optimizer resource controls must be positive integers.")
        if set(spec.controls) != {"initial_sigma", "maxiter", "maxfevals", "popsize"}:
            raise RuntimeContractError("Optimizer controls contain an unsupported V1 field.")
        sigma = spec.controls["initial_sigma"]
        if (
            isinstance(sigma, bool)
            or not isinstance(sigma, (int, float))
            or not math.isfinite(float(sigma))
            or sigma <= 0
        ):
            raise RuntimeContractError(
                "Optimizer control initial_sigma must be finite and positive."
            )
        for name in ("maxiter", "maxfevals", "popsize"):
            value = spec.controls.get(name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise RuntimeContractError(f"Optimizer control {name} must be a positive integer.")
        self._optimizer = spec

    def optimize(
        self, *, action: Literal["execute", "resolve"]
    ) -> ResolvedCircuitStage:
        if action == "resolve":
            return self._resolve_stage("optimize")
        _validate_stage_action(action)
        if self._optimizer is None:
            raise RuntimeContractError("optimize requires set_optimizer first.")
        if self._optimizer.algorithm != "cma_es":
            raise RuntimeContractError("Circuit Workbench V1 supports only algorithm='cma_es'.")
        if not self._variables:
            raise RuntimeContractError("optimize requires at least one declared VariableSpec.")
        request = self._request(action="optimize", backend="direct")
        return self._run_julia(request, "optimize")

    def refine_winner(
        self, *, action: Literal["execute", "resolve"]
    ) -> ResolvedCircuitStage:
        if action == "resolve":
            return self._resolve_stage("refine_winner")
        _validate_stage_action(action)
        if (
            self._refinement_plan is None
            or self._refinement_tolerance is None
        ):
            raise RuntimeContractError("refine_winner requires set_refinement first.")
        optimization = self._require_stage("optimize")
        result = _mapping(optimization.receipt.get("result"), "optimization result")
        best = _mapping(result.get("best"), "optimization winner")
        overrides = _mapping(
            result.get("winner_physical_parameters"), "optimization winner parameters"
        )
        request = self._request(
            action="refine_winner",
            backend="direct",
            plan=self._refinement_plan,
            extras={
                "parameter_overrides": overrides,
                "coarse_outputs": _mapping(best.get("cared_outputs"), "winner cared outputs"),
                "relative_tolerance": self._refinement_tolerance,
                "upstream_receipts": {"optimize": optimization.canonical_sha256},
            },
        )
        return self._run_julia(request, "refine_winner")

    def evaluate_responses(
        self, *, action: Literal["execute", "resolve"]
    ) -> ResolvedCircuitStage:
        if action == "resolve":
            return self._resolve_stage("evaluate_responses")
        _validate_stage_action(action)
        if self._response is None:
            raise RuntimeContractError("evaluate_responses requires set_responses first.")
        optimization = self._require_stage("optimize")
        refinement = self._require_stage("refine_winner")
        winner = _mapping(optimization.receipt.get("result"), "optimization result")
        request = self._request(
            action="evaluate_responses",
            backend="direct_hb",
            extras={
                "parameter_overrides": _mapping(
                    winner.get("winner_physical_parameters"), "optimization winner parameters"
                ),
                "response": _plain(self._response),
                "upstream_receipts": {
                    "optimize": optimization.canonical_sha256,
                    "refine_winner": refinement.canonical_sha256,
                },
            },
        )
        return self._run_julia(request, "evaluate_responses")

    def fit_c11(
        self, *, action: Literal["execute", "resolve"]
    ) -> ResolvedCircuitStage:
        if action == "resolve":
            return self._resolve_stage("fit_c11")
        _validate_stage_action(action)
        responses = self._require_stage("evaluate_responses")
        request = self._request(
            action="fit_c11",
            backend="python",
            extras={
                "upstream_receipts": {
                    "evaluate_responses": responses.canonical_sha256,
                }
            },
        )
        return self._run_python_stage(
            request,
            "fit_c11",
            lambda directory: _fit_c11_stage(directory, responses),
        )

    def evaluate_t1(
        self, *, action: Literal["execute", "resolve"]
    ) -> ResolvedCircuitStage:
        if action == "resolve":
            return self._resolve_stage("evaluate_t1")
        _validate_stage_action(action)
        if self._t1 is None:
            raise RuntimeContractError("evaluate_t1 requires set_t1 first.")
        optimization = self._require_stage("optimize")
        c11 = self._require_stage("fit_c11")
        winner = _mapping(optimization.receipt.get("result"), "optimization result")
        request = self._request(
            action="evaluate_t1",
            backend="hb",
            extras={
                "parameter_overrides": _mapping(
                    winner.get("winner_physical_parameters"), "optimization winner parameters"
                ),
                "t1": _plain(self._t1),
                "upstream_receipts": {
                    "optimize": optimization.canonical_sha256,
                    "fit_c11": c11.canonical_sha256,
                },
            },
        )
        return self._run_julia(request, "evaluate_t1")

    def build_report(
        self, *, action: Literal["execute", "resolve"]
    ) -> ResolvedCircuitStage:
        if action == "resolve":
            return self._resolve_stage("build_report")
        _validate_stage_action(action)
        upstream = {name: self._require_stage(name) for name in STAGE_ORDER[:-1]}
        request = self._request(
            action="build_report",
            backend="python",
            extras={
                "upstream_receipts": {
                    name: stage.canonical_sha256 for name, stage in upstream.items()
                }
            },
        )
        return self._run_python_stage(
            request,
            "build_report",
            lambda directory: _build_report_stage(directory, self.run_id, upstream),
        )

    def _request(
        self,
        *,
        action: str,
        backend: str,
        plan: CircuitPlan | None = None,
        extras: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        selected_plan = plan or self._plan
        if selected_plan is None:
            raise RuntimeContractError(f"{action} requires set_plan first.")
        if self._objective is None:
            raise RuntimeContractError(f"{action} requires set_objective first.")
        sealed_plan = selected_plan.seal(self._libraries)
        if self._reduction is not None:
            exposed = set(sealed_plan["coordinate_bindings"])
            if self._reduction.eliminated != "complete_complement" or not self._reduction.retained:
                raise RuntimeContractError(
                    "ReductionSpec requires ordered retained coordinates and complete_complement."
                )
            for ref in self._reduction.retained:
                if f"{ref.component_id}.{ref.coordinate_name}" not in exposed:
                    raise RuntimeContractError(
                        "ReductionSpec references a coordinate not exposed by the sealed Plan."
                    )
            reduction = _resolved_reduction(self._reduction, sealed_plan)
        else:
            reduction = None
        cared_kinds = {item["kind"] for item in self._objective.cared_outputs.values()}
        if action in {"optimize", "refine_winner"} and backend == "direct":
            if cared_kinds <= {"closed_mode_frequency_hz"}:
                if reduction is not None:
                    raise RuntimeContractError(
                        "Closed-mode direct requests cannot carry an ignored ReductionSpec."
                    )
            elif cared_kinds <= {"schur_dynamic_stiffness_abs"}:
                if reduction is None:
                    raise RuntimeContractError(
                        "Direct Schur cared outputs require an explicit ReductionSpec."
                    )
            elif cared_kinds == {"targeted_schur"}:
                if reduction is None:
                    raise RuntimeContractError(
                        "Targeted Schur cared outputs require an explicit ReductionSpec."
                    )
            else:
                raise RuntimeContractError(
                    "Direct backend supports one cared-output family, not a mixture."
                )
        elif action in {"evaluate_responses", "evaluate_t1", "fit_c11", "build_report"}:
            pass
        else:
            raise RuntimeContractError(
                f"Unsupported Circuit Workbench staged action/backend: {action}/{backend}."
            )
        julia = _resolved_julia_executable()
        payload: dict[str, Any] = {
            "schema": REQUEST_SCHEMA,
            "action": action,
            "backend": backend,
            "run_id": self.run_id,
            "lifecycle_state": self.lifecycle_state,
            "data_classification": self.data_classification,
            "plan": sealed_plan,
            "artifacts": self._artifacts,
            "reduction": reduction,
            "objective": _plain(self._objective),
            "gates": [_plain(item) for item in self._gates],
            "variables": _resolved_variables(self._variables, sealed_plan),
            "optimizer": _plain(self._optimizer) if self._optimizer else None,
            "runtime": {
                "python": sys.version.split()[0],
                "python_package_source_sha256": _tree_sha256(
                    _PACKAGE_ROOT, excluded_top_level={"_julia"}
                ),
                "runner_tree_sha256": _tree_sha256(_RUNNER_PROJECT, excluded_top_level={"test"}),
                "core_tree_sha256": _tree_sha256(
                    _JULIA_ROOT / "SuperconductingCircuitsCore",
                    excluded_top_level={"test"},
                ),
                "julia_executable_path": str(julia),
                "julia_executable_sha256": _sha256(julia.read_bytes()),
            },
        }
        if extras:
            overlap = set(payload) & set(extras)
            if overlap:
                raise RuntimeContractError(
                    f"Stage request extras overlap reserved fields: {sorted(overlap)}."
                )
            payload.update(dict(extras))
        payload["fingerprint_sha256"] = _fingerprint(payload)
        return payload

    def _run_julia(
        self, request: Mapping[str, Any], stage: str
    ) -> ResolvedCircuitStage:
        if not (_RUNNER_PROJECT / "Project.toml").is_file() or not _RUNNER_CLI.is_file():
            raise RuntimeContractError(
                "Circuit Workbench Runner source project is unavailable; this source-editable runtime cannot launch Julia."
            )
        stage_dir = self._stage_dir(stage)
        if stage_dir.exists():
            raise RuntimeContractError(
                f"Stage '{stage}' already has durable bytes; use action='resolve' or a fresh run_id."
            )
        stage_dir.mkdir(parents=True)
        receipt = stage_dir / "circuit-workbench-run-receipt.v1.json"
        request_path = stage_dir / "circuit-workbench-run-request.v1.json"
        request_bytes = _canonical_bytes(request)
        _atomic_write(request_path, request_bytes)
        optimizer = request.get("optimizer")
        worker_count = (
            int(optimizer.get("resource_controls", {}).get("worker_count", 1))
            if isinstance(optimizer, Mapping)
            else 1
        )
        completed = subprocess.run(
            [
                str(_resolved_julia_executable()),
                "--startup-file=no",
                f"--threads={worker_count}",
                f"--project={_RUNNER_PROJECT}",
                str(_RUNNER_CLI),
                str(request_path),
                str(receipt),
            ],
            text=True,
        )
        if receipt.is_file():
            sealed = self._resolve_stage(stage)
            if completed.returncode:
                failure = sealed.receipt.get("failure")
                message = failure.get("message") if isinstance(failure, Mapping) else None
                error_code = (
                    failure.get("error_code")
                    if isinstance(failure, Mapping)
                    else "circuit_workbench_action_failed"
                )
                category = (
                    failure.get("category")
                    if isinstance(failure, Mapping)
                    else "task_execution_failed"
                )
                retryable = failure.get("retryable") if isinstance(failure, Mapping) else False
                if not isinstance(error_code, str) or not error_code:
                    error_code = "circuit_workbench_action_failed"
                if not isinstance(category, str) or not category:
                    category = "task_execution_failed"
                raise RuntimeContractError(
                    "Julia action failed after sealing its failure receipt"
                    f" (exit status {completed.returncode}): {message or 'no failure message'}",
                    error_code=error_code,
                    category=category,
                    retryable=retryable if isinstance(retryable, bool) else False,
                )
            return sealed
        raise RuntimeContractError(
            f"Julia action exited without sealing a receipt (exit status {completed.returncode})."
        )

    def _run_python_stage(
        self,
        request: Mapping[str, Any],
        stage: str,
        operation: Callable[[Path], Mapping[str, Any]],
    ) -> ResolvedCircuitStage:
        stage_dir = self._stage_dir(stage)
        if stage_dir.exists():
            raise RuntimeContractError(
                f"Stage '{stage}' already has durable bytes; use action='resolve' or a fresh run_id."
            )
        run_dir = stage_dir.parent.parent
        run_dir.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{stage}-", dir=run_dir))
        try:
            request_path = temporary / "circuit-workbench-run-request.v1.json"
            _atomic_write(request_path, _canonical_bytes(request))
            started = time.perf_counter()
            result = dict(operation(temporary))
            result["wall_seconds"] = time.perf_counter() - started
            receipt = _python_stage_receipt(
                request,
                request_path,
                result,
                durable_request_path=stage_dir
                / "circuit-workbench-run-request.v1.json",
                durable_stage_dir=stage_dir,
            )
            _atomic_write(
                temporary / "circuit-workbench-run-receipt.v1.json",
                _canonical_bytes(receipt),
            )
            temporary.replace(stage_dir)
        except Exception as error:
            if temporary.exists() and request_path.is_file():
                failure = {
                    "error_code": getattr(error, "error_code", "circuit_workbench_action_failed"),
                    "category": getattr(error, "category", "task_execution_failed"),
                    "retryable": getattr(error, "retryable", False),
                    "type": type(error).__name__,
                    "message": str(error),
                }
                receipt = _python_stage_receipt(
                    request,
                    request_path,
                    None,
                    durable_request_path=stage_dir
                    / "circuit-workbench-run-request.v1.json",
                    durable_stage_dir=stage_dir,
                    failure=failure,
                )
                _atomic_write(
                    temporary / "circuit-workbench-run-receipt.v1.json",
                    _canonical_bytes(receipt),
                )
                temporary.replace(stage_dir)
                raise RuntimeContractError(
                    f"Python stage failed after sealing its failure receipt: {error}",
                    error_code=str(failure["error_code"]),
                    category=str(failure["category"]),
                    retryable=bool(failure["retryable"]),
                ) from error
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return self._resolve_stage(stage)

    def _resolve_stage(self, stage: str) -> ResolvedCircuitStage:
        return resolve_circuit_result(self._run_dir()).stage(stage)

    def _require_stage(self, stage: str) -> ResolvedCircuitStage:
        resolved = self._resolve_stage(stage)
        if resolved.status != "PASS":
            raise RuntimeContractError(
                f"Stage '{stage}' is not a complete PASS dependency: {resolved.failure or resolved.status}."
            )
        return resolved

    def _run_dir(self) -> Path:
        root = Path(self.run_root).resolve()
        target = (root / self.run_id).resolve()
        if not target.is_relative_to(root):
            raise RuntimeContractError("run_id escapes run_root.")
        return target

    def _stage_dir(self, stage: str) -> Path:
        if stage not in STAGE_ORDER:
            raise RuntimeContractError(f"Unknown Circuit Workbench stage '{stage}'.")
        return self._run_dir() / "stages" / stage


def _validate_stage_action(action: str) -> None:
    if action not in _STAGE_ACTIONS:
        raise RuntimeContractError("Stage action must be 'execute' or 'resolve'.")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeContractError(f"{label} must be an object.")
    return value


@dataclass(frozen=True)
class _HtmlView:
    html_text: str

    def _repr_html_(self) -> str:
        return self.html_text

    def __str__(self) -> str:
        return self.html_text


@dataclass(frozen=True)
class ResolvedCircuitStage(Mapping[str, Any]):
    name: str
    path: Path
    receipt: Mapping[str, Any]
    status: str
    failure: str | None = None

    def __getitem__(self, key: str) -> Any:
        return self.receipt[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.receipt)

    def __len__(self) -> int:
        return len(self.receipt)

    @property
    def result(self) -> Mapping[str, Any] | None:
        value = self.receipt.get("result")
        return value if isinstance(value, Mapping) else None

    @property
    def canonical_sha256(self) -> str:
        value = self.receipt.get("canonical_sha256")
        return str(value) if isinstance(value, str) else ""

    def show(self) -> _HtmlView:
        return _HtmlView(
            _html_table(
                ("Field", "Value"),
                (
                    ("Stage", self.name),
                    ("Status", self.status),
                    ("Receipt", str(self.path)),
                    ("Receipt SHA-256", self.canonical_sha256 or "NOT_AVAILABLE"),
                    ("Failure", self.failure or "—"),
                ),
            )
        )


@dataclass(frozen=True)
class ResolvedCircuitResult:
    run_dir: Path
    stages: Mapping[str, ResolvedCircuitStage]

    @property
    def run_id(self) -> str:
        return self.run_dir.name

    @property
    def status(self) -> str:
        return (
            "PASS"
            if all(self.stages[name].status == "PASS" for name in STAGE_ORDER)
            else "NOT_EVALUABLE"
        )

    def stage(self, name: str) -> ResolvedCircuitStage:
        if name not in STAGE_ORDER:
            raise RuntimeContractError(f"Unknown Circuit Workbench stage '{name}'.")
        return self.stages[name]

    def show_run_trustworthiness(self) -> _HtmlView:
        rows = [
            (
                name,
                self.stages[name].status,
                self.stages[name].canonical_sha256 or "—",
                self.stages[name].failure or "—",
            )
            for name in STAGE_ORDER
        ]
        return _HtmlView(
            f"<h3>{html.escape(self.run_id)} · {self.status}</h3>"
            + _html_table(("Stage", "Status", "Receipt SHA-256", "Failure"), rows)
        )

    def show_optimization(self) -> _HtmlView:
        stage = self.stage("optimize")
        if stage.status != "PASS" or stage.result is None:
            return stage.show()
        result = stage.result
        best = result.get("best") if isinstance(result.get("best"), Mapping) else {}
        rows = (
            ("Candidate count", result.get("candidate_count", "—")),
            ("Generation count", result.get("generation_count", "—")),
            ("Stop reason", result.get("optimizer_stop_reason", "—")),
            ("Best cost", best.get("cost", "—") if isinstance(best, Mapping) else "—"),
            ("Winner", json.dumps(result.get("winner_physical_parameters"), sort_keys=True)),
            (
                "Winner cared outputs",
                json.dumps(best.get("cared_outputs"), sort_keys=True)
                if isinstance(best, Mapping)
                else "—",
            ),
            (
                "Winner residuals",
                json.dumps(best.get("residuals"), sort_keys=True)
                if isinstance(best, Mapping)
                else "—",
            ),
        )
        ledger = _stage_artifact_path(stage, "ledger")
        chart = ""
        if ledger is not None:
            payload = json.loads(ledger.read_text(encoding="utf-8"))
            costs = [
                float(entry["outcome"]["cost"])
                for entry in payload.get("entries", [])
                if isinstance(entry, Mapping)
                and isinstance(entry.get("outcome"), Mapping)
                and entry["outcome"].get("status") == "PASS"
            ]
            if costs:
                chart = _svg_line_chart(range(1, len(costs) + 1), costs, "Candidate", "Cost")
        return _HtmlView("<h3>Optimization</h3>" + chart + _html_table(("Field", "Value"), rows))

    def show_winner_refinement(self) -> _HtmlView:
        stage = self.stage("refine_winner")
        if stage.status != "PASS" or stage.result is None:
            return stage.show()
        comparison = stage.result.get("relative_changes", {})
        rows = [
            (name, value)
            for name, value in sorted(comparison.items())
        ] if isinstance(comparison, Mapping) else []
        return _HtmlView(
            "<h3>Winner N→2N Refinement</h3>"
            + _html_table(("Cared output", "Relative change"), rows)
        )

    def show_responses(self) -> _HtmlView:
        stage = self.stage("evaluate_responses")
        if stage.status != "PASS":
            return stage.show()
        path = _stage_artifact_path(stage, "response")
        if path is None:
            return stage.show()
        columns = _read_numeric_csv(path)
        frequency = columns["frequency_hz"]
        direct = [
            math.hypot(real, imag)
            for real, imag in zip(
                columns["direct_s21_real"], columns["direct_s21_imag"], strict=True
            )
        ]
        hb = [
            math.hypot(real, imag)
            for real, imag in zip(columns["hb_s21_real"], columns["hb_s21_imag"], strict=True)
        ]
        series = {"Direct": direct, "HB": hb}
        c11_stage = self.stage("fit_c11")
        c11_path = _stage_artifact_path(c11_stage, "response")
        if c11_stage.status == "PASS" and c11_path is not None:
            fitted = _read_numeric_csv(c11_path)
            series["C11"] = [
                math.hypot(real, imag)
                for real, imag in zip(
                    fitted["c11_s21_real"], fitted["c11_s21_imag"], strict=True
                )
            ]
        return _HtmlView(
            "<h3>Direct, pump-off HB, and C11 response</h3>"
            + _svg_multi_line_chart(frequency, series, "Frequency (Hz)", "|S21|")
        )

    def show_c11_fit(self) -> _HtmlView:
        stage = self.stage("fit_c11")
        if stage.status != "PASS" or stage.result is None:
            return stage.show()
        parameters = stage.result.get("parameters_hz", {})
        rows = list(sorted(parameters.items())) if isinstance(parameters, Mapping) else []
        rows.extend(
            [
                ("normalized_complex_rmse", stage.result.get("normalized_complex_rmse", "—")),
                ("successful_start_count", stage.result.get("successful_start_count", "—")),
            ]
        )
        return _HtmlView("<h3>Restricted C11 fit</h3>" + _html_table(("Field", "Value"), rows))

    def show_qubit_t1(self) -> _HtmlView:
        stage = self.stage("evaluate_t1")
        if stage.status != "PASS":
            return stage.show()
        path = _stage_artifact_path(stage, "t1")
        if path is None:
            return stage.show()
        columns = _read_numeric_csv(path)
        finite_x: list[float] = []
        finite_y: list[float] = []
        for frequency, value in zip(columns["frequency_hz"], columns["t1_s"], strict=True):
            if math.isfinite(value):
                finite_x.append(frequency)
                finite_y.append(value * 1.0e6)
        chart = (
            _svg_line_chart(finite_x, finite_y, "Frequency (Hz)", "T1 (µs)")
            if finite_x
            else "<p>NOT_EVALUABLE: no finite T1 samples.</p>"
        )
        admittance = _svg_multi_line_chart(
            columns["frequency_hz"],
            {"Re(Yeff)": columns["y_eff_real_s"], "Im(Yeff)": columns["y_eff_imag_s"]},
            "Frequency (Hz)",
            "Yeff (S)",
        )
        return _HtmlView("<h3>HB-derived qubit admittance and T1</h3>" + admittance + chart)

    def show_simulation_benchmark(self) -> _HtmlView:
        rows = []
        for name in STAGE_ORDER:
            result = self.stages[name].result
            rows.append((name, result.get("wall_seconds", "—") if result else "—"))
        return _HtmlView(
            "<h3>Stage timing</h3>" + _html_table(("Stage", "Wall seconds"), rows)
        )

    def show_all_results(self) -> _HtmlView:
        report = self.stage("build_report")
        path = _stage_artifact_path(report, "report") if report.status == "PASS" else None
        if path is not None:
            return _HtmlView(path.read_text(encoding="utf-8"))
        sections = (
            self.show_run_trustworthiness(),
            self.show_optimization(),
            self.show_winner_refinement(),
            self.show_responses(),
            self.show_c11_fit(),
            self.show_qubit_t1(),
            self.show_simulation_benchmark(),
        )
        return _HtmlView("".join(section.html_text for section in sections))


@dataclass(frozen=True)
class ResolvedCircuitCampaign:
    results: tuple[ResolvedCircuitResult, ...]

    @property
    def status(self) -> str:
        return "PASS" if all(item.status == "PASS" for item in self.results) else "NOT_EVALUABLE"

    def show_all_results(self) -> _HtmlView:
        rows = []
        for item in self.results:
            c11 = item.stage("fit_c11").result or {}
            t1 = item.stage("evaluate_t1").result or {}
            rows.append(
                (
                    item.run_id,
                    item.status,
                    c11.get("normalized_complex_rmse", "—"),
                    t1.get("minimum_finite_t1_s", "—"),
                )
            )
        return _HtmlView(
            f"<h2>Circuit campaign · {self.status}</h2>"
            + _html_table(("Run", "Status", "C11 RMSE", "Minimum finite T1 (s)"), rows)
        )


def resolve_circuit_result(run_dir: Path | str) -> ResolvedCircuitResult:
    root = Path(run_dir).resolve()
    stages = {
        name: _resolve_stage_directory(root, name)
        for name in STAGE_ORDER
    }
    return ResolvedCircuitResult(root, stages)


def resolve_circuit_campaign(run_dirs: Sequence[Path | str]) -> ResolvedCircuitCampaign:
    if isinstance(run_dirs, (str, Path)):
        raise RuntimeContractError("Circuit campaign requires a sequence of run directories.")
    paths = tuple(Path(path).resolve() for path in run_dirs)
    if not paths or len(set(paths)) != len(paths):
        raise RuntimeContractError("Circuit campaign requires unique explicit run directories.")
    return ResolvedCircuitCampaign(tuple(resolve_circuit_result(path) for path in paths))


def _resolve_stage_directory(run_dir: Path, stage: str) -> ResolvedCircuitStage:
    stage_dir = run_dir / "stages" / stage
    receipt_path = stage_dir / "circuit-workbench-run-receipt.v1.json"
    request_path = stage_dir / "circuit-workbench-run-request.v1.json"
    try:
        if not receipt_path.is_file() or not request_path.is_file():
            raise RuntimeContractError("sealed request/receipt pair is absent")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        request_bytes = request_path.read_bytes()
        request = json.loads(request_bytes)
        if receipt.get("schema") != RECEIPT_SCHEMA or request.get("schema") != REQUEST_SCHEMA:
            raise RuntimeContractError("request or receipt schema mismatches")
        if request.get("action") != stage:
            raise RuntimeContractError("request action does not match stage directory")
        if receipt.get("stage") != stage:
            raise RuntimeContractError("receipt stage does not match stage directory")
        if request.get("run_id") != run_dir.name or receipt.get("run_id") != run_dir.name:
            raise RuntimeContractError("request or receipt run_id mismatches the run directory")
        for name in ("lifecycle_state", "data_classification"):
            if receipt.get(name) != request.get(name):
                raise RuntimeContractError(f"receipt {name} mismatches the request")
        receipt_body = dict(receipt)
        receipt_hash = receipt_body.pop("canonical_sha256", None)
        if receipt_hash != _fingerprint(receipt_body):
            raise RuntimeContractError("receipt canonical hash mismatches")
        request_body = dict(request)
        fingerprint = request_body.pop("fingerprint_sha256", None)
        if fingerprint != _fingerprint(request_body):
            raise RuntimeContractError("request fingerprint mismatches")
        if (
            receipt.get("request_fingerprint_sha256") != fingerprint
            or receipt.get("request_sha256") != _sha256(request_bytes)
        ):
            raise RuntimeContractError("receipt does not bind the durable request")
        durable_path = Path(str(receipt.get("request_path", ""))).resolve()
        if durable_path != request_path:
            raise RuntimeContractError("receipt request path is not the stage request")
        plan = _mapping(request.get("plan"), "stage plan")
        plan_body = dict(plan)
        plan_hash = plan_body.pop("canonical_sha256", None)
        if plan_hash != _fingerprint(plan_body) or receipt.get("plan_sha256") != plan_hash:
            raise RuntimeContractError("plan identity mismatches")
        runtime = _mapping(request.get("runtime"), "stage runtime")
        for receipt_key, request_key in (
            ("python_runtime_source_sha256", "python_package_source_sha256"),
            ("runner_tree_sha256", "runner_tree_sha256"),
            ("core_tree_sha256", "core_tree_sha256"),
            ("julia_executable_sha256", "julia_executable_sha256"),
        ):
            if receipt.get(receipt_key) != runtime.get(request_key):
                raise RuntimeContractError(f"receipt runtime identity {receipt_key} mismatches")
        for name, artifact in _mapping(request.get("artifacts", {}), "artifacts").items():
            binding = _mapping(artifact, f"artifact {name}")
            path = Path(str(binding.get("path", "")))
            if not path.is_file() or _sha256(path.read_bytes()) != binding.get("source_sha256"):
                raise RuntimeContractError(f"bound artifact '{name}' is missing or changed")
        if receipt.get("artifact_bindings") != request.get("artifacts", {}):
            raise RuntimeContractError("receipt artifact bindings mismatch the request")
        upstream_receipts = _mapping(
            request.get("upstream_receipts", {}), "upstream receipts"
        )
        if set(upstream_receipts) != set(STAGE_DEPENDENCIES[stage]):
            raise RuntimeContractError("stage has invalid upstream dependencies")
        for upstream_name, expected in upstream_receipts.items():
            upstream_path = run_dir / "stages" / upstream_name / "circuit-workbench-run-receipt.v1.json"
            if not upstream_path.is_file():
                raise RuntimeContractError(f"upstream receipt '{upstream_name}' is absent")
            upstream = json.loads(upstream_path.read_text(encoding="utf-8"))
            if upstream.get("canonical_sha256") != expected:
                raise RuntimeContractError(f"upstream receipt '{upstream_name}' identity mismatches")
        result = receipt.get("result")
        if result is not None and receipt.get("output_sha256") != _fingerprint(result):
            raise RuntimeContractError("receipt result hash mismatches")
        produced = receipt.get("produced_artifacts", {})
        for name, artifact in _mapping(produced, "produced artifacts").items():
            declaration = _mapping(artifact, f"produced artifact {name}")
            relative = Path(str(declaration.get("path", "")))
            path = (stage_dir / relative).resolve()
            if (
                relative.is_absolute()
                or not path.is_relative_to(stage_dir.resolve())
                or not path.is_file()
                or _sha256(path.read_bytes()) != declaration.get("sha256")
            ):
                raise RuntimeContractError(f"produced artifact '{name}' is missing or changed")
        status = str(receipt.get("status", "NOT_EVALUABLE"))
        if status != "PASS":
            failure = receipt.get("failure")
            return ResolvedCircuitStage(stage, receipt_path, receipt, status, str(failure))
        return ResolvedCircuitStage(stage, receipt_path, receipt, status)
    except Exception as error:
        return ResolvedCircuitStage(stage, receipt_path, {}, "NOT_EVALUABLE", str(error))


def _python_stage_receipt(
    request: Mapping[str, Any],
    request_path: Path,
    result: Mapping[str, Any] | None,
    *,
    durable_request_path: Path,
    durable_stage_dir: Path,
    failure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    runtime = _mapping(request.get("runtime"), "request runtime")
    plan = _mapping(request.get("plan"), "request plan")
    produced = _mapping(result.get("produced_artifacts", {}), "produced artifacts") if result else {}
    for name, artifact in produced.items():
        declaration = _mapping(artifact, f"produced artifact {name}")
        relative = Path(str(declaration.get("path", "")))
        source = request_path.parent / relative
        if relative.is_absolute() or not source.is_file():
            raise RuntimeContractError(f"Python stage artifact '{name}' is absent.")
        if declaration.get("sha256") != _sha256(source.read_bytes()):
            raise RuntimeContractError(f"Python stage artifact '{name}' hash mismatches.")
        target = (durable_stage_dir / relative).resolve()
        if not target.is_relative_to(durable_stage_dir.resolve()):
            raise RuntimeContractError(f"Python stage artifact '{name}' escapes its stage.")
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "stage": request["action"],
        "run_id": request["run_id"],
        "request_fingerprint_sha256": request["fingerprint_sha256"],
        "request_path": str(durable_request_path.resolve()),
        "request_sha256": _sha256(request_path.read_bytes()),
        "plan_sha256": plan["canonical_sha256"],
        "python_runtime_source_sha256": runtime["python_package_source_sha256"],
        "julia_version": None,
        "runner_tree_sha256": runtime["runner_tree_sha256"],
        "core_tree_sha256": runtime["core_tree_sha256"],
        "julia_executable_sha256": runtime["julia_executable_sha256"],
        "status": "FAILED" if failure else "PASS",
        "lifecycle_state": request["lifecycle_state"],
        "data_classification": request["data_classification"],
        "promotion_eligible": False,
        "artifact_bindings": request.get("artifacts", {}),
        "produced_artifacts": produced,
        "output_sha256": _fingerprint(result) if result is not None else None,
        "ledger_sha256": None,
        "completed_at": datetime.now(UTC).isoformat(),
        "nonclaims": [
            "no scientific acceptance claim",
            "no promotion or publication claim",
        ],
        "result": result,
        "failure": failure,
    }
    receipt["canonical_sha256"] = _fingerprint(receipt)
    return receipt


def _endpoint(value: EndpointRef) -> EndpointRef:
    if (
        not isinstance(value, EndpointRef)
        or not _nonempty_string(value.component_id)
        or not _nonempty_string(value.pin_name)
    ):
        raise RuntimeContractError(
            "Connections and ports require ComponentInstance.pin() references."
        )
    return value


def _resolve_types(libraries: Sequence[CircuitLibrary]) -> dict[str, ComponentType]:
    result: dict[str, ComponentType] = {}
    for library in libraries:
        for type_id, declared in library.types.items():
            if type_id in result:
                raise RuntimeContractError(
                    f"Component type '{type_id}' is declared by multiple libraries."
                )
            result[type_id] = declared
    return result


def _validate_component(component: ComponentInstance, declared: ComponentType) -> None:
    if not _nonempty_string(component.id) or not _nonempty_string(component.type_id):
        raise RuntimeContractError("Component instance id and type_id must be nonempty strings.")
    parameters = cast(tuple[ParameterDeclaration, ...], declared.parameters)
    parameter_names = {item.name for item in parameters}
    if set(component.parameters) != parameter_names:
        raise RuntimeContractError(
            f"Component '{component.id}' parameters must exactly match '{declared.type_id}' declaration."
        )
    for name, value in component.parameters.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise RuntimeContractError(
                f"Component '{component.id}' parameter '{name}' must be finite."
            )
        if declared.lowerer == "parallel_lc_resonator":
            if name in {"capacitance_f", "inductance_h"} and float(value) <= 0:
                raise RuntimeContractError(
                    f"Component '{component.id}' LC parameter '{name}' must be positive."
                )
            if name == "conductance_s" and float(value) < 0:
                raise RuntimeContractError(
                    f"Component '{component.id}' conductance_s must be nonnegative."
                )
    if declared.lowerer == "transmission_line":
        _validate_positive_parameters(
            component,
            {"length_m", "l_per_m_h", "c_per_m_f"},
        )
        _validate_nonnegative_parameters(component, {"r_per_m_ohm", "g_per_m_s"})
        _validate_positive_integer_parameters(component, {"n_sections"})
    elif declared.lowerer == "linearized_floating_qubit":
        _validate_positive_parameters(
            component,
            {"c01_f", "c02_f", "c12_f", "cr1_f", "cr2_f", "l_j_per_junction_h"},
        )
        branch_count = component.parameters["josephson_branch_count"]
        if (
            isinstance(branch_count, bool)
            or not isinstance(branch_count, int)
            or branch_count not in {1, 2}
        ):
            raise RuntimeContractError(
                f"Component '{component.id}' josephson_branch_count must be exactly 1 or 2."
            )
    elif declared.lowerer == "intrinsic_interferometric_purcell_filter":
        _validate_intrinsic_interferometric_purcell_filter(component)


def _validate_positive_parameters(component: ComponentInstance, names: set[str]) -> None:
    for name in names:
        if component.parameters[name] <= 0:
            raise RuntimeContractError(
                f"Component '{component.id}' parameter '{name}' must be positive."
            )


def _validate_nonnegative_parameters(component: ComponentInstance, names: set[str]) -> None:
    for name in names:
        if component.parameters[name] < 0:
            raise RuntimeContractError(
                f"Component '{component.id}' parameter '{name}' must be nonnegative."
            )


def _validate_positive_integer_parameters(component: ComponentInstance, names: set[str]) -> None:
    for name in names:
        value = component.parameters[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise RuntimeContractError(
                f"Component '{component.id}' parameter '{name}' must be a positive integer."
            )


def _validate_intrinsic_interferometric_purcell_filter(component: ComponentInstance) -> None:
    _validate_positive_parameters(
        component,
        {
            "readout_open_length_m",
            "shared_short_length_m",
            "coupled_length_m",
            "filter_open_length_m",
            "readout_l_per_m_h",
            "readout_c_per_m_f",
            "filter_l_per_m_h",
            "filter_c_per_m_f",
            "mtl_l11_per_m_h",
            "mtl_l22_per_m_h",
            "mtl_c11_per_m_f",
            "mtl_c22_per_m_f",
            "idc_finger_length_um",
            "idc_source_min_um",
            "idc_source_max_um",
        },
    )
    _validate_positive_integer_parameters(
        component,
        {
            "readout_short_sections",
            "readout_open_sections",
            "coupled_sections",
            "filter_short_sections",
            "filter_open_sections",
        },
    )
    _validate_nonnegative_parameters(component, {"c0r_f"})
    minimum = component.parameters["idc_source_min_um"]
    maximum = component.parameters["idc_source_max_um"]
    finger_length = component.parameters["idc_finger_length_um"]
    if minimum >= maximum or not minimum <= finger_length <= maximum:
        raise RuntimeContractError(
            f"Component '{component.id}' IDC finger length must lie within its closed source support."
        )
    for capacitance_name, slope_name, intercept_name in (
        (
            "IDC filter-ground capacitance",
            "idc_filter_ground_slope_f_per_um",
            "idc_filter_ground_intercept_f",
        ),
        (
            "IDC feedline-ground capacitance",
            "idc_feedline_ground_slope_f_per_um",
            "idc_feedline_ground_intercept_f",
        ),
        ("IDC mutual capacitance", "idc_mutual_slope_f_per_um", "idc_mutual_intercept_f"),
    ):
        capacitance = (
            component.parameters[slope_name] * finger_length + component.parameters[intercept_name]
        )
        if capacitance <= 0:
            raise RuntimeContractError(
                f"Component '{component.id}' {capacitance_name} must evaluate positive."
            )


def _elaborate_components(
    components: Mapping[str, ComponentInstance], types: Mapping[str, ComponentType]
) -> tuple[
    list[dict[str, Any]],
    dict[tuple[str, str], EndpointRef],
    dict[str, CoordinateRef],
    dict[str, ParameterRef],
    list[_Connection],
]:
    """Freeze composite factories to registered leaves before the Julia boundary."""

    leaves: list[dict[str, Any]] = []
    internal_connections: list[_Connection] = []
    endpoints: dict[tuple[str, str], EndpointRef] = {}
    coordinates: dict[str, CoordinateRef] = {}
    parameters: dict[str, ParameterRef] = {}
    leaf_parameter_values: dict[tuple[str, str], float] = {}
    seen: set[str] = set()

    def visit(component: ComponentInstance) -> None:
        if component.id in seen:
            raise RuntimeContractError(f"Duplicate component instance id '{component.id}'.")
        seen.add(component.id)
        declared = types.get(component.type_id)
        if declared is None:
            raise RuntimeContractError(
                f"Component '{component.id}' uses unregistered type '{component.type_id}'."
            )
        _validate_component(component, declared)
        declared_coordinates = cast(tuple[CoordinateDeclaration, ...], declared.coordinates)
        declared_parameters = cast(tuple[ParameterDeclaration, ...], declared.parameters)
        if component.children:
            if declared.lowerer != "composite":
                raise RuntimeContractError(
                    f"Leaf component '{component.id}' cannot declare children."
                )
            if set(component.pin_bindings) != set(declared.pins):
                raise RuntimeContractError(
                    f"Composite '{component.id}' must bind every declared pin exactly once."
                )
            coordinate_names = {item.name for item in declared_coordinates}
            parameter_names = {item.name for item in declared_parameters}
            if (
                set(component.coordinate_bindings) != coordinate_names
                or set(component.parameter_bindings) != parameter_names
            ):
                raise RuntimeContractError(
                    f"Composite '{component.id}' must bind every declared coordinate and parameter."
                )
            for child in component.children:
                visit(child)
            child_ids = _descendant_ids(component.children)
            for raw_connection in component.internal_connections:
                if not (isinstance(raw_connection, tuple) and len(raw_connection) == 2):
                    raise RuntimeContractError(
                        "Composite internal_connections require (left_pin, right_pin) pairs."
                    )
                left, right = (_endpoint(raw_connection[0]), _endpoint(raw_connection[1]))
                if left.component_id not in child_ids or right.component_id not in child_ids:
                    raise RuntimeContractError(
                        "Composite internal connection endpoints must target direct sealed children."
                    )
                internal_connections.append(
                    _Connection(
                        _resolve_endpoint(left, endpoints), _resolve_endpoint(right, endpoints)
                    )
                )
            for pin, target in component.pin_bindings.items():
                endpoints[(component.id, pin)] = _resolve_endpoint(target, endpoints)
            for name, target in component.coordinate_bindings.items():
                key = f"{component.id}.{name}"
                coordinates[key] = _resolve_coordinate(target, coordinates, component.children)
            for name, target in component.parameter_bindings.items():
                key = f"{component.id}.{name}"
                resolved_target = _resolve_parameter(target, parameters, component.children)
                resolved_key = (resolved_target.component_id, resolved_target.parameter_name)
                if component.parameters[name] != leaf_parameter_values[resolved_key]:
                    raise RuntimeContractError(
                        f"Composite parameter '{key}' must exactly equal its resolved leaf binding."
                    )
                parameters[key] = resolved_target
            return
        if declared.lowerer == "composite":
            raise RuntimeContractError(
                f"Composite '{component.id}' requires sealed child instances."
            )
        leaves.append(_plain(component))
        for pin in declared.pins:
            endpoints[(component.id, pin)] = EndpointRef(component.id, pin)
        for coordinate in declared_coordinates:
            coordinates[f"{component.id}.{coordinate.name}"] = CoordinateRef(
                component.id, coordinate.name
            )
        for parameter in declared_parameters:
            parameters[f"{component.id}.{parameter.name}"] = ParameterRef(
                component.id, parameter.name
            )
            leaf_parameter_values[(component.id, parameter.name)] = float(
                component.parameters[parameter.name]
            )

    for component in components.values():
        visit(component)
    return leaves, endpoints, coordinates, parameters, internal_connections


def _resolve_endpoint(
    endpoint: EndpointRef, bindings: Mapping[tuple[str, str], EndpointRef]
) -> EndpointRef:
    endpoint = _endpoint(endpoint)
    resolved = bindings.get((endpoint.component_id, endpoint.pin_name))
    if resolved is None:
        raise RuntimeContractError(
            f"Endpoint '{endpoint.component_id}.{endpoint.pin_name}' is not declared by the sealed Plan."
        )
    return resolved


def _descendant_ids(children: Sequence[ComponentInstance]) -> set[str]:
    result: set[str] = set()
    for child in children:
        result.add(child.id)
        result.update(_descendant_ids(child.children))
    return result


def _resolve_coordinate(
    target: CoordinateRef,
    resolved: Mapping[str, CoordinateRef],
    children: Sequence[ComponentInstance],
) -> CoordinateRef:
    if not isinstance(target, CoordinateRef):
        raise RuntimeContractError("Composite coordinate bindings require CoordinateRef values.")
    child_ids = _descendant_ids(children)
    if target.component_id not in child_ids:
        raise RuntimeContractError("Composite coordinate binding must target a sealed child.")
    value = resolved.get(f"{target.component_id}.{target.coordinate_name}")
    if value is None:
        raise RuntimeContractError("Composite coordinate binding targets an undeclared coordinate.")
    return value


def _resolve_parameter(
    target: ParameterRef,
    resolved: Mapping[str, ParameterRef],
    children: Sequence[ComponentInstance],
) -> ParameterRef:
    if not isinstance(target, ParameterRef):
        raise RuntimeContractError("Composite parameter bindings require ParameterRef values.")
    child_ids = _descendant_ids(children)
    if target.component_id not in child_ids:
        raise RuntimeContractError("Composite parameter binding must target a sealed child.")
    value = resolved.get(f"{target.component_id}.{target.parameter_name}")
    if value is None:
        raise RuntimeContractError("Composite parameter binding targets an undeclared parameter.")
    return value


def _schematic_intent(
    components: Sequence[Mapping[str, Any]],
    connections: Sequence[_Connection],
    ports: Sequence[_Port],
    bindings: Mapping[tuple[str, str], EndpointRef],
) -> dict[str, Any]:
    return {
        "schema": "circuit-workbench-schematic-intent.v1",
        "components": [{"id": item["id"], "type_id": item["type_id"]} for item in components],
        "connections": [
            {
                "left": _plain(_resolve_endpoint(item.left, bindings)),
                "right": _plain(_resolve_endpoint(item.right, bindings)),
            }
            for item in connections
        ],
        "ports": [
            {
                "id": item.id,
                "endpoint": _plain(_resolve_endpoint(item.endpoint, bindings)),
                "resistance_ohm": item.resistance_ohm,
            }
            for item in ports
        ],
    }


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return _plain(asdict(cast(Any, value)))
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    return value


def _validate_expression(value: Any, allowed_outputs: set[str] | None) -> None:
    if (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    ):
        return
    if not isinstance(value, Mapping):
        raise RuntimeContractError(
            "Restricted expressions require finite numeric literals or mappings."
        )
    keys = set(value)
    if keys == {"output"}:
        output = value["output"]
        if (
            not isinstance(output, str)
            or not output
            or (allowed_outputs is not None and output not in allowed_outputs)
        ):
            raise RuntimeContractError("Expression references an unknown cared output.")
        return
    if keys == {"const"}:
        if (
            isinstance(value["const"], bool)
            or not isinstance(value["const"], (int, float))
            or not math.isfinite(float(value["const"]))
        ):
            raise RuntimeContractError("Expression constants must be finite.")
        return
    if (
        keys != {"op", "args"}
        or not isinstance(value["op"], str)
        or not isinstance(value["args"], Sequence)
    ):
        raise RuntimeContractError("Expression nodes require only op and args.")
    operation = value["op"]
    arity = len(value["args"])
    allowed = {"add", "mul", "sum_squares"}
    unary = {"abs", "square", "neg"}
    binary = {"sub", "div", "less_equal", "greater_equal"}
    if (
        operation not in allowed | unary | binary
        or (operation in unary and arity != 1)
        or (operation in binary and arity != 2)
    ):
        raise RuntimeContractError("Restricted expression operation or arity is invalid.")
    for child in value["args"]:
        _validate_expression(child, allowed_outputs)


def _validate_cared_output(name: str, cared: Mapping[str, Any]) -> None:
    """Reject malformed backend declarations before sealing an action subprocess."""

    kind = cared["kind"]
    if kind == "closed_mode_frequency_hz":
        value = cared["mode_index"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise RuntimeContractError(
                f"Cared output '{name}' mode_index must be a positive integer."
            )
    elif kind == "schur_dynamic_stiffness_abs":
        frequency = cared["frequency_hz"]
        if (
            isinstance(frequency, bool)
            or not isinstance(frequency, (int, float))
            or not math.isfinite(float(frequency))
            or frequency <= 0
        ):
            raise RuntimeContractError(
                f"Cared output '{name}' frequency_hz must be finite and positive."
            )
        for field_name in ("row", "column"):
            value = cared[field_name]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise RuntimeContractError(
                    f"Cared output '{name}' {field_name} must be a positive integer."
                )
    elif kind == "s_parameter":
        frequency = cared["frequency_hz"]
        ports = (cared["output_port"], cared["input_port"])
        if (
            isinstance(frequency, bool)
            or not isinstance(frequency, (int, float))
            or not math.isfinite(float(frequency))
            or frequency <= 0
        ):
            raise RuntimeContractError(
                f"Cared output '{name}' frequency_hz must be finite and positive."
            )
        if any(isinstance(port, bool) or not isinstance(port, int) or port < 1 for port in ports):
            raise RuntimeContractError(f"Cared output '{name}' ports must be positive integers.")
        if cared["part"] not in {"abs", "real", "imag"}:
            raise RuntimeContractError(f"Cared output '{name}' has unsupported S-parameter part.")
    else:
        if cared["quantity"] not in {
            "readout_diagonal_root_hz",
            "filter_diagonal_root_hz",
            "transfer_cofactor_zero_hz",
            "residue_normalized_midpoint_exchange_abs_real_hz",
            "diagonal_root_linewidth_sum_hz",
        }:
            raise RuntimeContractError(
                f"Cared output '{name}' has an unsupported targeted-Schur quantity."
            )
        for field_name in (
            "readout_root_anchor_hz",
            "filter_root_anchor_hz",
            "transfer_zero_anchor_hz",
        ):
            value = cared[field_name]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or value <= 0
            ):
                raise RuntimeContractError(
                    f"Cared output '{name}' {field_name} must be finite and positive."
                )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate_optimization_ledger(ledger: Mapping[str, Any], fingerprint: str) -> None:
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        raise RuntimeContractError("Optimization ledger entries must be a list.")
    previous = _fingerprint(
        {
            "schema": "circuit-workbench-optimization-ledger.v1",
        }
    )
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, Mapping) or entry.get("candidate_index") != index:
            raise RuntimeContractError("Optimization ledger candidate indices must be contiguous.")
        latent = entry.get("latent")
        if (
            not isinstance(latent, list)
            or any(
                isinstance(value, bool) or not isinstance(value, (int, float)) for value in latent
            )
            or entry.get("candidate_key") != _fingerprint([float(value) for value in latent])
            or entry.get("previous_entry_sha256") != previous
        ):
            raise RuntimeContractError("Optimization ledger hash chain is broken.")
        body = dict(entry)
        expected = body.pop("entry_sha256", None)
        actual = _fingerprint(body)
        if expected != actual:
            raise RuntimeContractError("Optimization ledger entry hash mismatches its content.")
        previous = actual
    if ledger.get("history_sha256") != previous:
        raise RuntimeContractError("Optimization ledger history hash mismatches its entries.")


def _tree_sha256(root: Path, *, excluded_top_level: set[str] | None = None) -> str:
    """Stable complete source-tree identity, excluding only generated/cache state."""

    if not root.is_dir():
        raise RuntimeContractError(f"Required source tree is absent: {root}")
    excluded_top_level = excluded_top_level or set()
    digest = hashlib.sha256()
    for path in sorted(
        (
            item
            for item in root.rglob("*")
            if item.is_file()
            and item.relative_to(root).parts[0] not in excluded_top_level
            and ".git" not in item.parts
            and "__pycache__" not in item.parts
            and item.suffix != ".pyc"
        ),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _resolved_julia_executable() -> Path:
    raw = os.environ.get("JULIA", "julia")
    candidate = Path(raw)
    resolved = (
        candidate.resolve()
        if candidate.parent != Path(".")
        else Path(shutil.which(raw) or "").resolve()
    )
    if resolved.name == "julialauncher":
        config_path = Path.home() / ".julia" / "juliaup" / "juliaup.json"
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            channel = config["Default"]
            version = config["InstalledChannels"][channel]["Version"]
            binary = config["InstalledVersions"][version]["BinaryPath"]
            resolved = (config_path.parent / binary).resolve()
        except (KeyError, OSError, TypeError, json.JSONDecodeError) as error:
            raise RuntimeContractError(
                "Juliaup launcher cannot be resolved to its selected executable for sealed runtime identity."
            ) from error
    if not resolved.is_file():
        raise RuntimeContractError(
            "Julia executable is unavailable; Circuit Workbench runtime cannot launch an action."
        )
    return resolved.resolve()


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _resolved_reduction(spec: ReductionSpec, plan: Mapping[str, Any]) -> dict[str, Any]:
    bindings = plan["coordinate_bindings"]
    retained: list[dict[str, str]] = []
    for ref in spec.retained:
        key = f"{ref.component_id}.{ref.coordinate_name}"
        target = bindings.get(key)
        if not isinstance(target, Mapping):
            raise RuntimeContractError(
                "ReductionSpec coordinate does not resolve through the sealed Plan."
            )
        retained.append(
            {
                "component_id": str(target["component_id"]),
                "coordinate_name": str(target["coordinate_name"]),
            }
        )
    transforms: list[dict[str, Any]] = []
    for raw in spec.transforms:
        if not isinstance(raw, Mapping):
            raise RuntimeContractError("Reduction transforms must be serializable mappings.")
        references = raw.get("coordinates")
        matrix = raw.get("matrix")
        if (
            not isinstance(references, Sequence)
            or isinstance(references, (str, bytes))
            or not references
        ):
            raise RuntimeContractError(
                "A reduction transform requires ordered coordinate references."
            )
        if not isinstance(matrix, Sequence) or len(matrix) != len(references):
            raise RuntimeContractError(
                "A reduction transform matrix must be square over its coordinates."
            )
        resolved_refs: list[dict[str, str]] = []
        numeric_matrix: list[list[float]] = []
        for reference in references:
            if not isinstance(reference, CoordinateRef):
                raise RuntimeContractError(
                    "Reduction transform coordinates require CoordinateRef values."
                )
            target = bindings.get(f"{reference.component_id}.{reference.coordinate_name}")
            if not isinstance(target, Mapping):
                raise RuntimeContractError(
                    "Reduction transform references an unexposed coordinate."
                )
            resolved_refs.append(
                {
                    "component_id": str(target["component_id"]),
                    "coordinate_name": str(target["coordinate_name"]),
                }
            )
        if len({(item["component_id"], item["coordinate_name"]) for item in resolved_refs}) != len(
            resolved_refs
        ):
            raise RuntimeContractError("Reduction transform coordinates must be unique.")
        for row in matrix:
            if not isinstance(row, Sequence) or len(row) != len(references):
                raise RuntimeContractError("Reduction transform matrix must be square.")
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in row):
                raise RuntimeContractError(
                    "Reduction transform matrix entries must be finite numbers, not booleans."
                )
            values = [float(value) for value in row]
            if not all(math.isfinite(value) for value in values):
                raise RuntimeContractError("Reduction transform matrix must be finite.")
            numeric_matrix.append(values)
        if not _has_nonsingular_pivots(numeric_matrix):
            raise RuntimeContractError("Reduction transform matrix must be invertible.")
        transforms.append({"coordinates": resolved_refs, "matrix": numeric_matrix})
    return {"retained": retained, "transforms": transforms, "eliminated": "complete_complement"}


def _resolved_variables(
    specs: Sequence[VariableSpec], plan: Mapping[str, Any]
) -> list[dict[str, Any]]:
    bindings = plan["parameter_bindings"]
    components = {item["id"]: item["type_id"] for item in plan["components"]}
    component_values = {item["id"]: item["parameters"] for item in plan["components"]}
    types = {item["type_id"]: item for item in plan["component_types"]}
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for spec in specs:
        if spec.transform not in {"identity", "log", "unit_interval"}:
            raise RuntimeContractError("VariableSpec transform is unsupported.")
        key = f"{spec.ref.component_id}.{spec.ref.parameter_name}"
        target = bindings.get(key)
        if not isinstance(target, Mapping):
            raise RuntimeContractError(
                "VariableSpec references a parameter not exposed by the sealed Plan."
            )
        resolved = (str(target["component_id"]), str(target["parameter_name"]))
        declaration = next(
            (
                item
                for item in types[components[resolved[0]]]["parameters"]
                if item["name"] == resolved[1]
            ),
            None,
        )
        if not declaration or not declaration["variable_capable"]:
            raise RuntimeContractError(
                "VariableSpec requires a variable-capable declared parameter."
            )
        if resolved in seen:
            raise RuntimeContractError("Variables cannot bind the same sealed parameter twice.")
        seen.add(resolved)
        baseline = component_values[resolved[0]][resolved[1]]
        if (
            isinstance(baseline, bool)
            or not isinstance(baseline, (int, float))
            or not math.isfinite(float(baseline))
        ):
            raise RuntimeContractError("VariableSpec resolved baseline must be finite numeric.")
        if spec.transform == "log" and baseline <= 0:
            raise RuntimeContractError(
                "VariableSpec log transform requires a positive resolved baseline."
            )
        for label, value in (("lower", spec.lower), ("upper", spec.upper)):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or (spec.transform == "log" and value <= 0)
            ):
                raise RuntimeContractError(
                    f"VariableSpec {label} must be finite and positive for log transform."
                )
        if spec.lower is not None and spec.upper is not None and spec.lower >= spec.upper:
            raise RuntimeContractError("VariableSpec lower must be less than upper.")
        if spec.transform == "unit_interval":
            if spec.lower is None or spec.upper is None:
                raise RuntimeContractError(
                    "VariableSpec unit_interval transform requires finite lower and upper bounds."
                )
            if not spec.lower <= baseline <= spec.upper:
                raise RuntimeContractError(
                    "VariableSpec unit_interval baseline must lie within its physical bounds."
                )
        result.append(
            {
                "requested_ref": {
                    "component_id": spec.ref.component_id,
                    "parameter_name": spec.ref.parameter_name,
                },
                "ref": {"component_id": resolved[0], "parameter_name": resolved[1]},
                "transform": spec.transform,
                "lower": spec.lower,
                "upper": spec.upper,
            }
        )
    return result


def _has_nonsingular_pivots(matrix: Sequence[Sequence[float]]) -> bool:
    """Exact finite Gaussian pivot test; never uses a determinant product threshold."""

    work = [list(row) for row in matrix]
    for column in range(len(work)):
        pivot = max(range(column, len(work)), key=lambda row: abs(work[row][column]))
        if work[pivot][column] == 0.0:
            return False
        if pivot != column:
            work[column], work[pivot] = work[pivot], work[column]
        scale = work[column][column]
        for row in range(column + 1, len(work)):
            factor = work[row][column] / scale
            for inner in range(column + 1, len(work)):
                work[row][inner] -= factor * work[column][inner]
    return True


def _fingerprint(value: Any) -> str:
    return _sha256(_canonical_bytes(_hashable(value)))


def _hashable(value: Any) -> Any:
    """Give Float64 values one language-neutral canonical representation."""

    if isinstance(value, float):
        if value.is_integer() and abs(value) <= 9_007_199_254_740_991:
            return int(value)
        return {"__float64__": struct.pack(">d", value).hex()}
    if isinstance(value, Mapping):
        return {str(key): _hashable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_hashable(item) for item in value]
    return value


def _stage_artifact_path(stage: ResolvedCircuitStage, name: str) -> Path | None:
    produced = stage.receipt.get("produced_artifacts", {})
    if isinstance(produced, Mapping) and isinstance(produced.get(name), Mapping):
        relative = Path(str(produced[name].get("path", "")))
        path = (stage.path.parent / relative).resolve()
        if not relative.is_absolute() and path.is_file():
            return path
    if name == "ledger" and stage.result is not None:
        raw = stage.result.get("ledger_path")
        if isinstance(raw, str) and Path(raw).is_file():
            return Path(raw)
    return None


def _read_numeric_csv(path: Path) -> dict[str, list[float]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise RuntimeContractError(f"CSV artifact has no header: {path}")
        result = {name: [] for name in reader.fieldnames}
        for row in reader:
            for name in reader.fieldnames:
                try:
                    result[name].append(float(row[name]))
                except (TypeError, ValueError) as error:
                    raise RuntimeContractError(
                        f"CSV artifact column '{name}' contains a nonnumeric value."
                    ) from error
    return result


def _fit_c11_stage(
    directory: Path,
    responses: ResolvedCircuitStage,
) -> Mapping[str, Any]:
    source = _stage_artifact_path(responses, "response")
    if source is None:
        raise RuntimeContractError("fit_c11 requires the sealed response CSV.")
    columns = _read_numeric_csv(source)
    required = {
        "frequency_hz",
        "direct_s21_real",
        "direct_s21_imag",
        "hb_s21_real",
        "hb_s21_imag",
    }
    if not required <= set(columns):
        raise RuntimeContractError("Response CSV lacks the Direct/HB complex trace columns.")

    import numpy as np
    from scipy.optimize import least_squares

    frequency = np.asarray(columns["frequency_hz"], dtype=float)
    direct = np.asarray(columns["direct_s21_real"], dtype=float) + 1j * np.asarray(
        columns["direct_s21_imag"], dtype=float
    )
    hb = np.asarray(columns["hb_s21_real"], dtype=float) + 1j * np.asarray(
        columns["hb_s21_imag"], dtype=float
    )
    if len(frequency) < 3 or not np.all(np.diff(frequency) > 0):
        raise RuntimeContractError("C11 requires a strictly increasing response grid.")
    weight = np.linspace(0.0, 1.0, len(hb))
    baseline = (1.0 - weight) * hb[0] + weight * hb[-1]
    if np.any(np.abs(baseline) <= np.finfo(float).eps):
        raise RuntimeContractError("C11 endpoint baseline crosses zero.")
    normalized = hb / baseline

    span = float(frequency[-1] - frequency[0])
    lower = np.asarray([frequency[0] + 1.0, frequency[0] + 1.0, 1.0, 1.0])
    upper = np.asarray([frequency[-1] - 1.0, frequency[-1] - 1.0, 2 * span, 4 * span])
    anchors = [frequency[0] + fraction * span for fraction in (0.25, 0.5, 0.75)]
    starts = [
        np.asarray([fa, fb, span * coupling_scale, span * kappa_scale])
        for fa, fb in (
            (anchors[0], anchors[1]),
            (anchors[1], anchors[2]),
            (anchors[0], anchors[2]),
        )
        for coupling_scale in (0.01, 0.05, 0.2)
        for kappa_scale in (0.01, 0.05, 0.2)
    ]

    def model(parameters: Any) -> Any:
        fa_hz, fb_hz, coupling_hz, kappa_hz = parameters
        omega = 2 * np.pi * frequency
        delta_a = 2 * np.pi * fa_hz - omega
        delta_b = 2 * np.pi * fb_hz - omega
        coupling = 2 * np.pi * coupling_hz
        kappa = 2 * np.pi * kappa_hz
        return 1 - kappa * (2j * delta_b) / (
            4 * coupling**2 + (2j * delta_a + kappa) * (2j * delta_b)
        )

    def residual(parameters: Any) -> Any:
        delta = model(parameters) - normalized
        return np.concatenate((delta.real, delta.imag))

    results = [
        least_squares(
            residual,
            start,
            bounds=(lower, upper),
            x_scale=np.asarray([span, span, span, span], dtype=float),
            ftol=1.0e-12,
            xtol=1.0e-12,
            gtol=1.0e-12,
            max_nfev=4000,
        )
        for start in starts
    ]
    successful = [result for result in results if result.success]
    if not successful:
        raise RuntimeContractError("All deterministic C11 least-squares starts failed.")
    winner = min(successful, key=lambda result: result.cost)
    parameters = np.asarray(winner.x, dtype=float)
    fitted = model(parameters) * baseline
    normalized_residual = fitted / baseline - normalized
    output = directory / "response.csv"
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "frequency_hz",
                "direct_s21_real",
                "direct_s21_imag",
                "hb_s21_real",
                "hb_s21_imag",
                "c11_s21_real",
                "c11_s21_imag",
            )
        )
        writer.writerows(
            zip(
                frequency,
                direct.real,
                direct.imag,
                hb.real,
                hb.imag,
                fitted.real,
                fitted.imag,
                strict=True,
            )
        )
    artifact = {"path": output.name, "sha256": _sha256(output.read_bytes())}
    return {
        "status": "PASS",
        "fit_input": "pump_off_hb_s21",
        "phasor_convention": "exp(-i*omega*t)",
        "baseline": "complex_linear_endpoints",
        "parameters_hz": {
            "fa_hz": float(parameters[0]),
            "fb_hz": float(parameters[1]),
            "coupling_hz": float(parameters[2]),
            "kappa_hz": float(parameters[3]),
        },
        "normalized_complex_rmse": float(
            np.sqrt(np.mean(np.abs(normalized_residual) ** 2))
        ),
        "normalized_maximum_absolute_residual": float(
            np.max(np.abs(normalized_residual))
        ),
        "start_count": len(results),
        "successful_start_count": len(successful),
        "iterations": int(winner.nfev),
        "produced_artifacts": {"response": artifact},
    }


def _build_report_stage(
    directory: Path,
    run_id: str,
    upstream: Mapping[str, ResolvedCircuitStage],
) -> Mapping[str, Any]:
    pending_report = ResolvedCircuitStage(
        "build_report", directory / "circuit-workbench-run-receipt.v1.json", {}, "PASS"
    )
    stages = {name: upstream.get(name, pending_report) for name in STAGE_ORDER}
    result = ResolvedCircuitResult(Path(run_id), stages)
    body = "".join(
        section.html_text
        for section in (
            result.show_run_trustworthiness(),
            result.show_optimization(),
            result.show_winner_refinement(),
            result.show_responses(),
            result.show_c11_fit(),
            result.show_qubit_t1(),
            result.show_simulation_benchmark(),
        )
    )
    report_path = directory / "report.html"
    report_path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>body{font:14px system-ui;max-width:1200px;margin:auto;padding:24px}"
        "table{border-collapse:collapse;width:100%;margin:12px 0 28px}"
        "th,td{border:1px solid #ccc;padding:6px;text-align:left}"
        "svg{width:100%;height:auto;background:#fff}</style></head><body>"
        f"<h1>{html.escape(run_id)} Circuit Report</h1>{body}</body></html>",
        encoding="utf-8",
    )
    manifest_path = directory / "report.json"
    manifest = {
        "schema": "circuit-workbench-report.v1",
        "run_id": run_id,
        "status": "PASS",
        "source_receipts": {
            name: stage.canonical_sha256 for name, stage in upstream.items()
        },
        "report": {"path": report_path.name, "sha256": _sha256(report_path.read_bytes())},
        "nonclaims": ["no scientific acceptance claim", "no publication claim"],
    }
    _atomic_write(manifest_path, _canonical_bytes(manifest))
    artifacts = {
        "report": {"path": report_path.name, "sha256": _sha256(report_path.read_bytes())},
        "manifest": {"path": manifest_path.name, "sha256": _sha256(manifest_path.read_bytes())},
    }
    return {"status": "PASS", "produced_artifacts": artifacts}


def _html_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    head = "".join(f"<th>{html.escape(str(value))}</th>" for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _svg_line_chart(
    x_values: Sequence[float], y_values: Sequence[float], x_label: str, y_label: str
) -> str:
    return _svg_multi_line_chart(x_values, {y_label: y_values}, x_label, y_label)


def _svg_multi_line_chart(
    x_values: Sequence[float],
    series: Mapping[str, Sequence[float]],
    x_label: str,
    y_label: str,
) -> str:
    x = [float(value) for value in x_values]
    finite_series = {
        name: [float(value) for value in values]
        for name, values in series.items()
        if len(values) == len(x)
    }
    all_y = [value for values in finite_series.values() for value in values if math.isfinite(value)]
    finite_x = [value for value in x if math.isfinite(value)]
    if not finite_x or not all_y:
        return "<p>NOT_EVALUABLE: no finite plot samples.</p>"
    x_min, x_max = min(finite_x), max(finite_x)
    y_min, y_max = min(all_y), max(all_y)
    x_span = x_max - x_min or 1.0
    y_span = y_max - y_min or 1.0
    colors = ("#2563eb", "#dc2626", "#16a34a", "#9333ea")
    polylines = []
    legends = []
    for index, (name, values) in enumerate(finite_series.items()):
        points = " ".join(
            f"{60 + 880 * (x_value - x_min) / x_span:.2f},{20 + 320 * (y_max - y_value) / y_span:.2f}"
            for x_value, y_value in zip(x, values, strict=True)
            if math.isfinite(x_value) and math.isfinite(y_value)
        )
        color = colors[index % len(colors)]
        polylines.append(
            f"<polyline fill='none' stroke='{color}' stroke-width='2' points='{points}'/>"
        )
        legends.append(
            f"<text x='{70 + index * 180}' y='380' fill='{color}'>{html.escape(name)}</text>"
        )
    return (
        "<svg viewBox='0 0 1000 410' role='img' aria-label='"
        + html.escape(f"{y_label} by {x_label}")
        + "'><line x1='60' y1='340' x2='940' y2='340' stroke='#444'/>"
        + "<line x1='60' y1='20' x2='60' y2='340' stroke='#444'/>"
        + "".join(polylines)
        + f"<text x='500' y='405' text-anchor='middle'>{html.escape(x_label)}</text>"
        + f"<text x='15' y='180' transform='rotate(-90 15 180)' text-anchor='middle'>{html.escape(y_label)}</text>"
        + "".join(legends)
        + "</svg>"
    )
