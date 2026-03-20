"""Thin adapters for canonical circuit-definition workflows."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from sc_core import inspect_circuit_definition_source

from sc_cli.errors import (
    exit_for_contract_error,
    exit_with_runtime_error,
    exit_with_usage_error,
)
from sc_cli.local_circuit_definitions import (
    LocalDefinitionBundle,
    LocalDefinitionBundleExportReceipt,
    LocalDefinitionBundleImportReceipt,
    build_local_circuit_definition_detail,
    build_local_circuit_definition_inspection,
    build_local_circuit_definition_summary,
)
from sc_cli.local_errors import CliContractError
from sc_cli.local_store import record_bundle_receipt
from sc_cli.output import OutputMode, OutputOption
from sc_cli.presenters import (
    render_circuit_definition_delete_result,
    render_circuit_definition_detail,
    render_circuit_definition_inspection,
    render_circuit_definition_summaries,
    render_definition_bundle_export_receipt,
    render_definition_bundle_import_receipt,
)
from sc_cli.runtime import (
    create_circuit_definition,
    delete_circuit_definition,
    export_definition_bundle,
    get_circuit_definition,
    import_definition_bundle,
    list_circuit_definitions,
    update_circuit_definition,
)

app = typer.Typer(
    help="Compatibility helpers for local circuit-definition catalog exchange.",
    no_args_is_help=True,
)


class CircuitDefinitionSortOption(StrEnum):
    CREATED_AT = "created_at"
    NAME = "name"
    ELEMENT_COUNT = "element_count"


class SortOrderOption(StrEnum):
    ASC = "asc"
    DESC = "desc"


@app.command("list")
def list_command(
    search: Annotated[
        str | None,
        typer.Option("--search", help="Case-insensitive name substring filter."),
    ] = None,
    sort_by: Annotated[
        CircuitDefinitionSortOption,
        typer.Option("--sort-by", help="Sort field for persisted circuit definitions."),
    ] = CircuitDefinitionSortOption.CREATED_AT,
    sort_order: Annotated[
        SortOrderOption,
        typer.Option("--sort-order", help="Sort direction."),
    ] = SortOrderOption.DESC,
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """List persisted local circuit definitions."""
    try:
        definitions = list_circuit_definitions(
            search=search,
            sort_by=sort_by.value,
            sort_order=sort_order.value,
        )
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(
        render_circuit_definition_summaries(
            [build_local_circuit_definition_summary(definition) for definition in definitions],
            output=output,
        )
    )


@app.command("inspect")
def inspect_command(
    source_file: Annotated[
        Path | None,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to a circuit-definition draft file.",
        ),
    ] = None,
    definition_id: Annotated[
        int | None,
        typer.Option(
            "--definition-id",
            min=1,
            help="Inspect one persisted local circuit definition by id.",
        ),
    ] = None,
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Inspect a draft file through sc_core or a persisted local definition by id."""
    if (source_file is None) == (definition_id is None):
        exit_with_usage_error("Provide exactly one of SOURCE_FILE or --definition-id.")

    if definition_id is not None:
        try:
            definition = get_circuit_definition(definition_id)
        except CliContractError as error:
            exit_for_contract_error(error, output=output)
        typer.echo(
            render_circuit_definition_detail(
                build_local_circuit_definition_detail(definition),
                output=output,
            )
        )
        return

    assert source_file is not None
    try:
        source_text = source_file.read_text(encoding="utf-8")
    except OSError as error:
        exit_with_runtime_error(f"Could not read {source_file}: {error}")
    inspection = inspect_circuit_definition_source(source_text)
    typer.echo(
        render_circuit_definition_inspection(
            build_local_circuit_definition_inspection(
                source_file=str(source_file),
                inspection=inspection,
                preview_artifacts=getattr(inspection, "preview_artifacts", ()),
            ),
            output=output,
        )
    )


