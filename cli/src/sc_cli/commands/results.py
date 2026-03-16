"""Persisted task result reference inspection commands."""

from pathlib import Path
from typing import Annotated

import typer

from sc_cli.errors import exit_for_contract_error, exit_with_runtime_error
from sc_cli.local_errors import CliContractError
from sc_cli.local_interchange import (
    LocalResultBundle,
    LocalResultBundleExportReceipt,
    LocalResultBundleImportReceipt,
)
from sc_cli.local_runtime import LocalTaskDetail
from sc_cli.local_store import record_bundle_receipt
from sc_cli.output import OutputMode, OutputOption
from sc_cli.presenters import (
    render_result_bundle_export_receipt,
    render_result_bundle_import_receipt,
    render_task_result_handles,
    render_task_result_refs,
    render_task_trace_payload,
)
from sc_cli.runtime import export_task_result_bundle, get_task, import_task_result_bundle
from sc_cli.task_operator import get_task_or_exit

app = typer.Typer(
    help="Inspect local result references and exchange result bundles.",
    no_args_is_help=True,
)


@app.command("show")
def show_command(
    task_id: Annotated[int, typer.Argument(min=1, help="Task id whose result refs to inspect.")],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Show persisted result-reference state for one task."""
    task = _get_task_or_exit(task_id=task_id, output=output)
    typer.echo(render_task_result_refs(task, output=output))


@app.command("trace")
def trace_command(
    task_id: Annotated[int, typer.Argument(min=1, help="Task id whose trace payload to inspect.")],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Show the persisted trace payload reference for one task."""
    task = _get_task_or_exit(task_id=task_id, output=output)
    if task.result_refs.trace_payload is None:
        exit_with_runtime_error(f"Task {task_id} does not expose a persisted trace payload.")
    typer.echo(render_task_trace_payload(task, output=output))


@app.command("handles")
def handles_command(
    task_id: Annotated[int, typer.Argument(min=1, help="Task id whose result handles to inspect.")],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Show persisted result handles for one task."""
    task = _get_task_or_exit(task_id=task_id, output=output)
    if not task.result_refs.result_handles:
        exit_with_runtime_error(f"Task {task_id} does not expose persisted result handles.")
    typer.echo(render_task_result_handles(task, output=output))


@app.command("export-bundle")
def export_bundle_command(
    task_id: Annotated[
        int,
        typer.Argument(min=1, help="Task id whose result payload should be exported."),
    ],
    bundle_file: Annotated[
        Path,
        typer.Argument(
            dir_okay=False,
            resolve_path=True,
            help="Output path for the exported result bundle JSON.",
        ),
    ],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Export one local result bundle for lineage-preserving app/archive interchange."""
    try:
        bundle = export_task_result_bundle(task_id)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    try:
        bundle_file.parent.mkdir(parents=True, exist_ok=True)
        bundle_file.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    except OSError as error:
        exit_with_runtime_error(f"Could not write {bundle_file}: {error}")
    receipt = LocalResultBundleExportReceipt(bundle_file=str(bundle_file), bundle=bundle)
    try:
        record_bundle_receipt(
            bundle_family="result_bundle",
            operation="export",
            receipt=receipt,
        )
    except OSError as error:
        exit_with_runtime_error(f"Could not record bundle receipt for {bundle_file}: {error}")
    typer.echo(render_result_bundle_export_receipt(receipt, output=output))


@app.command("import-bundle")
def import_bundle_command(
    bundle_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to an exported result bundle JSON file.",
        ),
    ],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Import one result bundle into the local run registry with lineage preserved."""
    try:
        bundle = LocalResultBundle.model_validate_json(bundle_file.read_text(encoding="utf-8"))
    except OSError as error:
        exit_with_runtime_error(f"Could not read {bundle_file}: {error}")
    except Exception as error:  # pragma: no cover - validated by CLI tests
        exit_with_runtime_error(f"Could not parse result bundle {bundle_file}: {error}")
    try:
        imported_task = import_task_result_bundle(bundle)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    receipt = LocalResultBundleImportReceipt(
        bundle_file=str(bundle_file),
        bundle=bundle,
        imported_task=imported_task,
    )
    try:
        record_bundle_receipt(
            bundle_family="result_bundle",
            operation="import",
            receipt=receipt,
        )
    except OSError as error:
        exit_with_runtime_error(f"Could not record bundle receipt for {bundle_file}: {error}")
    typer.echo(render_result_bundle_import_receipt(receipt, output=output))


def _get_task_or_exit(
    *,
    task_id: int,
    output: OutputMode,
) -> LocalTaskDetail:
    return get_task_or_exit(task_id=task_id, output=output, get_task_fn=get_task)
