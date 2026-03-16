"""Persisted task event history inspection commands."""

from enum import Enum
from typing import Annotated

import typer

from sc_cli.errors import exit_with_runtime_error
from sc_cli.local_runtime import LocalTaskDetail
from sc_cli.output import OutputMode, OutputOption
from sc_cli.presenters import render_task_event_history, render_task_latest_event
from sc_cli.runtime import get_task
from sc_cli.task_operator import get_task_or_exit, select_task_events

app = typer.Typer(
    help="Inspect standalone local run event history.",
    no_args_is_help=True,
)


class TaskEventTypeOption(str, Enum):
    TASK_SUBMITTED = "task_submitted"
    TASK_RUNNING = "task_running"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"


class TaskEventLevelOption(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@app.command("show")
def show_command(
    task_id: Annotated[int, typer.Argument(min=1, help="Task id whose event history to inspect.")],
    event_type: Annotated[
        TaskEventTypeOption | None,
        typer.Option("--event-type", help="Filter by persisted event type."),
    ] = None,
    level: Annotated[
        TaskEventLevelOption | None,
        typer.Option("--level", help="Filter by event severity level."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Limit the number of returned events."),
    ] = None,
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Show persisted event history for one task."""
    task = _get_task_or_exit(task_id=task_id, output=output)
    events = select_task_events(
        task,
        event_type=None if event_type is None else event_type.value,
        level=None if level is None else level.value,
        limit=limit,
    )
    if not events:
        exit_with_runtime_error(
            f"No persisted task events matched the requested filters for {task_id}."
        )
    typer.echo(render_task_event_history(task, events=events, output=output))


@app.command("latest")
def latest_command(
    task_id: Annotated[int, typer.Argument(min=1, help="Task id whose latest event to inspect.")],
    event_type: Annotated[
        TaskEventTypeOption | None,
        typer.Option("--event-type", help="Filter by persisted event type."),
    ] = None,
    level: Annotated[
        TaskEventLevelOption | None,
        typer.Option("--level", help="Filter by event severity level."),
    ] = None,
    output: OutputOption = OutputMode.TEXT,
) -> None:
    """Show the newest persisted event for one task."""
    task = _get_task_or_exit(task_id=task_id, output=output)
    events = select_task_events(
        task,
        event_type=None if event_type is None else event_type.value,
        level=None if level is None else level.value,
        limit=1,
    )
    if not events:
        exit_with_runtime_error(
            f"No persisted task events matched the requested filters for {task_id}."
        )
    typer.echo(render_task_latest_event(task, event=events[0], output=output))


def _get_task_or_exit(
    *,
    task_id: int,
    output: OutputMode,
) -> LocalTaskDetail:
    return get_task_or_exit(task_id=task_id, output=output, get_task_fn=get_task)
