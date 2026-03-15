"""CLI-facing error translation helpers."""

from typing import NoReturn

import typer

from sc_cli.local_errors import CliContractError
from sc_cli.output import OutputMode
from sc_cli.presenters import render_api_error


def exit_with_usage_error(message: str) -> NoReturn:
    _exit_with_message(f"error: {message}", exit_code=2)


def exit_with_runtime_error(message: str) -> NoReturn:
    _exit_with_message(f"error: {message}", exit_code=1)


def exit_for_contract_error(
    error: CliContractError,
    *,
    output: OutputMode = OutputMode.TEXT,
) -> NoReturn:
    exit_code = 2 if error.error.status < 500 else 1
    _exit_with_message(render_api_error(error.error, output=output), exit_code=exit_code)


exit_for_backend_error = exit_for_contract_error


def _exit_with_message(message: str, *, exit_code: int) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(code=exit_code)
