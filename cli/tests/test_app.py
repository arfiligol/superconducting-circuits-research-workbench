import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sc_cli.app import app
from sc_cli.commands import (
    characterization,
    datasets,
    events,
    ops,
    results,
    session,
    simulation,
    tasks,
)
from sc_cli.local_errors import build_contract_error
from sc_cli.local_runtime import LocalTaskDetail, LocalTaskSummary
from sc_cli.runtime import get_task as runtime_get_task
from sc_cli.runtime import list_tasks as runtime_list_tasks
from sc_cli.runtime import reset_runtime_state

PUBLISHED_ROOT_COMMANDS = (
    "core",
    "session",
    "datasets",
    "tasks",
    "ops",
    "events",
    "results",
    "characterization",
)

HIDDEN_COMPATIBILITY_COMMANDS = ("simulation", "circuit-definition")


@pytest.fixture(autouse=True)
def reset_cli_runtime() -> Iterator[None]:
    reset_runtime_state()
    yield
    reset_runtime_state()


def _list_runtime_tasks(
    *,
    status: str | None = None,
    lane: str | None = None,
    scope: str = "workspace",
    dataset_id: str | None = None,
    limit: int = 50,
) -> list[LocalTaskSummary]:
    return runtime_list_tasks(
        status=status,
        lane=lane,
        scope=scope,
        dataset_id=dataset_id,
        limit=limit,
    )


def _workspace_task_ids(*, limit: int = 20) -> list[int]:
    return [task.task_id for task in _list_runtime_tasks(limit=limit)]


def _owned_only_task_ids(*, limit: int = 20) -> list[int]:
    workspace_ids = set(_workspace_task_ids(limit=limit))
    return [
        task.task_id
        for task in _list_runtime_tasks(scope="owned", limit=limit)
        if task.task_id not in workspace_ids
    ]


def _task_detail(task_id: int) -> LocalTaskDetail:
    return runtime_get_task(task_id)


def _find_task_id(
    *,
    status: str | None = None,
    lane: str | None = None,
    scope: str = "workspace",
    require_result_handles: bool | None = None,
    require_trace_payload: bool | None = None,
) -> int:
    for task_summary in _list_runtime_tasks(status=status, lane=lane, scope=scope):
        task = _task_detail(task_summary.task_id)
        if require_result_handles is not None and (
            len(task.result_refs.result_handles) > 0
        ) is not require_result_handles:
            continue
        if require_trace_payload is not None and (
            task.result_refs.trace_payload is not None
        ) is not require_trace_payload:
            continue
        return task.task_id
    raise AssertionError(
        "No task matched the requested filters: "
        f"status={status!r}, lane={lane!r}, scope={scope!r}, "
        f"require_result_handles={require_result_handles!r}, "
        f"require_trace_payload={require_trace_payload!r}"
    )


def _running_simulation_task_id() -> int:
    return _find_task_id(status="running", lane="simulation")


def _completed_simulation_task_id() -> int:
    return _find_task_id(
        status="completed",
        lane="simulation",
        require_result_handles=True,
        require_trace_payload=True,
    )


def _queued_characterization_task_id() -> int:
    return _find_task_id(status="queued", lane="characterization")


def _task_without_trace_payload_id() -> int:
    return _find_task_id(require_trace_payload=False)


def _task_without_result_handles_id() -> int:
    return _find_task_id(
        status="running",
        lane="simulation",
        require_result_handles=False,
    )


def _canonical_definition_source(name: str) -> str:
    return "\n".join(
        [
            f"name: {name}",
            "components:",
            "  - name: R1",
            "    default: 50.0",
            "    unit: Ohm",
            "  - name: C1",
            "    default: 100.0",
            "    unit: fF",
            "  - name: Lj1",
            "    default: 1000.0",
            "    unit: pH",
            "  - name: C2",
            "    default: 1000.0",
            "    unit: fF",
            "topology:",
            '  - [P1, "1", "0", 1]',
            '  - [R1, "1", "0", "R1"]',
            '  - [C1, "1", "2", "C1"]',
            '  - [Lj1, "2", "0", "Lj1"]',
            '  - [C2, "2", "0", "C2"]',
        ]
    )


def test_root_help_aligns_with_published_cli_surface() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command_name in PUBLISHED_ROOT_COMMANDS:
        assert command_name in result.stdout
    for command_name in HIDDEN_COMPATIBILITY_COMMANDS:
        assert command_name not in result.stdout


def test_root_help_keeps_analysis_first_copy() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Standalone-first CLI for local datasets, analysis runs, results" in result.stdout
    assert "characterization" in result.stdout
    assert "analysis-first workflows across tasks" in result.stdout


def test_root_app_rejects_depublished_simulation_group() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["simulation", "--help"])

    assert result.exit_code == 2
    assert "No such command 'simulation'." in result.output


def test_group_help_copy_stays_analysis_first() -> None:
    runner = CliRunner()

    datasets_help = runner.invoke(app, ["datasets", "--help"])
    tasks_help = runner.invoke(app, ["tasks", "--help"])
    results_help = runner.invoke(app, ["results", "--help"])
    characterization_help = runner.invoke(app, ["characterization", "--help"])

    assert datasets_help.exit_code == 0
    assert tasks_help.exit_code == 0
    assert results_help.exit_code == 0
    assert characterization_help.exit_code == 0
    assert "lineage-preserving bundles" in datasets_help.stdout
    assert "analysis" in tasks_help.stdout
    assert "run registry" in tasks_help.stdout
    assert "result bundles" in results_help.stdout
    assert "analysis-lane workflows over local datasets" in characterization_help.stdout


def test_simulation_compatibility_help_is_not_primary_surface_copy() -> None:
    runner = CliRunner()

    result = runner.invoke(simulation.app, ["--help"])

    assert result.exit_code == 0
    assert "Compatibility wrapper for simulation-lane local runs." in result.stdout

