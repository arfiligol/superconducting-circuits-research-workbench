"""TraceBatch/TraceRecord contracts and local TraceStore helpers for simulation flows."""

from __future__ import annotations

import json
import math
import shutil
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
from sc_core.storage import (
    POSTPROCESS_SWEEP_TRACE_WRITER_VERSION,
    SIMULATION_RAW_SWEEP_TRACE_WRITER_VERSION,
)

from core.shared.persistence.trace_store import (
    LocalZarrTraceStore,
    LocalZarrTraceStoreBackend,
    get_trace_store_backend_binding,
    get_trace_store_path,
)
from core.simulation.application.post_processing import (
    PortMatrixSweep,
    PortMatrixSweepRun,
)
from core.simulation.application.run_simulation import (
    SimulationSweepAxis,
    SimulationSweepPointResult,
    SimulationSweepRun,
    simulation_sweep_run_from_payload,
    simulation_sweep_run_to_payload,
)
from core.simulation.domain.circuit import SimulationResult

TRACE_BATCH_BUNDLE_SCHEMA_KIND = "trace_batch_bundle"
TRACE_BATCH_BUNDLE_SCHEMA_VERSION = "1.0"
TRACE_STORE_BACKEND = "local_zarr"


@dataclass(frozen=True)
class TraceAxisSpec:
    """One axis definition plus numeric values."""

    name: str
    unit: str
    values: np.ndarray

    @property
    def length(self) -> int:
        """Return the axis length."""
        return int(self.values.shape[0])


@dataclass(frozen=True)
class TraceNumericSpec:
    """One canonical trace payload destined for TraceStore."""

    family: str
    parameter: str
    representation: str
    axes: tuple[TraceAxisSpec, ...]
    values: np.ndarray
    trace_meta: dict[str, Any]


def get_trace_store_root() -> Path:
    """Return the repository-local TraceStore root with env override support."""
    return get_trace_store_path()


def _require_local_trace_store_backend() -> LocalZarrTraceStoreBackend:
    """Resolve the local TraceStore backend binding for simulation trace writes."""
    binding = get_trace_store_backend_binding(backend=TRACE_STORE_BACKEND)
    if not isinstance(binding, LocalZarrTraceStoreBackend):
        raise TypeError(
            "Simulation trace persistence currently requires a local_zarr backend binding."
        )
    return binding


def is_trace_batch_bundle_payload(payload: Mapping[str, Any] | None) -> bool:
    """Return whether a result payload follows the trace-batch contract."""
    if not isinstance(payload, Mapping):
        return False
    return str(payload.get("schema_kind", "")).strip() == TRACE_BATCH_BUNDLE_SCHEMA_KIND


def build_raw_simulation_trace_specs(
    *,
    result: SimulationResult,
    sweep_payload: Mapping[str, Any] | None = None,
) -> list[TraceNumericSpec]:
    """Build canonical trace specs for one raw simulation result or parameter sweep."""
    if not isinstance(sweep_payload, Mapping):
        return _build_raw_trace_specs_for_result(
            result=result,
            axes=(
                TraceAxisSpec(
                    name="frequency",
                    unit="GHz",
                    values=np.asarray(result.frequencies_ghz, dtype=np.float64),
                ),
            ),
        )

    sweep_run = simulation_sweep_run_from_payload(sweep_payload)
    if not sweep_run.points:
        raise ValueError("Sweep payload has no points.")

    sweep_axes = tuple(
        TraceAxisSpec(
            name=str(axis.target_value_ref),
            unit=str(axis.unit),
            values=np.asarray(axis.values, dtype=np.float64),
        )
        for axis in sweep_run.axes
    )
    frequency_axis = TraceAxisSpec(
        name="frequency",
        unit="GHz",
        values=np.asarray(sweep_run.representative_result.frequencies_ghz, dtype=np.float64),
    )
    grouped_arrays: dict[tuple[str, str, str, str], np.ndarray] = {}
    spec_lookup: dict[tuple[str, str, str, str], TraceNumericSpec] = {}
    sweep_shape = tuple(axis.length for axis in sweep_axes)

    for point in sweep_run.points:
        point_specs = _build_raw_trace_specs_for_result(
            result=point.result,
            axes=(frequency_axis,),
        )
        for spec in point_specs:
            meta_key = json.dumps(spec.trace_meta, sort_keys=True, separators=(",", ":"))
            grouped_key = (spec.family, spec.parameter, spec.representation, meta_key)
            if grouped_key not in grouped_arrays:
                grouped_arrays[grouped_key] = np.full(
                    (frequency_axis.length, *sweep_shape),
                    np.nan,
                    dtype=np.float64,
                )
                spec_lookup[grouped_key] = spec
            grouped_arrays[grouped_key][(slice(None), *tuple(point.axis_indices))] = spec.values

    materialized_axes = (frequency_axis, *sweep_axes)
    persisted: list[TraceNumericSpec] = []
    for grouped_key in sorted(grouped_arrays):
        base_spec = spec_lookup[grouped_key]
        persisted.append(
            TraceNumericSpec(
                family=base_spec.family,
                parameter=base_spec.parameter,
                representation=base_spec.representation,
                axes=materialized_axes,
                values=grouped_arrays[grouped_key],
                trace_meta=dict(base_spec.trace_meta),
            )
        )
    return persisted


