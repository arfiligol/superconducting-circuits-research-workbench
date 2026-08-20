# ruff: noqa: E501
"""Sealed Python authoring and Julia-action transport for Circuit Workbench.

This module deliberately has no Julia embedding.  A completed evaluate action is
one Julia subprocess, while analyze only verifies an existing sealed receipt.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Literal, cast

PLAN_SCHEMA = "circuit-workbench-plan.v1"
REQUEST_SCHEMA = "circuit-workbench-run-request.v1"
RECEIPT_SCHEMA = "circuit-workbench-run-receipt.v1"
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


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


@dataclass(frozen=True)
class _ResultHandle(Mapping[str, Any]):
    payload: Mapping[str, Any]
    path: Path

    def __getitem__(self, key: str) -> Any:
        return self.payload[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.payload)

    def __len__(self) -> int:
        return len(self.payload)

    @property
    def status(self) -> str:
        return str(self.payload["status"])

    @property
    def result(self) -> Any:
        return self.payload.get("result")


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
    ),
    (CoordinateDeclaration("signal", "node_flux", "signal"),),
    lowerer="parallel_lc_resonator",
)
_BUILTIN_LIBRARY = CircuitLibrary(
    id="workbench.core.catalog",
    version="1",
    source_sha256=hashlib.sha256(
        json.dumps(asdict(_BUILTIN_PARALLEL_LC), sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest(),
    types={_BUILTIN_PARALLEL_LC.type_id: _BUILTIN_PARALLEL_LC},
)


@dataclass(frozen=True)
class ReductionSpec:
    retained: tuple[CoordinateRef, ...]
    transforms: tuple[Mapping[str, Any], ...] = ()
    eliminated: Literal["complete_complement"] = "complete_complement"


@dataclass(frozen=True)
class ObjectiveSpec:
    cared_outputs: Mapping[str, Mapping[str, Any]]
    residuals: Mapping[str, Mapping[str, Any]]
    cost: Mapping[str, Any]


@dataclass(frozen=True)
class GateSpec:
    id: str
    expression: Mapping[str, Any]
    state: Literal["active", "proposed", "inactive"]
    human_authority: str | None = None


@dataclass(frozen=True)
class VariableSpec:
    ref: ParameterRef
    transform: Literal["identity", "log"] = "identity"
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
        """Validate and render through the installed Schemdraw Circuit Library without Julia."""

        from schemdraw_circuit_library.rendering.runtime_plan import render_runtime_plan

        sealed = self.seal((_BUILTIN_LIBRARY, *libraries))
        drawing = render_runtime_plan(sealed)
        cast(Any, drawing).circuit_workbench_plan = sealed
        return drawing


@dataclass
class CircuitSim:
    run_root: Path | str
    run_id: str
    _libraries: list[CircuitLibrary] = field(default_factory=lambda: [_BUILTIN_LIBRARY], init=False)
    _plan: CircuitPlan | None = field(default=None, init=False)
    _artifacts: dict[str, Mapping[str, Any]] = field(default_factory=dict, init=False)
    _reduction: ReductionSpec | None = field(default=None, init=False)
    _objective: ObjectiveSpec | None = field(default=None, init=False)
    _gates: list[GateSpec] = field(default_factory=list, init=False)
    _variables: list[VariableSpec] = field(default_factory=list, init=False)
    _optimizer: OptimizerSpec | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if (
            not _nonempty_string(self.run_id)
            or Path(self.run_id).name != self.run_id
            or self.run_id in {".", ".."}
        ):
            raise RuntimeContractError("run_id must be one path-safe directory name.")

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
        builtin_leaf = "workbench.parallel_lc_resonator.v1"
        if any(component["type_id"] != builtin_leaf for component in sealed["components"]):
            raise RuntimeContractError(
                "Circuit Workbench V1 accepts only registered composite types and the built-in parallel-LC leaf lowerer."
            )
        self._plan = plan

    def bind_artifact(self, name: str, artifact: Mapping[str, Any]) -> None:
        if not name or not isinstance(artifact, Mapping):
            raise RuntimeContractError("Artifact bindings require a name and mapping.")
        units = artifact.get("units")
        provenance = artifact.get("provenance")
        if (
            not _nonempty_string(artifact.get("schema"))
            or not (_nonempty_string(units) or (isinstance(units, Mapping) and bool(units)))
            or not isinstance(provenance, Mapping)
            or not provenance
        ):
            raise RuntimeContractError(
                "Artifact binding requires declared schema, units, and provenance."
            )
        source = artifact.get("source_sha256")
        if (
            not isinstance(source, str)
            or len(source) != 64
            or any(char not in "0123456789abcdef" for char in source)
        ):
            raise RuntimeContractError("Artifact binding requires exact source_sha256.")
        path = artifact.get("path")
        if not isinstance(path, str) or not path:
            raise RuntimeContractError("Artifact binding requires a readable bound file path.")
        resolved = Path(path).resolve()
        if not resolved.is_file() or _sha256(resolved.read_bytes()) != source:
            raise RuntimeContractError("Artifact path is absent or does not match source_sha256.")
        sealed = {**dict(artifact), "path": str(resolved)}
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

    def set_objective(self, spec: ObjectiveSpec) -> None:
        if not isinstance(spec, ObjectiveSpec):
            raise RuntimeContractError("set_objective requires ObjectiveSpec.")
        if not spec.cared_outputs or not spec.residuals or not spec.cost:
            raise RuntimeContractError(
                "ObjectiveSpec requires cared outputs, residuals, and cost expression."
            )
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
            }.get(kind)
            if allowed is None or set(cared) != allowed:
                raise RuntimeContractError(
                    f"Unsupported or malformed cared-output declaration '{name}'."
                )
            _validate_cared_output(name, cared)
        for expression in spec.residuals.values():
            _validate_expression(expression, set(spec.cared_outputs))
        _validate_expression(spec.cost, set(spec.residuals))
        self._objective = spec

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

    def evaluate(self, *, backend: Literal["direct", "hb"] = "direct") -> Mapping[str, Any]:
        request = self._request(action="evaluate", backend=backend)
        return self._run_julia(request)

    def optimize(self) -> Mapping[str, Any]:
        if self._optimizer is None:
            raise RuntimeContractError("optimize requires set_optimizer first.")
        if self._optimizer.algorithm != "cma_es":
            raise RuntimeContractError("Circuit Workbench V1 supports only algorithm='cma_es'.")
        if not self._variables:
            raise RuntimeContractError("optimize requires at least one declared VariableSpec.")
        return self._run_julia(self._request(action="optimize", backend="direct"))

    def analyze(self) -> Mapping[str, Any]:
        receipt_path = self._receipt_path()
        if not receipt_path.is_file():
            raise RuntimeContractError(
                "No sealed run receipt exists for this run_id; analyze never recomputes."
            )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("schema") != RECEIPT_SCHEMA:
            raise RuntimeContractError("Receipt schema is not circuit-workbench-run-receipt.v1.")
        expected = receipt.get("canonical_sha256")
        body = dict(receipt)
        body.pop("canonical_sha256", None)
        if not isinstance(expected, str) or expected != _fingerprint(body):
            raise RuntimeContractError("Receipt canonical_sha256 is missing or mismatched.")
        run_dir = (Path(self.run_root).resolve() / self.run_id).resolve()
        request_path = Path(receipt.get("request_path", "")).resolve()
        expected_request_path = run_dir / "circuit-workbench-run-request.v1.json"
        if request_path != expected_request_path or not request_path.is_file():
            raise RuntimeContractError(
                "Receipt request path is not the standard durable request for this run_id."
            )
        request_bytes = request_path.read_bytes()
        if receipt.get("request_sha256") != _sha256(request_bytes):
            raise RuntimeContractError("Receipt durable request hash mismatches its request bytes.")
        request = json.loads(request_bytes)
        request_body = dict(request)
        fingerprint = request_body.pop("fingerprint_sha256", None)
        if fingerprint != _fingerprint(request_body) or fingerprint != receipt.get(
            "request_fingerprint_sha256"
        ):
            raise RuntimeContractError(
                "Request fingerprint does not match durable request or receipt."
            )
        plan = request.get("plan")
        if not isinstance(plan, Mapping):
            raise RuntimeContractError("Receipt Plan is absent from durable request.")
        plan_body = dict(plan)
        plan_hash = plan_body.pop("canonical_sha256", None)
        if plan_hash != _fingerprint(plan_body) or plan_hash != receipt.get("plan_sha256"):
            raise RuntimeContractError("Receipt Plan identity mismatches the durable request.")
        runtime = request.get("runtime")
        julia = _resolved_julia_executable()
        expected_runtime = {
            "python_package_source_sha256": _tree_sha256(
                _PACKAGE_ROOT, excluded_top_level={"_julia"}
            ),
            "runner_tree_sha256": _tree_sha256(_RUNNER_PROJECT, excluded_top_level={"test"}),
            "core_tree_sha256": _tree_sha256(
                _JULIA_ROOT / "SuperconductingCircuitsCore", excluded_top_level={"test"}
            ),
            "julia_executable_path": str(julia),
            "julia_executable_sha256": _sha256(julia.read_bytes()),
        }
        if not isinstance(runtime, Mapping) or any(
            runtime.get(key) != value for key, value in expected_runtime.items()
        ):
            raise RuntimeContractError("Request Python runtime package identity is stale.")
        if receipt.get("python_runtime_source_sha256") != runtime.get(
            "python_package_source_sha256"
        ):
            raise RuntimeContractError(
                "Receipt Python runtime identity mismatches durable request."
            )
        identities = {
            "runner_tree_sha256": expected_runtime["runner_tree_sha256"],
            "core_tree_sha256": expected_runtime["core_tree_sha256"],
            "julia_executable_sha256": expected_runtime["julia_executable_sha256"],
        }
        if any(receipt.get(name) != value for name, value in identities.items()):
            raise RuntimeContractError("Receipt Julia Runner/Core identity is stale.")
        if receipt.get("artifact_bindings") != request.get("artifacts", {}):
            raise RuntimeContractError(
                "Receipt artifact bindings do not exactly match durable request artifacts."
            )
        for name, artifact in request.get("artifacts", {}).items():
            if not isinstance(artifact, Mapping) or not isinstance(artifact.get("path"), str):
                raise RuntimeContractError(f"Artifact '{name}' is malformed in durable request.")
            artifact_path = Path(artifact["path"])
            if not artifact_path.is_file() or _sha256(artifact_path.read_bytes()) != artifact.get(
                "source_sha256"
            ):
                raise RuntimeContractError(
                    f"Artifact '{name}' no longer matches its sealed source hash."
                )
        result = receipt.get("result")
        if result is not None and receipt.get("output_sha256") != _fingerprint(result):
            raise RuntimeContractError("Receipt embedded output hash mismatches result.")
        if (
            isinstance(result, Mapping)
            and result.get("validated_artifacts") is not None
            and result.get("validated_artifacts") != request.get("artifacts", {})
        ):
            raise RuntimeContractError(
                "Result validated artifacts do not cross-bind every durable request artifact."
            )
        if isinstance(result, Mapping) and "ledger_path" in result:
            ledger = Path(result["ledger_path"])
            expected_ledger = run_dir / "circuit-workbench-optimization-ledger.v1.json"
            if (
                ledger != expected_ledger
                or not ledger.is_file()
                or _sha256(ledger.read_bytes()) != receipt.get("ledger_sha256")
            ):
                raise RuntimeContractError("Optimization ledger path/hash mismatches receipt.")
            ledger_data = json.loads(ledger.read_text(encoding="utf-8"))
            if (
                ledger_data.get("schema") != "circuit-workbench-optimization-ledger.v1"
                or ledger_data.get("request_fingerprint_sha256") != fingerprint
            ):
                raise RuntimeContractError(
                    "Optimization ledger does not bind the durable request fingerprint."
                )
        return _ResultHandle(receipt, receipt_path)

    def _request(self, *, action: str, backend: str) -> dict[str, Any]:
        if self._plan is None:
            raise RuntimeContractError("evaluate requires set_plan first.")
        if self._objective is None:
            raise RuntimeContractError("evaluate requires set_objective first.")
        sealed_plan = self._plan.seal(self._libraries)
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
        if backend == "direct":
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
            else:
                raise RuntimeContractError(
                    "Direct backend supports either closed-mode or Schur cared outputs, not a mixture."
                )
        elif backend == "hb":
            if cared_kinds != {"s_parameter"} or reduction is not None:
                raise RuntimeContractError(
                    "HB backend supports S-parameter cared outputs and no ReductionSpec."
                )
        else:
            raise RuntimeContractError(
                "Circuit Workbench V1 supports only direct or hb backend actions."
            )
        julia = _resolved_julia_executable()
        payload: dict[str, Any] = {
            "schema": REQUEST_SCHEMA,
            "action": action,
            "backend": backend,
            "run_id": self.run_id,
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
        payload["fingerprint_sha256"] = _fingerprint(payload)
        return payload

    def _run_julia(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        if not (_RUNNER_PROJECT / "Project.toml").is_file() or not _RUNNER_CLI.is_file():
            raise RuntimeContractError(
                "Circuit Workbench Runner source project is unavailable; this source-editable runtime cannot launch Julia."
            )
        run_dir = Path(self.run_root) / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        receipt = self._receipt_path()
        request_path = run_dir / "circuit-workbench-run-request.v1.json"
        request_bytes = _canonical_bytes(request)
        if request_path.exists() and request_path.read_bytes() != request_bytes:
            raise RuntimeContractError(
                "Existing durable request path has different sealed request bytes."
            )
        _atomic_write(request_path, request_bytes)
        optimizer = request.get("optimizer")
        worker_count = (
            int(optimizer.get("resource_controls", {}).get("worker_count", 1))
            if isinstance(optimizer, Mapping)
            else 1
        )
        subprocess.run(
            [
                str(_resolved_julia_executable()),
                f"--threads={worker_count}",
                f"--project={_RUNNER_PROJECT}",
                str(_RUNNER_CLI),
                str(request_path),
                str(receipt),
            ],
            check=True,
            text=True,
        )
        return self.analyze()

    def _receipt_path(self) -> Path:
        root = Path(self.run_root).resolve()
        target = (root / self.run_id / "circuit-workbench-run-receipt.v1.json").resolve()
        if not target.is_relative_to(root):
            raise RuntimeContractError("run_id escapes run_root.")
        return target


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
        if declared.lowerer == "parallel_lc_resonator" and float(value) <= 0:
            raise RuntimeContractError(
                f"Component '{component.id}' LC parameter '{name}' must be positive."
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
    else:
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


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
        if spec.transform not in {"identity", "log"}:
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
                not math.isfinite(value) or (spec.transform == "log" and value <= 0)
            ):
                raise RuntimeContractError(
                    f"VariableSpec {label} must be finite and positive for log transform."
                )
        if spec.lower is not None and spec.upper is not None and spec.lower >= spec.upper:
            raise RuntimeContractError("VariableSpec lower must be less than upper.")
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
