from __future__ import annotations

from src.app.domain.datasets import TraceAxis, TraceDetail, TraceMetadataSummary
from src.app.domain.tasks import TaskDetail
from src.app.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)


def build_simulation_publication_key(
    *,
    task_id: int,
    dataset_id: str,
    design_id: str,
) -> str:
    return f"simulation-publication:{task_id}:{dataset_id}:{design_id}"


def build_simulation_publication_trace_details(
    *,
    task: TaskDetail,
    dataset_id: str,
    design_id: str,
) -> tuple[tuple[str, str, TraceDetail], ...]:
    point_count = (
        task.simulation_setup.frequency_sweep.point_count
        if task.simulation_setup is not None
        else 1
    )
    published_families: list[tuple[str, str, str]] = [
        ("s_matrix", "raw", "raw"),
        ("y_matrix", "raw", "postprocess"),
        ("z_matrix", "raw", "postprocess"),
    ]
    if (
        task.simulation_setup is not None
        and task.simulation_setup.ptc is not None
        and task.simulation_setup.ptc.enabled
    ):
        published_families.extend(
            [
                ("y_matrix", "ptc", "postprocess"),
                ("z_matrix", "ptc", "postprocess"),
            ]
        )
    trace_batch_record = build_metadata_record_ref(
        "trace_batch",
        f"trace_batch:published:{task.task_id}:{dataset_id}:{design_id}",
        version=1,
    )
    details: list[tuple[str, str, TraceDetail]] = []
    for family, source, _stage_kind in published_families:
        trace_id = f"trace_simulation_task_{task.task_id}_{family}_{source}"
        result_handle_record = build_metadata_record_ref(
            "result_handle",
            f"result_handle:published:{task.task_id}:{family}:{source}",
            version=2,
        )
        details.append(
            (
                family,
                source,
                TraceDetail(
                    trace_id=trace_id,
                    dataset_id=dataset_id,
                    design_id=design_id,
                    axes=(TraceAxis(name="frequency", unit="GHz", length=point_count),),
                    preview_payload={
                        "kind": "sampled_series",
                        "source": source,
                        "family": family,
                        "points": [
                            [1.0, 0.11],
                            [2.0, 0.18],
                            [3.0, 0.15],
                        ],
                    },
                    payload_ref=build_trace_payload_ref(
                        payload_role="dataset_primary",
                        store_key=(
                            f"datasets/{dataset_id}/designs/{design_id}/simulation-results/"
                            f"task_{task.task_id}/{trace_id}.zarr"
                        ),
                        store_uri=(
                            f"trace_store/datasets/{dataset_id}/designs/{design_id}/"
                            f"simulation-results/task_{task.task_id}/{trace_id}.zarr"
                        ),
                        group_path=(
                            f"/datasets/{dataset_id}/designs/{design_id}/simulation_results"
                        ),
                        array_path=trace_id,
                        dtype="complex64",
                        shape=(point_count, 2),
                        chunk_shape=(min(point_count, 64), 2),
                    ),
                    result_handles=(
                        build_result_handle_ref(
                            handle_id=f"published-result:{task.task_id}:{family}:{source}",
                            kind="simulation_trace",
                            status="materialized",
                            label=f"Published {family.upper()} {source.upper()} result",
                            metadata_record=result_handle_record,
                            payload_backend="local_zarr",
                            payload_format="zarr",
                            payload_role="trace_payload",
                            payload_locator=(
                                f"trace_store/datasets/{dataset_id}/designs/{design_id}/"
                                f"simulation-results/task_{task.task_id}/{trace_id}.zarr"
                            ),
                            provenance_task_id=task.task_id,
                            provenance=build_result_provenance_ref(
                                source_dataset_id=task.dataset_id,
                                source_task_id=task.task_id,
                                trace_batch_record=trace_batch_record,
                            ),
                        ),
                    ),
                ),
            )
        )
    return tuple(details)


def build_simulation_publication_trace_summary(
    *,
    detail: TraceDetail,
    task: TaskDetail,
    family: str,
    source: str,
) -> TraceMetadataSummary:
    return TraceMetadataSummary(
        trace_id=detail.trace_id,
        dataset_id=detail.dataset_id,
        design_id=detail.design_id,
        family=family,
        parameter=source,
        representation="complex_matrix",
        trace_mode_group="base",
        source_kind="circuit_simulation",
        stage_kind=(
            "postprocess"
            if source == "ptc" or family in {"y_matrix", "z_matrix"}
            else "raw"
        ),
        provenance_summary=f"Published from simulation task {task.task_id}",
    )
