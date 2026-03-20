from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast

from sc_core.storage.contracts import TraceStoreBackend, TraceStoreLocator

TRACE_STORE_SCHEMA_BASELINE_VERSION = "1.0"
TRACE_STORE_EVOLUTION_CONTRACT_VERSION = "sc_tracestore_evolution.v1"
TraceStorePayloadRole = Literal["raw", "processed", "analysis", "export"]
DATASET_IMPORT_TRACE_WRITER_VERSION = "analysis.dataset_import.v1"
SIMULATION_RAW_SWEEP_TRACE_WRITER_VERSION = "simulation.incremental_raw_sweep.v1"
POSTPROCESS_SWEEP_TRACE_WRITER_VERSION = "simulation.incremental_postprocess_sweep.v1"


@dataclass(frozen=True)
class TraceStoreVersionMarkers:
    """Canonical version markers stamped onto persisted TraceStore payloads."""

    schema_version: str
    backend: TraceStoreBackend
    payload_role: TraceStorePayloadRole
    writer_version: str | None = None

    @classmethod
    def from_locator(
        cls,
        locator: TraceStoreLocator,
        *,
        payload_role: TraceStorePayloadRole,
        writer_version: str | None = None,
    ) -> TraceStoreVersionMarkers:
        return cls(
            schema_version=locator.schema_version,
            backend=locator.backend,
            payload_role=payload_role,
            writer_version=writer_version,
        )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> TraceStoreVersionMarkers:
        schema_version = _require_str(payload.get("schema_version"), field_name="schema_version")
        backend = _coerce_backend(payload.get("backend"))
        payload_role = _coerce_payload_role(payload.get("payload_role"))
        writer_version = _optional_str(payload.get("writer_version"))
        return cls(
            schema_version=schema_version,
            backend=backend,
            payload_role=payload_role,
            writer_version=writer_version,
        )

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "contract_version": TRACE_STORE_EVOLUTION_CONTRACT_VERSION,
            "schema_version": self.schema_version,
            "backend": self.backend,
            "payload_role": self.payload_role,
        }
        if self.writer_version is not None:
            payload["writer_version"] = self.writer_version
        return payload


@dataclass(frozen=True)
class TraceStorePayloadLifecycle:
    """Canonical lifecycle metadata for one persisted TraceStore payload."""

    locator: TraceStoreLocator
    version_markers: TraceStoreVersionMarkers

    @classmethod
    def from_store_ref(cls, payload: Mapping[str, object]) -> TraceStorePayloadLifecycle:
        locator = TraceStoreLocator.from_mapping(payload)
        version_markers = TraceStoreVersionMarkers.from_mapping(payload)
        return cls(locator=locator, version_markers=version_markers)

    def to_store_ref_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "backend": self.locator.backend,
            "store_key": self.locator.store_key,
            "group_path": self.locator.group_path,
            "array_path": self.locator.array_path,
            "dtype": self.locator.dtype,
            "shape": list(self.locator.shape),
            "chunk_shape": list(self.locator.chunk_shape),
            "schema_version": self.locator.schema_version,
            "payload_role": self.version_markers.payload_role,
        }
        if self.locator.store_uri is not None:
            payload["store_uri"] = self.locator.store_uri
        if self.version_markers.writer_version is not None:
            payload["writer_version"] = self.version_markers.writer_version
        return payload


def _coerce_backend(value: object) -> TraceStoreBackend:
    backend = _require_str(value, field_name="backend")
    if backend not in {"local_zarr", "s3_zarr"}:
        raise ValueError(f"Unsupported TraceStore backend: {backend}")
    return cast(TraceStoreBackend, backend)


def _coerce_payload_role(value: object) -> TraceStorePayloadRole:
    payload_role = _require_str(value, field_name="payload_role")
    if payload_role not in {"raw", "processed", "analysis", "export"}:
        raise ValueError(f"Unsupported TraceStore payload_role: {payload_role}")
    return cast(TraceStorePayloadRole, payload_role)


def _require_str(value: object, *, field_name: str) -> str:
    text = _optional_str(value)
    if text is None:
        raise ValueError(f"{field_name} is required.")
    return text


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
