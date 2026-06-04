"""tagorigin CLI entry point.

This is a Phase-1 stub. The full implementation follows docs/SPEC.md.
"""
from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(
    name="tagorigin",
    help="Classify the provenance of a PDF's tag tree.",
    no_args_is_help=True,
)


@app.command()
def check(
    target: Path = typer.Argument(..., exists=True, help="PDF file or folder to inspect."),
    fmt: str = typer.Option("text", "--format", help="Output format: text, json."),
) -> None:
    """Run provenance audit on a PDF or a folder of PDFs."""
    typer.echo("tagorigin is at pre-MVP stage. See docs/SPEC.md for the build plan.")
    typer.echo(f"Requested target: {target}")
    typer.echo(f"Requested format: {fmt}")
    raise typer.Exit(code=0)


@app.command()
def signals() -> None:
    """List the supported provenance signals and their weights."""
    typer.echo("Signal table is defined in docs/SPEC.md sections 2.1 to 2.4.")
    typer.echo("This subcommand will print the live signal registry once implemented.")
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
