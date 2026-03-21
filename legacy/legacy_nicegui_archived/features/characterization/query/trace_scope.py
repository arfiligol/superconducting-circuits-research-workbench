"""Design-scope trace query service for the Characterization page."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, cast, runtime_checkable

from core.analysis.domain import ModeGroup, ParameterKey, TraceKind
from core.shared.persistence.repositories import (
    DataRecordCharacterizationContract,
    ResultBundleCharacterizationContract,
    TraceIndexPageQuery,
)
from core.shared.persistence.repositories.query_objects import TraceModeFilter


@runtime_checkable
class CharacterizationTraceScopeUnitOfWork(Protocol):
    """Typed UoW interface consumed by design-facing trace scope queries."""

    @property
    def data_records(self) -> DataRecordCharacterizationContract: ...

    @property
    def result_bundles(self) -> ResultBundleCharacterizationContract: ...


@dataclass(frozen=True)
class TraceSourceSummary:
    """One aggregated source/provenance summary row for Characterization scope."""

    source_kind: str
    source_label: str
    trace_count: int
    batch_count: int
    stage_summary: str


_SOURCE_LABELS: dict[str, str] = {
    "circuit_simulation": "Circuit",
    "layout_simulation": "Layout",
    "measurement": "Measurement",
    "analysis": "Analysis",
}
_STAGE_LABELS: dict[str, str] = {
    "raw": "Raw",
    "import": "Imported",
    "manual_export": "Saved",
    "derived_from_simulation": "Derived",
    "postprocess": "Post-Processed",
    "analysis_run": "Analysis Run",
}
_SOURCE_PRIORITY: dict[str, int] = {
    "measurement": 5,
    "layout_simulation": 4,
    "circuit_simulation": 3,
    "analysis": 1,
}
_STAGE_PRIORITY: dict[str, int] = {
    "manual_export": 5,
    "import": 4,
    "derived_from_simulation": 3,
    "postprocess": 2,
    "raw": 1,
    "analysis_run": 0,
}


def _bundle_field(bundle: object, name: str) -> object:
    if isinstance(bundle, dict):
        return bundle.get(name)
    return getattr(bundle, name, None)


def _bundle_source_meta(bundle: object) -> dict[str, object]:
    raw_value = _bundle_field(bundle, "source_meta")
    return dict(raw_value) if isinstance(raw_value, dict) else {}


def _bundle_source_kind(bundle: object) -> str:
    source_meta = _bundle_source_meta(bundle)
    payload_value = source_meta.get("source_kind")
    if isinstance(payload_value, str) and payload_value.strip():
        return payload_value.strip()

    bundle_type = str(_bundle_field(bundle, "bundle_type") or "").strip()
    if bundle_type == "simulation_postprocess":
        return "circuit_simulation"
    if bundle_type == "characterization":
        return "analysis"
    return bundle_type


def _bundle_stage_kind(bundle: object) -> str:
    source_meta = _bundle_source_meta(bundle)
    payload_value = source_meta.get("stage_kind")
    if isinstance(payload_value, str) and payload_value.strip():
        return payload_value.strip()

    bundle_type = str(_bundle_field(bundle, "bundle_type") or "").strip()
    role = str(_bundle_field(bundle, "role") or "").strip()
    if bundle_type == "circuit_simulation" and role == "cache":
        return "raw"
    if bundle_type == "simulation_postprocess":
        return "postprocess"
    return role


def _source_label(source_kind: str) -> str:
    label = _SOURCE_LABELS.get(source_kind)
    if label is not None:
        return label
    token = source_kind.replace("_", " ").strip()
    return token.title() if token else "Untracked"


def _stage_label(stage_kind: str) -> str:
    label = _STAGE_LABELS.get(stage_kind)
    if label is not None:
        return label
    token = stage_kind.replace("_", " ").strip()
    return token.title() if token else "Unknown Stage"


def _source_sort_key(source_kind: str) -> tuple[int, str]:
    return (-_SOURCE_PRIORITY.get(source_kind, 0), source_kind)


def _provenance_sort_key(candidate: dict[str, object]) -> tuple[int, int, int]:
    stage_kind = str(candidate.get("stage_kind", "")).strip()
    source_kind = str(candidate.get("source_kind", "")).strip()
    raw_batch_id = candidate.get("source_batch_id", 0)
    batch_id = int(raw_batch_id) if isinstance(raw_batch_id, int | str) else 0
    return (
        _STAGE_PRIORITY.get(stage_kind, 0),
        _SOURCE_PRIORITY.get(source_kind, 0),
        batch_id,
    )


def _list_dataset_bundles(
    *,
    uow: CharacterizationTraceScopeUnitOfWork,
    dataset_id: int,
) -> list[object]:
    list_by_dataset = getattr(uow.result_bundles, "list_by_dataset", None)
    if not callable(list_by_dataset):
        return []
    bundles = list_by_dataset(dataset_id)
    return list(bundles) if isinstance(bundles, Sequence) else []


def _trace_provenance_index(
    *,
    uow: CharacterizationTraceScopeUnitOfWork,
    dataset_id: int,
    trace_ids: Sequence[int],
) -> dict[int, dict[str, str | int]]:
    normalized_ids = tuple(sorted({int(trace_id) for trace_id in trace_ids}))
    if not normalized_ids:
        return {}

    provenance_candidates: dict[int, list[dict[str, object]]] = defaultdict(list)
    for bundle in _list_dataset_bundles(uow=uow, dataset_id=dataset_id):
        raw_batch_id = _bundle_field(bundle, "id")
        batch_id = int(raw_batch_id) if isinstance(raw_batch_id, int | str) else 0
        if batch_id <= 0:
            continue
        source_kind = _bundle_source_kind(bundle)
        stage_kind = _bundle_stage_kind(bundle)
        rows, _ = uow.result_bundles.list_data_record_index_page(
            batch_id,
            ids=normalized_ids,
            limit=max(1, len(normalized_ids)),
            offset=0,
        )
        if not rows:
            continue
        for row in rows:
            trace_id = row.get("id")
            if not isinstance(trace_id, int):
                continue
            provenance_candidates[int(trace_id)].append(
                {
                    "source_kind": source_kind,
                    "stage_kind": stage_kind,
                    "source_label": _source_label(source_kind),
                    "stage_label": _stage_label(stage_kind),
                    "source_batch_id": batch_id,
                }
            )

    resolved: dict[int, dict[str, str | int]] = {}
    for trace_id, candidates in provenance_candidates.items():
        best = max(candidates, key=_provenance_sort_key)
        source_label = str(best["source_label"])
        stage_label = str(best["stage_label"])
        raw_batch_id = best["source_batch_id"]
        batch_id = int(raw_batch_id) if isinstance(raw_batch_id, int | str) else 0
        resolved[trace_id] = {
            "source_kind": str(best["source_kind"]),
            "stage_kind": str(best["stage_kind"]),
            "source_label": source_label,
            "stage_label": stage_label,
            "source_batch_id": batch_id,
            "provenance_label": f"{source_label} · {stage_label} · batch #{batch_id}",
        }
    return resolved


def _normalize_analysis_data_type(data_type: str) -> str:
    """Normalize analysis data_type keys to canonical repository tokens."""
    kind = TraceKind.from_token(data_type)
    return data_type.strip().lower() if kind is TraceKind.UNKNOWN else kind.value


def _normalize_analysis_parameter_name(parameter: str) -> str:
    """Normalize analysis parameter names by stripping sideband suffix tokens."""
    return ParameterKey.from_raw(parameter).canonical


def _normalize_analysis_representation(representation: str) -> str:
    """Normalize analysis representation token to lowercase form."""
    return representation.strip().lower()


def _normalize_analysis_requirement_value(key: str, value: object) -> object:
    """Normalize one `requires` value to align with record metadata normalization."""
    if key == "data_type":
        return _normalize_analysis_data_type(str(value))
    if key == "parameter":
        if isinstance(value, list):
            return [_normalize_analysis_parameter_name(str(item)) for item in value]
        return _normalize_analysis_parameter_name(str(value))
    if key == "representation":
        return _normalize_analysis_representation(str(value))
    return value


def _normalize_analysis_requirements(requirements: dict[str, object]) -> dict[str, object]:
    """Normalize `requires` block so all matching uses one canonical rule set."""
    return {
        key: _normalize_analysis_requirement_value(key, value)
        for key, value in requirements.items()
    }


def _analysis_data_type_candidates(data_type: str) -> list[str]:
    """Resolve canonical + alias data_type keys accepted by persistence rows."""
    kind = TraceKind.from_token(data_type)
    if kind is TraceKind.UNKNOWN:
        normalized = _normalize_analysis_data_type(data_type)
        return [normalized] if normalized else []
    return list(kind.accepted_tokens)


def _analysis_query_filters(analysis_requires: dict[str, object]) -> dict[str, object]:
    """Convert analysis `requires` into DB-friendly metadata filter clauses."""
    normalized_requires = _normalize_analysis_requirements(analysis_requires)
    data_type_value = normalized_requires.get("data_type", "")
    data_types: list[str] = []
    if isinstance(data_type_value, str) and data_type_value:
        data_types = _analysis_data_type_candidates(data_type_value)

    parameter_value = normalized_requires.get("parameter")
    parameters: list[str] = []
    if isinstance(parameter_value, list):
        parameters = [str(item) for item in parameter_value if str(item)]
    elif isinstance(parameter_value, str) and parameter_value:
        parameters = [parameter_value]

    representation = str(normalized_requires.get("representation", "") or "")
    return {
        "data_types": data_types,
        "parameters": parameters,
        "representation": representation,
    }


def count_scope_trace_records(
    *,
    uow: CharacterizationTraceScopeUnitOfWork,
    dataset_id: int,
    selected_bundle_id: int | None,
) -> int:
    """Count traces visible in the current design scope."""
    if selected_bundle_id is not None:
        return uow.result_bundles.count_data_records(selected_bundle_id)
    return uow.data_records.count_by_dataset(dataset_id)


def hydrate_trace_index_rows_with_provenance(
    *,
    uow: CharacterizationTraceScopeUnitOfWork,
    dataset_id: int,
    rows: Sequence[dict[str, str | int]],
) -> list[dict[str, str | int]]:
    """Attach source/provenance labels to trace-index rows using batch membership only."""
    normalized_rows = [dict(row) for row in rows]
    trace_ids = [int(row["id"]) for row in normalized_rows if isinstance(row.get("id"), int)]
    provenance_by_trace_id = _trace_provenance_index(
        uow=uow,
        dataset_id=dataset_id,
        trace_ids=trace_ids,
    )
    hydrated_rows: list[dict[str, str | int]] = []
    for row in normalized_rows:
        trace_id = row.get("id")
        if isinstance(trace_id, int) and int(trace_id) in provenance_by_trace_id:
            hydrated_rows.append({**row, **provenance_by_trace_id[int(trace_id)]})
            continue
        hydrated_rows.append(
            {
                **row,
                "source_kind": "",
                "stage_kind": "",
                "source_label": "Untracked",
                "stage_label": "Unknown Stage",
                "source_batch_id": 0,
                "provenance_label": "Untracked trace provenance",
            }
        )
    return hydrated_rows


def list_design_scope_source_summaries(
    *,
    uow: CharacterizationTraceScopeUnitOfWork,
    dataset_id: int,
) -> list[TraceSourceSummary]:
    """Aggregate design-scope trace availability by source/provenance family."""
    grouped_trace_counts: dict[str, int] = defaultdict(int)
    grouped_batch_ids: dict[str, set[int]] = defaultdict(set)
    grouped_stage_labels: dict[str, set[str]] = defaultdict(set)

    for bundle in _list_dataset_bundles(uow=uow, dataset_id=dataset_id):
        raw_batch_id = _bundle_field(bundle, "id")
        batch_id = int(raw_batch_id) if isinstance(raw_batch_id, int | str) else 0
        if batch_id <= 0:
            continue
        trace_count = int(uow.result_bundles.count_data_records(batch_id))
        if trace_count <= 0:
            continue
        source_kind = _bundle_source_kind(bundle)
        stage_kind = _bundle_stage_kind(bundle)
        grouped_trace_counts[source_kind] += trace_count
        grouped_batch_ids[source_kind].add(batch_id)
        grouped_stage_labels[source_kind].add(_stage_label(stage_kind))

    summaries: list[TraceSourceSummary] = []
    for source_kind in sorted(grouped_trace_counts, key=_source_sort_key):
        summaries.append(
            TraceSourceSummary(
                source_kind=source_kind,
                source_label=_source_label(source_kind),
                trace_count=int(grouped_trace_counts[source_kind]),
                batch_count=len(grouped_batch_ids[source_kind]),
                stage_summary=", ".join(sorted(grouped_stage_labels[source_kind])),
            )
        )
    return summaries


def list_scope_compatible_trace_source_summaries(
    *,
    uow: CharacterizationTraceScopeUnitOfWork,
    dataset_id: int,
    selected_bundle_id: int | None,
    analysis_requires: dict[str, object],
    search: str = "",
    mode_filter: str = "all",
) -> list[TraceSourceSummary]:
    """Aggregate compatible trace counts by source for one analysis under current scope."""
    _, compatible_total = list_scope_compatible_trace_index_page(
        uow=uow,
        dataset_id=dataset_id,
        selected_bundle_id=selected_bundle_id,
        analysis_requires=analysis_requires,
        search=search,
        mode_filter=mode_filter,
        limit=1,
        offset=0,
    )
    if compatible_total <= 0:
        return []

    compatible_rows, _ = list_scope_compatible_trace_index_page(
        uow=uow,
        dataset_id=dataset_id,
        selected_bundle_id=selected_bundle_id,
        analysis_requires=analysis_requires,
        search=search,
        mode_filter=mode_filter,
        limit=max(1, compatible_total),
        offset=0,
    )
    hydrated_rows = hydrate_trace_index_rows_with_provenance(
        uow=uow,
        dataset_id=dataset_id,
        rows=compatible_rows,
    )
    grouped_trace_ids: dict[str, set[int]] = defaultdict(set)
    grouped_batch_ids: dict[str, set[int]] = defaultdict(set)
    grouped_stage_labels: dict[str, set[str]] = defaultdict(set)

    for row in hydrated_rows:
        source_kind = str(row.get("source_kind", "")).strip()
        trace_id = row.get("id")
        batch_id = row.get("source_batch_id")
        if not source_kind or not isinstance(trace_id, int):
            continue
        grouped_trace_ids[source_kind].add(int(trace_id))
        if isinstance(batch_id, int) and batch_id > 0:
            grouped_batch_ids[source_kind].add(int(batch_id))
        stage_label = str(row.get("stage_label", "")).strip()
        if stage_label:
            grouped_stage_labels[source_kind].add(stage_label)

    summaries: list[TraceSourceSummary] = []
    for source_kind in sorted(grouped_trace_ids, key=_source_sort_key):
        summaries.append(
            TraceSourceSummary(
                source_kind=source_kind,
                source_label=_source_label(source_kind),
                trace_count=len(grouped_trace_ids[source_kind]),
                batch_count=len(grouped_batch_ids[source_kind]),
                stage_summary=", ".join(sorted(grouped_stage_labels[source_kind])),
            )
        )
    return summaries


def list_scope_compatible_trace_index_page(
    *,
    uow: CharacterizationTraceScopeUnitOfWork,
    dataset_id: int,
    selected_bundle_id: int | None,
    analysis_requires: dict[str, object],
    search: str = "",
    sort_by: str = "id",
    descending: bool = False,
    mode_filter: str = "all",
    ids: Sequence[int] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, str | int]], int]:
    """List one page of compatible trace metadata under the current design scope."""
    filters = _analysis_query_filters(analysis_requires)
    raw_data_types = filters.get("data_types")
    raw_parameters = filters.get("parameters")
    data_types = raw_data_types if isinstance(raw_data_types, list) else []
    parameters = raw_parameters if isinstance(raw_parameters, list) else []
    normalized_mode = ModeGroup.normalize(
        mode_filter,
        allow_all=True,
        default=ModeGroup.ALL,
    )
    query = TraceIndexPageQuery(
        search=search,
        sort_by=sort_by,
        descending=descending,
        data_types=tuple(str(item) for item in data_types),
        parameters=tuple(str(item) for item in parameters),
        representation=str(filters["representation"]),
        mode_filter=cast("TraceModeFilter", normalized_mode.value),
        ids=tuple(int(record_id) for record_id in ids) if ids is not None else None,
        limit=limit,
        offset=offset,
    )
    if selected_bundle_id is not None:
        return uow.result_bundles.list_data_record_index_page(
            selected_bundle_id,
            query=query,
        )
    return uow.data_records.list_index_page_by_dataset(
        dataset_id,
        query=query,
    )


__all__ = [
    "CharacterizationTraceScopeUnitOfWork",
    "TraceSourceSummary",
    "count_scope_trace_records",
    "hydrate_trace_index_rows_with_provenance",
    "list_design_scope_source_summaries",
    "list_scope_compatible_trace_index_page",
    "list_scope_compatible_trace_source_summaries",
]
