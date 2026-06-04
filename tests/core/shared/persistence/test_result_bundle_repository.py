"""Tests for design/trace/trace-batch persistence helpers."""

from datetime import UTC

from core.shared.persistence.models import (
    AnalysisRunRecord,
    CircuitRecord,
    DesignRecord,
    TraceBatchRecord,
    TraceRecord,
)
from core.shared.persistence.models import (
    DesignRecord as DatasetRecord,
)
from core.shared.persistence.models import (
    TraceBatchRecord as ResultBundleRecord,
)
from core.shared.persistence.models import (
    TraceRecord as DataRecord,
)
from core.shared.persistence.repositories.analysis_run_repository import AnalysisRunRepository
from core.shared.persistence.repositories.circuit_repository import CircuitRepository
from core.shared.persistence.repositories.data_record_repository import (
    TraceRepository,
)
from core.shared.persistence.repositories.data_record_repository import (
    TraceRepository as DataRecordRepository,
)
from core.shared.persistence.repositories.dataset_repository import (
    DesignRepository,
)
from core.shared.persistence.repositories.dataset_repository import (
    DesignRepository as DatasetRepository,
)
from core.shared.persistence.repositories.query_objects import TraceIndexPageQuery
from core.shared.persistence.repositories.result_bundle_repository import (
    TraceBatchRepository,
)
from core.shared.persistence.repositories.result_bundle_repository import (
    TraceBatchRepository as ResultBundleRepository,
)
from sqlmodel import Session, SQLModel, create_engine


def _memory_session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_dataset_repository_hides_system_datasets_by_default() -> None:
    with _memory_session() as session:
        repo = DatasetRepository(session)
        repo.add(DatasetRecord(name="Visible", source_meta={"system_hidden": False}, parameters={}))
        repo.add(DatasetRecord(name="Hidden", source_meta={"system_hidden": True}, parameters={}))
        session.commit()

        assert [dataset.name for dataset in repo.list_all()] == ["Visible"]
        assert [dataset.name for dataset in repo.list_all(include_hidden=True)] == [
            "Visible",
            "Hidden",
        ]


def test_dataset_repository_update_source_meta_replaces_payload() -> None:
    with _memory_session() as session:
        repo = DatasetRepository(session)
        dataset = repo.add(
            DatasetRecord(
                name="WithProfile",
                source_meta={"origin": "measurement"},
                parameters={},
            )
        )
        session.flush()
        assert dataset.id is not None

        updated = repo.update_source_meta(
            int(dataset.id),
            {
                "origin": "measurement",
                "dataset_profile": {
                    "schema_version": "1.0",
                    "device_type": "squid",
                    "capabilities": [
                        "y_parameter_characterization",
                        "squid_characterization",
                    ],
                    "source": "manual_override",
                },
            },
        )
        session.commit()

        assert updated.source_meta["origin"] == "measurement"
        assert updated.source_meta["dataset_profile"]["device_type"] == "squid"


def test_result_bundle_repository_finds_cache_bundle_and_lists_member_records() -> None:
    with _memory_session() as session:
        dataset_repo = DatasetRepository(session)
        data_repo = DataRecordRepository(session)
        bundle_repo = ResultBundleRepository(session)

        dataset = dataset_repo.add(
            DatasetRecord(name="Cache", source_meta={"system_hidden": True}, parameters={})
        )
        session.flush()
        assert dataset.id is not None

        bundle = bundle_repo.add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="circuit_simulation",
                role="cache",
                status="completed",
                schema_source_hash="sha256:schema",
                simulation_setup_hash="sha256:setup",
                source_meta={},
                config_snapshot={
                    "freq_range": {
                        "start_ghz": 4.0,
                        "stop_ghz": 5.0,
                        "points": 101,
                    }
                },
                result_payload={
                    "frequencies_ghz": [4.0, 5.0],
                    "s11_real": [0.0, 0.0],
                    "s11_imag": [0.0, 0.0],
                },
            )
        )
        session.flush()
        assert bundle.id is not None

        records = [
            data_repo.add(
                DataRecord(
                    dataset_id=dataset.id,
                    data_type="s_params",
                    parameter="S11",
                    representation="real",
                    axes=[{"name": "frequency", "unit": "GHz", "values": [4.0, 5.0]}],
                    values=[0.0, 0.0],
                )
            ),
            data_repo.add(
                DataRecord(
                    dataset_id=dataset.id,
                    data_type="s_params",
                    parameter="S11",
                    representation="imaginary",
                    axes=[{"name": "frequency", "unit": "GHz", "values": [4.0, 5.0]}],
                    values=[0.0, 0.0],
                )
            ),
        ]
        session.flush()
        bundle_repo.attach_data_records(
            bundle_id=bundle.id,
            data_record_ids=[record.id for record in records if record.id is not None],
        )
        session.commit()

        resolved = bundle_repo.find_simulation_cache(
            dataset_id=dataset.id,
            schema_source_hash="sha256:schema",
            simulation_setup_hash="sha256:setup",
        )

        assert resolved is not None
        assert resolved.id == bundle.id
        assert [
            (record.parameter, record.representation)
            for record in bundle_repo.list_data_records(bundle.id)
        ] == [("S11", "real"), ("S11", "imaginary")]
        assert data_repo.list_all() == []
        assert len(data_repo.list_all(include_hidden=True)) == 2


