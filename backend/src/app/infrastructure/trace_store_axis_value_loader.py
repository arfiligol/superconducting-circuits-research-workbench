from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from core.shared.persistence import LocalZarrTraceStore, get_trace_store_path

from src.app.domain.datasets import TraceDetail


class TraceStoreAxisValueLoader:
    def load_axis_values(
        self,
        detail: TraceDetail,
        axis_name: str,
    ) -> tuple[float, ...] | None:
        store_ref = _payload_ref_to_store_ref(detail)
        if store_ref is None:
            return None
        trace_store = LocalZarrTraceStore(root_path=get_trace_store_path())
        try:
            axis_values = trace_store.read_axis_slice(
                store_ref,
                axis_name=axis_name,
                selection=slice(None),
            )
        except (KeyError, ValueError, FileNotFoundError):
            return None
        return tuple(float(value) for value in np.asarray(axis_values).reshape(-1))


def _payload_ref_to_store_ref(detail: TraceDetail) -> Mapping[str, object] | None:
    payload_ref = detail.payload_ref
    if payload_ref is None:
        return None
    return {
        "backend": payload_ref.backend,
        "store_key": payload_ref.store_key,
        "store_uri": payload_ref.store_uri,
        "group_path": payload_ref.group_path,
        "array_path": payload_ref.array_path,
        "dtype": payload_ref.dtype,
        "shape": list(payload_ref.shape),
        "chunk_shape": list(payload_ref.chunk_shape),
        "schema_version": payload_ref.schema_version,
    }