def test_preview_artifacts_command_lists_sc_core_exports() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["core", "preview-artifacts"])

    assert result.exit_code == 0
    assert "sc_core preview artifacts:" in result.stdout
    assert "definition.normalized.json" in result.stdout
    assert "parameter-bundle.toml" in result.stdout


def test_circuit_definition_inspect_command_delegates_to_sc_core(tmp_path: Path) -> None:
    source_file = tmp_path / "demo.circuit.yaml"
    source_file.write_text(
        "\n".join(
            [
                "name: fluxonium_demo",
                "family: fluxonium",
                "junction_1: JJ",
                "capacitor_1: C",
                "inductor_1: L",
            ]
        ),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(app, ["circuit-definition", "inspect", str(source_file)])

    assert result.exit_code == 0
    assert f"source_file: {source_file.resolve()}" in result.stdout
    assert "circuit_name: fluxonium_demo" in result.stdout
    assert "family: fluxonium" in result.stdout
    assert '"schemdraw_ready": true' in result.stdout
    assert "Port mapping metadata still needs migration from legacy forms." in result.stdout


def test_circuit_definition_inspect_command_supports_definition_id() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["circuit-definition", "inspect", "--definition-id", "18"])

    assert result.exit_code == 0
    assert "source_definition_id: 18" in result.stdout
    assert "definition_name: FloatingQubitWithXYLine" in result.stdout
    assert "validation_status: warning" in result.stdout


def test_circuit_definition_list_command_reads_rewrite_state() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["circuit-definition", "list"])

    assert result.exit_code == 0
    assert "circuit_definitions: 3" in result.stdout
    assert "#18" in result.stdout
    assert "FloatingQubitWithXYLine" in result.stdout


def test_circuit_definition_list_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["circuit-definition", "list", "--output", "json"])

    assert result.exit_code == 0
    assert '"definition_id": 18' in result.stdout
    assert '"name": "FloatingQubitWithXYLine"' in result.stdout


def test_circuit_definition_inspect_command_supports_json_output(tmp_path: Path) -> None:
    source_file = tmp_path / "demo-json.circuit.yaml"
    source_file.write_text(
        "\n".join(
            [
                "name: fluxonium_demo_json",
                "family: fluxonium",
                "junction_1: JJ",
                "capacitor_1: C",
            ]
        ),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        app, ["circuit-definition", "inspect", str(source_file), "--output", "json"]
    )

    assert result.exit_code == 0
    assert f'"source_file": "{source_file.resolve()}"' in result.stdout
    assert '"circuit_name": "fluxonium_demo_json"' in result.stdout


def test_circuit_definition_create_command_persists_local_source(tmp_path: Path) -> None:
    source_file = tmp_path / "created.circuit.yaml"
    source_file.write_text(
        _canonical_definition_source("FluxoniumCliCreate"),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "circuit-definition",
            "create",
            str(source_file),
            "--name",
            "FluxoniumCliCreate",
        ],
    )

    assert result.exit_code == 0
    assert "source_definition_id: 19" in result.stdout
    assert "definition_name: FluxoniumCliCreate" in result.stdout
    assert "validation_status: warning" in result.stdout


def test_circuit_definition_create_command_supports_json_output(tmp_path: Path) -> None:
    source_file = tmp_path / "created-json.circuit.yaml"
    source_file.write_text(
        _canonical_definition_source("TransmonCliCreate"),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "circuit-definition",
            "create",
            str(source_file),
            "--name",
            "TransmonCliCreate",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"definition_id": 19' in result.stdout
    assert '"name": "TransmonCliCreate"' in result.stdout
    assert '"validation_status": "warning"' in result.stdout


def test_circuit_definition_create_command_uses_structured_validation_error(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "blank.circuit.yaml"
    source_file.write_text("   \n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "circuit-definition",
            "create",
            str(source_file),
            "--name",
            "BlankDefinition",
        ],
    )

    assert result.exit_code == 2
    assert (
        "error: Request validation failed. [validation/request_validation_failed]" in result.output
    )
    assert "field_error: source_text:" in result.output


def test_circuit_definition_update_command_updates_existing_definition(tmp_path: Path) -> None:
    source_file = tmp_path / "updated.circuit.yaml"
    source_file.write_text(
        _canonical_definition_source("FloatingQubitCliUpdate"),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "circuit-definition",
            "update",
            "18",
            str(source_file),
            "--name",
            "FloatingQubitCliUpdate",
        ],
    )

    assert result.exit_code == 0
    assert "source_definition_id: 18" in result.stdout
    assert "definition_name: FloatingQubitCliUpdate" in result.stdout
    assert "validation_status: warning" in result.stdout


def test_circuit_definition_update_command_supports_json_output(tmp_path: Path) -> None:
    source_file = tmp_path / "updated-json.circuit.yaml"
    source_file.write_text(
        _canonical_definition_source("ReadoutChainCliUpdate"),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "circuit-definition",
            "update",
            "12",
            str(source_file),
            "--name",
            "ReadoutChainCliUpdate",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"definition_id": 12' in result.stdout
    assert '"name": "ReadoutChainCliUpdate"' in result.stdout
    assert '"validation_status": "warning"' in result.stdout


def test_circuit_definition_delete_command_deletes_definition() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["circuit-definition", "delete", "7", "--yes"])

    assert result.exit_code == 0
    assert "operation: deleted" in result.stdout
    assert "definition_id: 7" in result.stdout


def test_circuit_definition_delete_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["circuit-definition", "delete", "7", "--yes", "--output", "json"])

    assert result.exit_code == 0
    assert '"operation": "deleted"' in result.stdout
    assert '"definition_id": 7' in result.stdout


def test_circuit_definition_delete_command_requires_confirmation() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["circuit-definition", "delete", "7"])

    assert result.exit_code == 2
    assert "error: Pass --yes to delete a persisted local circuit definition." in result.output