def test_result_bundle_repository_get_snapshot_returns_detached_dto() -> None:
    with _memory_session() as session:
        dataset = DatasetRepository(session).add(
            DatasetRecord(name="Snapshot Source", source_meta={}, parameters={})
        )
        session.flush()
        assert dataset.id is not None

        bundle = ResultBundleRepository(session).add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="simulation_postprocess",
                role="derived_from_simulation",
                status="completed",
                schema_source_hash="sha256:schema",
                simulation_setup_hash="sha256:setup",
                source_meta={"origin": "simulation_postprocess"},
                config_snapshot={"input_y_source": "ptc_y"},
                result_payload={
                    "run_kind": "parameter_sweep",
                    "point_count": 2,
                    "points": [{"source_point_index": 0}],
                },
            )
        )
        session.commit()
        assert bundle.id is not None

        snapshot = ResultBundleRepository(session).get_snapshot(bundle.id)

        assert snapshot is not None
        assert snapshot["id"] == bundle.id
        assert snapshot["bundle_type"] == "simulation_postprocess"
        assert snapshot["config_snapshot"]["input_y_source"] == "ptc_y"
        assert snapshot["result_payload"]["point_count"] == 2

        snapshot["source_meta"]["origin"] = "mutated"
        snapshot["result_payload"]["points"][0]["source_point_index"] = 99

        refreshed = ResultBundleRepository(session).get(bundle.id)
        assert refreshed is not None
        assert refreshed.source_meta["origin"] == "simulation_postprocess"
        assert refreshed.result_payload["points"][0]["source_point_index"] == 0
        assert refreshed.created_at.tzinfo == UTC


def test_result_bundle_repository_hides_incomplete_snapshots_and_lists_incomplete_batches() -> None:
    with _memory_session() as session:
        dataset = DatasetRepository(session).add(
            DatasetRecord(name="Incomplete Batches", source_meta={}, parameters={})
        )
        session.flush()
        assert dataset.id is not None

        completed = ResultBundleRepository(session).add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="circuit_simulation",
                role="cache",
                status="completed",
                source_meta={},
                config_snapshot={},
                result_payload={},
            )
        )
        incomplete = ResultBundleRepository(session).add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="simulation_postprocess",
                role="derived_from_simulation",
                status="in_progress",
                source_meta={},
                config_snapshot={},
                result_payload={},
            )
        )
        session.flush()
        assert completed.id is not None
        assert incomplete.id is not None

        repo = ResultBundleRepository(session)
        assert repo.get_snapshot(completed.id) is not None
        assert repo.get_trace_batch_snapshot(completed.id) is not None
        assert repo.get_snapshot(incomplete.id) is None
        assert repo.get_trace_batch_snapshot(incomplete.id) is None
        assert [batch.id for batch in repo.list_incomplete_by_dataset(dataset.id)] == [
            incomplete.id
        ]
        assert [batch.id for batch in repo.list_incomplete_batches()] == [incomplete.id]


