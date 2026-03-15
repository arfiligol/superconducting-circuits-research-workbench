"""Standalone local runtime models and persisted local state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from sc_cli.local_errors import CliContractError, build_contract_error
from sc_cli.local_store import (
    read_json,
    session_state_path,
    task_events_path,
    task_registry_path,
    task_results_path,
    write_json,
    write_model,
)

if TYPE_CHECKING:
    from sc_cli.local_interchange import LocalResultBundle

TaskKindValue = Literal["simulation", "post_processing", "characterization"]
TaskLaneValue = Literal["simulation", "characterization"]
TaskStatusValue = Literal["queued", "running", "completed", "failed"]
TaskScopeValue = Literal["workspace", "owned"]


class LocalSessionAuth(BaseModel):
    state: str
    mode: str
    scopes: list[str]
    can_submit_tasks: bool
    can_manage_datasets: bool


class LocalSessionIdentity(BaseModel):
    user_id: str
    display_name: str
    email: str | None = None


class LocalSessionDataset(BaseModel):
    dataset_id: str
    name: str
    family: str
    status: str
    owner: str
    access_scope: str


class LocalSessionWorkspace(BaseModel):
    workspace_id: str
    slug: str
    display_name: str
    role: str
    default_task_scope: str
    active_dataset: LocalSessionDataset | None = None


class LocalSession(BaseModel):
    session_id: str
    auth: LocalSessionAuth
    identity: LocalSessionIdentity | None = None
    workspace: LocalSessionWorkspace


class LocalTaskProgress(BaseModel):
    phase: str
    percent_complete: int
    summary: str
    updated_at: str


class LocalTaskDispatch(BaseModel):
    dispatch_key: str
    status: str
    submission_source: str


class LocalTaskEvent(BaseModel):
    event_key: str
    event_type: str
    level: str
    occurred_at: str
    message: str
    metadata: dict[str, object] = Field(default_factory=dict)


class LocalMetadataRecord(BaseModel):
    record_id: str
    record_type: str
    backend: str
    version: str
    schema_version: str


class LocalRecordRef(BaseModel):
    record_id: str


class LocalTracePayload(BaseModel):
    contract_version: str
    backend: str
    payload_role: str
    store_key: str
    store_uri: str
    group_path: str
    array_path: str
    dtype: str
    shape: list[int]
    chunk_shape: list[int]
    schema_version: str


class LocalResultLineage(BaseModel):
    source_runtime: str
    source_task_id: int | None = None
    source_dataset_id: str | None = None
    source_definition_id: int | None = None
    source_analysis_run_id: str | None = None
    source_trace_batch_id: int | None = None
    parent_bundle_id: str | None = None
    imported_from_bundle_id: str | None = None


class LocalResultProvenance(BaseModel):
    source_dataset_id: str | None = None
    trace_batch_record: LocalRecordRef | None = None
    analysis_run_record: LocalRecordRef | None = None


class LocalResultHandle(BaseModel):
    handle_id: str
    kind: str
    status: str
    label: str
    payload_backend: str | None = None
    payload_format: str | None = None
    payload_role: str | None = None
    payload_locator: str | None = None
    metadata_record: LocalMetadataRecord
    provenance_task_id: int | None = None
    provenance: LocalResultProvenance


class LocalTaskResultRefs(BaseModel):
    trace_batch_id: int | None = None
    analysis_run_id: str | None = None
    lineage: LocalResultLineage | None = None
    metadata_records: list[LocalMetadataRecord] = Field(default_factory=list)
    trace_payload: LocalTracePayload | None = None
    result_handles: list[LocalResultHandle] = Field(default_factory=list)


class LocalTaskSummary(BaseModel):
    task_id: int
    kind: TaskKindValue
    lane: TaskLaneValue
    execution_mode: str
    status: TaskStatusValue
    visibility_scope: TaskScopeValue
    dataset_id: str | None = None
    definition_id: int | None = None
    summary: str


class LocalTaskDetail(LocalTaskSummary):
    submitted_at: str
    owner_user_id: str
    owner_display_name: str
    workspace_id: str
    workspace_slug: str
    queue_backend: str
    worker_task_name: str
    request_ready: bool
    submitted_from_active_dataset: bool
    progress: LocalTaskProgress
    dispatch: LocalTaskDispatch
    events: list[LocalTaskEvent] = Field(default_factory=list)
    result_refs: LocalTaskResultRefs = Field(default_factory=LocalTaskResultRefs)


class _PersistedTaskRegistry(BaseModel):
    session: LocalSession
    next_task_id: int
    tasks: list[LocalTaskDetail]


_SEEDED_SESSION_DATASETS: dict[str, LocalSessionDataset] = {
    "fluxonium-2025-031": LocalSessionDataset(
        dataset_id="fluxonium-2025-031",
        name="Fluxonium sweep 031",
        family="fluxonium",
        status="ready",
        owner="Rewrite Local User",
        access_scope="workspace",
    ),
    "transmon-coupler-014": LocalSessionDataset(
        dataset_id="transmon-coupler-014",
        name="Coupler detuning 014",
        family="transmon",
        status="ready",
        owner="Rewrite Local User",
        access_scope="workspace",
    ),
}


def _contract_error(
    *,
    code: str,
    category: Literal["not_found", "validation", "forbidden", "conflict"],
    message: str,
    status: int,
    field_errors: list[dict[str, str]] | None = None,
) -> CliContractError:
    return build_contract_error(
        code=code,
        category=category,
        message=message,
        status=status,
        field_errors=field_errors,
    )


def _task_summary(task: LocalTaskDetail) -> LocalTaskSummary:
    return LocalTaskSummary(
        task_id=task.task_id,
        kind=task.kind,
        lane=task.lane,
        execution_mode=task.execution_mode,
        status=task.status,
        visibility_scope=task.visibility_scope,
        dataset_id=task.dataset_id,
        definition_id=task.definition_id,
        summary=task.summary,
    )


def _session_with_active_dataset(dataset_id: str | None) -> LocalSession:
    active_dataset = None if dataset_id is None else _get_session_dataset(dataset_id)
    return LocalSession(
        session_id="rewrite-local-session",
        auth=LocalSessionAuth(
            state="authenticated",
            mode="local",
            scopes=["datasets:read", "tasks:submit", "tasks:read"],
            can_submit_tasks=True,
            can_manage_datasets=True,
        ),
        identity=LocalSessionIdentity(
            user_id="researcher-01",
            display_name="Rewrite Local User",
            email="researcher-01@example.test",
        ),
        workspace=LocalSessionWorkspace(
            workspace_id="ws-device-lab",
            slug="device-lab",
            display_name="Device Lab Workspace",
            role="owner",
            default_task_scope="workspace",
            active_dataset=active_dataset,
        ),
    )


def _get_session_dataset(dataset_id: str) -> LocalSessionDataset:
    try:
        from sc_cli.local_datasets import get_local_session_dataset
    except ImportError:
        return _SEEDED_SESSION_DATASETS[dataset_id].model_copy(deep=True)
    return get_local_session_dataset(dataset_id)


def _dataset_exists(dataset_id: str) -> bool:
    try:
        from sc_cli.local_datasets import has_local_dataset
    except ImportError:
        return dataset_id in _SEEDED_SESSION_DATASETS
    return has_local_dataset(dataset_id)


def _seed_running_simulation_task() -> LocalTaskDetail:
    return LocalTaskDetail(
        task_id=301,
        kind="simulation",
        lane="simulation",
        execution_mode="run",
        status="running",
        visibility_scope="workspace",
        dataset_id="fluxonium-2025-031",
        definition_id=18,
        summary="Fluxonium local simulation run",
        submitted_at="2026-03-15T10:00:00Z",
        owner_user_id="researcher-01",
        owner_display_name="Rewrite Local User",
        workspace_id="ws-device-lab",
        workspace_slug="device-lab",
        queue_backend="local_registry",
        worker_task_name="simulation_run_task",
        request_ready=True,
        submitted_from_active_dataset=True,
        progress=LocalTaskProgress(
            phase="running",
            percent_complete=45,
            summary="Simulating circuit batch.",
            updated_at="2026-03-15T10:05:00Z",
        ),
        dispatch=LocalTaskDispatch(
            dispatch_key="dispatch:301",
            status="running",
            submission_source="local_cli",
        ),
        events=[
            LocalTaskEvent(
                event_key="task:301:submitted",
                event_type="task_submitted",
                level="info",
                occurred_at="2026-03-15T10:00:00Z",
                message="Task submitted to local registry.",
                metadata={
                    "dispatch_key": "dispatch:301",
                    "submission_source": "local_cli",
                },
            ),
            LocalTaskEvent(
                event_key="task:301:running",
                event_type="task_running",
                level="info",
                occurred_at="2026-03-15T10:01:00Z",
                message="Simulation is running locally.",
                metadata={
                    "dispatch_key": "dispatch:301",
                    "progress_phase": "running",
                },
            ),
        ],
    )


def _seed_characterization_task() -> LocalTaskDetail:
    return LocalTaskDetail(
        task_id=302,
        kind="characterization",
        lane="characterization",
        execution_mode="run",
        status="queued",
        visibility_scope="workspace",
        dataset_id="transmon-coupler-014",
        definition_id=None,
        summary="Coupler characterization queue entry",
        submitted_at="2026-03-15T09:58:00Z",
        owner_user_id="researcher-01",
        owner_display_name="Rewrite Local User",
        workspace_id="ws-device-lab",
        workspace_slug="device-lab",
        queue_backend="local_registry",
        worker_task_name="characterization_run_task",
        request_ready=True,
        submitted_from_active_dataset=False,
        progress=LocalTaskProgress(
            phase="queued",
            percent_complete=0,
            summary="Queued for local characterization execution.",
            updated_at="2026-03-15T09:58:00Z",
        ),
        dispatch=LocalTaskDispatch(
            dispatch_key="dispatch:302",
            status="queued",
            submission_source="local_cli",
        ),
        events=[
            LocalTaskEvent(
                event_key="task:302:submitted",
                event_type="task_submitted",
                level="info",
                occurred_at="2026-03-15T09:58:00Z",
                message="Characterization task submitted.",
                metadata={
                    "dispatch_key": "dispatch:302",
                    "submission_source": "local_cli",
                },
            )
        ],
    )


def _seed_completed_post_processing_task() -> LocalTaskDetail:
    metadata_record = LocalMetadataRecord(
        record_id="metadata:fluxonium-2025-031:analysis-summary",
        record_type="analysis_summary",
        backend="local_json",
        version="1.0",
        schema_version="analysis-result/v1",
    )
    plot_record = LocalMetadataRecord(
        record_id="metadata:fluxonium-2025-031:plot-bundle",
        record_type="plot_bundle",
        backend="local_json",
        version="1.0",
        schema_version="analysis-result/v1",
    )
    return LocalTaskDetail(
        task_id=303,
        kind="post_processing",
        lane="simulation",
        execution_mode="analyze",
        status="completed",
        visibility_scope="workspace",
        dataset_id="fluxonium-2025-031",
        definition_id=18,
        summary="Fluxonium fit extraction",
        submitted_at="2026-03-15T09:40:00Z",
        owner_user_id="researcher-01",
        owner_display_name="Rewrite Local User",
        workspace_id="ws-device-lab",
        workspace_slug="device-lab",
        queue_backend="local_registry",
        worker_task_name="post_processing_run_task",
        request_ready=True,
        submitted_from_active_dataset=False,
        progress=LocalTaskProgress(
            phase="completed",
            percent_complete=100,
            summary="Post-processing artifacts persisted.",
            updated_at="2026-03-15T09:45:00Z",
        ),
        dispatch=LocalTaskDispatch(
            dispatch_key="dispatch:303",
            status="completed",
            submission_source="local_cli",
        ),
        events=[
            LocalTaskEvent(
                event_key="task:303:submitted",
                event_type="task_submitted",
                level="info",
                occurred_at="2026-03-15T09:40:00Z",
                message="Post-processing task submitted.",
                metadata={
                    "dispatch_key": "dispatch:303",
                    "submission_source": "local_cli",
                },
            ),
            LocalTaskEvent(
                event_key="task:303:completed",
                event_type="task_completed",
                level="info",
                occurred_at="2026-03-15T09:45:00Z",
                message="Post-processing completed with persisted outputs.",
                metadata={
                    "dispatch_key": "dispatch:303",
                    "submission_source": "local_cli",
                    "result_handle_ids": [
                        "result:fluxonium-2025-031:fit-summary",
                        "result:fluxonium-2025-031:plot-bundle",
                    ],
                },
            ),
        ],
        result_refs=LocalTaskResultRefs(
            trace_batch_id=88,
            analysis_run_id="analysis:fluxonium-2025-031:fit-summary",
            lineage=LocalResultLineage(
                source_runtime="standalone_cli",
                source_task_id=303,
                source_dataset_id="fluxonium-2025-031",
                source_definition_id=18,
                source_analysis_run_id="analysis:fluxonium-2025-031:fit-summary",
                source_trace_batch_id=88,
            ),
            metadata_records=[metadata_record, plot_record],
            trace_payload=LocalTracePayload(
                contract_version="1.0",
                backend="local_zarr",
                payload_role="simulation_trace",
                store_key="datasets/fluxonium-2025-031/trace-batches/88.zarr",
                store_uri="trace_store/datasets/fluxonium-2025-031/trace-batches/88.zarr",
                group_path="/",
                array_path="/signals/s11",
                dtype="float64",
                shape=[184, 1024],
                chunk_shape=[46, 256],
                schema_version="trace-store/v1",
            ),
            result_handles=[
                LocalResultHandle(
                    handle_id="result:fluxonium-2025-031:fit-summary",
                    kind="analysis_summary",
                    status="ready",
                    label="fit-summary",
                    payload_backend="local_json",
                    payload_format="json",
                    payload_role="analysis_summary",
                    payload_locator="artifacts/fit-summary.json",
                    metadata_record=metadata_record,
                    provenance_task_id=303,
                    provenance=LocalResultProvenance(
                        source_dataset_id="fluxonium-2025-031",
                        trace_batch_record=LocalRecordRef(record_id="trace-batch:88"),
                        analysis_run_record=LocalRecordRef(
                            record_id="analysis-run:fluxonium-2025-031:fit-summary"
                        ),
                    ),
                ),
                LocalResultHandle(
                    handle_id="result:fluxonium-2025-031:plot-bundle",
                    kind="plot_bundle",
                    status="ready",
                    label="plot-bundle",
                    payload_backend="local_zip",
                    payload_format="zip",
                    payload_role="plot_bundle",
                    payload_locator="artifacts/plot-bundle.zip",
                    metadata_record=plot_record,
                    provenance_task_id=303,
                    provenance=LocalResultProvenance(
                        source_dataset_id="fluxonium-2025-031",
                        trace_batch_record=LocalRecordRef(record_id="trace-batch:88"),
                        analysis_run_record=LocalRecordRef(
                            record_id="analysis-run:fluxonium-2025-031:fit-summary"
                        ),
                    ),
                ),
            ],
        ),
    )


def _seed_owned_only_task() -> LocalTaskDetail:
    return LocalTaskDetail(
        task_id=304,
        kind="simulation",
        lane="simulation",
        execution_mode="smoke",
        status="queued",
        visibility_scope="owned",
        dataset_id="fluxonium-2025-031",
        definition_id=12,
        summary="Owner-only detached simulation draft",
        submitted_at="2026-03-15T10:10:00Z",
        owner_user_id="researcher-01",
        owner_display_name="Rewrite Local User",
        workspace_id="ws-device-lab",
        workspace_slug="device-lab",
        queue_backend="local_registry",
        worker_task_name="simulation_smoke_task",
        request_ready=False,
        submitted_from_active_dataset=True,
        progress=LocalTaskProgress(
            phase="queued",
            percent_complete=0,
            summary="Queued in local registry.",
            updated_at="2026-03-15T10:10:00Z",
        ),
        dispatch=LocalTaskDispatch(
            dispatch_key="dispatch:304",
            status="queued",
            submission_source="local_cli",
        ),
        events=[
            LocalTaskEvent(
                event_key="task:304:submitted",
                event_type="task_submitted",
                level="info",
                occurred_at="2026-03-15T10:10:00Z",
                message="Owner-only simulation task submitted.",
                metadata={
                    "dispatch_key": "dispatch:304",
                    "submission_source": "local_cli",
                },
            )
        ],
    )


@dataclass
class _LocalRuntimeState:
    session: LocalSession
    tasks: dict[int, LocalTaskDetail]
    next_task_id: int


def _seed_state() -> _LocalRuntimeState:
    tasks = {
        301: _seed_running_simulation_task(),
        302: _seed_characterization_task(),
        303: _seed_completed_post_processing_task(),
        304: _seed_owned_only_task(),
    }
    return _LocalRuntimeState(
        session=_session_with_active_dataset("fluxonium-2025-031"),
        tasks=tasks,
        next_task_id=305,
    )


def _strip_task_runtime_payloads(task: LocalTaskDetail) -> LocalTaskDetail:
    return task.model_copy(
        deep=True,
        update={
            "events": [],
            "result_refs": LocalTaskResultRefs(),
        },
    )


def _persist_task_state(state: _LocalRuntimeState) -> None:
    write_model(session_state_path(), state.session)
    registry = _PersistedTaskRegistry(
        session=state.session,
        next_task_id=state.next_task_id,
        tasks=[_strip_task_runtime_payloads(task) for task in state.tasks.values()],
    )
    write_model(task_registry_path(), registry)
    for task in state.tasks.values():
        write_json(
            task_events_path(task.task_id),
            [event.model_dump(mode="json") for event in task.events],
        )
        write_model(task_results_path(task.task_id), task.result_refs)


def _load_persisted_task_state() -> _LocalRuntimeState | None:
    payload = read_json(task_registry_path())
    if not isinstance(payload, dict):
        return None
    registry = _PersistedTaskRegistry.model_validate(payload)
    tasks: dict[int, LocalTaskDetail] = {}
    for task in registry.tasks:
        hydrated_task = task.model_copy(deep=True)
        events_payload = read_json(task_events_path(task.task_id))
        if isinstance(events_payload, list):
            hydrated_task.events = [
                LocalTaskEvent.model_validate(event_payload)
                for event_payload in events_payload
            ]
        results_payload = read_json(task_results_path(task.task_id))
        if isinstance(results_payload, dict):
            hydrated_task.result_refs = LocalTaskResultRefs.model_validate(results_payload)
        tasks[hydrated_task.task_id] = hydrated_task
    return _LocalRuntimeState(
        session=registry.session.model_copy(deep=True),
        tasks=tasks,
        next_task_id=registry.next_task_id,
    )


def _load_or_seed_state() -> _LocalRuntimeState:
    persisted_state = _load_persisted_task_state()
    if persisted_state is not None:
        return persisted_state
    seeded_state = _seed_state()
    _persist_task_state(seeded_state)
    return seeded_state


_STATE = _load_or_seed_state()


def reset_runtime_state() -> None:
    global _STATE
    _STATE = _seed_state()
    _persist_task_state(_STATE)


def reload_runtime_state() -> None:
    global _STATE
    _STATE = _load_or_seed_state()


def get_session() -> LocalSession:
    return _STATE.session.model_copy(deep=True)


def set_active_dataset(dataset_id: str | None) -> LocalSession:
    if dataset_id is not None and not _dataset_exists(dataset_id):
        raise _contract_error(
            code="dataset_not_found",
            category="not_found",
            message=f"Dataset {dataset_id} was not found.",
            status=404,
        )
    _STATE.session = _session_with_active_dataset(dataset_id)
    _persist_task_state(_STATE)
    return get_session()


def list_tasks(
    *,
    status: str | None = None,
    lane: str | None = None,
    scope: str = "workspace",
    dataset_id: str | None = None,
    limit: int = 20,
) -> list[LocalTaskSummary]:
    tasks = sorted(_STATE.tasks.values(), key=lambda task: task.task_id, reverse=True)
    visible_tasks: list[LocalTaskDetail] = []
    for task in tasks:
        if scope == "workspace" and task.visibility_scope != "workspace":
            continue
        if status is not None and task.status != status:
            continue
        if lane is not None and task.lane != lane:
            continue
        if dataset_id is not None and task.dataset_id != dataset_id:
            continue
        visible_tasks.append(task)
    return [_task_summary(task) for task in visible_tasks[:limit]]


def get_task(task_id: int) -> LocalTaskDetail:
    task = _STATE.tasks.get(task_id)
    if task is None:
        raise _contract_error(
            code="task_not_found",
            category="not_found",
            message=f"Task {task_id} was not found.",
            status=404,
        )
    return task.model_copy(deep=True)


def submit_task(
    *,
    kind: TaskKindValue,
    dataset_id: str | None = None,
    definition_id: int | None = None,
    summary: str | None = None,
) -> LocalTaskDetail:
    submitted_from_active_dataset = False
    effective_dataset_id = dataset_id

    if effective_dataset_id is None and _STATE.session.workspace.active_dataset is not None:
        effective_dataset_id = _STATE.session.workspace.active_dataset.dataset_id
        submitted_from_active_dataset = True

    if kind == "simulation" and definition_id is None:
        raise _contract_error(
            code="simulation_definition_required",
            category="validation",
            message="Simulation tasks require definition_id.",
            status=422,
        )

    if kind in {"simulation", "characterization"} and effective_dataset_id is None:
        raise _contract_error(
            code="dataset_context_required",
            category="validation",
            message="Provide --dataset-id or configure an active dataset in the local session.",
            status=422,
        )

    if effective_dataset_id is not None and not _dataset_exists(effective_dataset_id):
        raise _contract_error(
            code="dataset_not_found",
            category="not_found",
            message=f"Dataset {effective_dataset_id} was not found.",
            status=404,
        )

    task_id = _STATE.next_task_id
    _STATE.next_task_id += 1
    lane: TaskLaneValue = "characterization" if kind == "characterization" else "simulation"
    execution_mode = "run"
    worker_task_name = "local_task_runner"
    if kind == "simulation":
        execution_mode = "smoke"
        worker_task_name = "simulation_smoke_task"
    elif kind == "characterization":
        worker_task_name = "characterization_run_task"
    elif kind == "post_processing":
        execution_mode = "analyze"
        worker_task_name = "post_processing_run_task"
    task = LocalTaskDetail(
        task_id=task_id,
        kind=kind,
        lane=lane,
        execution_mode=execution_mode,
        status="queued",
        visibility_scope="workspace",
        dataset_id=effective_dataset_id,
        definition_id=definition_id,
        summary=summary or f"Local {kind} task",
        submitted_at="2026-03-15T11:00:00Z",
        owner_user_id="researcher-01",
        owner_display_name="Rewrite Local User",
        workspace_id="ws-device-lab",
        workspace_slug="device-lab",
        queue_backend="local_registry",
        worker_task_name=worker_task_name,
        request_ready=(kind == "characterization"),
        submitted_from_active_dataset=submitted_from_active_dataset,
        progress=LocalTaskProgress(
            phase="queued",
            percent_complete=0,
            summary="Queued in local run registry.",
            updated_at="2026-03-15T11:00:00Z",
        ),
        dispatch=LocalTaskDispatch(
            dispatch_key=f"dispatch:{task_id}",
            status="queued",
            submission_source="local_cli",
        ),
        events=[
            LocalTaskEvent(
                event_key=f"task:{task_id}:submitted",
                event_type="task_submitted",
                level="info",
                occurred_at="2026-03-15T11:00:00Z",
                message="Task submitted to local run registry.",
                metadata={
                    "dispatch_key": f"dispatch:{task_id}",
                    "submission_source": "local_cli",
                },
            )
        ],
    )
    _STATE.tasks[task_id] = task
    _persist_task_state(_STATE)
    return task.model_copy(deep=True)


def export_task_result_bundle(task_id: int):
    from sc_cli.local_interchange import build_result_bundle

    task = get_task(task_id)
    if not task.result_refs.result_handles and task.result_refs.trace_payload is None:
        raise _contract_error(
            code="result_bundle_unavailable",
            category="validation",
            message=f"Task {task_id} does not expose result payloads for bundle export.",
            status=422,
        )
    return build_result_bundle(task)


def import_task_result_bundle(bundle: LocalResultBundle) -> LocalTaskDetail:
    task_id = _STATE.next_task_id
    _STATE.next_task_id += 1
    imported_result_refs = bundle.result_refs.model_copy(deep=True)
    previous_lineage = imported_result_refs.lineage
    imported_result_refs.lineage = LocalResultLineage(
        source_runtime=(
            "bundle_import"
            if previous_lineage is None
            else previous_lineage.source_runtime
        ),
        source_task_id=(
            bundle.task.task_id if previous_lineage is None else previous_lineage.source_task_id
        ),
        source_dataset_id=(
            bundle.task.dataset_id
            if previous_lineage is None
            else previous_lineage.source_dataset_id
        ),
        source_definition_id=(
            bundle.task.definition_id
            if previous_lineage is None
            else previous_lineage.source_definition_id
        ),
        source_analysis_run_id=(
            imported_result_refs.analysis_run_id
            if previous_lineage is None
            else previous_lineage.source_analysis_run_id
        ),
        source_trace_batch_id=(
            imported_result_refs.trace_batch_id
            if previous_lineage is None
            else previous_lineage.source_trace_batch_id
        ),
        parent_bundle_id=bundle.metadata.bundle_id,
        imported_from_bundle_id=bundle.metadata.bundle_id,
    )
    imported_task = LocalTaskDetail(
        task_id=task_id,
        kind=bundle.task.kind,
        lane=bundle.task.lane,
        execution_mode="imported",
        status="completed",
        visibility_scope="workspace",
        dataset_id=bundle.task.dataset_id,
        definition_id=bundle.task.definition_id,
        summary=f"Imported result bundle from task {bundle.task.task_id}",
        submitted_at="2026-03-15T12:05:00Z",
        owner_user_id="researcher-01",
        owner_display_name="Rewrite Local User",
        workspace_id="ws-device-lab",
        workspace_slug="device-lab",
        queue_backend="local_registry",
        worker_task_name="result_bundle_import",
        request_ready=True,
        submitted_from_active_dataset=False,
        progress=LocalTaskProgress(
            phase="completed",
            percent_complete=100,
            summary="Imported result bundle into local registry.",
            updated_at="2026-03-15T12:05:00Z",
        ),
        dispatch=LocalTaskDispatch(
            dispatch_key=f"dispatch:{task_id}",
            status="completed",
            submission_source="bundle_import",
        ),
        events=[
            LocalTaskEvent(
                event_key=f"task:{task_id}:submitted",
                event_type="task_submitted",
                level="info",
                occurred_at="2026-03-15T12:05:00Z",
                message="Imported result bundle registered locally.",
                metadata={
                    "dispatch_key": f"dispatch:{task_id}",
                    "submission_source": "bundle_import",
                    "bundle_id": bundle.metadata.bundle_id,
                },
            ),
            LocalTaskEvent(
                event_key=f"task:{task_id}:completed",
                event_type="task_completed",
                level="info",
                occurred_at="2026-03-15T12:05:00Z",
                message="Imported result bundle is available for inspection.",
                metadata={
                    "bundle_id": bundle.metadata.bundle_id,
                    "source_task_id": bundle.task.task_id,
                },
            ),
        ],
        result_refs=imported_result_refs,
    )
    _STATE.tasks[task_id] = imported_task
    _persist_task_state(_STATE)
    return imported_task.model_copy(deep=True)