def test_circuit_definition_export_bundle_command_writes_lineage_preserving_bundle(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    bundle_file = tmp_path / "definition-bundle.json"

    result = runner.invoke(
        app,
        [
            "circuit-definition",
            "export-bundle",
            "18",
            str(bundle_file),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert bundle_file.exists()
    stdout_payload = json.loads(result.stdout)
    bundle_payload = json.loads(bundle_file.read_text(encoding="utf-8"))
    assert stdout_payload["bundle_file"] == str(bundle_file)
    assert bundle_payload["metadata"]["bundle_family"] == "definition_bundle"
    assert bundle_payload["definition"]["definition_id"] == 18
    assert bundle_payload["definition"]["source_text"].startswith("name:")
    assert bundle_payload["definition"]["validation_summary"]["status"] == "warning"
    assert bundle_payload["definition"]["preview_artifact_count"] == 3


def test_circuit_definition_import_bundle_command_round_trips_into_local_catalog(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    bundle_file = tmp_path / "definition-roundtrip.json"

    export_result = runner.invoke(
        app,
        ["circuit-definition", "export-bundle", "18", str(bundle_file)],
    )
    assert export_result.exit_code == 0

    import_result = runner.invoke(
        app,
        ["circuit-definition", "import-bundle", str(bundle_file), "--output", "json"],
    )

    assert import_result.exit_code == 0
    import_payload = json.loads(import_result.stdout)
    expected_bundle_id = "bundle:definition:18"
    imported_definition_id = import_payload["imported_definition"]["definition_id"]
    assert import_payload["bundle"]["metadata"]["bundle_id"] == expected_bundle_id
    assert imported_definition_id > 18
    assert (
        import_payload["imported_definition"]["lineage"]["source_definition_id"] == 18
    )
    assert (
        import_payload["imported_definition"]["lineage"]["imported_from_bundle_id"]
        == expected_bundle_id
    )

    show_result = runner.invoke(
        app,
        [
            "circuit-definition",
            "inspect",
            "--definition-id",
            str(imported_definition_id),
            "--output",
            "json",
        ],
    )

    assert show_result.exit_code == 0
    assert f'"definition_id": {imported_definition_id}' in show_result.stdout
    assert f'"imported_from_bundle_id": "{expected_bundle_id}"' in show_result.stdout


def test_session_show_command_reads_rewrite_session_state() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["session", "show"])

    assert result.exit_code == 0
    assert "session_id: rewrite-local-session" in result.stdout
    assert "workspace_id: ws-device-lab" in result.stdout
    assert "default_task_scope: workspace" in result.stdout


def test_session_show_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["session", "show", "--output", "json"])

    assert result.exit_code == 0
    assert '"session_id": "rewrite-local-session"' in result.stdout
    assert '"workspace_id": "ws-device-lab"' in result.stdout


def test_session_whoami_command_reads_identity_context() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["session", "whoami"])

    assert result.exit_code == 0
    assert "identity_user_id: researcher-01" in result.stdout
    assert "identity_display_name: Rewrite Local User" in result.stdout
    assert "can_submit_tasks: true" in result.stdout


def test_session_whoami_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["session", "whoami", "--output", "json"])

    assert result.exit_code == 0
    assert '"session_id": "rewrite-local-session"' in result.stdout
    assert '"user_id": "researcher-01"' in result.stdout
    assert '"can_manage_datasets": true' in result.stdout


def test_session_workspace_command_reads_workspace_context() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["session", "workspace"])

    assert result.exit_code == 0
    assert "workspace_id: ws-device-lab" in result.stdout
    assert "workspace_display_name: Device Lab Workspace" in result.stdout
    assert "active_dataset_id: fluxonium-2025-031" in result.stdout


def test_session_workspace_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["session", "workspace", "--output", "json"])

    assert result.exit_code == 0
    assert '"workspace_id": "ws-device-lab"' in result.stdout
    assert '"default_task_scope": "workspace"' in result.stdout
    assert '"active_dataset": {' in result.stdout


def test_session_active_dataset_command_reads_active_dataset_context() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["session", "active-dataset"])

    assert result.exit_code == 0
    assert "active_dataset_id: fluxonium-2025-031" in result.stdout
    assert "active_dataset_name: Fluxonium sweep 031" in result.stdout


def test_session_active_dataset_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["session", "active-dataset", "--output", "json"])

    assert result.exit_code == 0
    assert '"active_dataset": {' in result.stdout
    assert '"dataset_id": "fluxonium-2025-031"' in result.stdout


def test_session_set_active_dataset_command_updates_session_state() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["session", "set-active-dataset", "transmon-coupler-014"],
    )

    assert result.exit_code == 0
    assert "active_dataset_id: transmon-coupler-014" in result.stdout
    assert "active_dataset_name: Coupler detuning 014" in result.stdout


def test_session_set_active_dataset_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["session", "set-active-dataset", "transmon-coupler-014", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"dataset_id": "transmon-coupler-014"' in result.stdout
    assert '"name": "Coupler detuning 014"' in result.stdout


def test_session_set_active_dataset_command_supports_clearing_context() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["session", "set-active-dataset", "--clear"])

    assert result.exit_code == 0
    assert "active_dataset: none" in result.stdout


def test_session_active_dataset_command_reports_cleared_context() -> None:
    runner = CliRunner()

    clear_result = runner.invoke(app, ["session", "set-active-dataset", "--clear"])
    result = runner.invoke(app, ["session", "active-dataset"])

    assert clear_result.exit_code == 0
    assert result.exit_code == 0
    assert "active_dataset: none" in result.stdout


def test_datasets_list_command_reads_rewrite_dataset_state() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["datasets", "list"])

    assert result.exit_code == 0
    assert "datasets: 2" in result.stdout
    assert "fluxonium-2025-031" in result.stdout
    assert "transmon-coupler-014" in result.stdout