def test_result_bundle_snapshot_reads_reject_missing_explicit_design_scope() -> None:
    with _memory_session() as session:
        dataset = DatasetRepository(session).add(
            DatasetRecord(name="Legacy Batch", source_meta={}, parameters={})
        )
        session.flush()
        assert dataset.id is not None

        legacy_batch = TraceBatchRecord(
            dataset_id=dataset.id,
            bundle_type="circuit_simulation",
            role="cache",
            status="completed",
            source_meta={},
            config_snapshot={},
            result_payload={},
        )
        session.add(legacy_batch)
        session.commit()
        assert legacy_batch.id is not None

        repo = ResultBundleRepository(session)
        for loader in (repo.get_snapshot, repo.get_trace_batch_snapshot):
            try:
                loader(legacy_batch.id)
            except ValueError as exc:
                assert (
                    str(exc) == "Explicit design_id is required for canonical persistence writes."
                )
            else:
                raise AssertionError("Expected snapshot read path to reject legacy scope fallback.")


def test_result_bundle_repository_merges_summary_into_trace_batch_payload() -> None:
    with _memory_session() as session:
        dataset = DatasetRepository(session).add(
            DatasetRecord(name="Summary Merge", source_meta={}, parameters={})
        )
        session.flush()
        assert dataset.id is not None

        bundle = ResultBundleRepository(session).add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="circuit_simulation",
                role="cache",
                status="in_progress",
                source_meta={},
                config_snapshot={},
                result_payload={
                    "trace_batch_record": {
                        "summary_payload": {
                            "trace_count": 3,
                        }
                    }
                },
            )
        )
        session.flush()
        assert bundle.id is not None

        updated = ResultBundleRepository(session).mark_failed(
            bundle.id,
            summary_payload={"error_code": "write_failed"},
        )

        assert updated.status == "failed"
        assert updated.completed_at is not None
        assert updated.completed_at.tzinfo == UTC
        assert updated.result_payload["trace_batch_record"]["summary_payload"] == {
            "trace_count": 3,
            "error_code": "write_failed",
        }


def test_analysis_run_repository_legacy_write_path_round_trips_explicit_scope_columns() -> None:
    with _memory_session() as session:
        dataset = DatasetRepository(session).add(
            DatasetRecord(name="Analysis Legacy Scope", source_meta={}, parameters={})
        )
        session.flush()
        assert dataset.id is not None

        repo = AnalysisRunRepository(session)
        analysis_run = AnalysisRunRecord(
            dataset_id=dataset.id,
            design_id=dataset.id,
            analysis_id="fit_lc",
            analysis_label="Fit LC",
            run_id="run-1",
            status="completed",
            input_trace_ids=[7, 8],
            input_batch_ids=[9],
            input_scope="design",
            trace_mode_group="all",
            config_payload={"method": "fit"},
            summary_payload={"quality": "ok"},
        )
        analysis_run.design_id = None

        persisted = repo.add(analysis_run)
        session.commit()

        assert persisted.id is not None
        assert persisted.dataset_id == dataset.id
        assert persisted.design_id == dataset.id

        raw_batch = session.get(ResultBundleRecord, persisted.id)
        assert raw_batch is not None
        assert raw_batch.dataset_id == dataset.id
        assert raw_batch.design_id == dataset.id


def test_data_record_repository_index_page_filters_and_sorts() -> None:
    with _memory_session() as session:
        dataset = DatasetRepository(session).add(
            DatasetRecord(name="Dataset A", source_meta={}, parameters={})
        )
        session.flush()
        assert dataset.id is not None

        data_repo = DataRecordRepository(session)
        data_repo.add(
            DataRecord(
                dataset_id=dataset.id,
                data_type="s_params",
                parameter="S11",
                representation="real",
                axes=[],
                values=[],
            )
        )
        data_repo.add(
            DataRecord(
                dataset_id=dataset.id,
                data_type="s_params",
                parameter="S21",
                representation="imaginary",
                axes=[],
                values=[],
            )
        )
        data_repo.add(
            DataRecord(
                dataset_id=dataset.id,
                data_type="y_params",
                parameter="Y11",
                representation="imaginary",
                axes=[],
                values=[],
            )
        )
        session.commit()

        page_rows, total = data_repo.list_index_page_by_dataset(
            dataset.id,
            search="s",
            sort_by="parameter",
            descending=False,
            data_type="s_params",
            limit=1,
            offset=0,
        )
        assert total == 2
        assert len(page_rows) == 1
        assert page_rows[0]["parameter"] == "S11"

        page_rows_2, total_2 = data_repo.list_index_page_by_dataset(
            dataset.id,
            search="s",
            sort_by="parameter",
            descending=False,
            data_type="s_params",
            limit=1,
            offset=1,
        )
        assert total_2 == 2
        assert len(page_rows_2) == 1
        assert page_rows_2[0]["parameter"] == "S21"