@app.command("create")
def create_command(
    source_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to a circuit-definition source file to persist.",
        ),
    ],
    name: Annotated[
        str,
        typer.Option("--name", help="Display name for the persisted circuit definition."),
    ],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Create one persisted local circuit definition from a local source file."""
    try:
        source_text = source_file.read_text(encoding="utf-8")
    except OSError as error:
        exit_with_runtime_error(f"Could not read {source_file}: {error}")

    try:
        definition = create_circuit_definition(name=name, source_text=source_text)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(
        render_circuit_definition_detail(
            build_local_circuit_definition_detail(definition),
            output=output,
        )
    )


@app.command("update")
def update_command(
    definition_id: Annotated[
        int,
        typer.Argument(min=1, help="Persisted circuit-definition id to update."),
    ],
    source_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to a replacement circuit-definition source file.",
        ),
    ],
    name: Annotated[
        str,
        typer.Option("--name", help="Display name for the updated circuit definition."),
    ],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Update one persisted local circuit definition from a local source file."""
    try:
        source_text = source_file.read_text(encoding="utf-8")
    except OSError as error:
        exit_with_runtime_error(f"Could not read {source_file}: {error}")

    try:
        definition = update_circuit_definition(
            definition_id,
            name=name,
            source_text=source_text,
        )
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(
        render_circuit_definition_detail(
            build_local_circuit_definition_detail(definition),
            output=output,
        )
    )


@app.command("delete")
def delete_command(
    definition_id: Annotated[
        int,
        typer.Argument(min=1, help="Persisted circuit-definition id to delete."),
    ],
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help="Confirm deletion of the persisted circuit definition.",
        ),
    ] = False,
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Delete one persisted local circuit definition."""
    if not yes:
        exit_with_usage_error("Pass --yes to delete a persisted local circuit definition.")

    try:
        delete_circuit_definition(definition_id)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(render_circuit_definition_delete_result(definition_id, output=output))


@app.command("export-bundle")
def export_bundle_command(
    definition_id: Annotated[
        int,
        typer.Argument(min=1, help="Definition id whose bundle should be exported."),
    ],
    bundle_file: Annotated[
        Path,
        typer.Argument(
            dir_okay=False,
            resolve_path=True,
            help="Output path for the exported definition bundle JSON.",
        ),
    ],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Export one local definition bundle for interchange with app/archive consumers."""
    try:
        bundle = export_definition_bundle(definition_id)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    try:
        bundle_file.parent.mkdir(parents=True, exist_ok=True)
        bundle_file.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    except OSError as error:
        exit_with_runtime_error(f"Could not write {bundle_file}: {error}")
    receipt = LocalDefinitionBundleExportReceipt(bundle_file=str(bundle_file), bundle=bundle)
    try:
        record_bundle_receipt(
            bundle_family="definition_bundle",
            operation="export",
            receipt=receipt,
        )
    except OSError as error:
        exit_with_runtime_error(f"Could not record bundle receipt for {bundle_file}: {error}")
    typer.echo(render_definition_bundle_export_receipt(receipt, output=output))


@app.command("import-bundle")
def import_bundle_command(
    bundle_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to an exported definition bundle JSON file.",
        ),
    ],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Import one definition bundle into the local definition catalog."""
    try:
        bundle = LocalDefinitionBundle.model_validate_json(bundle_file.read_text(encoding="utf-8"))
    except OSError as error:
        exit_with_runtime_error(f"Could not read {bundle_file}: {error}")
    except Exception as error:  # pragma: no cover - validated by CLI tests
        exit_with_runtime_error(f"Could not parse definition bundle {bundle_file}: {error}")
    try:
        imported_definition = import_definition_bundle(bundle)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    receipt = LocalDefinitionBundleImportReceipt(
        bundle_file=str(bundle_file),
        bundle=bundle,
        imported_definition=imported_definition,
    )
    try:
        record_bundle_receipt(
            bundle_family="definition_bundle",
            operation="import",
            receipt=receipt,
        )
    except OSError as error:
        exit_with_runtime_error(f"Could not record bundle receipt for {bundle_file}: {error}")
    typer.echo(render_definition_bundle_import_receipt(receipt, output=output))