def test_datasets_list_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["datasets", "list", "--output", "json"])

    assert result.exit_code == 0
    assert '"dataset_id": "fluxonium-2025-031"' in result.stdout
    assert '"dataset_id": "transmon-coupler-014"' in result.stdout


def test_datasets_show_command_reads_one_dataset() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["datasets", "show", "fluxonium-2025-031"])

    assert result.exit_code == 0
    assert "dataset_id: fluxonium-2025-031" in result.stdout
    assert "name: Fluxonium sweep 031" in result.stdout
    assert "storage_metadata_record_id: dataset:fluxonium-2025-031" in result.stdout


def test_datasets_show_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["datasets", "show", "transmon-coupler-014", "--output", "json"])

    assert result.exit_code == 0
    assert '"dataset_id": "transmon-coupler-014"' in result.stdout
    assert '"device_type": "Transmon"' in result.stdout
    assert '"storage": {' in result.stdout


def test_datasets_set_metadata_command_updates_dataset_metadata() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "datasets",
            "set-metadata",
            "fluxonium-2025-031",
            "--device-type",
            "Fluxonium",
            "--source",
            "measured",
            "--capability",
            "sweep-ready",
            "--capability",
            "fit-ready",
        ],
    )

    assert result.exit_code == 0
    assert "updated_fields: device_type, capabilities, source" in result.stdout
    assert "device_type: Fluxonium" in result.stdout
    assert "source: measured" in result.stdout
    assert "- sweep-ready" in result.stdout
    assert "- fit-ready" in result.stdout


def test_datasets_set_metadata_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "datasets",
            "set-metadata",
            "transmon-coupler-014",
            "--device-type",
            "Transmon",
            "--source",
            "simulated",
            "--capability",
            "cross-resonance",
            "--capability",
            "detuning-scan",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"updated_fields": [' in result.stdout
    assert '"source": "simulated"' in result.stdout
    assert '"capabilities": [' in result.stdout
    assert '"detuning-scan"' in result.stdout


def test_datasets_set_metadata_command_uses_structured_validation_error() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "datasets",
            "set-metadata",
            "fluxonium-2025-031",
            "--device-type",
            "Fluxonium",
            "--source",
            "measured",
            "--capability",
            "duplicate-capability",
            "--capability",
            "duplicate-capability",
        ],
    )

    assert result.exit_code == 2
    assert (
        "error: Request validation failed. [validation/request_validation_failed]" in result.output
    )
    assert "field_error: capabilities:" in result.output


