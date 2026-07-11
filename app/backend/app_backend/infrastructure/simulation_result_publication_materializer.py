from __future__ import annotations

from dataclasses import dataclass, replace
from typing import cast

from app_backend.domain.characterization_analysis import (
    evaluate_trace_analysis_capabilities,
)
from app_backend.domain.datasets import TraceAxis, TraceDetail, TraceMetadataSummary
from app_backend.domain.result_traces import (
    ResultTraceSelection,
    build_trace_parameter,
)
from app_backend.domain.tasks import TaskDetail
from app_backend.domain.trace_structures import build_trace_structure_summary
from app_backend.infrastructure.persisted_runtime import (
    available_sources_for_task_family,
    build_trace_preview_payload,
    extract_selection_trace_data,
    extract_selection_trace_nd_data,
    write_nd_complex_trace_payload,
)
from app_backend.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
)


@dataclass(frozen=True)
class MaterializedSimulationPublicationTrace:
    family: str
    source: str
    summary: TraceMetadataSummary
    detail: TraceDetail


def build_simulation_publication_key(
    *,
    task_id: int,
    dataset_id: str,
    design_id: str,
) -> str:
    return f"simulation-publication:{task_id}:{dataset_id}:{design_id}"


def build_simulation_publication_traces(
    *,
    task: TaskDetail,
    dataset_family: str,
    dataset_id: str,
    design_id: str,
) -> tuple[MaterializedSimulationPublicationTrace, ...]:
    traces: list[MaterializedSimulationPublicationTrace] = []
    for family, source in _simulation_publication_targets(task):
        traces.append(
            _materialize_simulation_publication_trace(
                task=task,
                dataset_family=dataset_family,
                dataset_id=dataset_id,
                design_id=design_id,
                family=family,
                source=source,
            )
        )
    return tuple(traces)


def _simulation_publication_targets(task: TaskDetail) -> tuple[tuple[str, str], ...]:
    targets: list[tuple[str, str]] = []
    if "raw" in available_sources_for_task_family(task, "s_matrix"):
        targets.append(("s_matrix", "raw"))
    if "raw" in available_sources_for_task_family(task, "y_matrix"):
        targets.append(("y_matrix", "raw"))
    if "raw" in available_sources_for_task_family(task, "z_matrix"):
        targets.append(("z_matrix", "raw"))
    if "ptc" in available_sources_for_task_family(task, "y_matrix"):
        targets.append(("y_matrix", "ptc"))
    if "ptc" in available_sources_for_task_family(task, "z_matrix"):
        targets.append(("z_matrix", "ptc"))
    return tuple(targets)