def test_data_record_repository_characterization_contract_methods() -> None:
    with _memory_session() as session:
        dataset = DatasetRepository(session).add(
            DatasetRecord(name="Char Source", source_meta={}, parameters={})
        )
        session.flush()
        assert dataset.id is not None

        data_repo = DataRecordRepository(session)
        base = data_repo.add(
            DataRecord(
                dataset_id=dataset.id,
                data_type="y_parameters",
                parameter="Y11",
                representation="imaginary",
                axes=[],
                values=[],
            )
        )
        sideband = data_repo.add(
            DataRecord(
                dataset_id=dataset.id,
                data_type="y_parameters",
                parameter="Y11 [om=(1,), im=(0,)]",
                representation="imaginary",
                axes=[],
                values=[],
            )
        )
        zero_mode = data_repo.add(
            DataRecord(
                dataset_id=dataset.id,
                data_type="y_parameters",
                parameter="Y11 [om=(0,), im=(0,)]",
                representation="imaginary",
                axes=[],
                values=[],
            )
        )
        data_repo.add(
            DataRecord(
                dataset_id=dataset.id,
                data_type="s_parameters",
                parameter="S21",
                representation="real",
                axes=[],
                values=[],
            )
        )
        session.commit()

        assert data_repo.count_by_dataset(dataset.id) == 4
        distinct = data_repo.list_distinct_index_for_profile(dataset.id)
        assert any(
            row["family"] == "y_parameters" and row["parameter"] == "Y11" for row in distinct
        )

        base_rows, base_total = data_repo.list_index_page_by_dataset(
            dataset.id,
            data_types=["y_parameters"],
            parameters=["Y11"],
            representation="imaginary",
            mode_filter="base",
            sort_by="mode",
            limit=20,
            offset=0,
        )
        assert base_total == 2
        assert [int(row["id"]) for row in base_rows] == [int(base.id or 0), int(zero_mode.id or 0)]

        sideband_rows, sideband_total = data_repo.list_index_page_by_dataset(
            dataset.id,
            data_types=["y_parameters"],
            parameters=["Y11"],
            representation="imaginary",
            mode_filter="sideband",
            ids=[int(base.id or 0), int(sideband.id or 0), int(zero_mode.id or 0)],
            sort_by="mode",
            limit=20,
            offset=0,
        )
        assert sideband_total == 1
        assert [int(row["id"]) for row in sideband_rows] == [int(sideband.id or 0)]

        query_rows, query_total = data_repo.list_index_page_by_dataset(
            dataset.id,
            query=TraceIndexPageQuery(
                data_types=("y_parameters",),
                parameters=("Y11",),
                representation="imaginary",
                mode_filter="sideband",
                ids=(int(base.id or 0), int(sideband.id or 0), int(zero_mode.id or 0)),
                sort_by="mode",
                limit=20,
                offset=0,
            ),
        )
        assert query_total == 1
        assert [int(row["id"]) for row in query_rows] == [int(sideband.id or 0)]


