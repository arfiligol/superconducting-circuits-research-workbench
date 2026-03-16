"""Commands for inspecting standalone local dataset state."""

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from sc_cli.errors import exit_for_contract_error, exit_with_runtime_error
from sc_cli.local_datasets import (
    LocalDatasetBundle,
    LocalDatasetBundleExportReceipt,
    LocalDatasetBundleImportReceipt,
    LocalDatasetSortBy,
    LocalDatasetStatus,
    LocalSortOrder,
)
from sc_cli.local_errors import CliContractError
from sc_cli.local_store import record_bundle_receipt
from sc_cli.output import OutputMode, OutputOption
from sc_cli.presenters import (
    render_dataset_bundle_export_receipt,
    render_dataset_bundle_import_receipt,
    render_dataset_detail,
    render_dataset_metadata_update,
    render_dataset_summaries,
)
from sc_cli.runtime import (
    export_dataset_bundle,
    get_dataset,
    import_dataset_bundle,
    list_datasets,
    update_dataset_metadata,
)

app = typer.Typer(
    help="Browse local datasets and exchange lineage-preserving bundles.",
    no_args_is_help=True,
)


class DatasetStatusOption(str, Enum):
    READY = "Ready"
    QUEUED = "Queued"
    REVIEW = "Review"


class DatasetSortByOption(str, Enum):
    UPDATED_AT = "updated_at"
    NAME = "name"
    SAMPLES = "samples"


class SortOrderOption(str, Enum):
    ASC = "asc"
    DESC = "desc"


@app.command("list")
def list_command(
    family: Annotated[
        str | None,
        typer.Option("--family", help="Filter by dataset family."),
    ] = None,
    status: Annotated[
        DatasetStatusOption | None,
        typer.Option("--status", help="Filter by dataset status."),
    ] = None,
    sort_by: Annotated[
        DatasetSortByOption,
        typer.Option("--sort-by", help="Sort datasets by one local contract field."),
    ] = DatasetSortByOption.UPDATED_AT,
    sort_order: Annotated[
        SortOrderOption,
        typer.Option("--sort-order", help="Sort direction."),
    ] = SortOrderOption.DESC,
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """List datasets from the standalone local catalog."""
    try:
        datasets = list_datasets(
            family=family,
            status=None if status is None else _coerce_status(status.value),
            sort_by=_coerce_sort_by(sort_by.value),
            sort_order=_coerce_sort_order(sort_order.value),
        )
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(render_dataset_summaries(datasets, output=output))


@app.command("show")
def show_command(
    dataset_id: Annotated[
        str,
        typer.Argument(help="Dataset id to inspect."),
    ],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Show one dataset from the standalone local catalog."""
    try:
        dataset = get_dataset(dataset_id)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(render_dataset_detail(dataset, output=output))


@app.command("set-metadata")
def set_metadata_command(
    dataset_id: Annotated[
        str,
        typer.Argument(help="Dataset id to update."),
    ],
    device_type: Annotated[
        str,
        typer.Option("--device-type", help="Device type metadata value."),
    ],
    source: Annotated[
        str,
        typer.Option("--source", help="Dataset source metadata value."),
    ],
    capabilities: Annotated[
        list[str],
        typer.Option(
            "--capability",
            help="Capability metadata value. Repeat to provide multiple capabilities.",
        ),
    ],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Update dataset metadata through the standalone local catalog."""
    try:
        result = update_dataset_metadata(
            dataset_id,
            device_type=device_type,
            capabilities=tuple(capabilities),
            source=source,
        )
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(render_dataset_metadata_update(result, output=output))


@app.command("export-bundle")
def export_bundle_command(
    dataset_id: Annotated[
        str,
        typer.Argument(help="Dataset id whose bundle should be exported."),
    ],
    bundle_file: Annotated[
        Path,
        typer.Argument(
            dir_okay=False,
            resolve_path=True,
            help="Output path for the exported dataset bundle JSON.",
        ),
    ],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Export one local dataset bundle for lineage-preserving app/archive interchange."""
    try:
        bundle = export_dataset_bundle(dataset_id)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    try:
        bundle_file.parent.mkdir(parents=True, exist_ok=True)
        bundle_file.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    except OSError as error:
        exit_with_runtime_error(f"Could not write {bundle_file}: {error}")
    receipt = LocalDatasetBundleExportReceipt(bundle_file=str(bundle_file), bundle=bundle)
    try:
        record_bundle_receipt(
            bundle_family="dataset_bundle",
            operation="export",
            receipt=receipt,
        )
    except OSError as error:
        exit_with_runtime_error(f"Could not record bundle receipt for {bundle_file}: {error}")
    typer.echo(render_dataset_bundle_export_receipt(receipt, output=output))


@app.command("import-bundle")
def import_bundle_command(
    bundle_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to an exported dataset bundle JSON file.",
        ),
    ],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Import one dataset bundle into the local dataset catalog with lineage preserved."""
    try:
        bundle = LocalDatasetBundle.model_validate_json(bundle_file.read_text(encoding="utf-8"))
    except OSError as error:
        exit_with_runtime_error(f"Could not read {bundle_file}: {error}")
    except Exception as error:  # pragma: no cover - validated by CLI tests
        exit_with_runtime_error(f"Could not parse dataset bundle {bundle_file}: {error}")
    try:
        imported_dataset = import_dataset_bundle(bundle)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    receipt = LocalDatasetBundleImportReceipt(
        bundle_file=str(bundle_file),
        bundle=bundle,
        imported_dataset=imported_dataset,
    )
    try:
        record_bundle_receipt(
            bundle_family="dataset_bundle",
            operation="import",
            receipt=receipt,
        )
    except OSError as error:
        exit_with_runtime_error(f"Could not record bundle receipt for {bundle_file}: {error}")
    typer.echo(render_dataset_bundle_import_receipt(receipt, output=output))


def _coerce_status(value: str) -> LocalDatasetStatus:
    return value  # type: ignore[return-value]


def _coerce_sort_by(value: str) -> LocalDatasetSortBy:
    return value  # type: ignore[return-value]


def _coerce_sort_order(value: str) -> LocalSortOrder:
    return value  # type: ignore[return-value]
