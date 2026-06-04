from app_backend.infrastructure.rewrite_catalog_repository import InMemoryRewriteCatalogRepository
from app_backend.services.trace_collection_service import TraceCollectionService


class _StubAxisValueLoader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def load_axis_values(
        self,
        detail,
        axis_name: str,
    ) -> tuple[float, ...] | None:
        self.calls.append((detail.trace_id, axis_name))
        return tuple(float(index) for index in range(detail.axes[0].length))


def test_trace_collection_service_uses_injected_axis_loader_and_omits_dense_shared_axis_values():
    repository = InMemoryRewriteCatalogRepository()
    loader = _StubAxisValueLoader()
    service = TraceCollectionService(axis_value_loader=loader)
    measurement = repository.get_trace_detail(
        "local-dataset-001",
        "design_local_flux_playground",
        "trace_local_flux_measurement",
    )
    preview = repository.get_trace_detail(
        "local-dataset-001",
        "design_local_flux_playground",
        "trace_local_flux_preview",
    )

    payload = service.derive_input_collection_payload_from_trace_details((measurement, preview))

    assert payload is not None
    assert loader.calls == [
        ("trace_local_flux_measurement", "frequency"),
        ("trace_local_flux_preview", "frequency"),
    ]
    assert payload.shared_axes[0].name == "frequency"
    assert payload.shared_axes[0].values == ()