def test_datasets_export_bundle_command_supports_json_output(tmp_path: Path) -> None:
    runner = CliRunner()
    bundle_file = tmp_path / "dataset.bundle.json"

    result = runner.invoke(
        app,
        [
            "datasets",
            "export-bundle",
            "fluxonium-2025-031",
            str(bundle_file),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["bundle"]["metadata"]["bundle_family"] == "dataset_bundle"
    assert payload["bundle"]["dataset"]["dataset_id"] == "fluxonium-2025-031"
    assert payload["bundle"]["dataset"]["trace_manifest"][0]["trace_batch_id"] == "trace-batch:88"
    assert bundle_file.exists()


def test_datasets_export_bundle_text_receipt_mentions_lineage(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    bundle_file = tmp_path / "dataset.bundle.json"

    result = runner.invoke(
        app,
        ["datasets", "export-bundle", "fluxonium-2025-031", str(bundle_file)],
    )

    assert result.exit_code == 0
    assert "interchange_scope: local_app_bundle" in result.stdout
    assert "lineage_preserved: true" in result.stdout
    assert "trace_manifest_count: 1" in result.stdout


def test_datasets_import_bundle_command_preserves_lineage(tmp_path: Path) -> None:
    runner = CliRunner()
    bundle_file = tmp_path / "dataset.bundle.json"

    export_result = runner.invoke(
        app,
        [
            "datasets",
            "export-bundle",
            "transmon-coupler-014",
            str(bundle_file),
        ],
    )
    import_result = runner.invoke(
        app,
        [
            "datasets",
            "import-bundle",
            str(bundle_file),
            "--output",
            "json",
        ],
    )

    assert export_result.exit_code == 0
    assert import_result.exit_code == 0
    payload = json.loads(import_result.stdout)
    imported_dataset = payload["imported_dataset"]
    assert imported_dataset["dataset_id"].startswith("imported-dataset-")
    assert imported_dataset["lineage"]["source_dataset_id"] == "transmon-coupler-014"
    assert (
        imported_dataset["lineage"]["imported_from_bundle_id"]
        == payload["bundle"]["metadata"]["bundle_id"]
    )


def test_tasks_list_command_reads_rewrite_task_state() -> None:
    runner = CliRunner()
    workspace_task_ids = _workspace_task_ids(limit=20)
    owned_only_task_ids = _owned_only_task_ids(limit=20)

    result = runner.invoke(app, ["tasks", "list"])

    assert result.exit_code == 0
    assert f"tasks: {len(workspace_task_ids)}" in result.stdout
    for task_id in workspace_task_ids:
        assert f"#{task_id}" in result.stdout
    for task_id in owned_only_task_ids:
        assert f"#{task_id}" not in result.stdout


def test_tasks_list_command_supports_json_output() -> None:
    runner = CliRunner()
    workspace_task_ids = _workspace_task_ids(limit=20)
    owned_only_task_ids = _owned_only_task_ids(limit=20)

    result = runner.invoke(app, ["tasks", "list", "--output", "json"])

    assert result.exit_code == 0
    for task_id in workspace_task_ids:
        assert f'"task_id": {task_id}' in result.stdout
    for task_id in owned_only_task_ids:
        assert f'"task_id": {task_id}' not in result.stdout


def test_tasks_show_command_reads_one_task() -> None:
    runner = CliRunner()
    task_id = _running_simulation_task_id()

    result = runner.invoke(app, ["tasks", "show", str(task_id)])

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "lane: simulation" in result.stdout
    assert "execution_mode: run" in result.stdout
    assert "worker_task_name: simulation_run_task" in result.stdout
    assert "request_ready: true" in result.stdout


def test_tasks_show_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _running_simulation_task_id()

    result = runner.invoke(app, ["tasks", "show", str(task_id), "--output", "json"])

    assert result.exit_code == 0
    assert f'"task_id": {task_id}' in result.stdout
    assert '"metadata_records": []' in result.stdout
    assert '"result_handles": []' in result.stdout
    assert '"events": [' in result.stdout


def test_tasks_inspect_command_groups_operator_view() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["tasks", "inspect", str(task_id)])

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "inspection:" in result.stdout
    assert "event_count: 2" in result.stdout
    assert "latest_event_type: task_completed" in result.stdout
    assert "result_handle_count: 2" in result.stdout


def test_tasks_inspect_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["tasks", "inspect", str(task_id), "--output", "json"])

    assert result.exit_code == 0
    assert '"task": {' in result.stdout
    assert '"inspection": {' in result.stdout
    assert '"event_count": 2' in result.stdout


def test_tasks_latest_command_reads_latest_matching_task() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(
        app,
        ["tasks", "latest", "--lane", "simulation", "--status", "completed"],
    )

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "lane: simulation" in result.stdout
    assert "status: completed" in result.stdout


def test_tasks_wait_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(
        app,
        [
            "tasks",
            "wait",
            str(task_id),
            "--until-status",
            "completed",
            "--interval",
            "0.1",
            "--timeout",
            "0.2",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert f'"task_id": {task_id}' in result.stdout
    assert '"status": "completed"' in result.stdout


def test_ops_inspect_command_groups_connected_operator_bundle() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["ops", "inspect", str(task_id)])

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "inspection:" in result.stdout
    assert "recent_events:" in result.stdout
    assert "result_summary:" in result.stdout
    assert "result_handle_ids: result:fluxonium-2025-031:fit-summary" in result.stdout


def test_ops_latest_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["ops", "latest", "--lane", "simulation", "--status", "completed", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"task": {' in result.stdout
    assert '"inspection": {' in result.stdout
    assert '"recent_events": [' in result.stdout
    assert '"result_summary": {' in result.stdout


def test_ops_wait_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(
        app,
        [
            "ops",
            "wait",
            str(task_id),
            "--until-status",
            "completed",
            "--interval",
            "0.1",
            "--timeout",
            "0.2",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"task": {' in result.stdout
    assert '"recent_events": [' in result.stdout
    assert '"event_type": "task_completed"' in result.stdout


def test_ops_submit_command_can_wait_for_requested_status() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "ops",
            "submit",
            "characterization",
            "--dataset-id",
            "transmon-coupler-014",
            "--wait",
            "--until-status",
            "queued",
            "--interval",
            "0.1",
            "--timeout",
            "0.2",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"task": {' in result.stdout
    assert '"kind": "characterization"' in result.stdout
    assert '"status": "queued"' in result.stdout
    assert '"recent_events": [' in result.stdout
    assert '"result_summary": {' in result.stdout


def test_events_show_command_groups_persisted_task_history() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["events", "show", str(task_id)])

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "event_count: 2" in result.stdout
    assert "event_type: task_submitted" in result.stdout
    assert "event_type: task_completed" in result.stdout
    assert "result_handle_count: 2" in result.stdout
    assert "dispatch_status: completed" in result.stdout


def test_events_show_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["events", "show", str(task_id), "--output", "json"])

    assert result.exit_code == 0
    assert f'"task_id": {task_id}' in result.stdout
    assert '"event_count": 2' in result.stdout
    assert '"event_type": "task_completed"' in result.stdout


def test_events_show_command_supports_event_type_filters() -> None:
    runner = CliRunner()
    task_id = _running_simulation_task_id()

    result = runner.invoke(app, ["events", "show", str(task_id), "--event-type", "task_running"])

    assert result.exit_code == 0
    assert "event_type: task_running" in result.stdout
    assert "event_type: task_submitted" not in result.stdout


def test_events_latest_command_reads_latest_persisted_event() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["events", "latest", str(task_id)])

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "latest_event:" in result.stdout
    assert "event_type: task_completed" in result.stdout


def test_events_latest_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["events", "latest", str(task_id), "--output", "json"])

    assert result.exit_code == 0
    assert f'"task_id": {task_id}' in result.stdout
    assert '"event": {' in result.stdout
    assert '"event_type": "task_completed"' in result.stdout


def test_events_show_command_rejects_empty_filtered_history() -> None:
    runner = CliRunner()
    task_id = _running_simulation_task_id()

    result = runner.invoke(app, ["events", "show", str(task_id), "--level", "error"])

    assert result.exit_code == 1
    assert (
        f"error: No persisted task events matched the requested filters for {task_id}."
        in result.output
    )


def test_results_show_command_groups_persisted_result_refs() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["results", "show", str(task_id)])

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "trace_batch_id: 88" in result.stdout
    assert "metadata_record_count: 2" in result.stdout
    assert "result_handle_count: 2" in result.stdout
    assert "result:fluxonium-2025-031:fit-summary" in result.stdout


def test_results_show_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["results", "show", str(task_id), "--output", "json"])

    assert result.exit_code == 0
    assert f'"task_id": {task_id}' in result.stdout
    assert '"result_refs": {' in result.stdout
    assert '"trace_batch_id": 88' in result.stdout
    assert '"result_handles": [' in result.stdout
    assert '"lineage": {' in result.stdout
    assert '"source_runtime": "standalone_cli"' in result.stdout


def test_results_trace_command_reads_trace_payload() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["results", "trace", str(task_id)])

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "backend: local_zarr" in result.stdout
    assert (
        "store_uri: trace_store/datasets/fluxonium-2025-031/trace-batches/88.zarr" in result.stdout
    )
    assert "shape: 184, 1024" in result.stdout


def test_results_trace_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["results", "trace", str(task_id), "--output", "json"])

    assert result.exit_code == 0
    assert f'"task_id": {task_id}' in result.stdout
    assert '"trace_payload": {' in result.stdout
    assert '"store_key": "datasets/fluxonium-2025-031/trace-batches/88.zarr"' in result.stdout
    assert '"lineage": {' in result.stdout


