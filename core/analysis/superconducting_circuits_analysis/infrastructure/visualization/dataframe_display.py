from __future__ import annotations

import pandas as pd
from rich.console import Console
from rich.table import Table


def print_dataframe_table(title: str, df: pd.DataFrame) -> None:
    """
    Render a pandas DataFrame in the CLI with a consistent header/footer using Rich.

    Args:
        title: Short description displayed above the table.
        df: DataFrame to print.
    """
    console = Console()

    table = Table(title=title, show_header=True, header_style="bold magenta")

    if df.empty:
        console.print(f"[yellow]{title} (no rows)[/yellow]")
        return

    # Add columns
    for column in df.columns:
        table.add_column(str(column))

    # Add rows
    for _, row in df.iterrows():
        # Convert all values to string for display
        table.add_row(*[str(val) for val in row])

    console.print(table)
    console.print()  # Empty line for spacing
