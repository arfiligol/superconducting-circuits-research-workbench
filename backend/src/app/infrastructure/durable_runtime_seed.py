from __future__ import annotations

from collections.abc import Iterable

from src.app.domain.datasets import (
    CharacterizationResultDetail,
    CharacterizationResultSummary,
    CharacterizationRunHistoryRow,
    TraceAxis,
    TraceDetail,
    TraceMetadataSummary,
)
from src.app.domain.storage import MetadataRecordRef
from src.app.domain.tasks import TaskResultRefs
from src.app.infrastructure.rewrite_app_state_repository import build_seed_tasks
from src.app.infrastructure.rewrite_catalog_repository import (
    _seed_characterization_analysis_registry,
    _seed_characterization_result_details,
    _seed_characterization_results,
    _seed_characterization_run_history,
    _seed_circuit_definitions,
    _seed_datasets,
    _seed_designs,
    _seed_trace_details,
    _seed_trace_summaries,
)


def seed_durable_runtime_state() -> None:
    from src.app.infrastructure.runtime import (
        get_catalog_repository,
        get_circuit_definition_persistence_repository,
        get_persisted_characterization_repository,
        get_storage_metadata_repository,
        get_task_snapshot_repository,
    )

    catalog_repository = get_catalog_repository()
    circuit_definition_repository = get_circuit_definition_persistence_repository()
    characterization_repository = get_persisted_characterization_repository()
    storage_metadata_repository = get_storage_metadata_repository()
    task_snapshot_repository = get_task_snapshot_repository()

    for definition in _seed_circuit_definitions():
        circuit_definition_repository.save_circuit_definition(definition)

    for dataset in _seed_datasets():
        catalog_repository.upsert_seed_dataset(dataset)

    for design_rows in _seed_designs().values():
        for design in design_rows:
            catalog_repository.upsert_seed_design(design)

    for (dataset_id, design_id), rows in _seed_characterization_analysis_registry().items():
        catalog_repository.upsert_seed_characterization_analysis_registry(
            dataset_id=dataset_id,
            design_id=design_id,
            rows=rows,
        )

    trace_details = _seed_trace_details()
    for _key, summaries in _seed_trace_summaries().items():
        for summary in summaries:
            detail = trace_details.get(
                (summary.dataset_id, summary.design_id, summary.trace_id)
            ) or _build_seed_trace_detail(summary)
            catalog_repository.upsert_seed_trace(
                summary=summary,
                detail=detail,
                editable=False,
                mutation_policy_summary=(
                    "Seeded trace; mutate through the original workflow or publish source."
                ),
            )

    _seed_characterization_results_into_runtime(
        repository=characterization_repository,
        summaries_by_design=_seed_characterization_results(),
        run_history_by_design=_seed_characterization_run_history(),
        details_by_key=_seed_characterization_result_details(),
    )

    for task in build_seed_tasks():
        task_snapshot_repository.save_task_snapshot(task)
        _persist_result_refs(storage_metadata_repository, task.result_refs)


def _seed_characterization_results_into_runtime(
    *,
    repository,
    summaries_by_design: dict[tuple[str, str], tuple[CharacterizationResultSummary, ...]],
    run_history_by_design: dict[tuple[str, str], tuple[CharacterizationRunHistoryRow, ...]],
    details_by_key: dict[tuple[str, str, str], CharacterizationResultDetail],
) -> None:
    run_history_by_result: dict[
        tuple[str, str, str],
        CharacterizationRunHistoryRow,
    ] = {}
    for rows in run_history_by_design.values():
        for row in rows:
            if row.result_id is None:
                continue
            run_history_by_result[(row.dataset_id, row.design_id, row.result_id)] = row

    for summaries in summaries_by_design.values():
        for summary in summaries:
            key = (summary.dataset_id, summary.design_id, summary.result_id)
            run_history = run_history_by_result.get(key)
            detail = details_by_key.get(key)
            if run_history is None or detail is None:
                continue
            repository.upsert_seed_result(
                summary=summary,
                run_history=run_history,
                detail=detail,
            )


def _build_seed_trace_detail(summary: TraceMetadataSummary) -> TraceDetail:
    axis = TraceAxis(name="frequency", unit="GHz", length=401)
    points = [[round(5.7 + (index * 0.0005), 6), 0.0] for index in range(axis.length)]
    return TraceDetail(
        trace_id=summary.trace_id,
        dataset_id=summary.dataset_id,
        design_id=summary.design_id,
        axes=(axis,),
        preview_payload={
            "kind": "series",
            "parameter": summary.parameter,
            "default_parameter": summary.parameter,
            "history_steps": [summary.source_kind.replace("_", " ").title()],
            "history_summary": summary.provenance_summary,
            "points": points,
        },
        payload_ref=None,
        result_handles=(),
    )


def _persist_result_refs(storage_metadata_repository, result_refs: TaskResultRefs) -> None:
    _save_metadata_records(storage_metadata_repository, result_refs.metadata_records)

    trace_owner_record = _trace_owner_record(result_refs)
    if result_refs.trace_payload is not None and trace_owner_record is not None:
        storage_metadata_repository.save_trace_payload(
            trace_owner_record,
            result_refs.trace_payload,
            writer_version="backend.seed",
        )

    for result_handle in result_refs.result_handles:
        storage_metadata_repository.save_result_handle(result_handle)


def _save_metadata_records(
    storage_metadata_repository,
    records: Iterable[MetadataRecordRef],
) -> None:
    for record in records:
        storage_metadata_repository.save_storage_record(record)


def _trace_owner_record(result_refs: TaskResultRefs) -> MetadataRecordRef | None:
    if result_refs.trace_payload is None:
        return None
    for record in result_refs.metadata_records:
        if record.record_type in {"trace_batch", "analysis_run", "dataset"}:
            return record
    return None
