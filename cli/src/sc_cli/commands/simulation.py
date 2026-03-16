"""Compatibility wrapper for simulation-lane local runs."""

from typing import Annotated

import typer

from sc_cli.errors import exit_for_contract_error
from sc_cli.local_errors import CliContractError
from sc_cli.local_runtime import LocalTaskDetail
from sc_cli.output import OutputMode, OutputOption
from sc_cli.presenters import render_task_detail, render_task_inspection
from sc_cli.runtime import get_task, list_tasks, submit_task
from sc_cli.task_operator import (
    TaskScopeOption,
    TaskStatusOption,
    WaitStatusOption,
    get_lane_task_or_exit,
    has_reached_wait_target,
    latest_lane_task_or_exit,
    wait_for_task_or_exit,
)

app = typer.Typer(
    help="Compatibility wrapper for simulation-lane local runs.",
    no_args_is_help=True,
)


@app.command("submit")
def submit_command(
    definition_id: Annotated[
        int,
        typer.Option("--definition-id", min=1, help="Circuit definition id to simulate."),
    ],
    dataset_id: Annotated[
        str | None,
        typer.Option(
            "--dataset-id",
            help="Dataset id for the simulation task. Falls back to the active session dataset.",
        ),
    ] = None,
    summary: Annotated[
        str | None,
        typer.Option("--summary", help="Optional human summary for the submitted task."),
    ] = None,
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Submit a simulation-lane task through the generic local run contract."""
    try:
        task = submit_task(
            kind="simulation",
            dataset_id=dataset_id,
            definition_id=definition_id,
            summary=summary,
        )
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(render_task_detail(task, output=output))


@app.command("show")
def show_command(
    task_id: Annotated[int, typer.Argument(min=1, help="Simulation-lane task id to inspect.")],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Show one simulation-lane task."""
    task = _get_simulation_task_or_exit(task_id=task_id, output=output)
    typer.echo(render_task_detail(task, output=output))


@app.command("inspect")
def inspect_command(
    task_id: Annotated[
        int,
        typer.Argument(min=1, help="Simulation-lane task id to inspect as an operator view."),
    ],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Show one simulation-lane task with operator-oriented event/result summary."""
    task = _get_simulation_task_or_exit(task_id=task_id, output=output)
    typer.echo(render_task_inspection(task, output=output))


@app.command("latest")
def latest_command(
    status: Annotated[
        TaskStatusOption | None,
        typer.Option("--status", help="Filter by task status."),
    ] = None,
    scope: Annotated[
        TaskScopeOption,
        typer.Option("--scope", help="Task visibility scope."),
    ] = TaskScopeOption.WORKSPACE,
    dataset_id: Annotated[
        str | None,
        typer.Option("--dataset-id", help="Filter by dataset id."),
    ] = None,
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Show the newest task in the simulation lane."""
    task = latest_lane_task_or_exit(
        expected_lane="simulation",
        lane_label="simulation",
        output=output,
        get_task_fn=get_task,
        list_tasks_fn=list_tasks,
        no_match_message="No simulation-lane tasks matched the requested filters.",
        status=None if status is None else status.value,
        lane="simulation",
        scope=scope.value,
        dataset_id=dataset_id,
        limit=20,
    )
    typer.echo(render_task_detail(task, output=output))


@app.command("wait")
def wait_command(
    task_id: Annotated[int, typer.Argument(min=1, help="Simulation-lane task id to follow.")],
    until_status: Annotated[
        WaitStatusOption,
        typer.Option(
            "--until-status",
            help="Task status to wait for. Use terminal to wait for completed/failed.",
        ),
    ] = WaitStatusOption.TERMINAL,
    interval: Annotated[
        float,
        typer.Option("--interval", min=0.1, help="Polling interval in seconds."),
    ] = 1.0,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=0.1, help="Maximum wait time in seconds."),
    ] = 30.0,
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Poll one simulation-lane task until it reaches the requested status."""
    task = wait_for_task_or_exit(
        load_task=lambda: _get_simulation_task_or_exit(task_id=task_id, output=output),
        is_ready=lambda current_task: has_reached_wait_target(
            task=current_task,
            until_status=until_status,
        ),
        timeout_message=(
            f"Timed out waiting for simulation-lane task {task_id} to reach {until_status.value}."
        ),
        interval=interval,
        timeout=timeout,
    )
    typer.echo(render_task_detail(task, output=output))


def _get_simulation_task_or_exit(
    *,
    task_id: int,
    output: OutputMode,
) -> LocalTaskDetail:
    return get_lane_task_or_exit(
        task_id=task_id,
        lane="simulation",
        lane_label="simulation",
        output=output,
        get_task_fn=get_task,
    )
