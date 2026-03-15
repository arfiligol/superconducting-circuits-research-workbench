"""Output formatting helpers for the CLI adapter layer."""

from collections.abc import Iterable, Sequence
from json import dumps

from pydantic import BaseModel

from sc_cli.local_circuit_definitions import (
    LocalCircuitDefinitionDetail,
    LocalCircuitDefinitionInspection,
    LocalCircuitDefinitionSummary,
    LocalDefinitionBundleExportReceipt,
    LocalDefinitionBundleImportReceipt,
)
from sc_cli.local_datasets import (
    LocalDatasetBundleExportReceipt,
    LocalDatasetBundleImportReceipt,
    LocalDatasetDetail,
    LocalDatasetMetadataUpdateReceipt,
    LocalDatasetSummary,
)
from sc_cli.local_errors import CliErrorBody
from sc_cli.local_interchange import LocalResultBundleExportReceipt, LocalResultBundleImportReceipt
from sc_cli.local_runtime import LocalSession, LocalTaskDetail, LocalTaskEvent, LocalTaskSummary
from sc_cli.local_views import (
    build_session_active_dataset_envelope,
    build_session_identity_envelope,
    build_task_event_history_envelope,
    build_task_handles_envelope,
    build_task_inspection_envelope,
    build_task_latest_event_envelope,
    build_task_operations_bundle_envelope,
    build_task_result_refs_envelope,
    build_task_trace_payload_envelope,
)
from sc_cli.output import OutputMode


def render_preview_artifacts(artifacts: tuple[str, ...]) -> str:
    lines = ["sc_core preview artifacts:"]
    lines.extend(f"- {artifact}" for artifact in artifacts)
    return "\n".join(lines)