def test_results_handles_command_reads_persisted_handles() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["results", "handles", str(task_id)])

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "result_handle_count: 2" in result.stdout
    assert "handle_id: result:fluxonium-2025-031:fit-summary" in result.stdout
    assert "payload_locator: artifacts/fit-summary.json" in result.stdout
    assert "handle_id: result:fluxonium-2025-031:plot-bundle" in result.stdout


def test_results_handles_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(app, ["results", "handles", str(task_id), "--output", "json"])

    assert result.exit_code == 0
    assert f'"task_id": {task_id}' in result.stdout
    assert '"metadata_records": [' in result.stdout
    assert '"handle_id": "result:fluxonium-2025-031:fit-summary"' in result.stdout
    assert '"lineage": {' in result.stdout


def test_results_export_bundle_command_writes_lineage_preserving_bundle(tmp_path: Path) -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()
    bundle_file = tmp_path / "result-bundle.json"

    result = runner.invoke(
        app,
        ["results", "export-bundle", str(task_id), str(bundle_file), "--output", "json"],
    )

    assert result.exit_code == 0
    assert bundle_file.exists()
    stdout_payload = json.loads(result.stdout)
    bundle_payload = json.loads(bundle_file.read_text(encoding="utf-8"))

    assert stdout_payload["bundle_file"] == str(bundle_file)
    assert bundle_payload["metadata"]["bundle_family"] == "result_bundle"
    assert bundle_payload["task"]["task_id"] == task_id
    assert bundle_payload["result_refs"]["lineage"]["source_task_id"] == task_id
    assert bundle_payload["result_refs"]["lineage"]["source_dataset_id"] == "fluxonium-2025-031"