def build_post_processed_trace_specs(
    *,
    runtime_output: PortMatrixSweep | PortMatrixSweepRun,
) -> list[TraceNumericSpec]:
    """Build canonical trace specs for one post-processing output."""
    if isinstance(runtime_output, PortMatrixSweep):
        return _build_postprocess_trace_specs_for_sweep(runtime_output)

    if not runtime_output.points:
        raise ValueError("Post-processed sweep run produced no points.")

    representative = runtime_output.representative_sweep
    frequency_axis = TraceAxisSpec(
        name="frequency",
        unit="GHz",
        values=np.asarray(representative.frequencies_ghz, dtype=np.float64),
    )
    sweep_axes = tuple(
        TraceAxisSpec(
            name=str(axis.target_value_ref),
            unit=str(axis.unit),
            values=np.asarray(axis.values, dtype=np.float64),
        )
        for axis in runtime_output.axes
    )
    grouped_arrays: dict[tuple[str, str, str, str], np.ndarray] = {}
    spec_lookup: dict[tuple[str, str, str, str], TraceNumericSpec] = {}
    sweep_shape = tuple(axis.length for axis in sweep_axes)

    for point in runtime_output.points:
        point_specs = _build_postprocess_trace_specs_for_sweep(point.sweep)
        for spec in point_specs:
            meta_key = json.dumps(spec.trace_meta, sort_keys=True, separators=(",", ":"))
            grouped_key = (spec.family, spec.parameter, spec.representation, meta_key)
            if grouped_key not in grouped_arrays:
                grouped_arrays[grouped_key] = np.full(
                    (frequency_axis.length, *sweep_shape),
                    np.nan,
                    dtype=np.float64,
                )
                spec_lookup[grouped_key] = spec
            grouped_arrays[grouped_key][(slice(None), *tuple(point.axis_indices))] = spec.values

    materialized_axes = (frequency_axis, *sweep_axes)
    persisted: list[TraceNumericSpec] = []
    for grouped_key in sorted(grouped_arrays):
        base_spec = spec_lookup[grouped_key]
        persisted.append(
            TraceNumericSpec(
                family=base_spec.family,
                parameter=base_spec.parameter,
                representation=base_spec.representation,
                axes=materialized_axes,
                values=grouped_arrays[grouped_key],
                trace_meta=dict(base_spec.trace_meta),
            )
        )
    return persisted


