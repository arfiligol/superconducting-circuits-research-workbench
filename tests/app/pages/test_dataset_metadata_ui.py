"""Structural tests for dataset metadata UI entry points."""

from __future__ import annotations

import inspect
from datetime import datetime
from types import SimpleNamespace

import legacy.legacy_nicegui_archived.features.dashboard.page as dashboard_feature_page
import legacy.legacy_nicegui_archived.features.raw_data.page as raw_data_feature_page
import legacy.legacy_nicegui_archived.features.simulation.page as simulation_feature_page
from legacy.legacy_nicegui_archived.pages import dashboard, raw_data, simulation
from legacy.legacy_nicegui_archived.services.design_trace_workflow import summarize_design_trace_workflow


def test_dashboard_page_exposes_dataset_metadata_editor_controls() -> None:
    source = inspect.getsource(dashboard_feature_page)

    assert 'ui.label("Dataset Metadata")' in source
    assert 'label="Device Type"' in source
    assert 'label="Capabilities"' in source
    assert '"Auto Suggest"' in source
    assert '"Save Metadata"' in source


def test_raw_data_page_hides_dataset_metadata_editor_controls() -> None:
    source = inspect.getsource(raw_data_feature_page)

    assert 'ui.label("Design Summary")' in source
    assert 'f"Current Design Scope: {dataset.name}' in source
    assert 'ui.label("Trace Source Summary")' in source
    assert 'ui.label(f"Compare Readiness: {compare_status_label}")' in source
    assert '"Auto Suggest"' not in source
    assert '"Save Metadata"' not in source
    assert 'label="Device Type"' not in source
    assert 'label="Capabilities"' not in source


def test_simulation_page_hides_dataset_metadata_editor_controls() -> None:
    source = inspect.getsource(simulation_feature_page)

    assert 'ui.label("Dataset Metadata Summary")' in source
    assert 'label="Target Dataset"' in source
    assert "TraceStore-first authority is active for result inspection on this page." in source
    assert "Cross-source compare is inspect-only here and stays blocked" in source
    assert '"Auto Suggest"' not in source
    assert '"Save Metadata"' not in source
    assert 'label="Device Type"' not in source
    assert 'label="Capabilities"' not in source


class _FakeTraceRepo:
    def __init__(self, count: int) -> None:
        self._count = count

    def count_by_design(self, design_id: int) -> int:
        assert design_id == 42
        return self._count


class _FakeTraceBatchRepo:
    def __init__(
        self,
        *,
        batches: list[object],
        snapshots: dict[int, dict[str, object]],
        trace_rows: dict[int, list[dict[str, int | str]]],
    ) -> None:
        self._batches = batches
        self._snapshots = snapshots
        self._trace_rows = trace_rows

    def list_provenance_by_design(self, design_id: int) -> list[object]:
        assert design_id == 42
        return self._batches

    def get_trace_batch_snapshot(self, id: int) -> dict[str, object] | None:
        return self._snapshots.get(id)

    def list_data_record_index(self, bundle_id: int) -> list[dict[str, int | str]]:
        return list(self._trace_rows.get(bundle_id, ()))


def test_design_trace_workflow_summary_reports_ready_for_multi_source_design() -> None:
    summary = summarize_design_trace_workflow(
        design_id=42,
        design_name="Flux JPA",
        trace_repo=_FakeTraceRepo(count=3),
        trace_batch_repo=_FakeTraceBatchRepo(
            batches=[
                SimpleNamespace(id=11, completed_at=datetime(2026, 3, 8, 8, 0, 0)),
                SimpleNamespace(id=12, completed_at=datetime(2026, 3, 8, 9, 0, 0)),
            ],
            snapshots={
                11: {
                    "source_kind": "circuit_simulation",
                    "stage_kind": "raw",
                    "setup_kind": "circuit_simulation.raw",
                    "parent_batch_id": None,
                    "provenance_payload": {"run_kind": "single_run"},
                    "summary_payload": {"trace_count": 1},
                },
                12: {
                    "source_kind": "measurement",
                    "stage_kind": "raw",
                    "setup_kind": "measurement.raw",
                    "parent_batch_id": None,
                    "provenance_payload": {"run_kind": "single_run"},
                    "summary_payload": {"trace_count": 2},
                },
            },
            trace_rows={
                11: [
                    {
                        "id": 101,
                        "data_type": "y_params",
                        "parameter": "Y11",
                        "representation": "imaginary",
                    }
                ],
                12: [
                    {
                        "id": 201,
                        "data_type": "y_params",
                        "parameter": "Y11",
                        "representation": "imaginary",
                    },
                    {
                        "id": 202,
                        "data_type": "s_params",
                        "parameter": "S21",
                        "representation": "magnitude",
                    },
                ],
            },
        ),
    )

    assert summary.compare_status == "ready"
    assert summary.source_kind_count == 2
    assert len(summary.source_summaries) == 2
    assert summary.trace_membership_by_id[101][0].source_kind == "circuit_simulation"
    assert summary.trace_membership_by_id[201][0].source_kind == "measurement"


def test_design_trace_workflow_summary_reports_blocked_without_batches() -> None:
    summary = summarize_design_trace_workflow(
        design_id=42,
        design_name="Flux JPA",
        trace_repo=_FakeTraceRepo(count=0),
        trace_batch_repo=_FakeTraceBatchRepo(
            batches=[],
            snapshots={},
            trace_rows={},
        ),
    )

    assert summary.compare_status == "blocked"
    assert summary.source_summaries == ()
    assert "No persisted traces" in summary.compare_message
