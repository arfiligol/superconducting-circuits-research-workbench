"""Commands for inspecting standalone local task state."""

from enum import Enum
from typing import Annotated

import typer

from sc_cli.errors import exit_for_contract_error
from sc_cli.local_errors import CliContractError
from sc_cli.local_runtime import LocalTaskDetail
from sc_cli.output import OutputMode, OutputOption
from sc_cli.presenters import render_task_detail, render_task_inspection, render_task_summaries
from sc_cli.runtime import get_task, list_tasks, submit_task
from sc_cli.task_operator import (
    TaskScopeOption,
    TaskStatusOption,
    WaitStatusOption,
    has_reached_wait_target,
    latest_task_or_exit,
    wait_for_task_or_exit,
)

app = typer.Typer(
    help="Browse and operate the standalone local analysis run registry.",
    no_args_is_help=True,
)


class TaskLaneOption(str, Enum):
    SIMULATION = "simulation"
    CHARACTERIZATION = "characterization"


class TaskKindOption(str, Enum):
    SIMULATION = "simulation"
    POST_PROCESSING = "post_processing"
    CHARACTERIZATION = "characterization"


@app.command("list")
def list_command(
    status: Annotated[
        TaskStatusOption | None,
        typer.Option("--status", help="Filter by task status."),
    ] = None,
    lane: Annotated[
        TaskLaneOption | None,
        typer.Option("--lane", help="Filter by task lane."),
    ] = None,
    scope: Annotated[
        TaskScopeOption,
        typer.Option("--scope", help="Task visibility scope."),
    ] = TaskScopeOption.WORKSPACE,
    dataset_id: Annotated[
        str | None,
        typer.Option("--dataset-id", help="Filter by dataset id."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=50, help="Maximum number of tasks to show."),
    ] = 20,
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """List tasks from the standalone local run registry."""
    try:
        tasks = list_tasks(
            status=None if status is None else status.value,
            lane=None if lane is None else lane.value,
            scope=scope.value,
            dataset_id=dataset_id,
            limit=limit,
        )
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(render_task_summaries(tasks, output=output))


@app.command("show")
def show_command(
    task_id: Annotated[int, typer.Argument(min=1, help="Task id to inspect.")],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Show one task from the standalone local run registry."""
    try:
        task = get_task(task_id)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(render_task_detail(task, output=output))


@app.command("inspect")
def inspect_command(
    task_id: Annotated[int, typer.Argument(min=1, help="Task id to inspect as an operator view.")],
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Show one task with operator-oriented event/result summary."""
    try:
        task = get_task(task_id)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(render_task_inspection(task, output=output))


@app.command("latest")
def latest_command(
    status: Annotated[
        TaskStatusOption | None,
        typer.Option("--status", help="Filter by task status."),
    ] = None,
    lane: Annotated[
        TaskLaneOption | None,
        typer.Option("--lane", help="Filter by task lane."),
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
    """Show the newest task matching the requested filters."""
    task = latest_task_or_exit(
        output=output,
        no_match_message="No tasks matched the requested filters.",
        get_task_fn=get_task,
        list_tasks_fn=list_tasks,
        status=None if status is None else status.value,
        lane=None if lane is None else lane.value,
        scope=scope.value,
        dataset_id=dataset_id,
        limit=20,
    )
    typer.echo(render_task_detail(task, output=output))


@app.command("wait")
def wait_command(
    task_id: Annotated[int, typer.Argument(min=1, help="Task id to follow.")],
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
    """Poll one task until it reaches the requested status."""
    task = wait_for_task_or_exit(
        load_task=lambda: _get_task_or_exit(task_id=task_id, output=output),
        is_ready=lambda current_task: _has_reached_wait_target(
            task=current_task,
            until_status=until_status,
        ),
        timeout_message=f"Timed out waiting for task {task_id} to reach {until_status.value}.",
        interval=interval,
        timeout=timeout,
    )
    typer.echo(render_task_detail(task, output=output))


@app.command("submit")
def submit_command(
    kind: Annotated[
        TaskKindOption,
        typer.Argument(help="Task kind to submit."),
    ],
    dataset_id: Annotated[
        str | None,
        typer.Option(
            "--dataset-id",
            help="Dataset id for dataset-driven tasks. Falls back to the active session dataset.",
        ),
    ] = None,
    definition_id: Annotated[
        int | None,
        typer.Option(
            "--definition-id",
            min=1,
            help="Circuit definition id required by simulation tasks.",
        ),
    ] = None,
    summary: Annotated[
        str | None,
        typer.Option("--summary", help="Optional human summary for the submitted task."),
    ] = None,
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Submit one task through the standalone local run registry."""
    try:
        task = submit_task(
            kind=kind.value,
            dataset_id=dataset_id,
            definition_id=definition_id,
            summary=summary,
        )
    except CliContractError as error:
        exit_for_contract_error(error, output=output)
    typer.echo(render_task_detail(task, output=output))


def _get_task_or_exit(
    *,
    task_id: int,
    output: OutputMode,
) -> LocalTaskDetail:
    try:
        return get_task(task_id)
    except CliContractError as error:
        exit_for_contract_error(error, output=output)


def _has_reached_wait_target(
    *,
    task: LocalTaskDetail,
    until_status: WaitStatusOption,
) -> bool:
    return has_reached_wait_target(task=task, until_status=until_status)