def test_results_export_bundle_text_receipt_mentions_lineage(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()
    bundle_file = tmp_path / "result-bundle.json"

    result = runner.invoke(
        app,
        ["results", "export-bundle", str(task_id), str(bundle_file)],
    )

    assert result.exit_code == 0
    assert "interchange_scope: local_app_bundle" in result.stdout
    assert "lineage_preserved: true" in result.stdout
    assert "result_handle_count: 2" in result.stdout


def test_results_import_bundle_command_round_trips_bundle_into_local_registry(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    source_task_id = _completed_simulation_task_id()
    bundle_file = tmp_path / "roundtrip-result-bundle.json"

    export_result = runner.invoke(
        app,
        ["results", "export-bundle", str(source_task_id), str(bundle_file)],
    )
    import_result = runner.invoke(
        app,
        ["results", "import-bundle", str(bundle_file), "--output", "json"],
    )

    assert export_result.exit_code == 0
    assert import_result.exit_code == 0

    import_payload = json.loads(import_result.stdout)
    imported_task_id = import_payload["imported_task"]["task_id"]
    assert imported_task_id != source_task_id
    expected_bundle_id = f"bundle:result:{source_task_id}"
    assert import_payload["bundle"]["metadata"]["bundle_id"] == expected_bundle_id
    assert import_payload["imported_task"]["dispatch"]["submission_source"] == "bundle_import"
    assert (
        import_payload["imported_task"]["result_refs"]["lineage"]["imported_from_bundle_id"]
        == expected_bundle_id
    )
    assert (
        import_payload["imported_task"]["result_refs"]["lineage"]["source_task_id"]
        == source_task_id
    )

    show_result = runner.invoke(app, ["results", "show", str(imported_task_id), "--output", "json"])

    assert show_result.exit_code == 0
    assert f'"task_id": {imported_task_id}' in show_result.stdout
    assert '"submission_source": "bundle_import"' in show_result.stdout
    assert f'"imported_from_bundle_id": "{expected_bundle_id}"' in show_result.stdout


def test_results_trace_command_rejects_tasks_without_trace_payload() -> None:
    runner = CliRunner()
    task_id = _task_without_trace_payload_id()

    result = runner.invoke(app, ["results", "trace", str(task_id)])

    assert result.exit_code == 1
    assert f"error: Task {task_id} does not expose a persisted trace payload." in result.output


def test_results_handles_command_rejects_tasks_without_result_handles() -> None:
    runner = CliRunner()
    task_id = _task_without_result_handles_id()

    result = runner.invoke(app, ["results", "handles", str(task_id)])

    assert result.exit_code == 1
    assert f"error: Task {task_id} does not expose persisted result handles." in result.output


def test_simulation_show_command_reads_simulation_lane_task() -> None:
    runner = CliRunner()
    task_id = _running_simulation_task_id()

    result = runner.invoke(simulation.app, ["show", str(task_id)])

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "lane: simulation" in result.stdout
    assert "kind: simulation" in result.stdout


def test_simulation_inspect_command_groups_operator_view() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(simulation.app, ["inspect", str(task_id)])

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "inspection:" in result.stdout
    assert "latest_event_type: task_completed" in result.stdout


def test_simulation_show_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _running_simulation_task_id()

    result = runner.invoke(simulation.app, ["show", str(task_id), "--output", "json"])

    assert result.exit_code == 0
    assert f'"task_id": {task_id}' in result.stdout
    assert '"lane": "simulation"' in result.stdout


def test_simulation_latest_command_reads_latest_simulation_lane_task() -> None:
    runner = CliRunner()
    task_id = _running_simulation_task_id()

    result = runner.invoke(simulation.app, ["latest", "--status", "running"])

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "lane: simulation" in result.stdout


def test_simulation_latest_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(simulation.app, ["latest", "--status", "completed", "--output", "json"])

    assert result.exit_code == 0
    assert f'"task_id": {task_id}' in result.stdout
    assert '"kind": "post_processing"' in result.stdout
    assert '"lane": "simulation"' in result.stdout


def test_simulation_submit_command_submits_simulation_task() -> None:
    runner = CliRunner()

    result = runner.invoke(simulation.app, ["submit", "--definition-id", "18"])

    assert result.exit_code == 0
    assert "kind: simulation" in result.stdout
    assert "lane: simulation" in result.stdout
    assert "worker_task_name: simulation_smoke_task" in result.stdout


def test_simulation_submit_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(simulation.app, ["submit", "--definition-id", "18", "--output", "json"])

    assert result.exit_code == 0
    assert '"kind": "simulation"' in result.stdout
    assert '"lane": "simulation"' in result.stdout
    assert '"definition_id": 18' in result.stdout


def test_simulation_submit_command_falls_back_to_local_active_dataset() -> None:
    runner = CliRunner()

    set_result = runner.invoke(app, ["session", "set-active-dataset", "transmon-coupler-014"])
    result = runner.invoke(simulation.app, ["submit", "--definition-id", "18", "--output", "json"])

    assert set_result.exit_code == 0
    assert result.exit_code == 0
    assert '"dataset_id": "transmon-coupler-014"' in result.stdout
    assert '"submitted_from_active_dataset": true' in result.stdout


def test_simulation_wait_command_returns_terminal_simulation_lane_task() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(
        simulation.app,
        ["wait", str(task_id), "--interval", "0.1", "--timeout", "0.2"],
    )

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "status: completed" in result.stdout
    assert "lane: simulation" in result.stdout


def test_simulation_wait_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _completed_simulation_task_id()

    result = runner.invoke(
        simulation.app,
        [
            "wait",
            str(task_id),
            "--interval",
            "0.1",
            "--timeout",
            "0.2",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert f'"task_id": {task_id}' in result.stdout
    assert '"status": "completed"' in result.stdout
    assert '"lane": "simulation"' in result.stdout


def test_simulation_wait_command_supports_until_status_option() -> None:
    runner = CliRunner()
    task_id = _running_simulation_task_id()

    result = runner.invoke(
        simulation.app,
        [
            "wait",
            str(task_id),
            "--until-status",
            "running",
            "--interval",
            "0.1",
            "--timeout",
            "0.2",
        ],
    )

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "status: running" in result.stdout


def test_simulation_show_command_rejects_non_simulation_lane_task() -> None:
    runner = CliRunner()
    task_id = _queued_characterization_task_id()

    result = runner.invoke(simulation.app, ["show", str(task_id)])

    assert result.exit_code == 1
    assert f"error: Task {task_id} is not part of the simulation lane." in result.output


def test_characterization_show_command_reads_characterization_lane_task() -> None:
    runner = CliRunner()
    task_id = _queued_characterization_task_id()

    result = runner.invoke(app, ["characterization", "show", str(task_id)])

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "lane: characterization" in result.stdout
    assert "kind: characterization" in result.stdout


def test_characterization_inspect_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _queued_characterization_task_id()

    result = runner.invoke(app, ["characterization", "inspect", str(task_id), "--output", "json"])

    assert result.exit_code == 0
    assert '"task": {' in result.stdout
    assert '"inspection": {' in result.stdout
    assert '"lane": "characterization"' in result.stdout


def test_characterization_show_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _queued_characterization_task_id()

    result = runner.invoke(app, ["characterization", "show", str(task_id), "--output", "json"])

    assert result.exit_code == 0
    assert f'"task_id": {task_id}' in result.stdout
    assert '"lane": "characterization"' in result.stdout


def test_characterization_latest_command_reads_latest_characterization_lane_task() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["characterization", "latest"])

    assert result.exit_code == 0
    assert "task_id:" in result.stdout
    assert "kind: characterization" in result.stdout
    assert "lane: characterization" in result.stdout


def test_characterization_latest_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["characterization", "latest", "--status", "queued", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"lane": "characterization"' in result.stdout
    assert '"kind": "characterization"' in result.stdout


def test_characterization_submit_command_submits_characterization_task() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["characterization", "submit", "--dataset-id", "transmon-coupler-014"],
    )

    assert result.exit_code == 0
    assert "kind: characterization" in result.stdout
    assert "lane: characterization" in result.stdout
    assert "worker_task_name: characterization_run_task" in result.stdout


def test_characterization_submit_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["characterization", "submit", "--dataset-id", "transmon-coupler-014", "--output", "json"],
    )

    assert result.exit_code == 0
    assert '"kind": "characterization"' in result.stdout
    assert '"lane": "characterization"' in result.stdout
    assert '"dataset_id": "transmon-coupler-014"' in result.stdout


def test_characterization_wait_command_reaches_requested_status() -> None:
    runner = CliRunner()
    task_id = _queued_characterization_task_id()

    result = runner.invoke(
        app,
        [
            "characterization",
            "wait",
            str(task_id),
            "--until-status",
            "queued",
            "--interval",
            "0.1",
            "--timeout",
            "0.2",
        ],
    )

    assert result.exit_code == 0
    assert f"task_id: {task_id}" in result.stdout
    assert "status: queued" in result.stdout
    assert "lane: characterization" in result.stdout


def test_characterization_wait_command_supports_json_output() -> None:
    runner = CliRunner()
    task_id = _queued_characterization_task_id()

    result = runner.invoke(
        app,
        [
            "characterization",
            "wait",
            str(task_id),
            "--until-status",
            "queued",
            "--interval",
            "0.1",
            "--timeout",
            "0.2",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert f'"task_id": {task_id}' in result.stdout
    assert '"status": "queued"' in result.stdout
    assert '"lane": "characterization"' in result.stdout


def test_characterization_show_command_rejects_non_characterization_lane_task() -> None:
    runner = CliRunner()
    task_id = _running_simulation_task_id()

    result = runner.invoke(app, ["characterization", "show", str(task_id)])

    assert result.exit_code == 1
    assert f"error: Task {task_id} is not part of the characterization lane." in result.output


def test_tasks_submit_command_submits_simulation_task() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["tasks", "submit", "simulation", "--definition-id", "18"],
    )

    assert result.exit_code == 0
    assert "kind: simulation" in result.stdout
    assert "definition_id: 18" in result.stdout
    assert "status: queued" in result.stdout
    assert "worker_task_name: simulation_smoke_task" in result.stdout
    assert "request_ready: false" in result.stdout


def test_tasks_submit_command_supports_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "tasks",
            "submit",
            "characterization",
            "--dataset-id",
            "transmon-coupler-014",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"kind": "characterization"' in result.stdout
    assert '"dataset_id": "transmon-coupler-014"' in result.stdout
    assert '"status": "queued"' in result.stdout


def test_tasks_submit_command_falls_back_to_local_active_dataset() -> None:
    runner = CliRunner()

    set_result = runner.invoke(app, ["session", "set-active-dataset", "transmon-coupler-014"])
    result = runner.invoke(
        app,
        ["tasks", "submit", "characterization", "--output", "json"],
    )

    assert set_result.exit_code == 0
    assert result.exit_code == 0
    assert '"dataset_id": "transmon-coupler-014"' in result.stdout
    assert '"submitted_from_active_dataset": true' in result.stdout


def test_tasks_submit_command_uses_structured_backend_error_message() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["tasks", "submit", "simulation"])

    assert result.exit_code == 2
    assert (
        "error: Simulation tasks require definition_id. [validation/simulation_definition_required]"
    ) in result.output


def test_tasks_submit_command_uses_structured_backend_error_json() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["tasks", "submit", "simulation", "--output", "json"])

    assert result.exit_code == 2
    assert '"error": {' in result.output
    assert '"code": "simulation_definition_required"' in result.output
    assert '"category": "validation"' in result.output


def test_tasks_show_command_uses_structured_backend_error_message() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["tasks", "show", "999"])

    assert result.exit_code == 2
    assert "error: Task 999 was not found. [not_found/task_not_found]" in result.output