def render_circuit_definition_inspection(
    inspection: LocalCircuitDefinitionInspection,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(inspection)
    lines = [
        f"source_file: {inspection.source_file}",
        f"circuit_name: {inspection.circuit_name}",
        f"family: {inspection.family}",
        f"element_count: {inspection.element_count}",
        f"validation_status: {inspection.validation_status}",
        f"preview_artifact_count: {inspection.preview_artifact_count}",
        "preview_artifacts:",
    ]
    lines.extend(f"- {artifact}" for artifact in inspection.preview_artifacts)
    lines.extend(
        [
            "validation_summary:",
            f"status: {inspection.validation_summary.status}",
            f"notice_count: {inspection.validation_summary.notice_count}",
            f"warning_count: {inspection.validation_summary.warning_count}",
            f"invalid_count: {inspection.validation_summary.invalid_count}",
        ]
    )
    lines.extend(
        [
        "normalized_output:",
        inspection.normalized_output,
        "validation_notices:",
        ]
    )
    lines.extend(f"- [{notice.level}] {notice.message}" for notice in inspection.validation_notices)
    return "\n".join(lines)


def render_circuit_definition_summaries(
    definitions: list[LocalCircuitDefinitionSummary],
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_models(definitions)
    lines = [f"circuit_definitions: {len(definitions)}"]
    lines.extend(
        _render_list_line(
            f"#{definition.definition_id}",
            (
                definition.name,
                f"created_at={definition.created_at}",
                f"elements={definition.element_count}",
                f"validation={definition.validation_status}",
                f"preview_artifacts={definition.preview_artifact_count}",
            ),
        )
        for definition in definitions
    )
    return "\n".join(lines)


def render_session(session: LocalSession, *, output: OutputMode = OutputMode.TEXT) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(session)
    lines = [
        f"session_id: {session.session_id}",
        f"auth_state: {session.auth.state}",
        f"auth_mode: {session.auth.mode}",
        f"scopes: {', '.join(session.auth.scopes) if session.auth.scopes else '(none)'}",
        f"can_submit_tasks: {_render_bool(session.auth.can_submit_tasks)}",
        f"can_manage_datasets: {_render_bool(session.auth.can_manage_datasets)}",
        f"workspace_id: {session.workspace.workspace_id}",
        f"workspace_slug: {session.workspace.slug}",
        f"workspace_display_name: {session.workspace.display_name}",
        f"workspace_role: {session.workspace.role}",
        f"default_task_scope: {session.workspace.default_task_scope}",
    ]
    if session.identity is None:
        lines.append("identity: none")
    else:
        lines.extend(
            [
                f"identity_user_id: {session.identity.user_id}",
                f"identity_display_name: {session.identity.display_name}",
                f"identity_email: {session.identity.email or '-'}",
            ]
        )
    if session.workspace.active_dataset is None:
        lines.append("active_dataset: none")
    else:
        lines.extend(
            [
                f"active_dataset_id: {session.workspace.active_dataset.dataset_id}",
                f"active_dataset_name: {session.workspace.active_dataset.name}",
                f"active_dataset_family: {session.workspace.active_dataset.family}",
                f"active_dataset_status: {session.workspace.active_dataset.status}",
                f"active_dataset_owner: {session.workspace.active_dataset.owner}",
                f"active_dataset_access_scope: {session.workspace.active_dataset.access_scope}",
            ]
        )
    return "\n".join(lines)


def render_session_identity(
    session: LocalSession,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(build_session_identity_envelope(session))
    lines = [
        f"session_id: {session.session_id}",
        f"auth_state: {session.auth.state}",
        f"auth_mode: {session.auth.mode}",
        f"scopes: {', '.join(session.auth.scopes) if session.auth.scopes else '(none)'}",
        f"can_submit_tasks: {_render_bool(session.auth.can_submit_tasks)}",
        f"can_manage_datasets: {_render_bool(session.auth.can_manage_datasets)}",
    ]
    if session.identity is None:
        lines.append("identity: none")
    else:
        lines.extend(
            [
                f"identity_user_id: {session.identity.user_id}",
                f"identity_display_name: {session.identity.display_name}",
                f"identity_email: {session.identity.email or '-'}",
            ]
        )
    return "\n".join(lines)


def render_session_workspace(
    session: LocalSession,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(session.workspace)
    lines = [
        f"workspace_id: {session.workspace.workspace_id}",
        f"workspace_slug: {session.workspace.slug}",
        f"workspace_display_name: {session.workspace.display_name}",
        f"workspace_role: {session.workspace.role}",
        f"default_task_scope: {session.workspace.default_task_scope}",
    ]
    lines.extend(_render_active_dataset_lines(session))
    return "\n".join(lines)


def render_session_active_dataset(
    session: LocalSession,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(build_session_active_dataset_envelope(session))
    return "\n".join(_render_active_dataset_lines(session))


def render_dataset_summaries(
    datasets: list[LocalDatasetSummary],
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_models(datasets)
    lines = [f"datasets: {len(datasets)}"]
    lines.extend(
        _render_list_line(
            dataset.dataset_id,
            (
                dataset.name,
                f"family={dataset.family}",
                f"status={dataset.status}",
                f"samples={dataset.samples}",
                f"updated_at={dataset.updated_at}",
            ),
        )
        for dataset in datasets
    )
    return "\n".join(lines)


def render_dataset_detail(
    dataset: LocalDatasetDetail,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(dataset)
    lines = [
        f"dataset_id: {dataset.dataset_id}",
        f"name: {dataset.name}",
        f"family: {dataset.family}",
        f"owner: {dataset.owner}",
        f"status: {dataset.status}",
        f"device_type: {dataset.device_type}",
        f"source: {dataset.source}",
        f"samples: {dataset.samples}",
        f"updated_at: {dataset.updated_at}",
        f"capability_count: {dataset.capability_count}",
        f"tag_count: {dataset.tag_count}",
        "capabilities:",
    ]
    lines.extend(f"- {capability}" for capability in dataset.capabilities)
    lines.extend(["tags:"])
    lines.extend(f"- {tag}" for tag in dataset.tags)
    lines.extend(
        [
            (
                "preview_columns: "
                f"{', '.join(dataset.preview_columns) if dataset.preview_columns else '-'}"
            ),
            "preview_rows:",
        ]
    )
    lines.extend(f"- {', '.join(row)}" for row in dataset.preview_rows)
    lines.extend(["artifacts:"])
    lines.extend(f"- {artifact}" for artifact in dataset.artifacts)
    lines.extend(["lineage:"])
    if dataset.lineage is None:
        lines.append("- none")
    else:
        lines.extend(
            [
                f"- source_runtime={dataset.lineage.source_runtime}",
                (
                    "- source_dataset_id="
                    f"{_render_nullable(dataset.lineage.source_dataset_id)}"
                ),
                f"- source_bundle_id={dataset.lineage.source_bundle_id or '-'}",
                f"- parent_bundle_id={dataset.lineage.parent_bundle_id or '-'}",
                (
                    "- imported_from_bundle_id="
                    f"{dataset.lineage.imported_from_bundle_id or '-'}"
                ),
            ]
        )
    lines.extend(
        [
            f"metrics_capability_count: {dataset.metrics.capability_count}",
            f"metrics_tag_count: {dataset.metrics.tag_count}",
            f"metrics_preview_row_count: {dataset.metrics.preview_row_count}",
            f"metrics_artifact_count: {dataset.metrics.artifact_count}",
            f"metrics_lineage_depth: {dataset.metrics.lineage_depth}",
            f"storage_metadata_record_id: {dataset.storage.metadata_record.record_id}",
            (f"storage_primary_trace_store_uri: {_render_primary_trace_store_uri(dataset)}"),
            f"storage_result_handle_count: {len(dataset.storage.result_handles)}",
        ]
    )
    lines.extend(
        [
            f"design_scope_count: {len(dataset.design_scopes)}",
            f"trace_manifest_count: {len(dataset.trace_manifest)}",
        ]
    )
    return "\n".join(lines)


def render_dataset_metadata_update(
    result: LocalDatasetMetadataUpdateReceipt,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(result)
    lines = [
        (
            "updated_fields: "
            f"{', '.join(result.updated_fields) if result.updated_fields else '(none)'}"
        ),
        render_dataset_detail(result.dataset, output=OutputMode.TEXT),
    ]
    return "\n".join(lines)


def render_dataset_bundle_export_receipt(
    receipt: LocalDatasetBundleExportReceipt,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(receipt)
    lineage = receipt.bundle.dataset.lineage
    return "\n".join(
        [
            "operation: exported",
            f"bundle_file: {receipt.bundle_file}",
            f"bundle_id: {receipt.bundle.metadata.bundle_id}",
            f"bundle_family: {receipt.bundle.metadata.bundle_family}",
            f"bundle_version: {receipt.bundle.metadata.bundle_version}",
            f"source_dataset_id: {receipt.bundle.dataset.dataset_id}",
            f"source_dataset_name: {receipt.bundle.dataset.name}",
            (
                "lineage_source_dataset_id: "
                f"{_render_nullable(None if lineage is None else lineage.source_dataset_id)}"
            ),
            (
                "lineage_source_bundle_id: "
                f"{_render_nullable(None if lineage is None else lineage.source_bundle_id)}"
            ),
        ]
    )


def render_dataset_bundle_import_receipt(
    receipt: LocalDatasetBundleImportReceipt,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(receipt)
    lineage = receipt.imported_dataset.lineage
    return "\n".join(
        [
            "operation: imported",
            f"bundle_file: {receipt.bundle_file}",
            f"bundle_id: {receipt.bundle.metadata.bundle_id}",
            f"imported_dataset_id: {receipt.imported_dataset.dataset_id}",
            f"imported_dataset_name: {receipt.imported_dataset.name}",
            (
                "source_dataset_id: "
                f"{_render_nullable(None if lineage is None else lineage.source_dataset_id)}"
            ),
            (
                "imported_from_bundle_id: "
                f"{_render_nullable(None if lineage is None else lineage.imported_from_bundle_id)}"
            ),
        ]
    )


def render_task_summaries(
    tasks: list[LocalTaskSummary],
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_models(tasks)
    lines = [f"tasks: {len(tasks)}"]
    lines.extend(
        _render_list_line(
            f"#{task.task_id}",
            (
                f"kind={task.kind}",
                f"lane={task.lane}",
                f"mode={task.execution_mode}",
                f"status={task.status}",
                f"scope={task.visibility_scope}",
                f"dataset={task.dataset_id or '-'}",
                f"definition={task.definition_id if task.definition_id is not None else '-'}",
                f"summary={task.summary}",
            ),
        )
        for task in tasks
    )
    return "\n".join(lines)


def render_task_detail(task: LocalTaskDetail, *, output: OutputMode = OutputMode.TEXT) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(task)
    trace_batch_id = task.result_refs.trace_batch_id
    analysis_run_id = task.result_refs.analysis_run_id
    return "\n".join(
        [
            f"task_id: {task.task_id}",
            f"kind: {task.kind}",
            f"lane: {task.lane}",
            f"execution_mode: {task.execution_mode}",
            f"status: {task.status}",
            f"submitted_at: {task.submitted_at}",
            f"owner_user_id: {task.owner_user_id}",
            f"owner_display_name: {task.owner_display_name}",
            f"workspace_id: {task.workspace_id}",
            f"workspace_slug: {task.workspace_slug}",
            f"visibility_scope: {task.visibility_scope}",
            f"dataset_id: {task.dataset_id or '-'}",
            f"definition_id: {task.definition_id if task.definition_id is not None else '-'}",
            f"summary: {task.summary}",
            f"queue_backend: {task.queue_backend}",
            f"worker_task_name: {task.worker_task_name}",
            f"request_ready: {_render_bool(task.request_ready)}",
            f"submitted_from_active_dataset: {_render_bool(task.submitted_from_active_dataset)}",
            f"progress_phase: {task.progress.phase}",
            f"progress_percent_complete: {task.progress.percent_complete}",
            f"progress_summary: {task.progress.summary}",
            f"progress_updated_at: {task.progress.updated_at}",
            f"result_trace_batch_id: {trace_batch_id if trace_batch_id is not None else '-'}",
            f"result_analysis_run_id: {analysis_run_id if analysis_run_id is not None else '-'}",
        ]
    )


def render_task_inspection(
    task: LocalTaskDetail,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    envelope = build_task_inspection_envelope(task)
    latest_event = envelope.inspection.latest_event
    if output is OutputMode.JSON:
        return _render_json_model(envelope)
    lines = [
        render_task_detail(task, output=OutputMode.TEXT),
        "inspection:",
        f"event_count: {envelope.inspection.event_count}",
        f"latest_event_type: {latest_event.event_type if latest_event is not None else '-'}",
        f"latest_event_level: {latest_event.level if latest_event is not None else '-'}",
        (
            "latest_event_occurred_at: "
            f"{latest_event.occurred_at if latest_event is not None else '-'}"
        ),
        f"metadata_record_count: {envelope.inspection.metadata_record_count}",
        f"result_handle_count: {envelope.inspection.result_handle_count}",
        f"trace_payload_present: {_render_bool(envelope.inspection.trace_payload_present)}",
        f"inspection_trace_batch_id: {_render_nullable(envelope.inspection.trace_batch_id)}",
        f"inspection_analysis_run_id: {_render_nullable(envelope.inspection.analysis_run_id)}",
    ]
    if latest_event is not None:
        lines.append(f"latest_event_message: {latest_event.message}")
    return "\n".join(lines)


def render_task_operations_bundle(
    task: LocalTaskDetail,
    *,
    recent_event_limit: int = 3,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    recent_events = task.events[-recent_event_limit:]
    envelope = build_task_operations_bundle_envelope(task, recent_events=recent_events)
    if output is OutputMode.JSON:
        return _render_json_model(envelope)
    lines = [
        render_task_inspection(task, output=OutputMode.TEXT),
        "recent_events:",
    ]
    if not recent_events:
        lines.append("- none")
    else:
        for event in recent_events:
            lines.append(
                _render_list_line(
                    event.occurred_at,
                    (
                        f"type={event.event_type}",
                        f"level={event.level}",
                        f"message={event.message}",
                    ),
                )
            )
        lines.extend(
        [
            "result_summary:",
            f"trace_batch_id: {_render_nullable(envelope.result_summary.trace_batch_id)}",
            f"analysis_run_id: {_render_nullable(envelope.result_summary.analysis_run_id)}",
            f"metadata_record_count: {envelope.result_summary.metadata_record_count}",
            f"result_handle_count: {envelope.result_summary.result_handle_count}",
            f"trace_payload_present: {_render_bool(envelope.result_summary.trace_payload_present)}",
            "result_handle_ids: "
            + (
                ", ".join(envelope.result_summary.result_handle_ids)
                if envelope.result_summary.result_handle_ids
                else "-"
            ),
        ]
    )
    lines.extend(_render_lineage_lines(task))
    return "\n".join(lines)


def render_task_result_refs(
    task: LocalTaskDetail,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(build_task_result_refs_envelope(task))
    lines = [
        *_build_task_result_context_lines(task),
        f"trace_batch_id: {_render_nullable(task.result_refs.trace_batch_id)}",
        f"analysis_run_id: {_render_nullable(task.result_refs.analysis_run_id)}",
        *_render_lineage_lines(task),
        f"metadata_record_count: {len(task.result_refs.metadata_records)}",
        "metadata_records:",
    ]
    lines.extend(_render_metadata_record_lines(task))
    lines.extend(
        [
            f"trace_payload_present: {_render_bool(task.result_refs.trace_payload is not None)}",
            "trace_payload_summary:",
        ]
    )
    lines.extend(_render_trace_payload_summary_lines(task))
    lines.extend(["result_handles:"])
    lines.extend(_render_result_handle_summary_lines(task))
    return "\n".join(lines)


def render_task_trace_payload(
    task: LocalTaskDetail,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    trace_payload = task.result_refs.trace_payload
    assert trace_payload is not None
    if output is OutputMode.JSON:
        return _render_json_model(build_task_trace_payload_envelope(task))
    return "\n".join(
        [
            *_build_task_result_context_lines(task),
            f"trace_batch_id: {_render_nullable(task.result_refs.trace_batch_id)}",
            f"analysis_run_id: {_render_nullable(task.result_refs.analysis_run_id)}",
            *_render_lineage_lines(task),
            f"contract_version: {trace_payload.contract_version}",
            f"backend: {trace_payload.backend}",
            f"payload_role: {trace_payload.payload_role}",
            f"store_key: {trace_payload.store_key}",
            f"store_uri: {trace_payload.store_uri}",
            f"group_path: {trace_payload.group_path}",
            f"array_path: {trace_payload.array_path}",
            f"dtype: {trace_payload.dtype}",
            f"shape: {_render_list_value(trace_payload.shape)}",
            f"chunk_shape: {_render_list_value(trace_payload.chunk_shape)}",
            f"schema_version: {trace_payload.schema_version}",
        ]
    )


def render_task_result_handles(
    task: LocalTaskDetail,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(build_task_handles_envelope(task))
    lines = [
        *_build_task_result_context_lines(task),
        *_render_lineage_lines(task),
        "metadata_records:",
    ]
    lines.extend(_render_metadata_record_lines(task))
    lines.extend(["result_handles:"])
    lines.extend(_render_result_handle_detail_lines(task))
    return "\n".join(lines)


def render_task_event_history(
    task: LocalTaskDetail,
    *,
    events: Sequence[LocalTaskEvent],
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(
            build_task_event_history_envelope(task, events=list(events))
        )
    lines = [
        *_build_task_result_context_lines(task),
        "events:",
    ]
    for event in events:
        lines.extend(_render_event_lines(event))
    return "\n".join(lines)


def render_task_latest_event(
    task: LocalTaskDetail,
    *,
    event: LocalTaskEvent,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(build_task_latest_event_envelope(task, event=event))
    lines = [
        *_build_task_result_context_lines(task),
        "latest_event:",
    ]
    lines.extend(_render_event_lines(event))
    return "\n".join(lines)


def render_result_bundle_export_receipt(
    receipt: LocalResultBundleExportReceipt,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(receipt)
    bundle = receipt.bundle
    lineage = bundle.result_refs.lineage
    lineage_source_dataset_id = (
        "-"
        if lineage is None or lineage.source_dataset_id is None
        else lineage.source_dataset_id
    )
    return "\n".join(
        [
            "operation: exported",
            f"bundle_file: {receipt.bundle_file}",
            f"bundle_id: {bundle.metadata.bundle_id}",
            f"bundle_family: {bundle.metadata.bundle_family}",
            f"bundle_version: {bundle.metadata.bundle_version}",
            f"source_task_id: {bundle.task.task_id}",
            f"source_dataset_id: {bundle.task.dataset_id or '-'}",
            (
                "lineage_source_task_id: "
                f"{_render_nullable(None if lineage is None else lineage.source_task_id)}"
            ),
            (
                "lineage_source_dataset_id: "
                f"{lineage_source_dataset_id}"
            ),
        ]
    )


def render_result_bundle_import_receipt(
    receipt: LocalResultBundleImportReceipt,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(receipt)
    lines = [
        "operation: imported",
        f"bundle_file: {receipt.bundle_file}",
        f"bundle_id: {receipt.bundle.metadata.bundle_id}",
        f"imported_task_id: {receipt.imported_task.task_id}",
        f"imported_task_status: {receipt.imported_task.status}",
    ]
    lines.extend(_render_lineage_lines(receipt.imported_task))
    return "\n".join(lines)


def render_circuit_definition_detail(
    definition: LocalCircuitDefinitionDetail,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(definition)
    lines = [
        f"source_definition_id: {definition.definition_id}",
        f"definition_name: {definition.name}",
        f"created_at: {definition.created_at}",
        f"element_count: {definition.element_count}",
        f"validation_status: {definition.validation_status}",
        f"preview_artifact_count: {definition.preview_artifact_count}",
        "preview_artifacts:",
    ]
    lines.extend(f"- {artifact}" for artifact in definition.preview_artifacts)
    lines.extend(
        [
            "source_text:",
            definition.source_text,
            "normalized_output:",
            definition.normalized_output,
            "validation_notices:",
        ]
    )
    lines.extend(f"- [{notice.level}] {notice.message}" for notice in definition.validation_notices)
    lines.extend(
        [
            "validation_summary:",
            f"status: {definition.validation_summary.status}",
            f"notice_count: {definition.validation_summary.notice_count}",
            f"warning_count: {definition.validation_summary.warning_count}",
            f"invalid_count: {definition.validation_summary.invalid_count}",
        ]
    )
    if definition.lineage is None:
        lines.append("lineage: none")
    else:
        lines.extend(
            [
                "lineage:",
                f"source_runtime: {definition.lineage.source_runtime}",
                (
                    "source_definition_id: "
                    f"{_render_nullable(definition.lineage.source_definition_id)}"
                ),
                f"source_bundle_id: {definition.lineage.source_bundle_id or '-'}",
                f"parent_bundle_id: {definition.lineage.parent_bundle_id or '-'}",
                (
                    "imported_from_bundle_id: "
                    f"{definition.lineage.imported_from_bundle_id or '-'}"
                ),
            ]
        )
    return "\n".join(lines)


def render_definition_bundle_export_receipt(
    receipt: LocalDefinitionBundleExportReceipt,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(receipt)
    lineage = receipt.bundle.definition.lineage
    return "\n".join(
        [
            "operation: exported",
            f"bundle_file: {receipt.bundle_file}",
            f"bundle_id: {receipt.bundle.metadata.bundle_id}",
            f"bundle_family: {receipt.bundle.metadata.bundle_family}",
            f"bundle_version: {receipt.bundle.metadata.bundle_version}",
            f"source_definition_id: {receipt.bundle.definition.definition_id}",
            f"source_definition_name: {receipt.bundle.definition.name}",
            (
                "lineage_source_definition_id: "
                f"{_render_nullable(None if lineage is None else lineage.source_definition_id)}"
            ),
            (
                "lineage_source_bundle_id: "
                f"{_render_nullable(None if lineage is None else lineage.source_bundle_id)}"
            ),
        ]
    )


def render_definition_bundle_import_receipt(
    receipt: LocalDefinitionBundleImportReceipt,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_model(receipt)
    lineage = receipt.imported_definition.lineage
    return "\n".join(
        [
            "operation: imported",
            f"bundle_file: {receipt.bundle_file}",
            f"bundle_id: {receipt.bundle.metadata.bundle_id}",
            f"imported_definition_id: {receipt.imported_definition.definition_id}",
            f"imported_definition_name: {receipt.imported_definition.name}",
            (
                "source_definition_id: "
                f"{_render_nullable(None if lineage is None else lineage.source_definition_id)}"
            ),
            (
                "imported_from_bundle_id: "
                f"{_render_nullable(None if lineage is None else lineage.imported_from_bundle_id)}"
            ),
        ]
    )


def render_circuit_definition_delete_result(
    definition_id: int,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> str:
    if output is OutputMode.JSON:
        return _render_json_payload({"operation": "deleted", "definition_id": definition_id})
    return "\n".join(
        [
            "operation: deleted",
            f"definition_id: {definition_id}",
        ]
    )


def render_api_error(error: CliErrorBody, *, output: OutputMode = OutputMode.TEXT) -> str:
    if output is OutputMode.JSON:
        return _render_json_payload({"error": error.model_dump(mode="json")})
    suffix = f" [{error.category}/{error.code}]"
    lines = [f"error: {error.message}{suffix}"]
    lines.extend(
        f"field_error: {field_error.field}: {field_error.message}"
        for field_error in error.field_errors
    )
    return "\n".join(lines)


def _render_bool(value: bool) -> str:
    return "true" if value else "false"


def _render_nullable(value: object | None) -> str:
    return "-" if value is None else str(value)


def _render_list_value(values: Sequence[object]) -> str:
    return ", ".join(str(value) for value in values)


def _render_list_line(label: str, parts: Iterable[str]) -> str:
    return f"- {label} | " + " | ".join(parts)


def _build_task_result_context(task: LocalTaskDetail) -> dict[str, object]:
    lineage = None
    if task.result_refs.lineage is not None:
        lineage = task.result_refs.lineage.model_dump(mode="json")
    return {
        "task_id": task.task_id,
        "kind": task.kind,
        "lane": task.lane,
        "execution_mode": task.execution_mode,
        "status": task.status,
        "worker_task_name": task.worker_task_name,
        "dataset_id": task.dataset_id,
        "definition_id": task.definition_id,
        "summary": task.summary,
        "event_count": len(task.events),
        "result_handle_count": len(task.result_refs.result_handles),
        "trace_batch_id": task.result_refs.trace_batch_id,
        "analysis_run_id": task.result_refs.analysis_run_id,
        "dispatch": task.dispatch.model_dump(mode="json"),
        "lineage": lineage,
    }


def _build_task_result_context_lines(task: LocalTaskDetail) -> list[str]:
    lines = [
        f"task_id: {task.task_id}",
        f"kind: {task.kind}",
        f"lane: {task.lane}",
        f"execution_mode: {task.execution_mode}",
        f"status: {task.status}",
        f"worker_task_name: {task.worker_task_name}",
        f"dataset_id: {task.dataset_id or '-'}",
        f"definition_id: {_render_nullable(task.definition_id)}",
        f"summary: {task.summary}",
        f"dispatch_key: {task.dispatch.dispatch_key}",
        f"dispatch_status: {task.dispatch.status}",
        f"submission_source: {task.dispatch.submission_source}",
        f"event_count: {len(task.events)}",
        f"result_handle_count: {len(task.result_refs.result_handles)}",
    ]
    return lines


def _render_lineage_lines(task: LocalTaskDetail) -> list[str]:
    lineage = task.result_refs.lineage
    if lineage is None:
        return ["lineage: none"]
    return [
        "lineage:",
        f"source_runtime: {lineage.source_runtime}",
        f"source_task_id: {_render_nullable(lineage.source_task_id)}",
        f"source_dataset_id: {lineage.source_dataset_id or '-'}",
        f"source_definition_id: {_render_nullable(lineage.source_definition_id)}",
        f"source_analysis_run_id: {lineage.source_analysis_run_id or '-'}",
        f"source_trace_batch_id: {_render_nullable(lineage.source_trace_batch_id)}",
        f"parent_bundle_id: {lineage.parent_bundle_id or '-'}",
        f"imported_from_bundle_id: {lineage.imported_from_bundle_id or '-'}",
    ]


def _render_metadata_record_lines(task: LocalTaskDetail) -> list[str]:
    if not task.result_refs.metadata_records:
        return ["- none"]
    return [
        _render_list_line(
            record.record_id,
            (
                f"type={record.record_type}",
                f"backend={record.backend}",
                f"version={record.version}",
                f"schema={record.schema_version}",
            ),
        )
        for record in task.result_refs.metadata_records
    ]


def _render_trace_payload_summary_lines(task: LocalTaskDetail) -> list[str]:
    trace_payload = task.result_refs.trace_payload
    if trace_payload is None:
        return ["- none"]
    return [
        f"- store_uri={trace_payload.store_uri}",
        f"- array_path={trace_payload.array_path}",
        f"- dtype={trace_payload.dtype}",
        f"- shape={_render_list_value(trace_payload.shape)}",
        f"- chunk_shape={_render_list_value(trace_payload.chunk_shape)}",
        f"- role={trace_payload.payload_role}",
    ]


def _render_result_handle_summary_lines(task: LocalTaskDetail) -> list[str]:
    if not task.result_refs.result_handles:
        return ["- none"]
    return [
        _render_list_line(
            handle.handle_id,
            (
                f"kind={handle.kind}",
                f"status={handle.status}",
                f"label={handle.label}",
                f"payload_format={handle.payload_format or '-'}",
                f"payload_locator={handle.payload_locator or '-'}",
            ),
        )
        for handle in task.result_refs.result_handles
    ]


def _render_result_handle_detail_lines(task: LocalTaskDetail) -> list[str]:
    if not task.result_refs.result_handles:
        return ["- none"]
    lines: list[str] = []
    for handle in task.result_refs.result_handles:
        trace_batch_record_id = (
            "-"
            if handle.provenance.trace_batch_record is None
            else handle.provenance.trace_batch_record.record_id
        )
        analysis_run_record_id = (
            "-"
            if handle.provenance.analysis_run_record is None
            else handle.provenance.analysis_run_record.record_id
        )
        lines.extend(
            [
                f"- handle_id: {handle.handle_id}",
                f"  kind: {handle.kind}",
                f"  status: {handle.status}",
                f"  label: {handle.label}",
                f"  payload_backend: {handle.payload_backend or '-'}",
                f"  payload_format: {handle.payload_format or '-'}",
                f"  payload_role: {handle.payload_role or '-'}",
                f"  payload_locator: {handle.payload_locator or '-'}",
                f"  metadata_record_id: {handle.metadata_record.record_id}",
                f"  provenance_task_id: {_render_nullable(handle.provenance_task_id)}",
                f"  provenance_source_dataset_id: {handle.provenance.source_dataset_id or '-'}",
                f"  provenance_trace_batch_record: {trace_batch_record_id}",
                f"  provenance_analysis_run_record: {analysis_run_record_id}",
            ]
        )
    return lines


def _render_event_lines(event: BaseModel) -> list[str]:
    event_data = event.model_dump(mode="json")
    metadata = event_data["metadata"]
    lines = [
        f"- event_key: {event_data['event_key']}",
        f"  event_type: {event_data['event_type']}",
        f"  level: {event_data['level']}",
        f"  occurred_at: {event_data['occurred_at']}",
        f"  message: {event_data['message']}",
        "  metadata:",
    ]
    if not metadata:
        lines.append("  - none")
        return lines
    for key, value in metadata.items():
        lines.append(f"  - {key}: {_render_event_metadata_value(value)}")
    return lines


def _render_event_metadata_value(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if value is None:
        return "-"
    return str(value)


def _render_primary_trace_store_uri(dataset: LocalDatasetDetail) -> str:
    if dataset.storage.primary_trace is None:
        return "-"
    return dataset.storage.primary_trace.store_uri


def _render_active_dataset_lines(session: LocalSession) -> list[str]:
    if session.workspace.active_dataset is None:
        return ["active_dataset: none"]
    return [
        f"active_dataset_id: {session.workspace.active_dataset.dataset_id}",
        f"active_dataset_name: {session.workspace.active_dataset.name}",
        f"active_dataset_family: {session.workspace.active_dataset.family}",
        f"active_dataset_status: {session.workspace.active_dataset.status}",
        f"active_dataset_owner: {session.workspace.active_dataset.owner}",
        f"active_dataset_access_scope: {session.workspace.active_dataset.access_scope}",
    ]


def _render_json_model(model: BaseModel) -> str:
    return model.model_dump_json(indent=2)


def _render_json_models(models: Sequence[BaseModel]) -> str:
    return _render_json_payload([model.model_dump(mode="json") for model in models])


def _render_json_payload(payload: object) -> str:
    return dumps(payload, indent=2)
