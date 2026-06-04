from __future__ import annotations

from collections.abc import Collection, Mapping

MAX_PROVENANCE_SUMMARY_LENGTH = 255


def build_ingested_trace_id(
    *,
    kind: str,
    parameter: str,
    index: int,
    provenance_label: str,
    preview_payload: Mapping[str, object],
    existing_trace_ids: Collection[str],
) -> str:
    source_slug = _source_context_slug(
        provenance_label=provenance_label,
        preview_payload=preview_payload,
    )
    parts = ["trace", _slugify(kind), _slugify(parameter)]
    if source_slug:
        parts.append(source_slug)
    parts.append(str(index))
    candidate = "_".join(part for part in parts if part)
    return _deduplicate_trace_id(candidate, existing_trace_ids)


def build_ingested_trace_provenance_summary(
    *,
    provenance_summary: str,
    provenance_label: str,
    preview_payload: Mapping[str, object],
) -> str:
    source_label = provenance_label.strip()
    summary = provenance_summary.strip()
    if not source_label or not _should_include_source_context(preview_payload):
        return summary
    if source_label.casefold() in summary.casefold():
        return summary
    return _truncate_provenance_summary(f"{summary} · source: {source_label}")


def _deduplicate_trace_id(candidate: str, existing_trace_ids: Collection[str]) -> str:
    if candidate not in existing_trace_ids:
        return candidate
    suffix = 2
    while f"{candidate}_{suffix}" in existing_trace_ids:
        suffix += 1
    return f"{candidate}_{suffix}"


def _source_context_slug(
    *,
    provenance_label: str,
    preview_payload: Mapping[str, object],
) -> str:
    if not _should_include_source_context(preview_payload):
        return ""
    return _slugify(provenance_label)


def _should_include_source_context(preview_payload: Mapping[str, object]) -> bool:
    return preview_payload.get("kind") == "nd_grid"


def _truncate_provenance_summary(value: str) -> str:
    if len(value) <= MAX_PROVENANCE_SUMMARY_LENGTH:
        return value
    return value[: MAX_PROVENANCE_SUMMARY_LENGTH - 3].rstrip() + "..."


def _slugify(value: str) -> str:
    return "-".join(
        token
        for token in "".join(
            character.lower() if character.isalnum() else "-" for character in value.strip()
        ).split("-")
        if token
    )
