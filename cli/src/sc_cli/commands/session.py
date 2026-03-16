"""Commands for inspecting standalone local session state."""

from typing import Annotated

import typer

from sc_cli.errors import exit_for_contract_error, exit_with_usage_error
from sc_cli.local_errors import CliContractError
from sc_cli.local_runtime import LocalSession
from sc_cli.output import OutputMode, OutputOption
from sc_cli.presenters import (
    render_session,
    render_session_active_dataset,
    render_session_identity,
    render_session_workspace,
)
from sc_cli.runtime import get_session, set_active_dataset

app = typer.Typer(
    help="Inspect standalone local session context and active dataset fallback.",
    no_args_is_help=True,
)


@app.command("show")
def show_command(output: OutputOption = OutputMode.TEXT) -> None:
    """Show the current standalone session and workspace context."""
    session = _get_session_or_exit(output)
    typer.echo(render_session(session, output=output))


@app.command("whoami")
def whoami_command(output: OutputOption = OutputMode.TEXT) -> None:
    """Show the current session identity and auth context."""
    session = _get_session_or_exit(output)
    typer.echo(render_session_identity(session, output=output))


@app.command("workspace")
def workspace_command(output: OutputOption = OutputMode.TEXT) -> None:
    """Show the current workspace context."""
    session = _get_session_or_exit(output)
    typer.echo(render_session_workspace(session, output=output))


@app.command("active-dataset")
def active_dataset_command(output: OutputOption = OutputMode.TEXT) -> None:
    """Show the currently active dataset context."""
    session = _get_session_or_exit(output)
    typer.echo(render_session_active_dataset(session, output=output))


@app.command("set-active-dataset")
def set_active_dataset_command(
    dataset_id: Annotated[
        str | None,
        typer.Argument(help="Dataset id to activate in the current session context."),
    ] = None,
    clear: Annotated[
        bool,
        typer.Option(
            "--clear",
            help="Clear the active dataset from the current session context.",
        ),
    ] = False,
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Update the active dataset in the current standalone session context."""
    if clear == (dataset_id is not None):
        exit_with_usage_error("Provide exactly one of DATASET_ID or --clear.")

    try:
        session = set_active_dataset(None if clear else dataset_id)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(render_session(session, output=output))


def _get_session_or_exit(output: OutputMode) -> LocalSession:
    try:
        return get_session()
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