def build_trace_batch_bundle_payload(
    *,
    bundle_id: int,
    design_id: int,
    design_name: str,
    source_kind: str,
    stage_kind: str,
    setup_kind: str,
    setup_payload: Mapping[str, Any],
    provenance_payload: Mapping[str, Any],
    trace_records: Sequence[Mapping[str, Any]],
    status: str = "completed",
    setup_version: str = "1.0",
    parent_batch_id: int | None = None,
    summary_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one trace-batch payload around pre-materialized trace metadata."""
    return {
        "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
        "schema_version": TRACE_BATCH_BUNDLE_SCHEMA_VERSION,
        "design_record": {
            "id": int(design_id),
            "name": str(design_name),
        },
        "trace_batch_record": {
            "id": int(bundle_id),
            "design_id": int(design_id),
            "source_kind": str(source_kind),
            "stage_kind": str(stage_kind),
            "parent_batch_id": int(parent_batch_id) if parent_batch_id is not None else None,
            "status": str(status),
            "setup_kind": str(setup_kind),
            "setup_version": str(setup_version),
            "setup_payload": json.loads(json.dumps(dict(setup_payload))),
            "provenance_payload": json.loads(json.dumps(dict(provenance_payload))),
            "summary_payload": (
                json.loads(json.dumps(dict(summary_payload)))
                if isinstance(summary_payload, Mapping)
                else {
                    "trace_count": len(trace_records),
                }
            ),
        },
        "trace_records": [
            json.loads(json.dumps(dict(trace_record))) for trace_record in trace_records
        ],
    }


def rebind_trace_batch_bundle_payload(
    payload: Mapping[str, Any],
    *,
    bundle_id: int,
    design_id: int,
    design_name: str,
    source_kind: str,
    stage_kind: str,
    setup_kind: str,
    setup_payload: Mapping[str, Any],
    provenance_payload: Mapping[str, Any],
    status: str = "completed",
    setup_version: str = "1.0",
    parent_batch_id: int | None = None,
    summary_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebind one pre-materialized trace-batch payload to a persisted bundle boundary."""
    if not is_trace_batch_bundle_payload(payload):
        raise ValueError("Payload is not a trace-batch bundle.")
    raw_trace_records = payload.get("trace_records", [])
    if not isinstance(raw_trace_records, list) or not raw_trace_records:
        raise ValueError("Trace-batch payload has no trace records.")
    trace_records = [
        json.loads(json.dumps(dict(trace_record)))
        for trace_record in raw_trace_records
        if isinstance(trace_record, Mapping)
    ]
    return build_trace_batch_bundle_payload(
        bundle_id=bundle_id,
        design_id=design_id,
        design_name=design_name,
        source_kind=source_kind,
        stage_kind=stage_kind,
        setup_kind=setup_kind,
        setup_payload=setup_payload,
        provenance_payload=provenance_payload,
        trace_records=trace_records,
        status=status,
        setup_version=setup_version,
        parent_batch_id=parent_batch_id,
        summary_payload=summary_payload,
    )


def _build_inflight_store_key(*, design_id: int, run_id: str, stage: str = "raw") -> str:
    """Build one stable runtime store key for in-flight simulation sweeps."""
    normalized_run_id = "".join(
        character
        for character in str(run_id).strip()
        if character.isalnum() or character in {"-", "_"}
    ).strip("-_")
    if not normalized_run_id:
        raise ValueError("run_id is required for incremental sweep persistence.")
    normalized_stage = "".join(
        character
        for character in str(stage).strip()
        if character.isalnum() or character in {"-", "_"}
    ).strip("-_")
    if not normalized_stage:
        normalized_stage = "raw"
    return f"designs/{int(design_id)}/runtime/{normalized_run_id}-{normalized_stage}.zarr"


@dataclass
class IncrementalRawSimulationSweepWriter:
    """Incrementally materialize one raw parameter sweep into TraceStore."""

    design_id: int
    design_name: str
    run_id: str
    sweep_axes: tuple[SimulationSweepAxis, ...]
    source_kind: str = "circuit_simulation"
    stage_kind: str = "raw"
    setup_kind: str = "circuit_simulation.raw"
    status: str = "completed"

    def __post_init__(self) -> None:
        backend_binding = _require_local_trace_store_backend()
        self._trace_store = LocalZarrTraceStore(root_path=get_trace_store_root())
        self._store_key = _build_inflight_store_key(
            design_id=int(self.design_id),
            run_id=self.run_id,
            stage=self.stage_kind,
        )
        self._store_path = backend_binding.resolve_store_path(store_key=self._store_key)
        if self._store_path.exists():
            shutil.rmtree(self._store_path)
        self._trace_store.root_path.mkdir(parents=True, exist_ok=True)
        self._trace_records: list[dict[str, Any]] = []
        self._trace_record_lookup: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self._representative_result: SimulationResult | None = None
        self._frequency_axis: TraceAxisSpec | None = None

    @property
    def representative_result(self) -> SimulationResult:
        """Return the representative result once at least one point has been written."""
        if self._representative_result is None:
            raise ValueError("Incremental sweep writer has no representative result yet.")
        return self._representative_result

    @property
    def trace_count(self) -> int:
        """Return the number of canonical traces materialized for this sweep."""
        return len(self._trace_records)

    def append_point(
        self,
        *,
        point_index: int,
        axis_indices: Sequence[int],
        axis_values: Mapping[str, float],
        result: SimulationResult,
    ) -> None:
        """Persist one sweep point directly into TraceStore-backed ND traces."""
        if self._representative_result is None:
            self._initialize_from_first_result(result)
        if self._frequency_axis is None:
            raise ValueError("Incremental sweep writer is missing frequency metadata.")

        point_specs = _build_raw_trace_specs_for_result(
            result=result,
            axes=(self._frequency_axis,),
        )
        normalized_axis_indices = tuple(int(value) for value in axis_indices)
        selection = (slice(None), *normalized_axis_indices)
        for spec in point_specs:
            meta_key = json.dumps(spec.trace_meta, sort_keys=True, separators=(",", ":"))
            grouped_key = (spec.family, spec.parameter, spec.representation, meta_key)
            trace_record = self._trace_record_lookup.get(grouped_key)
            if trace_record is None:
                raise ValueError(
                    "Sweep point trace shape drift detected; grouped trace metadata changed "
                    f"at point {int(point_index)} for {spec.family}/{spec.parameter}/"
                    f"{spec.representation}."
                )
            self._trace_store.write_trace_slice(
                trace_record["store_ref"],
                selection=selection,
                values=spec.values,
            )

    def build_payload(
        self,
        *,
        summary_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Return one canonical trace-batch payload backed by the incremental store."""
        return build_trace_batch_bundle_payload(
            bundle_id=0,
            design_id=int(self.design_id),
            design_name=str(self.design_name),
            source_kind=self.source_kind,
            stage_kind=self.stage_kind,
            setup_kind=self.setup_kind,
            setup_payload={},
            provenance_payload={},
            trace_records=self._trace_records,
            status=self.status,
            summary_payload=summary_payload,
        )

    def cleanup(self) -> None:
        """Remove any on-disk runtime trace-store artifacts for this writer."""
        if self._store_path.exists():
            shutil.rmtree(self._store_path)

    def _initialize_from_first_result(self, result: SimulationResult) -> None:
        self._representative_result = result
        sweep_axes = tuple(
            TraceAxisSpec(
                name=str(axis.target_value_ref),
                unit=str(axis.unit),
                values=np.asarray(axis.values, dtype=np.float64),
            )
            for axis in self.sweep_axes
        )
        self._frequency_axis = TraceAxisSpec(
            name="frequency",
            unit="GHz",
            values=np.asarray(result.frequencies_ghz, dtype=np.float64),
        )
        materialized_axes = (self._frequency_axis, *sweep_axes)
        sweep_shape = tuple(axis.length for axis in sweep_axes)
        shape = (self._frequency_axis.length, *sweep_shape)
        point_specs = _build_raw_trace_specs_for_result(
            result=result,
            axes=(self._frequency_axis,),
        )
        for trace_index, spec in enumerate(point_specs, start=1):
            write_result = self._trace_store.create_trace(
                design_id=int(self.design_id),
                batch_id=0,
                trace_id=trace_index,
                shape=shape,
                dtype=np.dtype(np.float64),
                axes=[
                    {
                        "name": axis.name,
                        "unit": axis.unit,
                        "values": axis.values,
                    }
                    for axis in materialized_axes
                ],
                chunk_shape=_default_chunk_shape(shape),
                array_path="values",
                store_key=self._store_key,
                payload_role="raw",
                writer_version=SIMULATION_RAW_SWEEP_TRACE_WRITER_VERSION,
            )
            store_ref = {
                **dict(write_result.store_ref),
                "axis_array_refs": [
                    {
                        "name": axis.name,
                        "unit": axis.unit,
                        "array_path": f"axes/{axis_position}",
                        "shape": [axis.length],
                        "dtype": "float64",
                    }
                    for axis_position, axis in enumerate(materialized_axes)
                ],
            }
            trace_record = {
                "id": int(trace_index),
                "design_id": int(self.design_id),
                "family": spec.family,
                "parameter": spec.parameter,
                "representation": spec.representation,
                "axes": [
                    {
                        "name": axis.name,
                        "unit": axis.unit,
                        "length": axis.length,
                    }
                    for axis in materialized_axes
                ],
                "trace_meta": dict(spec.trace_meta),
                "store_ref": store_ref,
            }
            meta_key = json.dumps(spec.trace_meta, sort_keys=True, separators=(",", ":"))
            grouped_key = (spec.family, spec.parameter, spec.representation, meta_key)
            self._trace_record_lookup[grouped_key] = trace_record
            self._trace_records.append(trace_record)


@dataclass
class IncrementalPostProcessedSweepWriter:
    """Incrementally materialize one post-processed parameter sweep into TraceStore."""

    design_id: int
    design_name: str
    run_id: str
    sweep_axes: tuple[SimulationSweepAxis, ...]
    representative_point_index: int = 0
    source_kind: str = "circuit_simulation"
    stage_kind: str = "postprocess"
    setup_kind: str = "circuit_simulation.postprocess"
    status: str = "completed"

    def __post_init__(self) -> None:
        backend_binding = _require_local_trace_store_backend()
        self._trace_store = LocalZarrTraceStore(root_path=get_trace_store_root())
        self._store_key = _build_inflight_store_key(
            design_id=int(self.design_id),
            run_id=self.run_id,
            stage=self.stage_kind,
        )
        self._store_path = backend_binding.resolve_store_path(store_key=self._store_key)
        if self._store_path.exists():
            shutil.rmtree(self._store_path)
        self._trace_store.root_path.mkdir(parents=True, exist_ok=True)
        self._trace_records: list[dict[str, Any]] = []
        self._trace_record_lookup: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self._representative_sweep: PortMatrixSweep | None = None
        self._frequency_axis: TraceAxisSpec | None = None

    @property
    def representative_sweep(self) -> PortMatrixSweep:
        """Return the representative post-processed sweep once written."""
        if self._representative_sweep is None:
            raise ValueError("Incremental post-processed sweep writer has no representative sweep.")
        return self._representative_sweep

    @property
    def trace_count(self) -> int:
        """Return the number of canonical traces materialized for this sweep."""
        return len(self._trace_records)

    def append_point(
        self,
        *,
        point_index: int,
        axis_indices: Sequence[int],
        sweep: PortMatrixSweep,
    ) -> None:
        """Persist one post-processed sweep point directly into TraceStore-backed ND traces."""
        if self._representative_sweep is None:
            self._initialize_from_first_sweep(sweep)
        if self._frequency_axis is None:
            raise ValueError(
                "Incremental post-processed sweep writer is missing frequency metadata."
            )
        if int(point_index) == int(self.representative_point_index):
            self._representative_sweep = sweep

        point_specs = _build_postprocess_trace_specs_for_sweep(sweep)
        normalized_axis_indices = tuple(int(value) for value in axis_indices)
        selection = (slice(None), *normalized_axis_indices)
        for spec in point_specs:
            meta_key = json.dumps(spec.trace_meta, sort_keys=True, separators=(",", ":"))
            grouped_key = (spec.family, spec.parameter, spec.representation, meta_key)
            trace_record = self._trace_record_lookup.get(grouped_key)
            if trace_record is None:
                raise ValueError(
                    "Post-processed sweep trace shape drift detected; grouped trace metadata "
                    f"changed at point {int(point_index)} for {spec.family}/{spec.parameter}/"
                    f"{spec.representation}."
                )
            self._trace_store.write_trace_slice(
                trace_record["store_ref"],
                selection=selection,
                values=spec.values,
            )

    def build_payload(
        self,
        *,
        summary_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Return one canonical post-processed trace-batch payload.

        The numeric payload remains backed by the incremental trace store.
        """
        return build_trace_batch_bundle_payload(
            bundle_id=0,
            design_id=int(self.design_id),
            design_name=str(self.design_name),
            source_kind=self.source_kind,
            stage_kind=self.stage_kind,
            setup_kind=self.setup_kind,
            setup_payload={},
            provenance_payload={},
            trace_records=self._trace_records,
            status=self.status,
            summary_payload=summary_payload,
        )

    def cleanup(self) -> None:
        """Remove any on-disk runtime trace-store artifacts for this writer."""
        if self._store_path.exists():
            shutil.rmtree(self._store_path)

    def _initialize_from_first_sweep(self, sweep: PortMatrixSweep) -> None:
        self._representative_sweep = sweep
        sweep_axes = tuple(
            TraceAxisSpec(
                name=str(axis.target_value_ref),
                unit=str(axis.unit),
                values=np.asarray(axis.values, dtype=np.float64),
            )
            for axis in self.sweep_axes
        )
        self._frequency_axis = TraceAxisSpec(
            name="frequency",
            unit="GHz",
            values=np.asarray(sweep.frequencies_ghz, dtype=np.float64),
        )
        materialized_axes = (self._frequency_axis, *sweep_axes)
        sweep_shape = tuple(axis.length for axis in sweep_axes)
        shape = (self._frequency_axis.length, *sweep_shape)
        point_specs = _build_postprocess_trace_specs_for_sweep(sweep)
        for trace_index, spec in enumerate(point_specs, start=1):
            write_result = self._trace_store.create_trace(
                design_id=int(self.design_id),
                batch_id=0,
                trace_id=trace_index,
                shape=shape,
                dtype=np.dtype(np.float64),
                axes=[
                    {
                        "name": axis.name,
                        "unit": axis.unit,
                        "values": axis.values,
                    }
                    for axis in materialized_axes
                ],
                chunk_shape=_default_chunk_shape(shape),
                array_path="values",
                store_key=self._store_key,
                payload_role="processed",
                writer_version=POSTPROCESS_SWEEP_TRACE_WRITER_VERSION,
            )
            store_ref = {
                **dict(write_result.store_ref),
                "axis_array_refs": [
                    {
                        "name": axis.name,
                        "unit": axis.unit,
                        "array_path": f"axes/{axis_position}",
                        "shape": [axis.length],
                        "dtype": "float64",
                    }
                    for axis_position, axis in enumerate(materialized_axes)
                ],
            }
            trace_record = {
                "id": int(trace_index),
                "design_id": int(self.design_id),
                "family": spec.family,
                "parameter": spec.parameter,
                "representation": spec.representation,
                "axes": [
                    {
                        "name": axis.name,
                        "unit": axis.unit,
                        "length": axis.length,
                    }
                    for axis in materialized_axes
                ],
                "trace_meta": dict(spec.trace_meta),
                "store_ref": store_ref,
            }
            meta_key = json.dumps(spec.trace_meta, sort_keys=True, separators=(",", ":"))
            grouped_key = (spec.family, spec.parameter, spec.representation, meta_key)
            self._trace_record_lookup[grouped_key] = trace_record
            self._trace_records.append(trace_record)


def persist_trace_batch_bundle(
    *,
    bundle_id: int,
    design_id: int,
    design_name: str,
    source_kind: str,
    stage_kind: str,
    setup_kind: str,
    setup_payload: Mapping[str, Any],
    provenance_payload: Mapping[str, Any],
    trace_specs: Sequence[TraceNumericSpec],
    status: str = "completed",
    setup_version: str = "1.0",
    parent_batch_id: int | None = None,
    summary_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write numeric traces into the local TraceStore and return bundle metadata."""
    if not trace_specs:
        raise ValueError("At least one trace spec is required.")

    backend_binding = _require_local_trace_store_backend()
    store_key = backend_binding.build_store_key(design_id=int(design_id), batch_id=int(bundle_id))
    store_path = backend_binding.resolve_store_path(store_key=store_key)
    if store_path.exists():
        shutil.rmtree(store_path)
    _write_group(store_path)
    _write_group(store_path / "traces")

    trace_records: list[dict[str, Any]] = []
    for trace_index, spec in enumerate(trace_specs, start=1):
        trace_group = store_path / "traces" / str(trace_index)
        _write_group(trace_group)
        _write_group(trace_group / "axes")
        values_group = trace_group / "values"
        chunk_shape = _default_chunk_shape(spec.values.shape)
        _write_zarr_array(values_group, spec.values, chunk_shape=chunk_shape)

        axis_refs: list[dict[str, Any]] = []
        for axis_position, axis in enumerate(spec.axes):
            axis_group = trace_group / "axes" / f"{axis_position}"
            _write_zarr_array(
                axis_group,
                np.asarray(axis.values, dtype=np.float64),
                chunk_shape=(axis.length,),
            )
            axis_refs.append(
                {
                    "name": axis.name,
                    "unit": axis.unit,
                    "array_path": f"axes/{axis_position}",
                    "shape": [axis.length],
                    "dtype": "float64",
                }
            )

        trace_records.append(
            {
                "id": trace_index,
                "design_id": int(design_id),
                "family": spec.family,
                "parameter": spec.parameter,
                "representation": spec.representation,
                "axes": [
                    {
                        "name": axis.name,
                        "unit": axis.unit,
                        "length": axis.length,
                    }
                    for axis in spec.axes
                ],
                "trace_meta": dict(spec.trace_meta),
                "store_ref": {
                    "backend": TRACE_STORE_BACKEND,
                    "store_key": store_key,
                    "store_uri": backend_binding.build_store_uri(store_key=store_key),
                    "group_path": f"/traces/{trace_index}",
                    "array_path": "values",
                    "dtype": str(np.asarray(spec.values).dtype),
                    "shape": [int(value) for value in spec.values.shape],
                    "chunk_shape": [int(value) for value in chunk_shape],
                    "axis_array_refs": axis_refs,
                    "schema_version": TRACE_BATCH_BUNDLE_SCHEMA_VERSION,
                },
            }
        )

    return build_trace_batch_bundle_payload(
        bundle_id=bundle_id,
        design_id=design_id,
        design_name=design_name,
        source_kind=source_kind,
        stage_kind=stage_kind,
        setup_kind=setup_kind,
        setup_payload=setup_payload,
        provenance_payload=provenance_payload,
        trace_records=trace_records,
        status=status,
        setup_version=setup_version,
        parent_batch_id=parent_batch_id,
        summary_payload=summary_payload,
    )


def load_raw_simulation_bundle(
    payload: Mapping[str, Any],
) -> tuple[SimulationResult, dict[str, Any] | None]:
    """Rebuild preview data from one trace-batch payload."""
    if not is_trace_batch_bundle_payload(payload):
        raise ValueError("Payload is not a trace-batch bundle.")

    trace_store = LocalZarrTraceStore(root_path=get_trace_store_root())
    trace_records = payload.get("trace_records", [])
    if not isinstance(trace_records, list) or not trace_records:
        raise ValueError("Trace-batch bundle has no trace records.")

    first_axes = trace_records[0].get("axes", [])
    if not isinstance(first_axes, list) or not first_axes:
        raise ValueError("Trace-batch bundle has no axis metadata.")

    sweep_axis_defs = first_axes[1:]
    if not sweep_axis_defs:
        result = _build_simulation_result_from_trace_slice(
            trace_store=trace_store,
            trace_records=trace_records,
        )
        return (result, None)

    representative_point_index = int(
        payload.get("trace_batch_record", {})
        .get("summary_payload", {})
        .get(
            "representative_point_index",
            0,
        )
    )
    first_store_ref = trace_records[0].get("store_ref", {})
    sweep_axes: list[SimulationSweepAxis] = []
    for axis_offset, axis_def in enumerate(sweep_axis_defs, start=1):
        axis_values = _load_axis_values(
            trace_store=trace_store,
            store_ref=first_store_ref,
            axis_name=str(axis_def.get("name", "")),
            axis_index=axis_offset,
        )
        sweep_axes.append(
            SimulationSweepAxis(
                target_value_ref=str(axis_def.get("name", "")),
                unit=str(axis_def.get("unit", "")),
                values=tuple(float(value) for value in axis_values.tolist()),
            )
        )

    points: list[SimulationSweepPointResult] = []
    sweep_ranges = [range(len(axis.values)) for axis in sweep_axes]
    for point_index, axis_indices in enumerate(product(*sweep_ranges)):
        axis_values = {
            axis.target_value_ref: float(axis.values[axis_position])
            for axis, axis_position in zip(sweep_axes, axis_indices, strict=False)
        }
        points.append(
            SimulationSweepPointResult(
                point_index=point_index,
                axis_indices=tuple(int(value) for value in axis_indices),
                axis_values=axis_values,
                result=_build_simulation_result_from_trace_slice(
                    trace_store=trace_store,
                    trace_records=trace_records,
                    axis_indices=tuple(int(value) for value in axis_indices),
                ),
            )
        )

    representative_point_index = max(0, min(len(points) - 1, representative_point_index))
    sweep_run = SimulationSweepRun(
        axes=tuple(sweep_axes),
        points=tuple(points),
        representative_point_index=representative_point_index,
    )
    return (
        sweep_run.representative_result,
        simulation_sweep_run_to_payload(sweep_run),
    )


def _build_raw_trace_specs_for_result(
    *,
    result: SimulationResult,
    axes: tuple[TraceAxisSpec, ...],
) -> list[TraceNumericSpec]:
    """Build one trace-spec list for a single SimulationResult projection."""
    specs: list[TraceNumericSpec] = []

    resolved_s_real = result._resolved_mode_s_parameter_real()
    resolved_s_imag = result._resolved_mode_s_parameter_imag()
    for label in sorted(set(resolved_s_real) & set(resolved_s_imag)):
        parsed = SimulationResult._parse_mode_trace_label(label)
        if parsed is None:
            continue
        output_mode, output_port, input_mode, input_port = parsed
        parameter = f"S{output_port}{input_port}"
        trace_meta = {
            "label": label,
            "output_mode": list(output_mode),
            "output_port": int(output_port),
            "input_mode": list(input_mode),
            "input_port": int(input_port),
        }
        specs.extend(
            (
                TraceNumericSpec(
                    family="s_matrix",
                    parameter=parameter,
                    representation="real",
                    axes=axes,
                    values=np.asarray(resolved_s_real[label], dtype=np.float64),
                    trace_meta=trace_meta,
                ),
                TraceNumericSpec(
                    family="s_matrix",
                    parameter=parameter,
                    representation="imaginary",
                    axes=axes,
                    values=np.asarray(resolved_s_imag[label], dtype=np.float64),
                    trace_meta=trace_meta,
                ),
            )
        )

    specs.extend(
        _build_mode_trace_specs(
            family="z_matrix",
            parameter_prefix="Z",
            real_map=result.z_parameter_mode_real,
            imag_map=result.z_parameter_mode_imag,
            axes=axes,
        )
    )
    specs.extend(
        _build_mode_trace_specs(
            family="y_matrix",
            parameter_prefix="Y",
            real_map=result.y_parameter_mode_real,
            imag_map=result.y_parameter_mode_imag,
            axes=axes,
        )
    )
    specs.extend(
        _build_scalar_mode_trace_specs(
            family="qe",
            parameter_prefix="QE",
            value_map=result.qe_parameter_mode,
            axes=axes,
        )
    )
    specs.extend(
        _build_scalar_mode_trace_specs(
            family="qe_ideal",
            parameter_prefix="QEideal",
            value_map=result.qe_ideal_parameter_mode,
            axes=axes,
        )
    )
    specs.extend(
        _build_commutation_trace_specs(
            value_map=result.cm_parameter_mode,
            axes=axes,
        )
    )
    return specs


def _build_mode_trace_specs(
    *,
    family: str,
    parameter_prefix: str,
    real_map: Mapping[str, Sequence[float]],
    imag_map: Mapping[str, Sequence[float]],
    axes: tuple[TraceAxisSpec, ...],
) -> list[TraceNumericSpec]:
    """Build one real/imag trace-spec list for mode-aware matrix families."""
    specs: list[TraceNumericSpec] = []
    for label in sorted(set(real_map) & set(imag_map)):
        parsed = SimulationResult._parse_mode_trace_label(label)
        if parsed is None:
            continue
        output_mode, output_port, input_mode, input_port = parsed
        parameter = f"{parameter_prefix}{output_port}{input_port}"
        trace_meta = {
            "label": label,
            "output_mode": list(output_mode),
            "output_port": int(output_port),
            "input_mode": list(input_mode),
            "input_port": int(input_port),
        }
        specs.extend(
            (
                TraceNumericSpec(
                    family=family,
                    parameter=parameter,
                    representation="real",
                    axes=axes,
                    values=np.asarray(real_map[label], dtype=np.float64),
                    trace_meta=trace_meta,
                ),
                TraceNumericSpec(
                    family=family,
                    parameter=parameter,
                    representation="imaginary",
                    axes=axes,
                    values=np.asarray(imag_map[label], dtype=np.float64),
                    trace_meta=trace_meta,
                ),
            )
        )
    return specs


def _build_scalar_mode_trace_specs(
    *,
    family: str,
    parameter_prefix: str,
    value_map: Mapping[str, Sequence[float]],
    axes: tuple[TraceAxisSpec, ...],
) -> list[TraceNumericSpec]:
    """Build one value-trace list for mode-aware scalar families."""
    specs: list[TraceNumericSpec] = []
    for label in sorted(value_map):
        parsed = SimulationResult._parse_mode_trace_label(label)
        if parsed is None:
            continue
        output_mode, output_port, input_mode, input_port = parsed
        specs.append(
            TraceNumericSpec(
                family=family,
                parameter=f"{parameter_prefix}{output_port}{input_port}",
                representation="value",
                axes=axes,
                values=np.asarray(value_map[label], dtype=np.float64),
                trace_meta={
                    "label": label,
                    "output_mode": list(output_mode),
                    "output_port": int(output_port),
                    "input_mode": list(input_mode),
                    "input_port": int(input_port),
                },
            )
        )
    return specs


def _build_commutation_trace_specs(
    *,
    value_map: Mapping[str, Sequence[float]],
    axes: tuple[TraceAxisSpec, ...],
) -> list[TraceNumericSpec]:
    """Build one value-trace list for commutation traces."""
    specs: list[TraceNumericSpec] = []
    for label in sorted(value_map):
        parsed = SimulationResult._parse_cm_trace_label(label)
        if parsed is None:
            continue
        output_mode, output_port = parsed
        specs.append(
            TraceNumericSpec(
                family="commutation",
                parameter=f"CM{output_port}",
                representation="value",
                axes=axes,
                values=np.asarray(value_map[label], dtype=np.float64),
                trace_meta={
                    "label": label,
                    "output_mode": list(output_mode),
                    "output_port": int(output_port),
                },
            )
        )
    return specs


def _build_postprocess_trace_specs_for_sweep(
    sweep: PortMatrixSweep,
) -> list[TraceNumericSpec]:
    """Build one trace-spec list for a single post-processed Y sweep."""
    frequency_axis = TraceAxisSpec(
        name="frequency",
        unit="GHz",
        values=np.asarray(sweep.frequencies_ghz, dtype=np.float64),
    )
    specs: list[TraceNumericSpec] = []
    mode_token = list(sweep.mode)
    for row_index, row_label in enumerate(sweep.labels):
        for col_index, col_label in enumerate(sweep.labels):
            parameter = _format_post_processed_parameter_name(
                row_label=str(row_label),
                col_label=str(col_label),
                mode=sweep.mode,
            )
            complex_values = np.asarray(sweep.trace(row_index, col_index), dtype=np.complex128)
            trace_meta = {
                "row_label": str(row_label),
                "col_label": str(col_label),
                "mode": mode_token,
                "source_kind": str(sweep.source_kind),
                "labels": [str(label) for label in sweep.labels],
            }
            specs.extend(
                (
                    TraceNumericSpec(
                        family="y_matrix",
                        parameter=parameter,
                        representation="real",
                        axes=(frequency_axis,),
                        values=np.asarray(complex_values.real, dtype=np.float64),
                        trace_meta=trace_meta,
                    ),
                    TraceNumericSpec(
                        family="y_matrix",
                        parameter=parameter,
                        representation="imaginary",
                        axes=(frequency_axis,),
                        values=np.asarray(complex_values.imag, dtype=np.float64),
                        trace_meta=trace_meta,
                    ),
                )
            )
    return specs


def _format_post_processed_parameter_name(
    *,
    row_label: str,
    col_label: str,
    mode: tuple[int, ...],
) -> str:
    """Build the canonical Y-parameter name for post-processed traces."""
    if row_label.isdigit() and col_label.isdigit():
        base = f"Y{row_label}{col_label}"
    else:
        row_token = _sanitize_postprocess_label_token(row_label)
        col_token = _sanitize_postprocess_label_token(col_label)
        base = f"Y_{row_token}_{col_token}"
    mode_tuple = tuple(int(value) for value in mode)
    return f"{base} [om={mode_tuple}, im={mode_tuple}]"


def _sanitize_postprocess_label_token(label: str) -> str:
    """Sanitize transformed port labels into stable parameter tokens."""
    sanitized = (
        str(label)
        .replace("(", "_")
        .replace(")", "")
        .replace(",", "_")
        .replace(" ", "")
        .replace("-", "_")
        .replace("/", "_")
    )
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    return sanitized.strip("_") or "x"


def _build_simulation_result_from_trace_slice(
    *,
    trace_store: LocalZarrTraceStore,
    trace_records: Sequence[Mapping[str, Any]],
    axis_indices: tuple[int, ...] | None = None,
) -> SimulationResult:
    """Rebuild one SimulationResult from all trace records at one sweep slice."""
    first_store_ref = trace_records[0].get("store_ref", {})
    frequencies = _load_axis_values(
        trace_store=trace_store,
        store_ref=first_store_ref,
        axis_name="frequency",
        axis_index=0,
    ).astype(np.float64)

    s_real: dict[str, list[float]] = {}
    s_imag: dict[str, list[float]] = {}
    z_real: dict[str, list[float]] = {}
    z_imag: dict[str, list[float]] = {}
    y_real: dict[str, list[float]] = {}
    y_imag: dict[str, list[float]] = {}
    qe_values: dict[str, list[float]] = {}
    qe_ideal_values: dict[str, list[float]] = {}
    cm_values: dict[str, list[float]] = {}
    zero_mode_s_real: dict[str, list[float]] = {}
    zero_mode_s_imag: dict[str, list[float]] = {}
    ports: set[int] = set()
    modes: set[tuple[int, ...]] = set()

    for trace_record in trace_records:
        store_ref = trace_record.get("store_ref", {})
        trace_meta = trace_record.get("trace_meta", {})
        label = str(trace_meta.get("label", "")).strip()
        values = _load_trace_values(
            trace_store=trace_store,
            store_ref=store_ref,
            axis_indices=axis_indices,
        )
        family = str(trace_record.get("family", "")).strip()
        representation = str(trace_record.get("representation", "")).strip()
        output_mode = tuple(int(value) for value in trace_meta.get("output_mode", [])) or (0,)
        input_mode = tuple(int(value) for value in trace_meta.get("input_mode", [])) or (0,)
        output_port = int(trace_meta.get("output_port", 0) or 0)
        input_port = int(trace_meta.get("input_port", 0) or 0)

        if family in {"s_matrix", "z_matrix", "y_matrix", "qe", "qe_ideal"}:
            if output_port > 0:
                ports.add(output_port)
            if input_port > 0:
                ports.add(input_port)
            modes.add(output_mode)
            modes.add(input_mode)
        elif family == "commutation":
            if output_port > 0:
                ports.add(output_port)
            modes.add(output_mode)

        if family == "s_matrix":
            if representation == "real":
                s_real[label] = values
                if output_mode == (0,) and input_mode == (0,):
                    zero_mode_s_real[f"S{output_port}{input_port}"] = values
            elif representation == "imaginary":
                s_imag[label] = values
                if output_mode == (0,) and input_mode == (0,):
                    zero_mode_s_imag[f"S{output_port}{input_port}"] = values
        elif family == "z_matrix":
            if representation == "real":
                z_real[label] = values
            elif representation == "imaginary":
                z_imag[label] = values
        elif family == "y_matrix":
            if representation == "real":
                y_real[label] = values
            elif representation == "imaginary":
                y_imag[label] = values
        elif family == "qe" and representation == "value":
            qe_values[label] = values
        elif family == "qe_ideal" and representation == "value":
            qe_ideal_values[label] = values
        elif family == "commutation" and representation == "value":
            cm_values[label] = values

    s11_real = list(zero_mode_s_real.get("S11", [0.0 for _ in frequencies.tolist()]))
    s11_imag = list(zero_mode_s_imag.get("S11", [0.0 for _ in frequencies.tolist()]))
    return SimulationResult(
        frequencies_ghz=[float(value) for value in frequencies.tolist()],
        s11_real=s11_real,
        s11_imag=s11_imag,
        port_indices=sorted(ports) or [1],
        mode_indices=sorted(modes) or [(0,)],
        s_parameter_real=zero_mode_s_real,
        s_parameter_imag=zero_mode_s_imag,
        s_parameter_mode_real=s_real,
        s_parameter_mode_imag=s_imag,
        z_parameter_mode_real=z_real,
        z_parameter_mode_imag=z_imag,
        y_parameter_mode_real=y_real,
        y_parameter_mode_imag=y_imag,
        qe_parameter_mode=qe_values,
        qe_ideal_parameter_mode=qe_ideal_values,
        cm_parameter_mode=cm_values,
    )


def _load_axis_values(
    *,
    trace_store: LocalZarrTraceStore,
    store_ref: Mapping[str, Any],
    axis_name: str,
    axis_index: int,
) -> np.ndarray:
    """Load one axis array from the TraceStore via slice-first reads."""
    axis_refs = store_ref.get("axis_array_refs", [])
    if not isinstance(axis_refs, list):
        raise ValueError("TraceStore ref is missing axis_array_refs.")
    target_ref = None
    for candidate in axis_refs:
        if (
            isinstance(candidate, Mapping)
            and str(candidate.get("name", "")) == str(axis_name)
            and str(candidate.get("array_path", "")).endswith(str(axis_index))
        ):
            target_ref = candidate
            break
    if target_ref is None:
        for candidate in axis_refs:
            if isinstance(candidate, Mapping) and str(candidate.get("name", "")) == str(axis_name):
                target_ref = candidate
                break
    if target_ref is None:
        raise ValueError(f"Axis '{axis_name}' is not available in store_ref.")

    return np.asarray(
        trace_store.read_axis_slice(
            store_ref,
            axis_name=str(axis_name),
            selection=slice(None),
        )
    )


def _load_trace_values(
    *,
    trace_store: LocalZarrTraceStore,
    store_ref: Mapping[str, Any],
    axis_indices: tuple[int, ...] | None,
) -> list[float]:
    """Load one trace array slice via the TraceStore abstraction."""
    selection: tuple[slice | int, ...]
    if axis_indices:
        selection = (slice(None), *tuple(int(value) for value in axis_indices))
    else:
        selection = (slice(None),)
    values = trace_store.read_trace_slice(
        store_ref,
        selection=selection,
    )
    return [float(value) for value in np.asarray(values, dtype=np.float64).tolist()]


def _default_chunk_shape(shape: Sequence[int]) -> tuple[int, ...]:
    """Choose a frequency-major chunk layout for sweep-friendly slices."""
    if len(shape) <= 1:
        return tuple(int(value) for value in shape)
    return (int(shape[0]), *tuple(1 for _ in shape[1:]))


def _write_group(path: Path) -> None:
    """Create one Zarr group directory and metadata marker."""
    path.mkdir(parents=True, exist_ok=True)
    (path / ".zgroup").write_text(
        json.dumps({"zarr_format": 2}, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def _write_zarr_array(path: Path, array: np.ndarray, *, chunk_shape: Sequence[int]) -> None:
    """Write one uncompressed Zarr v2 array with directory-store chunks."""
    path.mkdir(parents=True, exist_ok=True)
    normalized = np.asarray(array)
    chunks = tuple(int(value) for value in chunk_shape)
    metadata = {
        "zarr_format": 2,
        "shape": [int(value) for value in normalized.shape],
        "chunks": [int(value) for value in chunks],
        "dtype": normalized.dtype.str,
        "compressor": None,
        "fill_value": None,
        "order": "C",
        "filters": None,
    }
    (path / ".zarray").write_text(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    chunk_ranges = [
        range(math.ceil(size / chunk))
        for size, chunk in zip(normalized.shape, chunks, strict=False)
    ]
    for chunk_index in product(*chunk_ranges):
        slices = tuple(
            slice(position * chunk, min((position + 1) * chunk, size))
            for position, chunk, size in zip(chunk_index, chunks, normalized.shape, strict=False)
        )
        chunk_array = np.asarray(normalized[slices], dtype=normalized.dtype, order="C")
        (path / _chunk_key(chunk_index)).write_bytes(chunk_array.tobytes(order="C"))


def _read_zarr_array(path: Path) -> np.ndarray:
    """Read one uncompressed Zarr v2 array written by this module."""
    metadata = json.loads((path / ".zarray").read_text(encoding="utf-8"))
    shape = tuple(int(value) for value in metadata["shape"])
    chunks = tuple(int(value) for value in metadata["chunks"])
    dtype = np.dtype(metadata["dtype"])
    result = np.empty(shape, dtype=dtype)

    chunk_ranges = [
        range(math.ceil(size / chunk)) for size, chunk in zip(shape, chunks, strict=False)
    ]
    for chunk_index in product(*chunk_ranges):
        slices = tuple(
            slice(position * chunk, min((position + 1) * chunk, size))
            for position, chunk, size in zip(chunk_index, chunks, shape, strict=False)
        )
        chunk_shape = tuple(slice_.stop - slice_.start for slice_ in slices)
        chunk_payload = np.frombuffer(
            (path / _chunk_key(chunk_index)).read_bytes(),
            dtype=dtype,
        ).reshape(chunk_shape, order="C")
        result[slices] = chunk_payload
    return result


def _chunk_key(chunk_index: Iterable[int]) -> str:
    """Encode one chunk index tuple using the default v2 separator."""
    return ".".join(str(int(value)) for value in chunk_index)
