"""Tests for Characterization trace-scope query service."""

from __future__ import annotations

from dataclasses import dataclass

from legacy.legacy_nicegui_archived.features.characterization.query.trace_scope import (
    CharacterizationTraceScopeUnitOfWork,
    TraceSourceSummary,
    count_scope_trace_records,
    hydrate_trace_index_rows_with_provenance,
    list_design_scope_source_summaries,
    list_scope_compatible_trace_index_page,
    list_scope_compatible_trace_source_summaries,
)
from core.shared.persistence.repositories import (
    DataRecordCharacterizationContract,
    ResultBundleCharacterizationContract,
)


@dataclass
class _FakeDataRecordsRepo:
    count_value: int = 0
    page_rows: list[dict[str, str | int]] | None = None
    page_total: int = 0
    counted_dataset_id: int | None = None
    page_dataset_id: int | None = None
    last_query: object | None = None

    def count_by_dataset(self, dataset_id: int) -> int:
        self.counted_dataset_id = dataset_id
        return self.count_value

    def list_distinct_index_for_profile(self, dataset_id: int) -> list[dict[str, str]]:
        _ = dataset_id
        return []

    def list_index_page_by_dataset(
        self,
        dataset_id: int,
        *,
        query: object | None = None,
        **kwargs: object,
    ) -> tuple[list, int]:
        self.page_dataset_id = dataset_id
        self.last_query = query if query is not None else kwargs.get("query")
        return (self.page_rows or []), self.page_total


@dataclass
class _FakeResultBundlesRepo:
    count_value: int = 0
    page_rows: list[dict[str, str | int]] | None = None
    page_total: int = 0
    bundles_by_dataset: dict[int, list[dict[str, object]]] | None = None
    bundle_rows_by_id: dict[int, list[dict[str, str | int]]] | None = None
    count_by_bundle_id: dict[int, int] | None = None
    counted_bundle_id: int | None = None
    page_bundle_id: int | None = None
    last_query: object | None = None

    def count_data_records(self, bundle_id: int) -> int:
        self.counted_bundle_id = bundle_id
        if self.count_by_bundle_id and bundle_id in self.count_by_bundle_id:
            return self.count_by_bundle_id[bundle_id]
        return self.count_value

    def list_by_dataset(self, dataset_id: int) -> list[dict[str, object]]:
        return list((self.bundles_by_dataset or {}).get(dataset_id, []))

    def list_data_record_index_page(
        self,
        bundle_id: int,
        *,
        query: object | None = None,
        **kwargs: object,
    ) -> tuple[list, int]:
        self.page_bundle_id = bundle_id
        self.last_query = query if query is not None else kwargs.get("query")
        rows = list((self.bundle_rows_by_id or {}).get(bundle_id, self.page_rows or []))
        ids = kwargs.get("ids")
        if query is not None:
            ids = getattr(query, "ids", ids)
        if ids is not None:
            normalized_ids = {int(record_id) for record_id in ids}
            rows = [row for row in rows if int(row.get("id", 0)) in normalized_ids]
        total = (
            self.count_by_bundle_id.get(bundle_id, len(rows))
            if self.count_by_bundle_id
            else len(rows)
            if self.bundle_rows_by_id and bundle_id in self.bundle_rows_by_id
            else self.page_total
        )
        return (rows, total)


@dataclass
class _FakeUow:
    data_records: _FakeDataRecordsRepo
    result_bundles: _FakeResultBundlesRepo


def test_trace_scope_service_protocol_contracts_are_satisfied() -> None:
    data_records = _FakeDataRecordsRepo()
    bundles = _FakeResultBundlesRepo()
    uow = _FakeUow(data_records=data_records, result_bundles=bundles)

    assert isinstance(data_records, DataRecordCharacterizationContract)
    assert isinstance(bundles, ResultBundleCharacterizationContract)
    assert isinstance(uow, CharacterizationTraceScopeUnitOfWork)


def test_count_scope_trace_records_uses_dataset_repo_when_scope_is_all_dataset() -> None:
    data_records = _FakeDataRecordsRepo(count_value=42)
    bundles = _FakeResultBundlesRepo(count_value=7)
    uow = _FakeUow(data_records=data_records, result_bundles=bundles)

    total = count_scope_trace_records(uow=uow, dataset_id=12, selected_bundle_id=None)

    assert total == 42
    assert data_records.counted_dataset_id == 12
    assert bundles.counted_bundle_id is None


def test_count_scope_trace_records_uses_bundle_repo_when_bundle_is_selected() -> None:
    data_records = _FakeDataRecordsRepo(count_value=42)
    bundles = _FakeResultBundlesRepo(count_value=7)
    uow = _FakeUow(data_records=data_records, result_bundles=bundles)

    total = count_scope_trace_records(uow=uow, dataset_id=12, selected_bundle_id=99)

    assert total == 7
    assert bundles.counted_bundle_id == 99
    assert data_records.counted_dataset_id is None


def test_list_scope_compatible_trace_index_page_builds_normalized_query() -> None:
    data_records = _FakeDataRecordsRepo(
        page_rows=[{"id": 1, "parameter": "Y11", "representation": "imaginary"}],
        page_total=1,
    )
    bundles = _FakeResultBundlesRepo()
    uow = _FakeUow(data_records=data_records, result_bundles=bundles)

    rows, total = list_scope_compatible_trace_index_page(
        uow=uow,
        dataset_id=5,
        selected_bundle_id=None,
        analysis_requires={
            "data_type": "y_params",
            "parameter": "Y11 [om=(0,)]",
            "representation": "Imaginary",
        },
        mode_filter="invalid",
        limit=10,
        offset=20,
    )

    assert rows == [{"id": 1, "parameter": "Y11", "representation": "imaginary"}]
    assert total == 1
    query = data_records.last_query
    assert query is not None
    assert query.data_types == (
        "y_parameters",
        "y_params",
        "y_matrix",
        "admittance",
        "admittance_matrix",
    )
    assert query.parameters == ("Y11",)
    assert query.representation == "imaginary"
    assert query.mode_filter == "all"
    assert query.limit == 10
    assert query.offset == 20