def _materialize_simulation_publication_trace(
    *,
    task: TaskDetail,
    dataset_family: str,
    dataset_id: str,
    design_id: str,
    family: str,
    source: str,
) -> MaterializedSimulationPublicationTrace:
    selection = ResultTraceSelection(
        family=family,
        source=source,
        output_port=1,
        input_port=1,
        z0_ohm=50.0 if family in {"y_matrix", "z_matrix"} else None,
    )
    trace_data = extract_selection_trace_data(
        task,
        basis_task=task,
        selection=selection,
    )
    nd_trace_data = extract_selection_trace_nd_data(
        task,
        basis_task=task,
        selection=selection,
    )
    trace_id = f"trace_simulation_task_{task.task_id}_{family}_{source}"
    payload_ref = write_nd_complex_trace_payload(
        dataset_id=dataset_id,
        design_id=design_id,
        trace_id=trace_id,
        axes=nd_trace_data.axes,
        values=nd_trace_data.values,
    )
    trace_batch_record = build_metadata_record_ref(
        "trace_batch",
        f"trace_batch:published:{task.task_id}:{dataset_id}:{design_id}",
        version=1,
    )
    result_handle_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:published:{task.task_id}:{family}:{source}",
        version=2,
    )
    result_handle = build_result_handle_ref(
        handle_id=f"published-result:{task.task_id}:{family}:{source}",
        kind="simulation_trace",
        status="materialized",
        label=f"Published {family.upper()} {source.upper()} result",
        metadata_record=result_handle_record,
        payload_backend="local_zarr",
        payload_format="zarr",
        payload_role="trace_payload",
        payload_locator=payload_ref.store_uri or payload_ref.store_key,
        provenance_task_id=task.task_id,
        provenance=build_result_provenance_ref(
            source_dataset_id=task.dataset_id,
            source_task_id=task.task_id,
            trace_batch_record=trace_batch_record,
        ),
    )
    axes = tuple(
        TraceAxis(
            name=str(axis["name"]),
            unit=str(axis["unit"]),
            length=int(axis["length"]),
        )
        for axis in nd_trace_data.axes
    )
    structure = build_trace_structure_summary(
        dataset_id=dataset_id,
        design_id=design_id,
        family=selection.family,
        parameter=source,
        representation="complex_matrix",
        trace_mode_group=selection.trace_mode_group,
        source_kind=cast(str, nd_trace_data.source_kind),
        stage_kind=cast(str, nd_trace_data.stage_kind),
        axes=nd_trace_data.axes,
    )
    summary = TraceMetadataSummary(
        trace_id=trace_id,
        dataset_id=dataset_id,
        design_id=design_id,
        family=selection.family,
        parameter=source,
        representation="complex_matrix",
        trace_mode_group=selection.trace_mode_group,
        source_kind=cast(str, nd_trace_data.source_kind),
        stage_kind=cast(str, nd_trace_data.stage_kind),
        ndim=structure.ndim,
        shape=structure.shape,
        axes_summary=structure.axes_summary,
        axis_signature=structure.axis_signature,
        available_sweep_axes=structure.available_sweep_axes,
        collection_projection=structure.collection_projection,
        provenance_summary=f"Published from simulation task {task.task_id}",
    )
    analysis_capabilities = evaluate_trace_analysis_capabilities(
        dataset_family=dataset_family,
        trace=summary,
        axes=axes,
    )
    preview = build_trace_preview_payload(
        selection=selection,
        trace_data=trace_data,
    )
    preview["kind"] = "series"
    preview["family"] = selection.family
    preview["source"] = selection.source
    preview["parameter"] = source
    preview["default_parameter"] = build_trace_parameter(selection)
    preview["output_port"] = selection.output_port
    preview["input_port"] = selection.input_port
    preview["trace_mode_group"] = selection.trace_mode_group
    preview["output_mode"] = selection.output_mode
    preview["input_mode"] = selection.input_mode
    preview["history_steps"] = _build_trace_history_steps(task=task, selection=selection)
    preview["history_summary"] = " -> ".join(preview["history_steps"])
    preview["points"] = [
        [float(frequency), float(value.real), float(value.imag)]
        for frequency, value in zip(
            trace_data.frequencies_ghz,
            trace_data.values,
            strict=True,
        )
    ]
    detail = TraceDetail(
        trace_id=trace_id,
        dataset_id=dataset_id,
        design_id=design_id,
        family=selection.family,
        parameter=summary.parameter,
        representation=summary.representation,
        trace_mode_group=selection.trace_mode_group,
        source_kind=cast(str, nd_trace_data.source_kind),
        stage_kind=cast(str, nd_trace_data.stage_kind),
        axes=axes,
        ndim=structure.ndim,
        shape=structure.shape,
        axes_summary=structure.axes_summary,
        axis_signature=structure.axis_signature,
        available_sweep_axes=structure.available_sweep_axes,
        collection_projection=structure.collection_projection,
        preview_payload=preview,
        payload_ref=payload_ref,
        result_handles=(result_handle,),
        analysis_capabilities=analysis_capabilities,
    )
    return MaterializedSimulationPublicationTrace(
        family=family,
        source=source,
        summary=replace(summary, analysis_capabilities=analysis_capabilities),
        detail=detail,
    )


def _build_trace_history_steps(
    *,
    task: TaskDetail,
    selection: ResultTraceSelection,
) -> list[str]:
    history = ["PTC" if selection.source == "ptc" else "Raw"]
    if task.kind != "post_processing" or task.post_processing_setup is None:
        return history

    for operation in task.post_processing_setup.operations:
        if not operation.enabled:
            continue
        history.append(_humanize_post_processing_operation(operation.operation))
    return history


def _humanize_post_processing_operation(operation: str) -> str:
    if operation == "coordinate_transform":
        return "Coordinate Transformation"
    if operation == "kron_reduction":
        return "Kron Reduction"
    return operation.replace("_", " ").title()