def test_result_bundle_repository_characterization_contract_methods() -> None:
    with _memory_session() as session:
        dataset = DatasetRepository(session).add(
            DatasetRecord(name="Bundle Source", source_meta={}, parameters={})
        )
        session.flush()
        assert dataset.id is not None

        data_repo = DataRecordRepository(session)
        bundle_repo = ResultBundleRepository(session)
        base = data_repo.add(
            DataRecord(
                dataset_id=dataset.id,
                data_type="y_parameters",
                parameter="Y11",
                representation="imaginary",
                axes=[],
                values=[],
            )
        )
        sideband = data_repo.add(
            DataRecord(
                dataset_id=dataset.id,
                data_type="y_parameters",
                parameter="Y11 [om=(1,), im=(0,)]",
                representation="imaginary",
                axes=[],
                values=[],
            )
        )
        zero_mode = data_repo.add(
            DataRecord(
                dataset_id=dataset.id,
                data_type="y_parameters",
                parameter="Y11 [om=(0,), im=(0,)]",
                representation="imaginary",
                axes=[],
                values=[],
            )
        )
        bundle = bundle_repo.add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="characterization",
                role="analysis_run",
                status="completed",
                source_meta={},
                config_snapshot={},
                result_payload={},
            )
        )
        session.flush()
        assert bundle.id is not None
        bundle_repo.attach_data_records(
            bundle_id=bundle.id,
            data_record_ids=[int(base.id or 0), int(sideband.id or 0), int(zero_mode.id or 0)],
        )
        session.commit()

        assert bundle_repo.count_data_records(bundle.id) == 3
        base_rows, base_total = bundle_repo.list_data_record_index_page(
            bundle.id,
            data_types=["y_parameters"],
            parameters=["Y11"],
            representation="imaginary",
            mode_filter="base",
            sort_by="mode",
            limit=20,
            offset=0,
        )
        assert base_total == 2
        assert [int(row["id"]) for row in base_rows] == [int(base.id or 0), int(zero_mode.id or 0)]
        rows, total = bundle_repo.list_data_record_index_page(
            bundle.id,
            data_types=["y_parameters"],
            parameters=["Y11"],
            representation="imaginary",
            mode_filter="sideband",
            sort_by="mode",
            limit=20,
            offset=0,
        )
        assert total == 1
        assert [int(row["id"]) for row in rows] == [int(sideband.id or 0)]

        query_rows, query_total = bundle_repo.list_data_record_index_page(
            bundle.id,
            query=TraceIndexPageQuery(
                data_types=("y_parameters",),
                parameters=("Y11",),
                representation="imaginary",
                mode_filter="sideband",
                sort_by="mode",
                limit=20,
                offset=0,
            ),
        )
        assert query_total == 1
        assert [int(row["id"]) for row in query_rows] == [int(sideband.id or 0)]


def test_result_bundle_repository_exposes_cache_and_provenance_queries() -> None:
    with _memory_session() as session:
        dataset = DatasetRepository(session).add(
            DatasetRecord(name="Bundle Semantics", source_meta={}, parameters={})
        )
        session.flush()
        assert dataset.id is not None

        bundle_repo = ResultBundleRepository(session)
        bundle_repo.add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="circuit_simulation",
                role="cache",
                status="completed",
                source_meta={},
                config_snapshot={},
                result_payload={},
            )
        )
        bundle_repo.add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="circuit_simulation",
                role="manual_export",
                status="completed",
                source_meta={},
                config_snapshot={},
                result_payload={},
            )
        )
        bundle_repo.add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="characterization",
                role="analysis_run",
                status="completed",
                source_meta={},
                config_snapshot={},
                result_payload={},
            )
        )
        session.commit()

        all_rows = bundle_repo.list_by_dataset(dataset.id)
        cache_rows = bundle_repo.list_cache_by_dataset(dataset.id)
        provenance_rows = bundle_repo.list_provenance_by_dataset(dataset.id)

        assert len(all_rows) == 3
        assert len(cache_rows) == 1
        assert cache_rows[0].role == "cache"
        assert len(provenance_rows) == 2
        assert all(row.role != "cache" for row in provenance_rows)
        assert bundle_repo.count_by_dataset(dataset.id) == 3
        assert bundle_repo.count_by_dataset(dataset.id, include_cache=False) == 2
        assert (
            bundle_repo.count_by_dataset(
                dataset.id,
                bundle_type="characterization",
                role="analysis_run",
            )
            == 1
        )


def test_result_bundle_repository_lists_primitive_analysis_run_summaries() -> None:
    with _memory_session() as session:
        dataset = DatasetRepository(session).add(
            DatasetRecord(name="Analysis Summary Dataset", source_meta={}, parameters={})
        )
        session.flush()
        assert dataset.id is not None

        bundle_repo = ResultBundleRepository(session)
        bundle_repo.add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="characterization",
                role="analysis_run",
                status="completed",
                source_meta={
                    "analysis_id": "squid_fitting",
                    "analysis_label": "SQUID Fitting",
                },
                config_snapshot={},
                result_payload={},
            )
        )
        bundle_repo.add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="characterization",
                role="analysis_run",
                status="failed",
                source_meta={
                    "analysis_id": "y11_fit",
                    "analysis_label": "Y11 Response Fit",
                },
                config_snapshot={},
                result_payload={},
            )
        )
        bundle_repo.add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="characterization",
                role="analysis_run",
                status="completed",
                source_meta={},
                config_snapshot={},
                result_payload={},
            )
        )
        session.commit()

        summaries = bundle_repo.list_analysis_run_summaries_by_dataset(dataset.id)

        assert summaries == [
            {
                "bundle_id": 1,
                "dataset_id": dataset.id,
                "design_id": dataset.id,
                "analysis_id": "squid_fitting",
                "analysis_label": "SQUID Fitting",
                "status": "completed",
            },
            {
                "bundle_id": 2,
                "dataset_id": dataset.id,
                "design_id": dataset.id,
                "analysis_id": "y11_fit",
                "analysis_label": "Y11 Response Fit",
                "status": "failed",
            },
        ]