def test_hydrate_trace_index_rows_with_provenance_prefers_saved_source_batch() -> None:
    data_records = _FakeDataRecordsRepo()
    bundles = _FakeResultBundlesRepo(
        bundles_by_dataset={
            5: [
                {
                    "id": 11,
                    "bundle_type": "layout_simulation",
                    "role": "import",
                    "source_meta": {"source_kind": "layout_simulation", "stage_kind": "import"},
                },
                {
                    "id": 12,
                    "bundle_type": "layout_simulation",
                    "role": "manual_export",
                    "source_meta": {
                        "source_kind": "layout_simulation",
                        "stage_kind": "manual_export",
                    },
                },
            ]
        },
        bundle_rows_by_id={
            11: [{"id": 101, "parameter": "Y11", "representation": "imaginary"}],
            12: [{"id": 101, "parameter": "Y11", "representation": "imaginary"}],
        },
        count_by_bundle_id={11: 1, 12: 1},
    )
    uow = _FakeUow(data_records=data_records, result_bundles=bundles)

    rows = hydrate_trace_index_rows_with_provenance(
        uow=uow,
        dataset_id=5,
        rows=[{"id": 101, "parameter": "Y11", "representation": "imaginary"}],
    )

    assert rows[0]["source_kind"] == "layout_simulation"
    assert rows[0]["stage_kind"] == "manual_export"
    assert rows[0]["source_label"] == "Layout"
    assert rows[0]["provenance_label"] == "Layout · Saved · batch #12"


def test_list_design_scope_source_summaries_aggregates_cross_source_batches() -> None:
    data_records = _FakeDataRecordsRepo()
    bundles = _FakeResultBundlesRepo(
        bundles_by_dataset={
            9: [
                {
                    "id": 20,
                    "bundle_type": "circuit_simulation",
                    "role": "manual_export",
                    "source_meta": {
                        "source_kind": "circuit_simulation",
                        "stage_kind": "manual_export",
                    },
                },
                {
                    "id": 21,
                    "bundle_type": "layout_simulation",
                    "role": "import",
                    "source_meta": {
                        "source_kind": "layout_simulation",
                        "stage_kind": "import",
                    },
                },
                {
                    "id": 22,
                    "bundle_type": "measurement",
                    "role": "import",
                    "source_meta": {"source_kind": "measurement", "stage_kind": "import"},
                },
            ]
        },
        count_by_bundle_id={20: 2, 21: 3, 22: 1},
    )
    uow = _FakeUow(data_records=data_records, result_bundles=bundles)

    summaries = list_design_scope_source_summaries(uow=uow, dataset_id=9)

    assert summaries == [
        TraceSourceSummary(
            source_kind="measurement",
            source_label="Measurement",
            trace_count=1,
            batch_count=1,
            stage_summary="Imported",
        ),
        TraceSourceSummary(
            source_kind="layout_simulation",
            source_label="Layout",
            trace_count=3,
            batch_count=1,
            stage_summary="Imported",
        ),
        TraceSourceSummary(
            source_kind="circuit_simulation",
            source_label="Circuit",
            trace_count=2,
            batch_count=1,
            stage_summary="Saved",
        ),
    ]


def test_list_scope_compatible_trace_source_summaries_aggregates_by_source() -> None:
    data_records = _FakeDataRecordsRepo(
        page_rows=[
            {"id": 101, "parameter": "Y11", "representation": "imaginary"},
            {"id": 102, "parameter": "Y11", "representation": "imaginary"},
            {"id": 103, "parameter": "Y11", "representation": "imaginary"},
        ],
        page_total=3,
    )
    bundles = _FakeResultBundlesRepo(
        bundles_by_dataset={
            5: [
                {
                    "id": 31,
                    "bundle_type": "layout_simulation",
                    "role": "import",
                    "source_meta": {
                        "source_kind": "layout_simulation",
                        "stage_kind": "import",
                    },
                },
                {
                    "id": 32,
                    "bundle_type": "measurement",
                    "role": "import",
                    "source_meta": {"source_kind": "measurement", "stage_kind": "import"},
                },
            ]
        },
        bundle_rows_by_id={
            31: [
                {"id": 101, "parameter": "Y11", "representation": "imaginary"},
                {"id": 102, "parameter": "Y11", "representation": "imaginary"},
            ],
            32: [{"id": 103, "parameter": "Y11", "representation": "imaginary"}],
        },
        count_by_bundle_id={31: 2, 32: 1},
    )
    uow = _FakeUow(data_records=data_records, result_bundles=bundles)

    summaries = list_scope_compatible_trace_source_summaries(
        uow=uow,
        dataset_id=5,
        selected_bundle_id=None,
        analysis_requires={"data_type": "y_parameters", "parameter": "Y11"},
    )

    assert summaries == [
        TraceSourceSummary(
            source_kind="measurement",
            source_label="Measurement",
            trace_count=1,
            batch_count=1,
            stage_summary="Imported",
        ),
        TraceSourceSummary(
            source_kind="layout_simulation",
            source_label="Layout",
            trace_count=2,
            batch_count=1,
            stage_summary="Imported",
        ),
    ]
