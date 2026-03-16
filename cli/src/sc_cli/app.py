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
    tasks,
)

app = typer.Typer(
    help=(
        "Standalone-first CLI for local datasets, analysis runs, results, "
        "and characterization workflows."
    ),
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

app.add_typer(core.app, name="core", help="Inspect the shared core package boundary.")
app.add_typer(
    session.app,
    name="session",
    help="Inspect standalone local session context and active dataset fallback.",
)
app.add_typer(
    datasets.app,
    name="datasets",
    help="Browse local datasets and exchange lineage-preserving bundles.",
)
app.add_typer(tasks.app, name="tasks", help="Browse and submit local analysis runs.")
app.add_typer(
    ops.app,
    name="ops",
    help="Run connected analysis-first workflows across tasks, events, and results.",
)
app.add_typer(events.app, name="events", help="Inspect standalone local run event history.")
app.add_typer(
    results.app,
    name="results",
    help="Inspect local result references and exchange result bundles.",
)
app.add_typer(
    characterization.app,
    name="characterization",
    help="Run characterization and analysis-lane workflows over local datasets.",
)
app.add_typer(
    circuit_definition.app,
    name="circuit-definition",
    help="Compatibility helpers for local circuit-definition catalog exchange.",
    hidden=True,
)
