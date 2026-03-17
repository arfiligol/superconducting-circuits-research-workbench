from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from sc_cli.app import app
from sc_cli.commands import circuit_definition
from sc_cli.local_circuit_definitions import (
    LocalDefinitionLineage,
    LocalValidationNotice,
    build_definition_bundle,
    build_local_circuit_definition_detail,
    build_local_circuit_definition_summary,
    build_local_inspection_summary,
    create_local_circuit_definition,
    import_definition_bundle,
    reset_local_circuit_definition_state,
)


def test_build_local_inspection_summary_preserves_invalid_status() -> None:
    summary = build_local_inspection_summary(
        inspection_status="invalid",
        notices=[
            LocalValidationNotice(level="warning", message="Port mapping needs migration."),
        ],
        payload_summary=None,
    )

    assert summary.status == "invalid"
    assert summary.notice_count == 1
    assert summary.warning_count == 1
    assert summary.error_count == 1
    assert summary.diagnostic_count == 2


def test_local_contract_source_does_not_import_backend_dtos() -> None:
    source = files("sc_cli").joinpath("local_circuit_definitions.py").read_text(encoding="utf-8")

    assert "CircuitDefinitionDetailResponse" not in source
    assert "CircuitDefinitionSummaryResponse" not in source


def test_local_detail_adapter_derives_invalid_status_without_backend_dto_types() -> None:
    detail = build_local_circuit_definition_detail(
        SimpleNamespace(
            definition_id=18,
            name="BrokenDefinition",
            created_at="2026-03-15 10:30:00",
            element_count=4,
            inspection_status="invalid",
            summary=SimpleNamespace(
                status="invalid",
                warning_count=1,
                diagnostic_count=2,
                error_count=1,
                info_count=0,
            ),
            preview_artifact_count=3,
            source_text="name: BrokenDefinition",
            normalized_output="{}",
            validation_notices=[
                SimpleNamespace(level="warning", message="Port mapping needs migration."),
                SimpleNamespace(level="warning", message="Undefined coupling component."),
            ],
            preview_artifacts=[
                "definition.normalized.json",
                "schematic-input.yaml",
                "parameter-bundle.toml",
            ],
        )
    )

    assert detail.inspection_status == "invalid"
    assert detail.inspection_summary.status == "invalid"
    assert detail.inspection_summary.error_count == 1
    assert detail.validation_notices[1].level == "warning"


def test_local_summary_adapter_preserves_invalid_catalog_status_without_backend_dto_types() -> None:
    summary = build_local_circuit_definition_summary(
        SimpleNamespace(
            definition_id=18,
            name="BrokenSummaryDefinition",
            created_at="2026-03-15 10:30:00",
            element_count=5,
            inspection_status="invalid",
            preview_artifact_count=3,
        )
    )

    assert summary.definition_id == 18
    assert summary.inspection_status == "invalid"


def test_circuit_definition_inspect_source_file_preserves_invalid_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_file = tmp_path / "invalid-source.circuit.yaml"
    source_file.write_text("name: invalid_surface\nfamily: fluxonium\n", encoding="utf-8")

    monkeypatch.setattr(
        circuit_definition,
        "inspect_circuit_definition_source",
        lambda _: SimpleNamespace(
            circuit_name="invalid_surface",
            family="fluxonium",
            element_count=2,
            normalized_output="{}",
            summary=SimpleNamespace(
                status="invalid",
                warning_count=1,
                diagnostic_count=2,
                error_count=1,
                info_count=0,
            ),
            validation_notices=(
                SimpleNamespace(level="warning", message="Topology contains unknown node."),
            ),
        ),
    )

    runner = CliRunner()
    text_result = runner.invoke(app, ["circuit-definition", "inspect", str(source_file)])
    json_result = runner.invoke(
        app,
        ["circuit-definition", "inspect", str(source_file), "--output", "json"],
    )

    assert text_result.exit_code == 0
    assert "inspection_status: invalid" in text_result.stdout
    assert "- [warning] Topology contains unknown node." in text_result.stdout

    assert json_result.exit_code == 0
    assert '"inspection_status": "invalid"' in json_result.stdout
    assert '"error_count": 1' in json_result.stdout


def test_circuit_definition_inspect_definition_id_derives_invalid_status_from_notices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        circuit_definition,
        "get_circuit_definition",
        lambda _definition_id: SimpleNamespace(
            definition_id=18,
            name="BrokenDefinition",
            created_at="2026-03-15 10:30:00",
            element_count=4,
            inspection_status="invalid",
            summary=SimpleNamespace(
                status="invalid",
                warning_count=1,
                diagnostic_count=2,
                error_count=1,
                info_count=0,
            ),
            preview_artifact_count=3,
            source_text="name: BrokenDefinition",
            normalized_output="{}",
            validation_notices=[
                SimpleNamespace(level="warning", message="Port mapping needs migration."),
                SimpleNamespace(level="warning", message="Undefined coupling component."),
            ],
            preview_artifacts=[
                "definition.normalized.json",
                "schematic-input.yaml",
                "parameter-bundle.toml",
            ],
        ),
    )

    runner = CliRunner()
    text_result = runner.invoke(app, ["circuit-definition", "inspect", "--definition-id", "18"])
    json_result = runner.invoke(
        app,
        ["circuit-definition", "inspect", "--definition-id", "18", "--output", "json"],
    )

    assert text_result.exit_code == 0
    assert "inspection_status: invalid" in text_result.stdout
    assert "status: invalid" in text_result.stdout
    assert "- [warning] Undefined coupling component." in text_result.stdout

    assert json_result.exit_code == 0
    assert '"inspection_status": "invalid"' in json_result.stdout
    assert '"status": "invalid"' in json_result.stdout


