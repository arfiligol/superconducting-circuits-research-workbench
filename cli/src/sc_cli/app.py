"""Installable Typer entrypoint for the standalone-first CLI."""

import typer

from sc_cli.commands import (
    characterization,
    circuit_definition,
    core,
    datasets,
    events,
    ops,
    results,
    session,
    simulation,
    tasks,
)

app = typer.Typer(
    help="Standalone-first CLI for local datasets, runs, results, and characterization workflows.",
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

app.add_typer(core.app, name="core", help="Inspect the shared core package boundary.")
app.add_typer(session.app, name="session", help="Inspect standalone local session context.")
app.add_typer(datasets.app, name="datasets", help="Inspect standalone local datasets and bundles.")
app.add_typer(tasks.app, name="tasks", help="Inspect and submit standalone local runs.")
app.add_typer(ops.app, name="ops", help="Run connected analysis-first operator workflows.")
app.add_typer(events.app, name="events", help="Inspect standalone local task event history.")
app.add_typer(results.app, name="results", help="Inspect standalone local result references.")
app.add_typer(
    characterization.app,
    name="characterization",
    help="Operate on characterization and analysis-lane tasks.",
)
app.add_typer(
    circuit_definition.app,
    name="circuit-definition",
    help="Inspect and exchange local circuit-definition catalog entries.",
    hidden=True,
)
app.add_typer(
    simulation.app,
    name="simulation",
    help="Operate on simulation-lane tasks.",
    hidden=True,
)
