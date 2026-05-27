from __future__ import annotations

from src.app.tooling.openapi_snapshot import (
    check_openapi_snapshot_drift,
    export_openapi_snapshot,
)


def test_export_openapi_snapshot_round_trips_without_drift(tmp_path) -> None:
    snapshot_path = tmp_path / "openapi.json"

    export_openapi_snapshot(snapshot_path)
    report = check_openapi_snapshot_drift(snapshot_path)

    assert report.is_current is True
    assert report.diff_preview == ()


def test_check_openapi_snapshot_drift_detects_stale_snapshot(tmp_path) -> None:
    snapshot_path = tmp_path / "openapi.json"
    export_openapi_snapshot(snapshot_path)
    snapshot_path.write_text('{"openapi":"3.1.0","paths":{}}', encoding="utf-8")

    report = check_openapi_snapshot_drift(snapshot_path)

    assert report.is_current is False
    assert len(report.diff_preview) > 0