def test_circuit_definition_create_uses_local_detail_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "created.circuit.yaml"
    source_file.write_text("name: CreatedDefinition\nfamily: fluxonium\n", encoding="utf-8")

    monkeypatch.setattr(
        circuit_definition,
        "create_circuit_definition",
        lambda **_: SimpleNamespace(
            definition_id=21,
            name="CreatedDefinition",
            created_at="2026-03-15 10:30:00",
            element_count=2,
            inspection_status="invalid",
            summary=SimpleNamespace(
                status="invalid",
                warning_count=1,
                diagnostic_count=2,
                error_count=1,
                info_count=0,
            ),
            preview_artifact_count=3,
            source_text="name: CreatedDefinition",
            normalized_output="{}",
            validation_notices=[
                SimpleNamespace(level="warning", message="Missing component binding.")
            ],
            preview_artifacts=[
                "definition.normalized.json",
                "schematic-input.yaml",
                "parameter-bundle.toml",
            ],
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "circuit-definition",
            "create",
            str(source_file),
            "--name",
            "CreatedDefinition",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"definition_id": 21' in result.stdout
    assert '"inspection_status": "invalid"' in result.stdout
    assert '"error_count": 1' in result.stdout


def test_circuit_definition_update_uses_local_detail_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "updated.circuit.yaml"
    source_file.write_text("name: UpdatedDefinition\nfamily: fluxonium\n", encoding="utf-8")

    monkeypatch.setattr(
        circuit_definition,
        "update_circuit_definition",
        lambda *_args, **_kwargs: SimpleNamespace(
            definition_id=21,
            name="UpdatedDefinition",
            created_at="2026-03-15 10:30:00",
            element_count=2,
            inspection_status="invalid",
            summary=SimpleNamespace(
                status="invalid",
                warning_count=1,
                diagnostic_count=2,
                error_count=1,
                info_count=0,
            ),
            preview_artifact_count=3,
            source_text="name: UpdatedDefinition",
            normalized_output="{}",
            validation_notices=[
                SimpleNamespace(level="warning", message="Port index is out of range.")
            ],
            preview_artifacts=[
                "definition.normalized.json",
                "schematic-input.yaml",
                "parameter-bundle.toml",
            ],
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "circuit-definition",
            "update",
            "21",
            str(source_file),
            "--name",
            "UpdatedDefinition",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"definition_id": 21' in result.stdout
    assert '"inspection_status": "invalid"' in result.stdout
    assert '"error_count": 1' in result.stdout


def test_circuit_definition_list_uses_local_summary_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        circuit_definition,
        "list_circuit_definitions",
        lambda **_: [
            SimpleNamespace(
                definition_id=18,
                name="BrokenSummaryDefinition",
                created_at="2026-03-15 10:30:00",
                element_count=5,
                inspection_status="invalid",
                preview_artifact_count=3,
            )
        ],
    )

    runner = CliRunner()
    text_result = runner.invoke(app, ["circuit-definition", "list"])
    json_result = runner.invoke(app, ["circuit-definition", "list", "--output", "json"])

    assert text_result.exit_code == 0
    assert "inspection=invalid" in text_result.stdout

    assert json_result.exit_code == 0
    assert '"inspection_status": "invalid"' in json_result.stdout


def test_definition_bundle_round_trip_preserves_lineage() -> None:
    reset_local_circuit_definition_state()
    created_definition = create_local_circuit_definition(
        name="BundleDefinition",
        source_text="\n".join(
            [
                "name: BundleDefinition",
                "components:",
                "  - name: R1",
                "    default: 50.0",
                "    unit: Ohm",
                "topology:",
                '  - [P1, "1", "0", 1]',
                '  - [R1, "1", "0", "R1"]',
            ]
        ),
    )
    exported_bundle = build_definition_bundle(created_definition)
    imported_definition = import_definition_bundle(exported_bundle)

    assert exported_bundle.metadata.bundle_family == "definition_bundle"
    assert imported_definition.definition_id != created_definition.definition_id
    assert imported_definition.lineage == LocalDefinitionLineage(
        source_runtime="standalone_cli",
        source_definition_id=created_definition.definition_id,
        source_bundle_id=exported_bundle.metadata.bundle_id,
        parent_bundle_id=exported_bundle.metadata.bundle_id,
        imported_from_bundle_id=exported_bundle.metadata.bundle_id,
    )