def test_result_bundle_repository_analysis_runs_round_trip_via_logical_contract() -> None:
    with _memory_session() as session:
        design = DesignRepository(session).add(
            DesignRecord(name="Analysis Run Design", source_meta={}, parameters={})
        )
        session.flush()
        assert design.id is not None

        bundle_repo = ResultBundleRepository(session)
        persisted = bundle_repo.analysis_runs.add(
            AnalysisRunRecord(
                dataset_id=design.id,
                design_id=design.id,
                analysis_id="squid_fitting",
                analysis_label="SQUID Fitting",
                run_id="run-123",
                status="completed",
                input_trace_ids=[11, 12],
                input_batch_ids=[7],
                input_scope="all_dataset_records",
                trace_mode_group="base",
                config_payload={"model": "lc", "max_iter": 50},
                summary_payload={"selected_trace_count": 2},
            )
        )
        session.commit()

        assert persisted.id is not None

        stored_batch = bundle_repo.get(persisted.id)
        assert stored_batch is not None
        assert stored_batch.bundle_type == "characterization"
        assert stored_batch.role == "analysis_run"
        assert stored_batch.parent_batch_id is None
        assert stored_batch.source_meta["input_trace_ids"] == [11, 12]
        assert stored_batch.source_meta["input_batch_ids"] == [7]
        assert stored_batch.config_snapshot == {"model": "lc", "max_iter": 50}
        assert stored_batch.result_payload == {"selected_trace_count": 2}

        loaded = bundle_repo.analysis_runs.get(persisted.id)
        assert loaded is not None
        assert loaded.dataset_id == design.id
        assert loaded.design_id == design.id
        assert loaded.analysis_id == "squid_fitting"
        assert loaded.analysis_label == "SQUID Fitting"
        assert loaded.run_id == "run-123"
        assert loaded.input_trace_ids == [11, 12]
        assert loaded.input_batch_ids == [7]
        assert loaded.input_scope == "all_dataset_records"
        assert loaded.trace_mode_group == "base"
        assert loaded.config_payload == {"model": "lc", "max_iter": 50}
        assert loaded.summary_payload == {"selected_trace_count": 2}

        summaries = bundle_repo.analysis_runs.list_summaries_by_design(design.id)
        assert summaries == [
            {
                "analysis_run_id": int(persisted.id),
                "dataset_id": design.id,
                "design_id": design.id,
                "analysis_id": "squid_fitting",
                "analysis_label": "SQUID Fitting",
                "status": "completed",
            }
        ]


def test_result_bundle_repository_analysis_runs_read_legacy_execution_payloads() -> None:
    with _memory_session() as session:
        dataset = DatasetRepository(session).add(
            DatasetRecord(name="Legacy Analysis Run Dataset", source_meta={}, parameters={})
        )
        session.flush()
        assert dataset.id is not None

        bundle_repo = ResultBundleRepository(session)
        bundle_repo.add(
            ResultBundleRecord(
                dataset_id=dataset.id,
                bundle_type="characterization",
                role="analysis_run",
                status="completed",
                source_meta={
                    "analysis_id": "y11_fit",
                    "analysis_label": "Y11 Fit",
                    "run_id": "legacy-run",
                    "input_bundle_id": 5,
                    "input_scope": "all_dataset_records",
                },
                config_snapshot={
                    "selected_trace_ids": [101, 102],
                    "selected_trace_mode_group": "sideband",
                    "selected_trace_count": 2,
                    "fit_window": 4.2,
                },
                result_payload={},
            )
        )
        session.commit()

        loaded = bundle_repo.analysis_runs.get(1)
        assert loaded is not None
        assert loaded.analysis_id == "y11_fit"
        assert loaded.run_id == "legacy-run"
        assert loaded.input_batch_ids == [5]
        assert loaded.input_trace_ids == [101, 102]
        assert loaded.input_scope == "all_dataset_records"
        assert loaded.trace_mode_group == "sideband"
        assert loaded.config_payload == {"fit_window": 4.2}
        assert loaded.summary_payload == {"selected_trace_count": 2}


