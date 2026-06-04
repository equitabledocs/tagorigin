"""tagorigin CLI entry point (typer)."""
from __future__ import annotations

from pathlib import Path

import typer

from tagorigin.classify import classify
from tagorigin.inspect import PdfInspector
from tagorigin.report import render_json, render_text, write_report

app = typer.Typer(
    name="tagorigin",
    help="Classify the provenance of a PDF's tag tree.",
    no_args_is_help=True,
)


@app.command()
def check(
    target: Path = typer.Argument(..., exists=True, help="PDF file or folder to inspect."),
    fmt: str = typer.Option("text", "--format", help="Output format: text, json."),
    report: Path | None = typer.Option(None, "--report", help="Write a text report to this file."),
    verbose: bool = typer.Option(False, "--verbose", help="Show all signals in output."),
) -> None:
    """Run provenance audit on a PDF or a folder of PDFs."""
    if target.is_dir():
        typer.echo("Batch mode is not implemented in Phase 1. Use a single PDF file.", err=True)
        raise typer.Exit(code=64)

    if not target.suffix.lower() == ".pdf":
        typer.echo(f"Expected a .pdf file, got: {target}", err=True)
        raise typer.Exit(code=64)

    try:
        with PdfInspector.open(target) as inspector:
            result = classify(inspector, target)
    except Exception as exc:
        typer.echo(f"Failed to process {target}: {exc}", err=True)
        raise typer.Exit(code=1)

    output = render_json(result) if fmt.lower() == "json" else render_text(result)
    typer.echo(output)

    if report:
        write_report(result, report)
        typer.echo(f"\nReport written to {report}")

    raise typer.Exit(code=0)


@app.command()
def signals() -> None:
    """List the supported provenance signals and their weights."""
    from tagorigin.signals.metadata import METADATA_SIGNALS
    from tagorigin.signals.structure import STRUCTURE_SIGNALS

    typer.echo("Metadata signals:")
    for fn in METADATA_SIGNALS:
        sig = fn.__doc__ or fn.__name__
        typer.echo(f"  {fn.__name__}  --  {sig}")

    typer.echo("\nStructure signals:")
    for fn in STRUCTURE_SIGNALS:
        sig = fn.__doc__ or fn.__name__
        typer.echo(f"  {fn.__name__}  --  {sig}")

    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