def test_tasks_show_command_uses_structured_backend_error_json() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["tasks", "show", "999", "--output", "json"])

    assert result.exit_code == 2
    assert '"error": {' in result.output
    assert '"code": "task_not_found"' in result.output
    assert '"category": "not_found"' in result.output


def test_session_set_active_dataset_command_uses_structured_backend_error_message() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["session", "set-active-dataset", "missing-dataset"])

    assert result.exit_code == 2
    assert (
        "error: Dataset missing-dataset was not found. [not_found/dataset_not_found]"
        in result.output
    )


def test_session_set_active_dataset_command_uses_structured_backend_error_json() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["session", "set-active-dataset", "missing-dataset", "--output", "json"],
    )

    assert result.exit_code == 2
    assert '"error": {' in result.output
    assert '"code": "dataset_not_found"' in result.output
    assert '"category": "not_found"' in result.output


def test_session_show_command_handles_backend_contract_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        session,
        "get_session",
        lambda: _raise_backend_error("Session lookup failed."),
    )

    result = runner.invoke(app, ["session", "show"])

    assert result.exit_code == 2
    assert "error: Session lookup failed. [validation/request_failed]" in result.output


def test_datasets_list_command_handles_backend_contract_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        datasets,
        "list_datasets",
        lambda **_: _raise_backend_error("Dataset read failed."),
    )

    result = runner.invoke(app, ["datasets", "list"])

    assert result.exit_code == 2
    assert "error: Dataset read failed. [validation/request_failed]" in result.output


def test_tasks_list_command_handles_backend_contract_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.setattr(tasks, "list_tasks", lambda **_: _raise_backend_error("Task list failed."))

    result = runner.invoke(app, ["tasks", "list"])

    assert result.exit_code == 2
    assert "error: Task list failed. [validation/request_failed]" in result.output


def test_simulation_wait_command_handles_backend_contract_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.setattr(simulation, "get_task", lambda _: _raise_backend_error("Task read failed."))

    result = runner.invoke(simulation.app, ["wait", "301"])

    assert result.exit_code == 2
    assert "error: Task read failed. [validation/request_failed]" in result.output


def test_characterization_wait_command_handles_backend_contract_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        characterization,
        "get_task",
        lambda _: _raise_backend_error("Task read failed."),
    )

    result = runner.invoke(app, ["characterization", "wait", "302"])

    assert result.exit_code == 2
    assert "error: Task read failed. [validation/request_failed]" in result.output


def test_results_show_command_handles_backend_contract_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.setattr(results, "get_task", lambda _: _raise_backend_error("Task read failed."))

    result = runner.invoke(app, ["results", "show", "303"])

    assert result.exit_code == 2
    assert "error: Task read failed. [validation/request_failed]" in result.output


def test_events_show_command_handles_backend_contract_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.setattr(events, "get_task", lambda _: _raise_backend_error("Task read failed."))

    result = runner.invoke(app, ["events", "show", "303"])

    assert result.exit_code == 2
    assert "error: Task read failed. [validation/request_failed]" in result.output


def test_ops_inspect_command_handles_backend_contract_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.setattr(ops, "get_task", lambda _: _raise_backend_error("Task read failed."))

    result = runner.invoke(app, ["ops", "inspect", "303"])

    assert result.exit_code == 2
    assert "error: Task read failed. [validation/request_failed]" in result.output


def _backend_error(message: str):
    return build_contract_error(
        code="request_failed",
        category="validation",
        message=message,
        status=422,
    )


def _raise_backend_error(message: str) -> None:
    raise _backend_error(message)