def test_circuit_repository_summary_page_supports_search_and_sort() -> None:
    with _memory_session() as session:
        circuit_repo = CircuitRepository(session)
        circuit_repo.add(CircuitRecord(name="Gamma", definition_json="{}"))
        circuit_repo.add(CircuitRecord(name="Alpha", definition_json="{}"))
        circuit_repo.add(CircuitRecord(name="Beta", definition_json="{}"))
        session.commit()

        page_rows, total = circuit_repo.list_summary_page(
            search="a",
            sort_by="name",
            descending=False,
            limit=2,
            offset=0,
        )
        assert total == 3
        assert [row["name"] for row in page_rows] == ["Alpha", "Beta"]


def test_design_trace_batch_repository_exposes_canonical_snapshot_and_lineage() -> None:
    with _memory_session() as session:
        design = DesignRepository(session).add(
            DesignRecord(name="Canonical Batch Design", source_meta={}, parameters={})
        )
        session.flush()
        assert design.id is not None

        batch_repo = TraceBatchRepository(session)
        parent = batch_repo.add(
            TraceBatchRecord(
                dataset_id=design.id,
                bundle_type="circuit_simulation",
                role="cache",
                status="completed",
                source_meta={"source_kind": "circuit_simulation", "stage_kind": "raw"},
                config_snapshot={"setup_version": "1.0"},
                result_payload={"trace_count": 2},
            )
        )
        session.flush()
        assert parent.id is not None

        child = batch_repo.add(
            TraceBatchRecord(
                dataset_id=design.id,
                parent_batch_id=parent.id,
                bundle_type="simulation_postprocess",
                role="derived_from_simulation",
                status="completed",
                source_meta={"source_kind": "circuit_simulation", "stage_kind": "postprocess"},
                config_snapshot={"setup_kind": "circuit_simulation.postprocess"},
                result_payload={"trace_count": 1},
            )
        )
        session.commit()
        assert child.id is not None

        snapshot = batch_repo.get_trace_batch_snapshot(child.id)
        assert snapshot is not None
        assert snapshot["dataset_id"] == design.id
        assert snapshot["design_id"] == design.id
        assert snapshot["parent_batch_id"] == parent.id
        assert snapshot["source_kind"] == "circuit_simulation"
        assert snapshot["stage_kind"] == "postprocess"
        assert snapshot["setup_kind"] == "circuit_simulation.postprocess"

        children = batch_repo.list_child_batches(parent.id)
        assert [row.id for row in children] == [child.id]


def test_trace_repository_returns_canonical_trace_index_rows() -> None:
    with _memory_session() as session:
        design = DesignRepository(session).add(
            DesignRecord(name="Canonical Trace Design", source_meta={}, parameters={})
        )
        session.flush()
        assert design.id is not None

        trace_repo = TraceRepository(session)
        trace_repo.add(
            TraceRecord(
                dataset_id=design.id,
                data_type="y_parameters",
                parameter="Y11",
                representation="imaginary",
                axes=[],
                values=[],
            )
        )
        session.commit()

        rows, total = trace_repo.list_index_page_by_design(design.id)
        assert total == 1
        assert rows == [
            {
                "id": 1,
                "family": "y_parameters",
                "parameter": "Y11",
                "representation": "imaginary",
            }
        ]


def test_trace_repository_legacy_write_path_round_trips_explicit_scope_columns() -> None:
    with _memory_session() as session:
        design = DesignRepository(session).add(
            DesignRecord(name="Legacy Trace Write Design", source_meta={}, parameters={})
        )
        session.flush()
        assert design.id is not None

        trace_repo = TraceRepository(session)
        trace_repo.add(
            TraceRecord(
                dataset_id=design.id,
                data_type="y_parameters",
                parameter="Y21",
                representation="real",
                axes=[],
                values=[],
            )
        )
        session.commit()

        persisted = trace_repo.get(1)
        assert persisted is not None
        assert persisted.dataset_id == design.id
        assert persisted.design_id == design.id

        summary_rows = trace_repo.list_summary_by_design(design.id)
        assert summary_rows == [
            {
                "id": 1,
                "dataset_id": design.id,
                "design_id": design.id,
                "family": "y_parameters",
                "parameter": "Y21",
                "representation": "real",
                "created_at": None,
            }
        ]
